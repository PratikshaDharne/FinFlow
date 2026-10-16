-- SQLite schema: zero-setup local/CI equivalent of sql/mysql/02..05 (same tables and columns).
-- MySQL remains the real target; this file exists so the pipeline is runnable and testable anywhere.
CREATE TABLE IF NOT EXISTS etl_load_audit (
    load_id TEXT PRIMARY KEY, status TEXT NOT NULL, source_dir TEXT NOT NULL,
    started_at TEXT NOT NULL, finished_at TEXT,
    azure_status TEXT NOT NULL DEFAULT 'NOT_ENABLED', snowflake_status TEXT NOT NULL DEFAULT 'NOT_ENABLED',
    error_message TEXT,
    CHECK (status IN ('RUNNING','SUCCESS','FAILED','SKIPPED','DRY_RUN'))
);
CREATE INDEX IF NOT EXISTS idx_load_audit_started ON etl_load_audit (started_at);

CREATE TABLE IF NOT EXISTS etl_file_registry (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT, entity TEXT NOT NULL, file_name TEXT NOT NULL,
    sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, row_count INTEGER NOT NULL,
    load_id TEXT NOT NULL REFERENCES etl_load_audit (load_id), status TEXT NOT NULL DEFAULT 'LOADED',
    registered_at TEXT NOT NULL, UNIQUE (entity, sha256)
);

