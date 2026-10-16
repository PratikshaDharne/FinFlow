"""Database layer: engine creation, schema bootstrap and all SQL used by the pipeline.

Only parameterised SQL via SQLAlchemy ``text()`` is used - identifiers come from the trusted
schema definitions, values are always bound parameters. Two dialects are supported:
MySQL 8.0 (target) and SQLite (zero-setup local/CI).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import Settings
from .errors import ConfigError
from .logging_utils import get_logger
from .schemas import ENTITIES, Entity
from .utils import chunked

log = get_logger("db")
BATCH = 2000


def make_engine(settings: Settings) -> Engine:
    url = settings.database_url()
    log.info("creating engine", extra={"url": settings.safe_database_url()})
    kwargs = {"pool_pre_ping": True} if settings.db_backend == "mysql" else {}
    return create_engine(url, **kwargs)


def dialect(engine_or_conn) -> str:
    name = engine_or_conn.dialect.name
    if name not in {"mysql", "sqlite"}:
        raise ConfigError(f"Unsupported database dialect: {name}")
    return name


@contextmanager
def begin(engine: Engine) -> Iterator:
    """Transaction scope: commit on success, rollback on any exception."""
    with engine.begin() as conn:
        if dialect(conn) == "sqlite":
            conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        yield conn


# ------------------------------------------------------------------ schema bootstrap
def _split_statements(sql: str) -> list[str]:
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    cleaned = "\n".join(re.sub(r"\s--.*$", "", ln) for ln in lines)
    return [s.strip() for s in cleaned.split(";") if s.strip()]


def schema_files(sql_dir: Path, dialect_name: str) -> list[Path]:
    if dialect_name == "sqlite":
        return [sql_dir / "sqlite" / "schema.sql"]
    return [sql_dir / "mysql" / n for n in (
        "02_audit_tables.sql", "03_staging_tables.sql", "04_curated_tables.sql", "05_views.sql")]


def init_schema(engine: Engine, sql_dir: Path) -> None:
    """Idempotent DDL bootstrap (CREATE ... IF NOT EXISTS)."""
    name = dialect(engine)
    for path in schema_files(sql_dir, name):
        statements = _split_statements(path.read_text(encoding="utf-8"))
        with engine.begin() as conn:
            for stmt in statements:
                conn.exec_driver_sql(stmt)
        log.info("schema script applied", extra={"file": path.name, "statements": len(statements)})


# ------------------------------------------------------------------ audit helpers
def audit_start(engine: Engine, load_id: str, source_dir: str, started: str, dry_run: bool) -> None:
    with begin(engine) as conn:
        conn.execute(
            text("INSERT INTO etl_load_audit (load_id, status, source_dir, started_at) "
                 "VALUES (:l, :s, :d, :t)"),
            {"l": load_id, "s": "RUNNING", "d": source_dir, "t": started},
        )


def audit_finish(engine: Engine, load_id: str, status: str, finished: str, *, error: str | None = None,
                 azure: str | None = None, snowflake: str | None = None) -> None:
    with begin(engine) as conn:
        conn.execute(
            text("UPDATE etl_load_audit SET status=:s, finished_at=:f, error_message=:e, "
                 "azure_status=COALESCE(:a, azure_status), snowflake_status=COALESCE(:w, snowflake_status) "
                 "WHERE load_id=:l"),
            {"s": status, "f": finished, "e": error, "a": azure, "w": snowflake, "l": load_id},
        )


def registered_hashes(conn, entity: str) -> set[str]:
    rows = conn.execute(
        text("SELECT sha256 FROM etl_file_registry WHERE entity=:e AND status='LOADED'"), {"e": entity}
    ).fetchall()
    return {r[0] for r in rows}


def fetch_watermark(conn, entity: str) -> str | None:
    row = conn.execute(
        text("SELECT watermark_value FROM etl_watermark WHERE entity=:e"), {"e": entity}
    ).fetchone()
    return str(row[0])[:19].replace("T", " ") if row else None


def existing_keys(conn, spec: Entity) -> set[str]:
    return {r[0] for r in conn.execute(text(f"SELECT {spec.pk} FROM {spec.table}")).fetchall()}


def existing_account_currency(conn) -> dict[str, str]:
    return {r[0]: r[1] for r in conn.execute(text("SELECT account_id, currency FROM accounts")).fetchall()}


# ------------------------------------------------------------------ staging + merge
def stage_rows(conn, spec: Entity, records: list[dict], load_id: str, source_file: str, now: str) -> None:
    """Replace this load's staging rows (rerun-safe) and insert the validated records."""
    conn.execute(text(f"DELETE FROM {spec.stg_table} WHERE load_id = :l"), {"l": load_id})
    if not records:
        return
    cols = spec.column_names + ["row_hash"]
    col_sql = ", ".join(["load_id", *cols, "source_file", "source_row_number", "staged_at"])
    val_sql = ", ".join(f":{c}" for c in ["load_id", *cols, "source_file", "source_row_number", "staged_at"])
    stmt = text(f"INSERT INTO {spec.stg_table} ({col_sql}) VALUES ({val_sql})")
    for part in chunked(records, BATCH):
        payload = [{**r, "load_id": load_id, "source_file": source_file, "staged_at": now} for r in part]
        conn.execute(stmt, payload)


@dataclass
class MergeCounts:
    staged: int
    inserted: int
    updated: int
    unchanged: int


