# FinFlow run report

- **Load ID:** `20261016T020111Z-0e629c9b`
- **Status:** SUCCESS
- **Started / finished (UTC):** 2026-10-16 02:01:11 / 2026-10-16 02:01:12
- **Azure staging:** NOT_ENABLED | **Snowflake:** NOT_ENABLED
- **Reconciliation:** 40 passed, 0 failed

## Row disposition per entity

| entity | source_rows | rejected_rows | skipped_watermark | staged_rows | inserted | updated | unchanged | skipped_duplicate_file |
|---|---|---|---|---|---|---|---|---|
| customers | 119 | 6 | 11 | 102 | 63 | 36 | 3 | False |
| accounts | 134 | 5 | 10 | 119 | 91 | 23 | 5 | False |
| transactions | 1251 | 57 | 15 | 1179 | 1146 | 29 | 4 | False |
| payments | 339 | 20 | 12 | 307 | 283 | 19 | 5 | False |

## Failed reconciliation checks

_none_

## Top data-quality rule failures

| entity | rule_code | severity | failed_rows | checked_rows |
|---|---|---|---|---|
| transactions | FK_VIOLATION:account_id | ERROR | 51 | 1251 |
| payments | FK_VIOLATION:account_id | ERROR | 14 | 339 |
| payments | FK_VIOLATION:transaction_id | ERROR | 10 | 339 |
| customers | DUPLICATE_KEY:customer_id | ERROR | 4 | 119 |
| accounts | DUPLICATE_KEY:account_id | ERROR | 3 | 134 |
| transactions | DUPLICATE_ROW:transaction_id | ERROR | 2 | 1251 |
| transactions | INVALID_ENUM:txn_type | ERROR | 2 | 1251 |
| accounts | FK_VIOLATION:customer_id | ERROR | 2 | 134 |
| transactions | INVALID_NUMBER:amount | ERROR | 2 | 1251 |
| payments | INVALID_ENUM:method | ERROR | 2 | 339 |
| customers | INVALID_FORMAT:email | ERROR | 1 | 119 |
| customers | INVALID_DATE:date_of_birth | ERROR | 1 | 119 |

