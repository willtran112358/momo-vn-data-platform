"""Fraud feature pipeline with online/offline parity.

A single feature DEFINITION is reused by:
  * the offline backfill (point-in-time, for training)
  * the online path (streaming, for serving)

This kills training/serving skew — the #1 reason a model looks great offline and
fails in production.

Run:  DRY_RUN=1 python samples/ml/feature_pipeline_fraud.py
"""

from __future__ import annotations

import json
import os
from typing import Any

DRY_RUN = os.getenv("DRY_RUN", "1") == "1"


# --- single source of truth for feature logic -----------------------------


def compute_features(txn: dict[str, Any], user_ctx: dict[str, Any]) -> dict[str, Any]:
    """Pure function: same code offline and online (parity guarantee)."""
    avg_30d = max(user_ctx.get("avg_amount_30d", 0), 1)
    return {
        "amount_vnd": txn["amount_vnd"],
        "amount_to_avg_ratio": round(txn["amount_vnd"] / avg_30d, 3),
        "is_new_device": int(user_ctx.get("device_age_days", 999) <= 1),
        "txn_count_1m": user_ctx.get("txn_count_1m", 0),
        "low_kyc": int(user_ctx.get("kyc_tier") in ("NONE", "BASIC")),
    }


# --- offline path: point-in-time backfill ---------------------------------


def offline_backfill(labeled_txns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join features AS OF the transaction time (no future leakage)."""
    out = []
    for row in labeled_txns:
        feats = compute_features(row["txn"], row["user_ctx_as_of"])
        out.append({**feats, "label_is_fraud": row["label_is_fraud"]})
    return out


# --- online path: serving --------------------------------------------------


def online_serve(txn: dict[str, Any], online_store: dict[str, dict[str, Any]]) -> dict[str, Any]:
    user_ctx = online_store.get(txn["user_id"], {})
    return compute_features(txn, user_ctx)


def parity_check(offline_row: dict[str, Any], online_row: dict[str, Any]) -> bool:
    keys = set(offline_row) & set(online_row)
    return all(offline_row[k] == online_row[k] for k in keys)


def sample_training() -> list[dict[str, Any]]:
    return [
        {"txn": {"user_id": "U_002", "amount_vnd": 950000},
         "user_ctx_as_of": {"avg_amount_30d": 90000, "device_age_days": 1,
                            "txn_count_1m": 5, "kyc_tier": "BASIC"},
         "label_is_fraud": 1},
        {"txn": {"user_id": "U_001", "amount_vnd": 200000},
         "user_ctx_as_of": {"avg_amount_30d": 180000, "device_age_days": 420,
                            "txn_count_1m": 1, "kyc_tier": "FULL"},
         "label_is_fraud": 0},
    ]


if __name__ == "__main__":
    train = offline_backfill(sample_training())
    print("[offline] training features:")
    for r in train:
        print("   ", json.dumps(r, ensure_ascii=False))

    online_store = {"U_002": {"avg_amount_30d": 90000, "device_age_days": 1,
                              "txn_count_1m": 5, "kyc_tier": "BASIC"}}
    online_row = online_serve({"user_id": "U_002", "amount_vnd": 950000}, online_store)
    offline_row = {k: v for k, v in train[0].items() if k != "label_is_fraud"}
    print("\n[parity] offline==online:", parity_check(offline_row, online_row))
