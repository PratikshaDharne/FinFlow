-- Post-load checks in Snowflake (UNTESTED). Compare with MySQL: run sql/mysql/06_validation_queries.sql.
USE DATABASE FINFLOW_DB;
SELECT 'customers' AS tbl, COUNT(*) AS n FROM CURATED.CUSTOMERS
UNION ALL SELECT 'accounts', COUNT(*) FROM CURATED.ACCOUNTS
UNION ALL SELECT 'transactions', COUNT(*) FROM CURATED.TRANSACTIONS
UNION ALL SELECT 'payments', COUNT(*) FROM CURATED.PAYMENTS;

-- Totals per currency (must equal MySQL curated totals)
SELECT CURRENCY, SUM(AMOUNT) AS total_amount,
       SUM(IFF(TXN_TYPE = 'CREDIT', AMOUNT, -AMOUNT)) AS net_flow
FROM CURATED.TRANSACTIONS GROUP BY CURRENCY ORDER BY CURRENCY;

-- Orphans (Snowflake does not enforce FKs, so check explicitly; expect 0)
SELECT COUNT(*) AS orphan_txns FROM CURATED.TRANSACTIONS t
LEFT JOIN CURATED.ACCOUNTS a ON a.ACCOUNT_ID = t.ACCOUNT_ID WHERE a.ACCOUNT_ID IS NULL;
