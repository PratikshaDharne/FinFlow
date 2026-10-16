-- ETL control / audit tables ---------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_load_audit (
    load_id           VARCHAR(40)  NOT NULL,
    status            VARCHAR(20)  NOT NULL,           -- RUNNING|SUCCESS|FAILED|SKIPPED|DRY_RUN
    source_dir        VARCHAR(500) NOT NULL,
    started_at        DATETIME     NOT NULL,
    finished_at       DATETIME     NULL,
    azure_status      VARCHAR(20)  NOT NULL DEFAULT 'NOT_ENABLED',
    snowflake_status  VARCHAR(20)  NOT NULL DEFAULT 'NOT_ENABLED',
    error_message     TEXT         NULL,
    PRIMARY KEY (load_id),
    INDEX idx_load_audit_started (started_at),
    CONSTRAINT chk_load_audit_status CHECK (status IN ('RUNNING','SUCCESS','FAILED','SKIPPED','DRY_RUN'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS etl_file_registry (
    file_id        BIGINT       NOT NULL AUTO_INCREMENT,
    entity         VARCHAR(30)  NOT NULL,
    file_name      VARCHAR(255) NOT NULL,
    sha256         CHAR(64)     NOT NULL,
    size_bytes     BIGINT       NOT NULL,
    row_count      INT          NOT NULL,
    load_id        VARCHAR(40)  NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'LOADED',
    registered_at  DATETIME     NOT NULL,
    PRIMARY KEY (file_id),
    UNIQUE KEY uq_file_registry_entity_sha (entity, sha256),   -- duplicate-file prevention
    CONSTRAINT fk_file_registry_load FOREIGN KEY (load_id) REFERENCES etl_load_audit (load_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS etl_watermark (
    entity           VARCHAR(30) NOT NULL,
    watermark_value  DATETIME    NOT NULL,
    last_load_id     VARCHAR(40) NOT NULL,
    updated_at       DATETIME    NOT NULL,
    PRIMARY KEY (entity)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS etl_rejected_records (
    reject_id           BIGINT       NOT NULL AUTO_INCREMENT,
    load_id             VARCHAR(40)  NOT NULL,
    entity              VARCHAR(30)  NOT NULL,
    source_file         VARCHAR(255) NOT NULL,
    source_row_number   INT          NOT NULL,
    record_key          VARCHAR(40)  NULL,
    rule_codes          VARCHAR(500) NOT NULL,
    messages            TEXT         NOT NULL,
    raw_record          TEXT         NOT NULL,             -- PII masked when FINFLOW_MASK_PII_IN_REPORTS=true
    rejected_at         DATETIME     NOT NULL,
    PRIMARY KEY (reject_id),
    INDEX idx_rejected_load_entity (load_id, entity),
    INDEX idx_rejected_key (record_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS etl_dq_results (
    dq_id        BIGINT      NOT NULL AUTO_INCREMENT,
    load_id      VARCHAR(40) NOT NULL,
    entity       VARCHAR(30) NOT NULL,
    rule_code    VARCHAR(80) NOT NULL,
    severity     VARCHAR(10) NOT NULL,
    failed_rows  INT         NOT NULL,
    checked_rows INT         NOT NULL,
    checked_at   DATETIME    NOT NULL,
    PRIMARY KEY (dq_id),
    INDEX idx_dq_load_entity (load_id, entity)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS etl_reconciliation (
    recon_id      BIGINT        NOT NULL AUTO_INCREMENT,
    load_id       VARCHAR(40)   NOT NULL,
    entity        VARCHAR(30)   NOT NULL,
    check_name    VARCHAR(80)   NOT NULL,
    source_value  DECIMAL(24,2) NOT NULL,
    target_value  DECIMAL(24,2) NOT NULL,
    difference    DECIMAL(24,2) NOT NULL,
    status        VARCHAR(10)   NOT NULL,                 -- PASS|FAIL
    checked_at    DATETIME      NOT NULL,
    PRIMARY KEY (recon_id),
    INDEX idx_recon_load (load_id, entity)
) ENGINE=InnoDB;
