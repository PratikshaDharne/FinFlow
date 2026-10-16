-- Ad-hoc validation queries (read-only). Every query should return 0 rows / 0.
-- Orphans (must be impossible thanks to FKs; kept as defence in depth)
SELECT COUNT(*) AS orphan_accounts FROM accounts a LEFT JOIN customers c USING (customer_id) WHERE c.customer_id IS NULL;
SELECT COUNT(*) AS orphan_txns     FROM transactions t LEFT JOIN accounts a USING (account_id) WHERE a.account_id IS NULL;
SELECT COUNT(*) AS orphan_payments FROM payments p LEFT JOIN accounts a USING (account_id) WHERE a.account_id IS NULL;
-- Currency consistency between transactions and accounts
SELECT COUNT(*) AS currency_mismatch FROM transactions t JOIN accounts a USING (account_id) WHERE t.currency <> a.currency;
-- Failed reconciliation checks, latest loads
SELECT load_id, entity, check_name, source_value, target_value, difference FROM etl_reconciliation WHERE status = 'FAIL' ORDER BY checked_at DESC;
-- Top reject reasons
SELECT entity, rule_codes, COUNT(*) AS n FROM etl_rejected_records GROUP BY entity, rule_codes ORDER BY n DESC LIMIT 20;
-- Rows per layer
SELECT 'customers' t, COUNT(*) n FROM customers UNION ALL SELECT 'accounts', COUNT(*) FROM accounts
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions UNION ALL SELECT 'payments', COUNT(*) FROM payments;
