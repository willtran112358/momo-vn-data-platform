-- dq_freshness_checks.sql — SQL-side data quality checks.
-- Run as the final step of each gold build; a non-empty result = a breach.
-- Wire these into the orchestrator so CRITICAL rows block the publish.

-- 1) FRESHNESS (CRITICAL): gold must be < 2h old.
SELECT 'freshness' AS check_name, 'CRITICAL' AS severity,
       MAX(load_ts) AS last_load
FROM gold.fct_transaction_daily
HAVING MAX(load_ts) < NOW() - INTERVAL 2 HOUR;

-- 2) GRAIN UNIQUENESS (CRITICAL): no duplicate (dt, service_code, kyc_tier).
SELECT 'pk_unique' AS check_name, 'CRITICAL' AS severity,
       dt, service_code, kyc_tier, COUNT(*) AS dup_count
FROM gold.fct_transaction_daily
GROUP BY dt, service_code, kyc_tier
HAVING COUNT(*) > 1;

-- 3) NON-NEGATIVE GMV (CRITICAL).
SELECT 'gmv_non_negative' AS check_name, 'CRITICAL' AS severity,
       dt, service_code, gmv_vnd
FROM gold.fct_transaction_daily
WHERE gmv_vnd < 0;

-- 4) RECONCILIATION (CRITICAL): gold GMV vs ledger control total (±0.1%).
WITH g AS (
    SELECT dt, SUM(gmv_vnd) AS gold_gmv
    FROM gold.fct_transaction_daily GROUP BY dt
),
l AS (
    SELECT dt, SUM(amount_vnd) AS ledger_gmv
    FROM finance.ledger_settled GROUP BY dt
)
SELECT 'gmv_reconciliation' AS check_name, 'CRITICAL' AS severity,
       g.dt, g.gold_gmv, l.ledger_gmv,
       ABS(g.gold_gmv - l.ledger_gmv) / NULLIF(l.ledger_gmv, 0) AS rel_diff
FROM g JOIN l USING (dt)
WHERE ABS(g.gold_gmv - l.ledger_gmv) / NULLIF(l.ledger_gmv, 0) > 0.001;

-- 5) COMPLETENESS / DISTRIBUTION (WARN): income null-rate drift.
SELECT 'income_null_rate' AS check_name, 'WARN' AS severity,
       AVG(CASE WHEN declared_income IS NULL THEN 1 ELSE 0 END) AS null_rate
FROM silver.wallet_user
HAVING AVG(CASE WHEN declared_income IS NULL THEN 1 ELSE 0 END) > 0.6;
