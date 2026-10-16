# Agile backlog (sample)

Team of one, two-week sprints. Story points are rough. **Done** = implemented in this repo and covered by the tests described in the README.
"Not verified" = written but never executed against the real service.

## Epic 1 - Ingestion and layering
| ID | Story | Pts | Status |
|---|---|---|---|
| FF-1 | As an engineer I generate deterministic synthetic customers/accounts/transactions/payments with seeded defects | 3 | Done |
| FF-2 | As an operator I snapshot each source file to an immutable raw layer with SHA-256 | 2 | Done |
| FF-3 | As an operator I get raw/staging/curated layers with `load_id` lineage | 5 | Done |
| FF-4 | As a platform owner raw files are also staged to Azure Blob/ADLS | 3 | Written - not verified |

## Epic 2 - Data quality and reconciliation
| ID | Story | Pts | Status |
|---|---|---|---|
| FF-5 | Rules for missing values, formats, dates, amounts, enums, duplicates, FKs, cross-table currency | 8 | Done |
| FF-6 | Rejected-record report + table with rule codes and source row numbers | 3 | Done |
| FF-7 | Source-to-target row-count and per-currency financial reconciliation, failing the load on mismatch | 5 | Done |
| FF-8 | Circuit breaker on reject percentage | 1 | Done |

## Epic 3 - Loading
| ID | Story | Pts | Status |
|---|---|---|---|
| FF-9 | Incremental loading with watermark + look-back + row-hash change detection | 5 | Done |
| FF-10 | Atomic, rerun-safe loads (file registry, hash merge, rollback) | 5 | Done (SQLite); MySQL path not verified |
| FF-11 | MySQL 8.0 schemas with PK/FK/CHECK/indexes/audit columns | 5 | Written - not verified on MySQL |
| FF-12 | Snowflake MERGE load and DDL | 5 | SQL generation tested; execution not verified |

## Epic 4 - Orchestration and operations
| ID | Story | Pts | Status |
|---|---|---|---|
| FF-13 | ADF pipeline: validate, copy, run ETL, alert, fail; tumbling-window trigger with retry | 5 | Written - not verified |
| FF-14 | Azure Monitor alert for failed runs | 2 | Written - not verified |
| FF-15 | Structured JSON logging with secret redaction | 2 | Done |
| FF-16 | GitHub Actions CI: lint, tests, SQLite smoke test, MySQL service job | 3 | Written - first real run pending |

## Next sprint candidates
| ID | Story | Pts |
|---|---|---|
| FF-17 | Move FK/currency validation into set-based SQL on staging for very large files | 5 |
| FF-18 | Parquet raw layer + partitioned Snowflake external tables | 5 |
| FF-19 | SCD2 history for `customers` | 8 |
| FF-20 | Data-freshness SLA metric and Azure Monitor dashboard | 3 |
| FF-21 | Great Expectations/dbt-style test catalogue alignment | 5 |
| FF-22 | Run MySQL integration test locally and in CI; record results | 2 |

## Definition of done
Code + tests pass in CI, SQL scripts versioned, docs/data dictionary regenerated, no secrets, reconciliation green on sample data.
