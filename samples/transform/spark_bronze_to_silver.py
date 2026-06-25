"""Bronze -> Silver conform step (Spark-shaped, with pure-Python fallback).

Responsibilities:
  * type & schema conform
  * dedup by primary key keeping latest by LSN/updated_at
  * validate and QUARANTINE bad records (never silently drop or null->0)
  * preserve declared vs estimated attributes separately

Run:  DRY_RUN=1 python samples/transform/spark_bronze_to_silver.py
"""

from __future__ import annotations

import json
import os
from typing import Any

DRY_RUN = os.getenv("DRY_RUN", "1") == "1"


def sample_bronze() -> list[dict[str, Any]]:
    return [
        {"id": 1, "user_id": "U_001", "amount_vnd": "250000", "status": "SETTLED",
         "declared_income": "20000000", "updated_at": "2026-06-25T08:15:00Z", "_lsn": 5},
        {"id": 1, "user_id": "U_001", "amount_vnd": "250000", "status": "SETTLED",
         "declared_income": "20000000", "updated_at": "2026-06-25T08:14:00Z", "_lsn": 3},  # dup, older
        {"id": 2, "user_id": "U_002", "amount_vnd": "-5000", "status": "SETTLED",
         "declared_income": None, "updated_at": "2026-06-25T08:20:00Z", "_lsn": 7},  # invalid amount
        {"id": 3, "user_id": "U_003", "amount_vnd": "120000", "status": "SETTLED",
         "declared_income": None, "updated_at": "2026-06-25T08:25:00Z", "_lsn": 9},  # null income OK
    ]


def conform_row(r: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Returns (clean_row, None) or (None, quarantine_reason)."""
    try:
        amount = int(r["amount_vnd"])
    except (TypeError, ValueError):
        return None, "AMOUNT_NOT_NUMERIC"
    if amount < 0:
        return None, "AMOUNT_NEGATIVE"

    income_raw = r.get("declared_income")
    # Preserve NULL — do NOT coerce to 0. Track imputation separately.
    declared_income = int(income_raw) if income_raw not in (None, "") else None

    clean = {
        "txn_id": r["id"],
        "user_id": r["user_id"],
        "amount_vnd": amount,
        "status": r["status"],
        "declared_income": declared_income,
        "is_income_imputed": False,
        "updated_at": r["updated_at"],
        "_lsn": r["_lsn"],
    }
    return clean, None


def dedup_latest(rows: list[dict[str, Any]], pk: str = "txn_id") -> list[dict[str, Any]]:
    latest: dict[Any, dict[str, Any]] = {}
    for r in rows:
        cur = latest.get(r[pk])
        if cur is None or r["_lsn"] > cur["_lsn"]:
            latest[r[pk]] = r
    return list(latest.values())


def run() -> dict[str, Any]:
    bronze = sample_bronze()
    clean, quarantine = [], []
    for r in bronze:
        row, reason = conform_row(r)
        if reason:
            quarantine.append({**r, "_quarantine_reason": reason})
        else:
            clean.append(row)

    silver = dedup_latest(clean)

    if DRY_RUN:
        print(f"[silver] {len(silver)} conformed rows:")
        for r in silver:
            print("   ", json.dumps(r, ensure_ascii=False))
        print(f"[quarantine] {len(quarantine)} rejected rows:")
        for r in quarantine:
            print("   ", json.dumps(r, ensure_ascii=False))

    return {"silver": len(silver), "quarantined": len(quarantine)}


def run_spark() -> None:  # pragma: no cover
    # from pyspark.sql import SparkSession, functions as F
    # df = spark.read.format("parquet").load("lake/bronze/...")
    # ... withColumn casts, filter amount>=0 to quarantine path, dropDuplicates ...
    raise NotImplementedError("Translate conform/dedup/quarantine to Spark DataFrame ops.")


if __name__ == "__main__":
    print("[result]", json.dumps(run(), ensure_ascii=False))
