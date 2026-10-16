"""Source-to-target reconciliation: row counts, financial totals and referential integrity.

Runs INSIDE the load transaction, so any FAIL aborts and rolls back the whole load.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
from sqlalchemy import text

from .schemas import ENTITY_BY_NAME, Entity

CENT = Decimal("0.01")


def _dec(value) -> Decimal:
    return Decimal(str(value if value is not None else 0)).quantize(CENT)


@dataclass
class ReconCheck:
    entity: str
    check_name: str
    source_value: Decimal
    target_value: Decimal

    @property
    def difference(self) -> Decimal:
        return (self.source_value - self.target_value).quantize(CENT)

    @property
    def status(self) -> str:
        return "PASS" if self.difference == 0 else "FAIL"

    def as_record(self) -> dict:
        return {
            "entity": self.entity,
            "check_name": self.check_name,
            "source_value": str(self.source_value),
            "target_value": str(self.target_value),
            "difference": str(self.difference),
            "status": self.status,
        }


def python_totals(df: pd.DataFrame, spec: Entity) -> dict[str, dict[str, Decimal]]:
    """Per-currency totals computed from the validated rows (the 'source' side)."""
    result: dict[str, dict[str, Decimal]] = {}
    if spec.amount_column is None or df.empty:
        return result
    for _, row in df.iterrows():
        cur = row[spec.currency_column]
        bucket = result.setdefault(cur, {"total": Decimal("0"), "net": Decimal("0")})
        amount = Decimal(row[spec.amount_column])
        bucket["total"] += amount
        if spec.direction_column:
            bucket["net"] += amount if row[spec.direction_column] == "CREDIT" else -amount
    return result


def _sql_totals(conn, spec: Entity, load_id: str, side: str) -> dict[str, dict[str, Decimal]]:
    amt, cur = spec.amount_column, spec.currency_column
    net = (
        f"SUM(CASE WHEN x.{spec.direction_column} = 'CREDIT' THEN x.{amt} ELSE -x.{amt} END)"
        if spec.direction_column else "0"
    )
    if side == "stage":
        sql = (f"SELECT x.{cur}, SUM(x.{amt}), {net} FROM {spec.stg_table} x "
               f"WHERE x.load_id = :l GROUP BY x.{cur}")
    else:  # rows of the curated table that match this load's staged rows by key AND content hash
        sql = (f"SELECT x.{cur}, SUM(x.{amt}), {net} FROM {spec.table} x "
               f"JOIN {spec.stg_table} s ON s.{spec.pk} = x.{spec.pk} AND s.row_hash = x.row_hash "
               f"WHERE s.load_id = :l GROUP BY x.{cur}")
    rows = conn.execute(text(sql), {"l": load_id}).fetchall()
    return {r[0]: {"total": _dec(r[1]), "net": _dec(r[2])} for r in rows}


def reconcile_entity(conn, spec: Entity, load_id: str, source_rows: int, rejected: int,
                     skipped: int, staged_df: pd.DataFrame, counts) -> list[ReconCheck]:
    n = spec.name
    checks: list[ReconCheck] = []
    staged = len(staged_df)
    d = Decimal
    checks.append(ReconCheck(n, "ROWS_SOURCE_TO_DISPOSITION", d(source_rows), d(rejected + skipped + staged)))
    stage_count = conn.execute(text(f"SELECT COUNT(*) FROM {spec.stg_table} WHERE load_id=:l"), {"l": load_id}).scalar()
    checks.append(ReconCheck(n, "ROWS_VALIDATED_TO_STAGING", d(staged), d(int(stage_count))))
    checks.append(ReconCheck(n, "ROWS_STAGED_TO_NEW_CHANGED_UNCHANGED", d(staged),
                             d(counts.inserted + counts.updated + counts.unchanged)))
    matched = conn.execute(
        text(f"SELECT COUNT(*) FROM {spec.table} x JOIN {spec.stg_table} s ON s.{spec.pk} = x.{spec.pk} "
             f"AND s.row_hash = x.row_hash WHERE s.load_id = :l"), {"l": load_id}).scalar()
    checks.append(ReconCheck(n, "ROWS_STAGING_TO_CURATED", d(staged), d(int(matched))))

    if spec.amount_column:
        src = python_totals(staged_df, spec)
        stg = _sql_totals(conn, spec, load_id, "stage")
        tgt = _sql_totals(conn, spec, load_id, "target")
        for cur in sorted(set(src) | set(stg) | set(tgt)):
            zero = {"total": Decimal("0.00"), "net": Decimal("0.00")}
            s, g, t = src.get(cur, zero), stg.get(cur, zero), tgt.get(cur, zero)
            checks.append(ReconCheck(n, f"AMOUNT_TOTAL_SOURCE_TO_STAGING:{cur}", s["total"], g["total"]))
            checks.append(ReconCheck(n, f"AMOUNT_TOTAL_STAGING_TO_CURATED:{cur}", g["total"], t["total"]))
            if spec.direction_column:
                checks.append(ReconCheck(n, f"NET_FLOW_SOURCE_TO_CURATED:{cur}", s["net"], t["net"]))
    return checks


def referential_checks(conn) -> list[ReconCheck]:
    """Curated-layer orphan counts; expected value is always 0."""
    out = []
    for child_name, fk_col, parent_name in (
        ("accounts", "customer_id", "customers"),
        ("transactions", "account_id", "accounts"),
        ("payments", "account_id", "accounts"),
        ("payments", "transaction_id", "transactions"),
    ):
        child, parent = ENTITY_BY_NAME[child_name], ENTITY_BY_NAME[parent_name]
        orphans = conn.execute(text(
            f"SELECT COUNT(*) FROM {child.table} c LEFT JOIN {parent.table} p ON p.{parent.pk} = c.{fk_col} "
            f"WHERE c.{fk_col} IS NOT NULL AND p.{parent.pk} IS NULL")).scalar()
        out.append(ReconCheck(child_name, f"ORPHANS:{child_name}.{fk_col}", Decimal(0), Decimal(int(orphans))))
    return out
