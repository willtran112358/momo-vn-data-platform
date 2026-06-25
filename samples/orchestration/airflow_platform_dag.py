"""Airflow DAG: dependency-aware daily platform pipeline.

ingest -> bronze->silver -> DQ gate -> gold marts -> semantic refresh
                                  |
                                  +-- CRITICAL fail -> block gold + alert

Every task carries cost tags (team/project) for FinOps rollup. The DQ gate is a
hard dependency: gold tasks only run if the contract passes.

This is illustrative; install Airflow only if you actually wire it.
"""

from __future__ import annotations

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator, BranchPythonOperator
    from airflow.operators.empty import EmptyOperator
    AIRFLOW = True
except ImportError:  # allows the file to be imported/linted without Airflow
    AIRFLOW = False

COST_TAGS = {"team": "platform-data-eng", "project": "daily-marts",
             "department": "corporate-data-office"}

DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "sla": timedelta(hours=2),
}


# --- task callables --------------------------------------------------------


def ingest_sources(**_):
    from samples.ingestion.batch_jdbc_ingest import run, IngestSpec  # noqa
    return run(IngestSpec(source="payment_core", table="transactions"))


def bronze_to_silver(**_):
    from samples.transform.spark_bronze_to_silver import run  # noqa
    return run()


def run_dq_gate(**_) -> str:
    """Return the next task id based on the DQ verdict (branch)."""
    from samples.quality.dq_contract import evaluate, CONTRACT, sample_gold  # noqa
    verdict = evaluate(sample_gold(), CONTRACT)
    return "build_gold_marts" if verdict["publish"] else "block_and_alert"


def build_gold_marts(**_):
    # Would execute gold_txn_daily_mart.sql with RUN_DATE / PIPELINE_RUN_ID bound.
    return {"status": "gold_built"}


def refresh_semantic_layer(**_):
    # dbt run --select semantic+  (semantic metrics for self-serve BI)
    return {"status": "semantic_refreshed"}


def block_and_alert(**_):
    raise RuntimeError("DQ CRITICAL breach — gold publish blocked; owner paged.")


# --- DAG -------------------------------------------------------------------

if AIRFLOW:
    with DAG(
        dag_id="momo_daily_platform",
        description="MoMo self-serve platform daily pipeline",
        schedule="0 23 * * *",  # 06:00 ICT (UTC+7)
        start_date=datetime(2026, 6, 1),
        catchup=False,
        default_args=DEFAULT_ARGS,
        tags=["platform", "gold", "finops"],
        params=COST_TAGS,
    ) as dag:

        ingest = PythonOperator(task_id="ingest_sources", python_callable=ingest_sources)
        silver = PythonOperator(task_id="bronze_to_silver", python_callable=bronze_to_silver)
        dq_gate = BranchPythonOperator(task_id="dq_gate", python_callable=run_dq_gate)
        gold = PythonOperator(task_id="build_gold_marts", python_callable=build_gold_marts)
        semantic = PythonOperator(task_id="refresh_semantic_layer",
                                  python_callable=refresh_semantic_layer)
        blocked = PythonOperator(task_id="block_and_alert", python_callable=block_and_alert)
        done = EmptyOperator(task_id="done", trigger_rule="none_failed_min_one_success")

        ingest >> silver >> dq_gate
        dq_gate >> gold >> semantic >> done
        dq_gate >> blocked