def merge_counts(conn, spec: Entity, load_id: str) -> MergeCounts:
    row = conn.execute(
        text(
            f"SELECT COUNT(*), "
            f"COALESCE(SUM(CASE WHEN c.{spec.pk} IS NULL THEN 1 ELSE 0 END), 0), "
            f"COALESCE(SUM(CASE WHEN c.{spec.pk} IS NOT NULL AND c.row_hash <> s.row_hash THEN 1 ELSE 0 END), 0) "
            f"FROM {spec.stg_table} s LEFT JOIN {spec.table} c ON c.{spec.pk} = s.{spec.pk} "
            f"WHERE s.load_id = :l"
        ),
        {"l": load_id},
    ).fetchone()
    staged, inserted, updated = int(row[0]), int(row[1]), int(row[2])
    return MergeCounts(staged, inserted, updated, staged - inserted - updated)


def merge_sql(dialect_name: str, spec: Entity) -> str:
    """Staging -> curated upsert. Only new or changed rows (row_hash differs) are written."""
    cols = spec.column_names
    insert_cols = [*cols, "row_hash", "source_file", "created_load_id", "updated_load_id",
                   "etl_created_at", "etl_updated_at"]
    select_exprs = [f"s.{c}" for c in cols] + [
        "s.row_hash", "s.source_file", "s.load_id", "s.load_id", ":now", ":now"]
    body = (
        f"INSERT INTO {spec.table} ({', '.join(insert_cols)}) "
        f"SELECT {', '.join(select_exprs)} FROM {spec.stg_table} s "
        f"LEFT JOIN {spec.table} c ON c.{spec.pk} = s.{spec.pk} "
        f"WHERE s.load_id = :load_id AND (c.{spec.pk} IS NULL OR c.row_hash <> s.row_hash) "
    )
    updatable = [c for c in cols if c != spec.pk] + ["row_hash", "source_file", "updated_load_id", "etl_updated_at"]
    if dialect_name == "mysql":
        sets = ", ".join(f"{c} = VALUES({c})" for c in updatable)
        return body + f"ON DUPLICATE KEY UPDATE {sets}"
    sets = ", ".join(f"{c} = excluded.{c}" for c in updatable)
    return body + f"ON CONFLICT ({spec.pk}) DO UPDATE SET {sets}"


def merge_to_curated(conn, spec: Entity, load_id: str, now: str) -> None:
    conn.execute(text(merge_sql(dialect(conn), spec)), {"load_id": load_id, "now": now})


def purge_staging(conn, keep_loads: int) -> None:
    """Keep staging rows only for the most recent N loads."""
    keep = (
        "SELECT load_id FROM (SELECT load_id FROM etl_load_audit "
        f"ORDER BY started_at DESC, load_id DESC LIMIT {int(keep_loads)}) recent"
    )
    for spec in ENTITIES:
        conn.execute(text(f"DELETE FROM {spec.stg_table} WHERE load_id NOT IN ({keep})"))


# ------------------------------------------------------------------ diagnostics persistence
def persist_rejects(conn, load_id: str, source_file_by_entity: dict[str, str], rejects: list[dict], now: str) -> None:
    stmt = text(
        "INSERT INTO etl_rejected_records (load_id, entity, source_file, source_row_number, record_key, "
        "rule_codes, messages, raw_record, rejected_at) VALUES "
        "(:load_id, :entity, :source_file, :source_row_number, :record_key, :rule_codes, :messages, "
        ":raw_record, :now)"
    )
    for part in chunked(rejects, BATCH):
        conn.execute(stmt, [
            {**r, "load_id": load_id, "source_file": source_file_by_entity[r["entity"]], "now": now}
            for r in part])


def persist_dq(conn, load_id: str, stats: list[dict], now: str) -> None:
    if stats:
        conn.execute(
            text("INSERT INTO etl_dq_results (load_id, entity, rule_code, severity, failed_rows, "
                 "checked_rows, checked_at) VALUES (:load_id, :entity, :rule_code, :severity, "
                 ":failed_rows, :checked_rows, :now)"),
            [{**s, "load_id": load_id, "now": now} for s in stats])


def persist_recon(conn, load_id: str, checks: list[dict], now: str) -> None:
    if checks:
        conn.execute(
            text("INSERT INTO etl_reconciliation (load_id, entity, check_name, source_value, target_value, "
                 "difference, status, checked_at) VALUES (:load_id, :entity, :check_name, :source_value, "
                 ":target_value, :difference, :status, :now)"),
            [{**c, "load_id": load_id, "now": now} for c in checks])


def register_file(conn, entity: str, file_name: str, sha256: str, size: int, rows: int, load_id: str, now: str) -> None:
    exists = conn.execute(
        text("SELECT COUNT(*) FROM etl_file_registry WHERE entity=:e AND sha256=:h"),
        {"e": entity, "h": sha256}).scalar()
    params = {"e": entity, "n": file_name, "h": sha256, "z": size, "r": rows, "l": load_id, "t": now}
    if exists:
        conn.execute(text("UPDATE etl_file_registry SET file_name=:n, size_bytes=:z, row_count=:r, "
                          "load_id=:l, status='LOADED', registered_at=:t WHERE entity=:e AND sha256=:h"), params)
    else:
        conn.execute(text("INSERT INTO etl_file_registry (entity, file_name, sha256, size_bytes, row_count, "
                          "load_id, status, registered_at) VALUES (:e, :n, :h, :z, :r, :l, 'LOADED', :t)"), params)


def advance_watermark(conn, entity: str, value: str | None, load_id: str, now: str) -> None:
    if not value:
        return
    current = fetch_watermark(conn, entity)
    if current is None:
        conn.execute(text("INSERT INTO etl_watermark (entity, watermark_value, last_load_id, updated_at) "
                          "VALUES (:e, :v, :l, :t)"), {"e": entity, "v": value, "l": load_id, "t": now})
    elif value > current:
        conn.execute(text("UPDATE etl_watermark SET watermark_value=:v, last_load_id=:l, updated_at=:t "
                          "WHERE entity=:e"), {"e": entity, "v": value, "l": load_id, "t": now})
