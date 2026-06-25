-- gold_txn_daily_mart.sql — self-serve daily transaction mart (StarRocks).
-- Pre-aggregated for high-concurrency BI (Superset / Looker / Data Studio).
-- One governed definition of GMV / active users so every team reports the same number.
--
-- Grain: dt x service_code x kyc_tier
-- Refresh: daily 06:00 ICT (see airflow_platform_dag.py); blocked on DQ contract.

CREATE TABLE IF NOT EXISTS gold.fct_transaction_daily (
    dt              DATE         NOT NULL,
    service_code    VARCHAR(32)  NOT NULL,
    kyc_tier        VARCHAR(16)  NOT NULL,
    gmv_vnd         BIGINT       NOT NULL COMMENT 'sum of settled amount',
    txn_count       BIGINT       NOT NULL,
    active_users    BIGINT       NOT NULL COMMENT 'distinct users with >=1 settled txn',
    avg_ticket_vnd  BIGINT       NOT NULL,
    pipeline_run_id VARCHAR(32)  NOT NULL,
    load_ts         DATETIME     NOT NULL
)
DUPLICATE KEY(dt, service_code, kyc_tier)
PARTITION BY RANGE(dt) ()
DISTRIBUTED BY HASH(service_code) BUCKETS 8;

-- Idempotent rebuild of one partition (safe to re-run a date).
INSERT OVERWRITE gold.fct_transaction_daily
SELECT
    t.dt,
    t.service_code,
    u.kyc_tier,
    SUM(t.amount_vnd)                              AS gmv_vnd,
    COUNT(*)                                       AS txn_count,
    COUNT(DISTINCT t.user_id)                      AS active_users,
    CAST(SUM(t.amount_vnd) / COUNT(*) AS BIGINT)   AS avg_ticket_vnd,
    '${PIPELINE_RUN_ID}'                           AS pipeline_run_id,
    NOW()                                          AS load_ts
FROM silver.transaction t
-- as-of join: the user's attributes as they were at transaction time (SCD2).
JOIN gold.dim_user_scd2 u
  ON  u.user_id = t.user_id
  AND t.event_ts >= u.valid_from
  AND t.event_ts <  u.valid_to
WHERE t.status = 'SETTLED'
  AND t.dt = DATE('${RUN_DATE}')
GROUP BY t.dt, t.service_code, u.kyc_tier;
