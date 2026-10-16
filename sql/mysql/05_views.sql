-- Reporting views --------------------------------------------------------------
CREATE OR REPLACE VIEW v_account_balances AS
SELECT a.account_id, a.customer_id, a.currency,
       COALESCE(SUM(CASE WHEN t.txn_type = 'CREDIT' THEN t.amount
                         WHEN t.txn_type = 'DEBIT'  THEN -t.amount END), 0) AS net_posted_amount,
       COUNT(t.transaction_id) AS posted_txn_count
FROM accounts a
LEFT JOIN transactions t ON t.account_id = a.account_id AND t.status = 'POSTED'
GROUP BY a.account_id, a.customer_id, a.currency;

CREATE OR REPLACE VIEW v_load_summary AS
SELECT l.load_id, l.status, l.started_at, l.finished_at, l.azure_status, l.snowflake_status,
       (SELECT COUNT(*) FROM etl_rejected_records r WHERE r.load_id = l.load_id) AS rejected_rows,
       (SELECT COUNT(*) FROM etl_reconciliation c WHERE c.load_id = l.load_id AND c.status = 'FAIL') AS failed_checks
FROM etl_load_audit l;
