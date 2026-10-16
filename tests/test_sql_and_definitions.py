import json
import re
from pathlib import Path

from finflow import db
from finflow.schemas import ENTITIES
from finflow.snowflake_loader import curated_ddl, merge_statement, render_sql_file

ROOT = Path(__file__).resolve().parents[1]
AUDIT = {"row_hash", "source_file", "created_load_id", "updated_load_id", "etl_created_at", "etl_updated_at"}


def _table_columns(sql: str, table: str) -> set[str]:
    m = re.search(rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\)", sql, re.S) or \
        re.search(rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\);", sql, re.S)
    cols = set()
    for part in re.split(r",\s*(?![^()]*\))", m.group(1)):
        tok = part.strip().split()
        if tok and tok[0].upper() not in {"PRIMARY", "INDEX", "CONSTRAINT", "UNIQUE", "CHECK", "KEY"}:
            cols.add(tok[0].lower())
    return cols


def test_sql_files_match_schema_definitions():
    mysql = (ROOT / "sql/mysql/04_curated_tables.sql").read_text()
    stg = (ROOT / "sql/mysql/03_staging_tables.sql").read_text()
    sqlite = (ROOT / "sql/sqlite/schema.sql").read_text()
    for spec in ENTITIES:
        expected = set(spec.column_names) | AUDIT
        assert _table_columns(mysql, spec.table) == expected, spec.table
        assert _table_columns(sqlite, spec.table) == expected, spec.table
        expected_stg = set(spec.column_names) | {"load_id", "row_hash", "source_file", "source_row_number", "staged_at"}
        assert _table_columns(stg, spec.stg_table) == expected_stg
        assert _table_columns(sqlite, spec.stg_table) == expected_stg


def test_mysql_and_sqlite_merge_sql_shape():
    spec = ENTITIES[0]
    my, lite = db.merge_sql("mysql", spec), db.merge_sql("sqlite", spec)
    assert "ON DUPLICATE KEY UPDATE" in my and "VALUES(email)" in my
    assert "ON CONFLICT (customer_id) DO UPDATE" in lite and "excluded.email" in lite
    for sql in (my, lite):
        assert "row_hash <> s.row_hash" in sql and "created_load_id" in sql
    assert "created_load_id = " not in my.split("ON DUPLICATE")[1]  # creation audit never overwritten


def test_statement_splitter_ignores_comments():
    stmts = db._split_statements("-- hi\nCREATE TABLE a (x INT); -- trailing\nCREATE TABLE b (y INT);")
    assert len(stmts) == 2


def test_snowflake_sql_generation_and_committed_files_in_sync():
    for spec in ENTITIES:
        merge = merge_statement(spec)
        assert f"MERGE INTO CURATED.{spec.name.upper()}" in merge and "WHEN NOT MATCHED" in merge
        assert "ROW_HASH <> s.ROW_HASH" in merge and "%(load_id)s" in merge
        assert f"PRIMARY KEY ({spec.pk.upper()})" in curated_ddl(spec)
    assert (ROOT / "sql/snowflake/03_tables.sql").read_text() == render_sql_file("tables")
    assert (ROOT / "sql/snowflake/05_merge_curated.sql").read_text() == render_sql_file("merge")


def test_adf_definitions_are_valid_json_with_retries_and_no_secrets():
    files = list((ROOT / "azure/adf").rglob("*.json"))
    assert len(files) >= 9
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        assert "name" in doc and "properties" in doc, f.name
        raw = f.read_text()
        assert not re.search(r"(?i)\"(password|accountKey|connectionString)\"\s*:\s*\"[^\"@{]", raw), f.name
    pipeline = json.loads((ROOT / "azure/adf/pipeline/pl_finflow_daily.json").read_text())
    text = json.dumps(pipeline)
    assert '"retry": 3' in text and "Notify_Failure" in text and "Fail_Pipeline" in text
    trigger = json.loads((ROOT / "azure/adf/trigger/tr_finflow_daily.json").read_text())
    assert trigger["properties"]["typeProperties"]["retryPolicy"]["count"] >= 1


def test_required_repo_files_exist():
    for rel in ("README.md", "requirements.txt", ".env.example", ".gitignore", ".github/workflows/ci.yml",
                "docs/architecture.md", "docs/data_dictionary.md", "docs/troubleshooting.md",
                "docs/agile_backlog.md", "docs/security_and_governance.md", "docs/source_to_target_mapping.md"):
        assert (ROOT / rel).exists(), rel
