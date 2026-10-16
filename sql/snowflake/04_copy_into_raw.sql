-- ELT alternative: load the raw CSVs from ADLS directly into Snowflake RAW tables (UNTESTED).
-- The Python pipeline validates BEFORE loading; this path is for landing the unvalidated raw copy
-- for audit/replay. COPY INTO is idempotent: Snowflake tracks loaded files for 64 days.
USE DATABASE FINFLOW_DB;
CREATE TABLE IF NOT EXISTS RAW.CUSTOMERS_RAW (
    CUSTOMER_ID STRING, FIRST_NAME STRING, LAST_NAME STRING, EMAIL STRING, PHONE STRING, DATE_OF_BIRTH STRING,
    COUNTRY STRING, SEGMENT STRING, KYC_STATUS STRING, CREATED_AT STRING, UPDATED_AT STRING,
    _SOURCE_FILE STRING, _LOADED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP());

COPY INTO RAW.CUSTOMERS_RAW (CUSTOMER_ID, FIRST_NAME, LAST_NAME, EMAIL, PHONE, DATE_OF_BIRTH, COUNTRY,
                             SEGMENT, KYC_STATUS, CREATED_AT, UPDATED_AT, _SOURCE_FILE)
FROM (SELECT $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11, METADATA$FILENAME FROM @RAW.STG_AZURE_RAW/customers/)
PATTERN = '.*customers\\.csv'
ON_ERROR = 'ABORT_STATEMENT';
-- Repeat for accounts / transactions / payments with their column lists (see docs/data_dictionary.md).
