"""Regenerate sql/snowflake/03_tables.sql and 05_merge_curated.sql from src/finflow/schemas.py.

    python scripts/generate_snowflake_sql.py
A unit test fails if the committed files drift from the generator.
"""
from pathlib import Path

from finflow.snowflake_loader import render_sql_file

OUT = Path(__file__).resolve().parents[1] / "sql" / "snowflake"
(OUT / "03_tables.sql").write_text(render_sql_file("tables"), encoding="utf-8", newline="\n")
(OUT / "05_merge_curated.sql").write_text(render_sql_file("merge"), encoding="utf-8", newline="\n")
print("Snowflake SQL regenerated in", OUT)
