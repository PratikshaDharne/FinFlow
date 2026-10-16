"""Transform step: row hashing for change detection and incremental (watermark) filtering."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import pandas as pd

from .schemas import WATERMARK_COLUMN, Entity
from .utils import TS_FORMAT, is_missing

_SEP = "\x1f"


def row_hash(values: list) -> str:
    payload = _SEP.join("" if is_missing(v) else str(v) for v in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def add_row_hash(valid: pd.DataFrame, spec: Entity) -> pd.DataFrame:
    out = valid.copy()
    cols = spec.column_names
    out["row_hash"] = [row_hash(list(r)) for r in out[cols].itertuples(index=False, name=None)]
    return out


def watermark_cutoff(watermark: str | None, lookback_hours: int) -> str | None:
    if not watermark:
        return None
    base = datetime.strptime(watermark, TS_FORMAT)
    return (base - timedelta(hours=lookback_hours)).strftime(TS_FORMAT)


def apply_watermark(
    valid: pd.DataFrame, cutoff: str | None, pk: str = "", known_keys: set[str] | None = None
) -> tuple[pd.DataFrame, int]:
    """Keep rows changed at/after the cutoff. Returns (kept, skipped_count).

    A row is skipped only if it is old AND its key already exists in the curated layer.
    Unknown keys are always kept, so a previously rejected record that is later corrected
    (and may carry an old updated_at) is never lost. The look-back window re-reads a little
    overlap for late arrivals; the row-hash comparison in the merge then guarantees unchanged
    rows are not rewritten.
    """
    if cutoff is None or valid.empty:
        return valid, 0
    old = valid[WATERMARK_COLUMN] < cutoff
    if pk:
        old = old & valid[pk].isin(known_keys or set())
    return valid.loc[~old].reset_index(drop=True), int(old.sum())


def max_watermark(valid: pd.DataFrame) -> str | None:
    if valid.empty:
        return None
    return str(valid[WATERMARK_COLUMN].max())
