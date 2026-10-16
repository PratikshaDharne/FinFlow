-- Staging layer: validated, typed rows for ONE load; rewritten per load_id (rerun-safe).
CREATE TABLE IF NOT EXISTS stg_customers (
    load_id VARCHAR(40) NOT NULL,
    customer_id VARCHAR(10) NOT NULL, first_name VARCHAR(50) NOT NULL, last_name VARCHAR(50) NOT NULL,
    email VARCHAR(120) NOT NULL, phone VARCHAR(20) NULL, date_of_birth DATE NOT NULL,
    country CHAR(2) NOT NULL, segment VARCHAR(10) NOT NULL, kyc_status VARCHAR(10) NOT NULL,
    created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
    row_hash CHAR(64) NOT NULL, source_file VARCHAR(255) NOT NULL,
    source_row_number INT NOT NULL, staged_at DATETIME NOT NULL,
    PRIMARY KEY (load_id, customer_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS stg_accounts (
    load_id VARCHAR(40) NOT NULL,
    account_id VARCHAR(10) NOT NULL, customer_id VARCHAR(10) NOT NULL, account_type VARCHAR(10) NOT NULL,
    currency CHAR(3) NOT NULL, opened_date DATE NOT NULL, status VARCHAR(10) NOT NULL,
    credit_limit DECIMAL(18,2) NULL, updated_at DATETIME NOT NULL,
    row_hash CHAR(64) NOT NULL, source_file VARCHAR(255) NOT NULL,
    source_row_number INT NOT NULL, staged_at DATETIME NOT NULL,
    PRIMARY KEY (load_id, account_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS stg_transactions (
    load_id VARCHAR(40) NOT NULL,
    transaction_id VARCHAR(12) NOT NULL, account_id VARCHAR(10) NOT NULL,
    transaction_ts DATETIME NOT NULL, amount DECIMAL(18,2) NOT NULL, currency CHAR(3) NOT NULL,
    txn_type VARCHAR(6) NOT NULL, channel VARCHAR(10) NOT NULL, merchant_category VARCHAR(40) NULL,
    status VARCHAR(10) NOT NULL, updated_at DATETIME NOT NULL,
    row_hash CHAR(64) NOT NULL, source_file VARCHAR(255) NOT NULL,
    source_row_number INT NOT NULL, staged_at DATETIME NOT NULL,
    PRIMARY KEY (load_id, transaction_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS stg_payments (
    load_id VARCHAR(40) NOT NULL,
    payment_id VARCHAR(12) NOT NULL, account_id VARCHAR(10) NOT NULL, transaction_id VARCHAR(12) NULL,
    payment_date DATE NOT NULL, amount DECIMAL(18,2) NOT NULL, currency CHAR(3) NOT NULL,
    method VARCHAR(10) NOT NULL, status VARCHAR(10) NOT NULL, updated_at DATETIME NOT NULL,
    row_hash CHAR(64) NOT NULL, source_file VARCHAR(255) NOT NULL,
    source_row_number INT NOT NULL, staged_at DATETIME NOT NULL,
    PRIMARY KEY (load_id, payment_id)
) ENGINE=InnoDB;
