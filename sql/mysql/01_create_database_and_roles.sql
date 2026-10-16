-- =============================================================================
-- FinFlow - MySQL 8.0 bootstrap. Run ONCE as an administrator (e.g. root / DBA).
-- Replace every <REPLACE_ME> with a strong secret generated and stored in Key Vault.
-- Do NOT commit real passwords. (Least privilege: three separate accounts.)
-- =============================================================================
CREATE DATABASE IF NOT EXISTS finflow
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- Deployment account: owns DDL (used by CI/CD or a DBA only).
CREATE USER IF NOT EXISTS 'finflow_deploy'@'%' IDENTIFIED BY '<REPLACE_ME>';
GRANT CREATE, ALTER, DROP, INDEX, REFERENCES, CREATE VIEW, SELECT, INSERT, UPDATE, DELETE
    ON finflow.* TO 'finflow_deploy'@'%';

-- Runtime ETL account: DML only, no DDL, no access to other schemas.
CREATE USER IF NOT EXISTS 'finflow_etl'@'%' IDENTIFIED BY '<REPLACE_ME>';
GRANT SELECT, INSERT, UPDATE, DELETE ON finflow.* TO 'finflow_etl'@'%';

-- Analyst account: read-only on curated tables/views and audit tables.
CREATE USER IF NOT EXISTS 'finflow_reader'@'%' IDENTIFIED BY '<REPLACE_ME>';
GRANT SELECT ON finflow.* TO 'finflow_reader'@'%';
-- Tighten further in production, e.g. revoke SELECT on etl_rejected_records (contains masked PII).

FLUSH PRIVILEGES;
