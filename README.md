# FinFlow - Enterprise Financial Data Engineering Pipeline

An end-to-end, runnable ETL/ELT pipeline for synthetic banking data (customers, accounts, transactions, payments):
ingest CSVs -> immutable **raw** layer -> validated **staging** -> audited **curated** tables in **MySQL 8.0**
(and **Snowflake**), with Azure staging and Azure Data Factory definitions for orchestration. Built as a portfolio
project for a data-engineering internship.

**Stack:** Python 3.11+, SQL, Pandas, NumPy, SQLAlchemy, PyMySQL, MySQL 8.0, Azure Blob/ADLS Gen2, Azure Data Factory,
Snowflake, pytest, ruff, Git/GitHub Actions.

## What was verified, and what was not

Be skeptical of any README that claims everything works. This one separates evidence from intent.

| Area | Status | Evidence |
|---|---|---|
| Synthetic data generation (deterministic) | **Verified** | regenerating produced byte-identical files |
| Extract, validation rules, transform, hashing, watermark | **Verified** | unit tests + end-to-end runs |
| Full pipeline on **SQLite** (batch 1, incremental batch 2, rerun skip, forced rerun, dry run, rollback on crash, rollback on failed reconciliation, reject-threshold abort) | **Verified** | `tests/test_pipeline_e2e.py` and CLI runs; outputs in `docs/sample_output/` are real |
| MySQL 8.0 DDL and `ON DUPLICATE KEY UPDATE` merge | **NOT verified** | No MySQL in the build environment. SQL is written and shape-tested; `tests/test_mysql_integration.py` + the CI `mysql-integration` job are the first real execution |
| Real **SQLAlchemy** and real **pytest** | **NOT verified here** | The build sandbox had no network, so neither package could be installed. The suite and pipeline were executed with small throw-away stand-ins (sqlite3-backed, not shipped) that implement only the API subset used. Your first `pytest` run on a normal machine is the first real run - see "First run" below |
| ruff lint | **NOT run** | ruff unavailable offline. Code was compile-checked and scanned for unused imports with a script |
| Azure Blob upload, Key Vault lookup | **UNTESTED** | No Azure access. Code written, labeled untested |
| ADF pipeline/trigger/linked services | **UNTESTED** | JSON validity and structure tested only; never deployed |
| Snowflake load | **UNTESTED** | MERGE/DDL SQL generation is unit-tested; nothing executed on Snowflake |
| GitHub Actions workflow | **UNTESTED** | Not yet run on GitHub |
| Performance | **No claims** | No benchmarks were run; the sample is ~7,000 rows |

## Repository layout

```
src/finflow/        config, schemas (single source of truth), extract, quality, transform, db, pipeline,
                    reconciliation, reports, azure_storage, snowflake_loader, generate_data, cli
sql/mysql/          01 bootstrap+roles, 02 audit, 03 staging, 04 curated, 05 views, 06 validation queries
sql/sqlite/         schema.sql (zero-setup local/CI equivalent)
sql/snowflake/      01 setup, 02 storage integration+stage, 03 tables*, 04 COPY INTO, 05 MERGE*, 06 checks  (*generated)
data/source/        synthetic CSVs: batch_01 (initial) and batch_02 (incremental, schema drift, replays)
azure/adf/          ADF linked services, datasets, pipeline, trigger (+ README);  azure/monitoring, azure/scripts
tests/              pytest suite
docs/               architecture, data dictionary, source-to-target mapping, security, troubleshooting, backlog, sample_output
.github/workflows/  ci.yml
scripts/            setup_windows.ps1, run_local.ps1, generate_snowflake_sql.py, generate_docs.py
```

## Windows setup (PowerShell) - exact steps

Prerequisites: Windows 10/11, **Python 3.11 or 3.12** from python.org (tick *Add python.exe to PATH*), **Git**. Docker Desktop and a MySQL are optional.

```powershell
# 1. Get the code (unzip FinFlow.zip, or clone your repo) and open PowerShell in the folder
cd C:\path\to\finflow

# 2. Create a virtual environment and install everything
py -3.11 -m venv .venv                      # or: py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1                # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .

# 3. Create your local config (SQLite by default - nothing else to install)
Copy-Item .env.example .env

# 4. Run the tests
pytest -q

# 5. Run the pipeline: initial load, incremental load, rerun
finflow run --source data/source/batch_01
finflow run --source data/source/batch_02
finflow run --source data/source/batch_02      # -> SKIPPED (same files already loaded)
finflow status
```

Or in one go: `powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1` then `.\scripts\run_local.ps1`.

Outputs appear in `data/reports/<load_id>/` (`run_report.md`, `rejected_records.csv`, `dq_summary.csv`,
`reconciliation.csv`, `run_summary.json`), `data/raw/<load_id>/` (immutable file copies), `logs/finflow.log`
(JSON lines) and the SQLite database `data/local/finflow.db` (all git-ignored). Inspect it with any SQLite viewer, or:

```powershell
python -c "import sqlite3;c=sqlite3.connect('data/local/finflow.db');print(c.execute('select status,count(*) from etl_load_audit group by 1').fetchall())"
```

