# Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `'finflow' is not recognized` | venv not active / package not installed | `.\.venv\Scripts\Activate.ps1` then `pip install -e .`; or use `python -m finflow ...` |
| `running scripts is disabled on this system` | PowerShell execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` or run with `powershell -ExecutionPolicy Bypass -File ...` |
| `ERROR: Missing required secret MYSQL_PASSWORD` (exit 10) | `FINFLOW_DB_BACKEND=mysql` but no password | Put it in `.env` (never commit) or set `KEY_VAULT_URL` and store `MYSQL-PASSWORD` in Key Vault |
| `Can't connect to MySQL server` / `OperationalError` | MySQL not running, wrong host/port, firewall | `docker compose up -d`, check `MYSQL_HOST/PORT`; the transaction is retried `FINFLOW_DB_RETRY_ATTEMPTS` times, then fails safely |
| `Access denied for user` | wrong credentials or missing grants | Re-run `sql/mysql/01_create_database_and_roles.sql` as admin; ETL user needs SELECT/INSERT/UPDATE/DELETE |
| `CREATE command denied` with `FINFLOW_AUTO_INIT_SCHEMA=true` | ETL user is (correctly) not allowed DDL | Deploy tables once with the deploy account (`finflow init-db`), then set `FINFLOW_AUTO_INIT_SCHEMA=false` |
| `RuntimeError: 'cryptography' package is required` | MySQL 8 `caching_sha2_password` | `pip install cryptography` (already in requirements.txt) |
| Exit 11 `Missing source files` | a CSV is absent | All four files are needed: customers, accounts, transactions, payments |
| Exit 12 `missing required column(s)` | upstream schema change | Fix the extract or update `schemas.py` + SQL; nothing was committed. Unexpected *extra* columns only log a warning |
| Exit 13 `% rows rejected exceeds limit` | upstream data problem | Inspect `data/reports/<load_id>/rejected_records.csv`; raise `FINFLOW_DQ_MAX_REJECT_PCT` only deliberately |
| Exit 14 `reconciliation check(s) failed` | row/total mismatch | Whole load rolled back. See `reconciliation.csv`; failed rows are also in `etl_reconciliation` |
| Load status `SKIPPED` | same file contents already loaded | Expected. Use `--force` to reprocess (safe) |
| Everything is `skipped_by_watermark` | data older than the watermark + look-back, and keys already loaded | Expected for replays. Use `--full-refresh` to ignore the watermark |
| `FOREIGN KEY constraint failed` | a code path bypassed validation | The load rolled back; open an issue with the load_id. Reject reasons are in `etl_rejected_records` |
| Snowflake sync failed after MySQL success (exit 15) | network/credentials/warehouse | MySQL is committed. Fix the cause, then `finflow sync-snowflake` |
| Azure upload `AuthorizationPermissionMismatch` | identity lacks `Storage Blob Data Contributor` on the raw container | Assign the role to the identity (not the account key) |
| `database is locked` (SQLite) | two runs at once | Run one load at a time (ADF trigger uses `maxConcurrency: 1`) |

## Where to look
- Console + `logs/finflow.log` (JSON lines, one object per event, `load_id` on every line)
- `data/reports/<load_id>/run_report.md` (human summary) and CSV/JSON detail
- `finflow status` or `SELECT * FROM v_load_summary`
- `sql/mysql/06_validation_queries.sql` for ad-hoc checks

## Resetting the local demo
Delete `data/local/finflow.db`, `data/raw/*`, `data/reports/*`, `logs/*` (all git-ignored), then re-run.