CREATE TABLE IF NOT EXISTS etl_watermark (
    entity TEXT PRIMARY KEY, watermark_value TEXT NOT NULL, last_load_id TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_rejected_records (
    reject_id INTEGER PRIMARY KEY AUTOINCREMENT, load_id TEXT NOT NULL, entity TEXT NOT NULL,
    source_file TEXT NOT NULL, source_row_number INTEGER NOT NULL, record_key TEXT,
    rule_codes TEXT NOT NULL, messages TEXT NOT NULL, raw_record TEXT NOT NULL, rejected_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rejected_load_entity ON etl_rejected_records (load_id, entity);
CREATE INDEX IF NOT EXISTS idx_rejected_key ON etl_rejected_records (record_key);

CREATE TABLE IF NOT EXISTS etl_dq_results (
    dq_id INTEGER PRIMARY KEY AUTOINCREMENT, load_id TEXT NOT NULL, entity TEXT NOT NULL,
    rule_code TEXT NOT NULL, severity TEXT NOT NULL, failed_rows INTEGER NOT NULL,
    checked_rows INTEGER NOT NULL, checked_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dq_load_entity ON etl_dq_results (load_id, entity);

CREATE TABLE IF NOT EXISTS etl_reconciliation (
    recon_id INTEGER PRIMARY KEY AUTOINCREMENT, load_id TEXT NOT NULL, entity TEXT NOT NULL,
    check_name TEXT NOT NULL, source_value NUMERIC NOT NULL, target_value NUMERIC NOT NULL,
    difference NUMERIC NOT NULL, status TEXT NOT NULL, checked_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recon_load ON etl_reconciliation (load_id, entity);

CREATE TABLE IF NOT EXISTS stg_customers (
    load_id TEXT NOT NULL,
    customer_id TEXT NOT NULL, first_name TEXT NOT NULL, last_name TEXT NOT NULL, email TEXT NOT NULL,
    phone TEXT, date_of_birth TEXT NOT NULL, country TEXT NOT NULL, segment TEXT NOT NULL,
    kyc_status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    row_hash TEXT NOT NULL, source_file TEXT NOT NULL, source_row_number INTEGER NOT NULL, staged_at TEXT NOT NULL,
    PRIMARY KEY (load_id, customer_id)
);
CREATE TABLE IF NOT EXISTS stg_accounts (
    load_id TEXT NOT NULL,
    account_id TEXT NOT NULL, customer_id TEXT NOT NULL, account_type TEXT NOT NULL, currency TEXT NOT NULL,
    opened_date TEXT NOT NULL, status TEXT NOT NULL, credit_limit NUMERIC, updated_at TEXT NOT NULL,
    row_hash TEXT NOT NULL, source_file TEXT NOT NULL, source_row_number INTEGER NOT NULL, staged_at TEXT NOT NULL,
    PRIMARY KEY (load_id, account_id)
);
CREATE TABLE IF NOT EXISTS stg_transactions (
    load_id TEXT NOT NULL,
    transaction_id TEXT NOT NULL, account_id TEXT NOT NULL, transaction_ts TEXT NOT NULL,
    amount NUMERIC NOT NULL, currency TEXT NOT NULL, txn_type TEXT NOT NULL, channel TEXT NOT NULL,
    merchant_category TEXT, status TEXT NOT NULL, updated_at TEXT NOT NULL,
    row_hash TEXT NOT NULL, source_file TEXT NOT NULL, source_row_number INTEGER NOT NULL, staged_at TEXT NOT NULL,
    PRIMARY KEY (load_id, transaction_id)
);
CREATE TABLE IF NOT EXISTS stg_payments (
    load_id TEXT NOT NULL,
    payment_id TEXT NOT NULL, account_id TEXT NOT NULL, transaction_id TEXT, payment_date TEXT NOT NULL,
    amount NUMERIC NOT NULL, currency TEXT NOT NULL, method TEXT NOT NULL, status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    row_hash TEXT NOT NULL, source_file TEXT NOT NULL, source_row_number INTEGER NOT NULL, staged_at TEXT NOT NULL,
    PRIMARY KEY (load_id, payment_id)
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL, email TEXT NOT NULL,
    phone TEXT, date_of_birth TEXT NOT NULL, country TEXT NOT NULL, segment TEXT NOT NULL,
    kyc_status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    row_hash TEXT NOT NULL, source_file TEXT NOT NULL, created_load_id TEXT NOT NULL,
    updated_load_id TEXT NOT NULL, etl_created_at TEXT NOT NULL, etl_updated_at TEXT NOT NULL,
    CHECK (segment IN ('RETAIL','SME','CORPORATE')),
    CHECK (kyc_status IN ('VERIFIED','PENDING','REJECTED'))
);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers (email);
CREATE INDEX IF NOT EXISTS idx_customers_updated ON customers (updated_at);

CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers (customer_id),
    account_type TEXT NOT NULL, currency TEXT NOT NULL, opened_date TEXT NOT NULL, status TEXT NOT NULL,
    credit_limit NUMERIC, updated_at TEXT NOT NULL,
    row_hash TEXT NOT NULL, source_file TEXT NOT NULL, created_load_id TEXT NOT NULL,
    updated_load_id TEXT NOT NULL, etl_created_at TEXT NOT NULL, etl_updated_at TEXT NOT NULL,
    CHECK (account_type IN ('CHECKING','SAVINGS','CREDIT','LOAN')),
    CHECK (currency IN ('USD','EUR','GBP','INR')),
    CHECK (status IN ('ACTIVE','DORMANT','CLOSED')),
    CHECK (credit_limit IS NULL OR credit_limit >= 0)
);
CREATE INDEX IF NOT EXISTS idx_accounts_customer ON accounts (customer_id);
CREATE INDEX IF NOT EXISTS idx_accounts_updated ON accounts (updated_at);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts (account_id),
    transaction_ts TEXT NOT NULL, amount NUMERIC NOT NULL, currency TEXT NOT NULL, txn_type TEXT NOT NULL,
    channel TEXT NOT NULL, merchant_category TEXT, status TEXT NOT NULL, updated_at TEXT NOT NULL,
    row_hash TEXT NOT NULL, source_file TEXT NOT NULL, created_load_id TEXT NOT NULL,
    updated_load_id TEXT NOT NULL, etl_created_at TEXT NOT NULL, etl_updated_at TEXT NOT NULL,
    CHECK (amount > 0), CHECK (txn_type IN ('CREDIT','DEBIT')),
    CHECK (status IN ('POSTED','PENDING','REVERSED'))
);
CREATE INDEX IF NOT EXISTS idx_txn_account_ts ON transactions (account_id, transaction_ts);
CREATE INDEX IF NOT EXISTS idx_txn_updated ON transactions (updated_at);

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts (account_id),
    transaction_id TEXT REFERENCES transactions (transaction_id), payment_date TEXT NOT NULL,
    amount NUMERIC NOT NULL, currency TEXT NOT NULL, method TEXT NOT NULL, status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    row_hash TEXT NOT NULL, source_file TEXT NOT NULL, created_load_id TEXT NOT NULL,
    updated_load_id TEXT NOT NULL, etl_created_at TEXT NOT NULL, etl_updated_at TEXT NOT NULL,
    CHECK (amount > 0), CHECK (method IN ('ACH','WIRE','CARD','UPI','CHEQUE')),
    CHECK (status IN ('SETTLED','FAILED','PENDING'))
);
CREATE INDEX IF NOT EXISTS idx_payments_account ON payments (account_id, payment_date);
CREATE INDEX IF NOT EXISTS idx_payments_txn ON payments (transaction_id);

CREATE VIEW IF NOT EXISTS v_account_balances AS
SELECT a.account_id, a.customer_id, a.currency,
       COALESCE(SUM(CASE WHEN t.txn_type = 'CREDIT' THEN t.amount
                         WHEN t.txn_type = 'DEBIT' THEN -t.amount END), 0) AS net_posted_amount,
       COUNT(t.transaction_id) AS posted_txn_count
FROM accounts a
LEFT JOIN transactions t ON t.account_id = a.account_id AND t.status = 'POSTED'
GROUP BY a.account_id, a.customer_id, a.currency;
