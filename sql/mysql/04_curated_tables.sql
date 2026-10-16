-- Curated layer: normalised, constrained, audited. Business columns + audit columns.
CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(10) NOT NULL, first_name VARCHAR(50) NOT NULL, last_name VARCHAR(50) NOT NULL,
    email VARCHAR(120) NOT NULL, phone VARCHAR(20) NULL, date_of_birth DATE NOT NULL,
    country CHAR(2) NOT NULL, segment VARCHAR(10) NOT NULL, kyc_status VARCHAR(10) NOT NULL,
    created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
    row_hash CHAR(64) NOT NULL, source_file VARCHAR(255) NOT NULL,
    created_load_id VARCHAR(40) NOT NULL, updated_load_id VARCHAR(40) NOT NULL,
    etl_created_at DATETIME NOT NULL, etl_updated_at DATETIME NOT NULL,
    PRIMARY KEY (customer_id),
    INDEX idx_customers_email (email),
    INDEX idx_customers_updated (updated_at),
    CONSTRAINT chk_customers_segment CHECK (segment IN ('RETAIL','SME','CORPORATE')),
    CONSTRAINT chk_customers_kyc CHECK (kyc_status IN ('VERIFIED','PENDING','REJECTED'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS accounts (
    account_id VARCHAR(10) NOT NULL, customer_id VARCHAR(10) NOT NULL, account_type VARCHAR(10) NOT NULL,
    currency CHAR(3) NOT NULL, opened_date DATE NOT NULL, status VARCHAR(10) NOT NULL,
    credit_limit DECIMAL(18,2) NULL, updated_at DATETIME NOT NULL,
    row_hash CHAR(64) NOT NULL, source_file VARCHAR(255) NOT NULL,
    created_load_id VARCHAR(40) NOT NULL, updated_load_id VARCHAR(40) NOT NULL,
    etl_created_at DATETIME NOT NULL, etl_updated_at DATETIME NOT NULL,
    PRIMARY KEY (account_id),
    INDEX idx_accounts_customer (customer_id),
    INDEX idx_accounts_updated (updated_at),
    CONSTRAINT fk_accounts_customer FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    CONSTRAINT chk_accounts_type CHECK (account_type IN ('CHECKING','SAVINGS','CREDIT','LOAN')),
    CONSTRAINT chk_accounts_currency CHECK (currency IN ('USD','EUR','GBP','INR')),
    CONSTRAINT chk_accounts_status CHECK (status IN ('ACTIVE','DORMANT','CLOSED')),
    CONSTRAINT chk_accounts_limit CHECK (credit_limit IS NULL OR credit_limit >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id VARCHAR(12) NOT NULL, account_id VARCHAR(10) NOT NULL,
    transaction_ts DATETIME NOT NULL, amount DECIMAL(18,2) NOT NULL, currency CHAR(3) NOT NULL,
    txn_type VARCHAR(6) NOT NULL, channel VARCHAR(10) NOT NULL, merchant_category VARCHAR(40) NULL,
    status VARCHAR(10) NOT NULL, updated_at DATETIME NOT NULL,
    row_hash CHAR(64) NOT NULL, source_file VARCHAR(255) NOT NULL,
    created_load_id VARCHAR(40) NOT NULL, updated_load_id VARCHAR(40) NOT NULL,
    etl_created_at DATETIME NOT NULL, etl_updated_at DATETIME NOT NULL,
    PRIMARY KEY (transaction_id),
    INDEX idx_txn_account_ts (account_id, transaction_ts),
    INDEX idx_txn_updated (updated_at),
    CONSTRAINT fk_txn_account FOREIGN KEY (account_id) REFERENCES accounts (account_id),
    CONSTRAINT chk_txn_amount CHECK (amount > 0),
    CONSTRAINT chk_txn_type CHECK (txn_type IN ('CREDIT','DEBIT')),
    CONSTRAINT chk_txn_status CHECK (status IN ('POSTED','PENDING','REVERSED'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(12) NOT NULL, account_id VARCHAR(10) NOT NULL, transaction_id VARCHAR(12) NULL,
    payment_date DATE NOT NULL, amount DECIMAL(18,2) NOT NULL, currency CHAR(3) NOT NULL,
    method VARCHAR(10) NOT NULL, status VARCHAR(10) NOT NULL, updated_at DATETIME NOT NULL,
    row_hash CHAR(64) NOT NULL, source_file VARCHAR(255) NOT NULL,
    created_load_id VARCHAR(40) NOT NULL, updated_load_id VARCHAR(40) NOT NULL,
    etl_created_at DATETIME NOT NULL, etl_updated_at DATETIME NOT NULL,
    PRIMARY KEY (payment_id),
    INDEX idx_payments_account (account_id, payment_date),
    INDEX idx_payments_txn (transaction_id),
    CONSTRAINT fk_payments_account FOREIGN KEY (account_id) REFERENCES accounts (account_id),
    CONSTRAINT fk_payments_txn FOREIGN KEY (transaction_id) REFERENCES transactions (transaction_id),
    CONSTRAINT chk_payments_amount CHECK (amount > 0),
    CONSTRAINT chk_payments_method CHECK (method IN ('ACH','WIRE','CARD','UPI','CHEQUE')),
    CONSTRAINT chk_payments_status CHECK (status IN ('SETTLED','FAILED','PENDING'))
) ENGINE=InnoDB;
