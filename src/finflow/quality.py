"""Data-quality engine: standardise, validate, de-duplicate and split into valid/rejected rows.

All rules are driven by the entity definitions in schemas.py. Rows are never silently
dropped: every non-valid row is returned with the rule codes that rejected it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd

from .schemas import Col, Entity
from .utils import TS_FORMAT, is_missing

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}Z?$")
_DEC_RE = re.compile(r"^-?\d{1,16}(\.\d{1,2})?$")

RULE_MESSAGES = {
    "MISSING_VALUE": "Required value is missing",
    "INVALID_FORMAT": "Value does not match the expected format",
    "INVALID_DATE": "Not a valid calendar date (expected YYYY-MM-DD)",
    "INVALID_TIMESTAMP": "Not a valid timestamp (expected YYYY-MM-DD HH:MM:SS)",
    "DATE_OUT_OF_RANGE": "Date is in the future or before the allowed minimum",
    "INVALID_NUMBER": "Not a valid number with at most 2 decimal places",
    "NON_POSITIVE_AMOUNT": "Amount must be positive",
    "NEGATIVE_VALUE": "Value must not be negative",
    "AMOUNT_OUT_OF_RANGE": "Amount exceeds the allowed maximum",
    "INVALID_ENUM": "Value is not in the allowed list",
    "VALUE_TOO_LONG": "Value exceeds the maximum length",
    "FK_VIOLATION": "Referenced parent record does not exist",
    "CURRENCY_MISMATCH": "Currency differs from the parent account currency",
    "UPDATED_BEFORE_CREATED": "updated_at is earlier than created_at",
    "DUPLICATE_ROW": "Exact duplicate of another row in the file",
    "DUPLICATE_KEY": "Primary key repeated; superseded by a later row",
}


@dataclass
class References:
    """Keys of parent records already known (curated layer + valid rows of this batch)."""

    keys: dict[str, set[str]] = field(default_factory=dict)
    account_currency: dict[str, str] = field(default_factory=dict)


@dataclass
class RuleStat:
    entity: str
    rule_code: str
    severity: str
    failed_rows: int
    checked_rows: int


@dataclass
class ValidationResult:
    entity: str
    source_rows: int
    valid: pd.DataFrame
    rejected: pd.DataFrame
    rule_stats: list[RuleStat]

    @property
    def rejected_rows(self) -> int:
        return len(self.rejected)


# ---------------------------------------------------------------- standardisation
def _clean(value, col: Col):
    if is_missing(value):
        return None
    text = " ".join(str(value).split())
    if col.strip_chars:
        text = text.translate({ord(c): None for c in col.strip_chars})
    if text == "":
        return None
    if col.case == "upper":
        text = text.upper()
    elif col.case == "lower":
        text = text.lower()
    return text


def standardize(df: pd.DataFrame, spec: Entity) -> pd.DataFrame:
    """Trim/collapse whitespace, empty -> None, apply case rules. Pure cleaning, no rejection."""
    out = df.copy()
    for col in spec.columns:
        out[col.name] = pd.Series(
            [_clean(v, col) for v in df[col.name].tolist()], index=df.index, dtype=object
        )
    return out


# ---------------------------------------------------------------- per-cell validators
def _check_cell(value, col: Col, now: datetime):
    """Return (normalised_value, error_code|None)."""
    if value is None:
        return None, None
    if col.kind == "date":
        if not _DATE_RE.match(value):
            return value, "INVALID_DATE"
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return value, "INVALID_DATE"
        if parsed > now or (col.min_date and parsed < datetime.fromisoformat(col.min_date)):
            return value, "DATE_OUT_OF_RANGE"
        return parsed.strftime("%Y-%m-%d"), None
    if col.kind == "datetime":
        if not _TS_RE.match(value):
            return value, "INVALID_TIMESTAMP"
        try:
            parsed = datetime.strptime(value.replace("T", " ").rstrip("Z"), TS_FORMAT)
        except ValueError:
            return value, "INVALID_TIMESTAMP"
        if parsed > now or (col.min_date and parsed < datetime.fromisoformat(col.min_date)):
            return value, "DATE_OUT_OF_RANGE"
        return parsed.strftime(TS_FORMAT), None
    if col.kind == "decimal":
        if not _DEC_RE.match(value):
            return value, "INVALID_NUMBER"
        try:
            number = Decimal(value)
        except InvalidOperation:
            return value, "INVALID_NUMBER"
        if col.min_value is not None:
            below = number < col.min_value if col.min_inclusive else number <= col.min_value
            if below:
                return value, "NON_POSITIVE_AMOUNT" if not col.min_inclusive else "NEGATIVE_VALUE"
        if col.max_value is not None and number > col.max_value:
            return value, "AMOUNT_OUT_OF_RANGE"
        return str(number.quantize(Decimal("0.01"))), None
    if col.kind == "enum" and value not in col.enum:
        return value, "INVALID_ENUM"
    if col.max_len and len(value) > col.max_len:
        return value, "VALUE_TOO_LONG"
    if col.pattern and not re.match(col.pattern, value):
        return value, "INVALID_FORMAT"
    return value, None


def _mask(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    return value[0] + "***"


class _Failures:
    """Accumulates rule-code -> boolean mask over the frame index."""

    def __init__(self, index: pd.Index):
        self.index = index
        self.masks: dict[str, pd.Series] = {}

    def flag(self, code: str, mask) -> None:
        mask = pd.Series(mask, index=self.index).fillna(False).astype(bool)
        if mask.any():
            self.masks[code] = self.masks[code] | mask if code in self.masks else mask

    def any_failed(self) -> pd.Series:
        result = pd.Series(False, index=self.index)
        for mask in self.masks.values():
            result = result | mask
        return result


def validate_entity(
    raw: pd.DataFrame,
    spec: Entity,
    refs: References,
    now: datetime,
    mask_pii: bool = True,
) -> ValidationResult:
    df = standardize(raw, spec)
    failures = _Failures(df.index)

    # 1) column-level rules (required, type, format, range, enum, length)
    for col in spec.columns:
        values = df[col.name].tolist()
        normalised, errors = [], []
        for v in values:
            n, e = _check_cell(v, col, now)
            normalised.append(n)
            errors.append(e)
        df[col.name] = pd.Series(normalised, index=df.index, dtype=object)
        if col.required:
            failures.flag(f"MISSING_VALUE:{col.name}", [v is None for v in values])
        for code in sorted({e for e in errors if e}):
            failures.flag(f"{code}:{col.name}", [e == code for e in errors])

    # 2) cross-column and cross-table rules
    if spec.name == "customers":
        both = df["created_at"].notna() & df["updated_at"].notna()
        later = pd.Series(
            [b and (u < c) for b, u, c in zip(both, df["updated_at"], df["created_at"], strict=True)],
            index=df.index,
        )
        ok_format = pd.Series(
            [_ok(v) for v in df["updated_at"].tolist()], index=df.index
        ) & pd.Series([_ok(v) for v in df["created_at"].tolist()], index=df.index)
        failures.flag("UPDATED_BEFORE_CREATED:updated_at", later & ok_format)

    for fk in spec.foreign_keys:
        known = refs.keys.get(fk.ref_entity, set())
        present = df[fk.column].notna()
        failures.flag(f"FK_VIOLATION:{fk.column}", present & ~df[fk.column].isin(known))

    if spec.name in {"transactions", "payments"}:
        parent = df["account_id"].map(refs.account_currency)
        failures.flag(
            "CURRENCY_MISMATCH:currency",
            parent.notna() & df["currency"].notna() & (parent != df["currency"]),
        )

    # 3) duplicates, only among rows that passed everything else
    candidates = df.index[~failures.any_failed()]
    cand = df.loc[candidates].copy()
    cand["_row_number"] = raw.loc[candidates, "_row_number"]
    business = spec.column_names
    exact = cand.duplicated(subset=business, keep="last")
    failures.flag("DUPLICATE_ROW:" + spec.pk, exact.reindex(df.index, fill_value=False))
    remaining = cand.loc[~exact].sort_values(["updated_at", "_row_number"], kind="stable")
    superseded = remaining.duplicated(subset=[spec.pk], keep="last")
    failures.flag("DUPLICATE_KEY:" + spec.pk, superseded.reindex(df.index, fill_value=False))

    # 4) split valid / rejected
    bad = failures.any_failed()
    valid = df.loc[~bad, business].copy()
    valid["_row_number"] = raw.loc[~bad, "_row_number"].astype(int)
    valid = valid.reset_index(drop=True)

    pii = {c.name for c in spec.columns if c.pii}
    reject_rows = []
    for idx in df.index[bad]:
        codes = sorted(code for code, mask in failures.masks.items() if mask.loc[idx])
        messages = "; ".join(f"{c} - {RULE_MESSAGES.get(c.split(':')[0], '')}" for c in codes)
        original = {c: raw.at[idx, c] for c in business}
        if mask_pii:
            original = {k: (_mask(v) if k in pii else v) for k, v in original.items()}
        reject_rows.append(
            {
                "entity": spec.name,
                "source_row_number": int(raw.at[idx, "_row_number"]),
                "record_key": raw.at[idx, spec.pk] or "",
                "rule_codes": ";".join(codes),
                "messages": messages,
                "raw_record": json.dumps(original, ensure_ascii=False),
            }
        )
    rejected = pd.DataFrame(
        reject_rows,
        columns=[
            "entity", "source_row_number", "record_key", "rule_codes", "messages", "raw_record",
        ],
    )
    total = len(df)
    stats = [
        RuleStat(spec.name, code, "ERROR", int(mask.sum()), total)
        for code, mask in sorted(failures.masks.items())
    ]
    return ValidationResult(spec.name, total, valid, rejected, stats)


def _ok(value) -> bool:
    return value is not None and bool(_TS_RE.match(str(value)))
