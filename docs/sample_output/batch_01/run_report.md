# FinFlow run report

- **Load ID:** `20261016T020110Z-33947a78`
- **Status:** SUCCESS
- **Started / finished (UTC):** 2026-10-16 02:01:10 / 2026-10-16 02:01:11
- **Azure staging:** NOT_ENABLED | **Snowflake:** NOT_ENABLED
- **Reconciliation:** 40 passed, 0 failed

## Row disposition per entity

| entity | source_rows | rejected_rows | skipped_watermark | staged_rows | inserted | updated | unchanged | skipped_duplicate_file |
|---|---|---|---|---|---|---|---|---|
| customers | 304 | 14 | 0 | 290 | 290 | 0 | 0 | False |
| accounts | 454 | 27 | 0 | 427 | 427 | 0 | 0 | False |
| transactions | 4006 | 266 | 0 | 3740 | 3740 | 0 | 0 | False |
| payments | 1202 | 78 | 0 | 1124 | 1124 | 0 | 0 | False |

## Failed reconciliation checks

_none_

## Top data-quality rule failures

| entity | rule_code | severity | failed_rows | checked_rows |
|---|---|---|---|---|
| transactions | FK_VIOLATION:account_id | ERROR | 242 | 4006 |
| payments | FK_VIOLATION:account_id | ERROR | 63 | 1202 |
| payments | FK_VIOLATION:transaction_id | ERROR | 45 | 1202 |
| accounts | FK_VIOLATION:customer_id | ERROR | 18 | 454 |
| transactions | NON_POSITIVE_AMOUNT:amount | ERROR | 5 | 4006 |
| transactions | INVALID_NUMBER:amount | ERROR | 4 | 4006 |
| transactions | DUPLICATE_ROW:transaction_id | ERROR | 3 | 4006 |
| transactions | INVALID_ENUM:currency | ERROR | 3 | 4006 |
| transactions | CURRENCY_MISMATCH:currency | ERROR | 3 | 4006 |
| transactions | INVALID_TIMESTAMP:transaction_ts | ERROR | 2 | 4006 |
| accounts | INVALID_DATE:opened_date | ERROR | 2 | 454 |
| customers | DUPLICATE_KEY:customer_id | ERROR | 2 | 304 |
| customers | DUPLICATE_ROW:customer_id | ERROR | 2 | 304 |
| customers | MISSING_VALUE:email | ERROR | 2 | 304 |
| accounts | DUPLICATE_ROW:account_id | ERROR | 2 | 454 |
| customers | INVALID_DATE:date_of_birth | ERROR | 2 | 304 |
| customers | INVALID_FORMAT:email | ERROR | 2 | 304 |
| payments | MISSING_VALUE:payment_date | ERROR | 2 | 1202 |
| transactions | INVALID_ENUM:txn_type | ERROR | 2 | 4006 |
| transactions | DUPLICATE_KEY:transaction_id | ERROR | 2 | 4006 |
| transactions | MISSING_VALUE:account_id | ERROR | 2 | 4006 |
| payments | DUPLICATE_ROW:payment_id | ERROR | 2 | 1202 |
| payments | INVALID_ENUM:method | ERROR | 2 | 1202 |
| accounts | DUPLICATE_KEY:account_id | ERROR | 2 | 454 |
| transactions | DATE_OUT_OF_RANGE:transaction_ts | ERROR | 2 | 4006 |