### First run - what to expect, and what to do if it differs
Expected sample results (also in `docs/sample_output/console_run.txt`): batch 1 -> customers 290 inserted / 14 rejected,
accounts 427 / 27, transactions 3,740 / 266, payments 1,124 / 78, reconciliation **40 passed, 0 failed**; batch 2 loads
inserts and updates and skips old replays; the third command prints `SKIPPED`.
Because real SQLAlchemy/pytest were not available when this was built, a failure on your first run is plausible. Please read
`logs/finflow.log` and `docs/troubleshooting.md`, and treat a real failure as a bug to fix, not noise.

### Switching to MySQL 8.0 (optional, recommended for the full experience)
```powershell
# A. Start MySQL (Docker Desktop required). Put MYSQL_ROOT_PASSWORD=<choose one> in .env first.
docker compose up -d
# B. Create the roles (edit the <REPLACE_ME> passwords first; run once as root)
Get-Content sql\mysql\01_create_database_and_roles.sql | docker exec -i finflow-mysql mysql -uroot -p
# C. In .env set:  FINFLOW_DB_BACKEND=mysql, MYSQL_USER=finflow_etl, MYSQL_PASSWORD=<the one you chose>
#    (to let the app create tables, use the deploy user once:  MYSQL_USER=finflow_deploy, then `finflow init-db`)
finflow init-db
finflow run --source data/source/batch_01
```
Optional MySQL integration test: `$env:FINFLOW_TEST_MYSQL_URL="mysql+pymysql://root:<pw>@localhost:3306/finflow_test"; pytest tests/test_mysql_integration.py -v` (use an empty scratch database).

### Azure and Snowflake (optional, UNTESTED)
```powershell
pip install -r requirements-cloud.txt
az login                                    # DefaultAzureCredential picks this up; no keys on disk
# .env: FINFLOW_AZURE_ENABLED=true, AZURE_STORAGE_ACCOUNT_URL=..., then:
finflow run --source data/source/batch_01 --azure
# Snowflake: run sql\snowflake\01..03 in a worksheet, set the SNOWFLAKE_* variables, then add --snowflake
finflow sync-snowflake                      # re-send a committed load if only the Snowflake step failed
```
ADF deployment: `azure/adf/README.md`. Key Vault: `docs/security_and_governance.md`.

## CLI reference

| Command | Purpose |
|---|---|
| `finflow generate-data [--out DIR] [--seed N]` | Regenerate synthetic CSVs (deterministic) |
| `finflow init-db` | Create schema (idempotent) |
| `finflow run --source DIR [--force] [--dry-run] [--full-refresh] [--azure] [--snowflake]` | Run the pipeline |
| `finflow status` | Last 10 loads |
| `finflow sync-snowflake [--load-id ID]` | Push a committed load to Snowflake |

Exit codes: 0 ok, 10 config, 11 source file, 12 schema violation, 13 reject threshold, 14 reconciliation, 15 cloud step.

## How it works (short)

1. **Extract** - copy the four CSVs to `data/raw/<load_id>/` and verify SHA-256 (optionally upload to Azure).
2. **Duplicate-file check** - a file whose hash is already `LOADED` is skipped (`--force` overrides).
3. **Validate** (read-only) - schema (missing column = load fails; extra column = warning), required values, formats,
   real calendar dates, non-future dates, positive amounts with <=2 decimals, enums, duplicates (exact vs superseded key),
   foreign keys (parents first, so rejections cascade), currency match. Rejected rows keep rule codes and row numbers.
4. **Incremental filter** - per-entity watermark with look-back; unseen keys are never skipped.
5. **One transaction** - stage -> merge changed rows (hash compare, upsert) -> reconcile -> persist rejects/DQ/registry/watermark.
   Any exception or failed check rolls it all back.
6. **Reports + audit** - reports on disk, status in `etl_load_audit`, JSON logs.

See `docs/architecture.md` (diagram, decisions, reconciliation checks), `docs/data_dictionary.md`, `docs/source_to_target_mapping.md`.

## Seeded data defects (so every rule has work to do)
Missing/invalid emails, impossible dates (`31/02/1990`, `1990-02-30`), future dates, unknown enums, missing keys,
exact and key duplicates, orphan foreign keys, negative/zero/non-numeric/3-decimal amounts, wrong currency,
malformed timestamps, plus in batch 2: an unexpected column (`legacy_flag`) and replayed unchanged rows.

## Development
```powershell
ruff check src tests scripts            # lint
pytest --cov=finflow                    # tests + coverage
python scripts\generate_snowflake_sql.py ; python scripts\generate_docs.py   # regenerate generated files
```
CI (`.github/workflows/ci.yml`) runs lint, tests on Python 3.11/3.12, a CLI smoke test with a rerun, a generated-files drift check, and a MySQL 8.0 service-container job.

## Known limitations
- FK and currency validation load parent keys into memory; fine for this scale, move to set-based SQL on staging for very large tables (backlog FF-17).
- Curated rows are never deleted; source deletions are not propagated.
- SQLite stores `NUMERIC` as floating point; money is exact only on MySQL/Snowflake (reconciliation quantizes to cents).
- No SCD2 history, no streaming, no orchestration of the Snowflake step beyond the Python sync.

## License
Add the license of your choice before publishing. All data is synthetic.
