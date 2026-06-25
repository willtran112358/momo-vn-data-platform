# Engineering code samples

Runnable, dependency-light samples for the MoMo VN data platform. Most run with
`DRY_RUN=1` (the default) — no database, cluster, or cloud account needed.

```bash
# from repo root
pip install -r requirements.txt

DRY_RUN=1 python samples/ingestion/batch_jdbc_ingest.py
DRY_RUN=1 python samples/ingestion/cdc_debezium_to_lake.py
DRY_RUN=1 python samples/streaming/flink_txn_enrichment.py
DRY_RUN=1 python samples/transform/spark_bronze_to_silver.py
DRY_RUN=1 python samples/quality/dq_contract.py          # exits 1 if CRITICAL fails
DRY_RUN=1 python samples/ml/feature_pipeline_fraud.py
DRY_RUN=1 python samples/ml/credit_scoring_train.py
```

| File | Layer | Highlights |
|------|-------|-----------|
| `ingestion/batch_jdbc_ingest.py` | Ingestion | Watermarked incremental pull, lineage stamp, watermark commit |
| `ingestion/cdc_debezium_to_lake.py` | Ingestion | Debezium op handling, out-of-order-safe LWW upserts, tombstones |
| `streaming/flink_txn_enrichment.py` | Streaming | Keyed velocity window, online feature lookup, fraud decision |
| `transform/spark_bronze_to_silver.py` | Transform | Conform + dedup + **quarantine** (no silent null→0) |
| `transform/dim_user_scd2.sql` | Transform | dbt SCD2 user dimension (point-in-time) |
| `transform/gold_txn_daily_mart.sql` | Serving | StarRocks self-serve mart, as-of SCD2 join |
| `quality/dq_contract.py` | Quality | Declarative contract engine, CRITICAL blocks publish |
| `quality/dq_freshness_checks.sql` | Quality | Freshness, grain, reconciliation, drift checks |
| `orchestration/airflow_platform_dag.py` | Orchestration | Branch on DQ gate, cost tags, SLA |
| `ml/feature_pipeline_fraud.py` | ML | Online/offline feature **parity** |
| `ml/credit_scoring_train.py` | ML | Leakage-safe, explainable reason codes |

> The SQL files (`.sql`) and the Airflow/Flink/Spark "production" branches are
> illustrative — they show the real shape of each job. The Python `DRY_RUN`
> paths are fully executable simulations of the same logic.
