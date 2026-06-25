"""Real-time transaction enrichment + fraud scoring (PyFlink-shaped).

Reads transactions from Kafka, joins low-latency user/device features from an
online store, computes velocity features in a keyed window, calls the fraud
model, and emits a scored decision back to Kafka (and to the lake for audit).

This file is structured like a real PyFlink job but falls back to a pure-Python
simulation when Flink isn't installed, so it runs anywhere:

    DRY_RUN=1 python samples/streaming/flink_txn_enrichment.py
"""

from __future__ import annotations

import json
import os
from collections import defaultdict, deque
from typing import Any

DRY_RUN = os.getenv("DRY_RUN", "1") == "1"

# --- Feature + model stubs (shared with offline path for parity) ----------


def fetch_online_features(user_id: str) -> dict[str, Any]:
    """Low-latency read (<10ms target) from online feature store. Mocked."""
    store = {
        "U_001": {"avg_amount_30d": 180000, "device_age_days": 420, "kyc_tier": "FULL"},
        "U_002": {"avg_amount_30d": 90000, "device_age_days": 1, "kyc_tier": "BASIC"},
    }
    return store.get(user_id, {"avg_amount_30d": 0, "device_age_days": 0, "kyc_tier": "NONE"})


def fraud_score(features: dict[str, Any]) -> tuple[float, list[str]]:
    """Tiny rule-blended score in [0,1] with reason codes (explainability)."""
    score, reasons = 0.0, []
    if features["amount_vnd"] > 5 * max(features["avg_amount_30d"], 1):
        score += 0.5
        reasons.append("AMOUNT_5X_HISTORY")
    if features["device_age_days"] <= 1:
        score += 0.3
        reasons.append("NEW_DEVICE")
    if features["txn_count_1m"] >= 5:
        score += 0.3
        reasons.append("HIGH_VELOCITY_1M")
    if features["kyc_tier"] in ("NONE", "BASIC"):
        score += 0.1
        reasons.append("LOW_KYC")
    return min(score, 1.0), reasons


def decide(score: float) -> str:
    if score >= 0.8:
        return "BLOCK"
    if score >= 0.5:
        return "STEP_UP"
    return "ALLOW"


# --- Stateful velocity (keyed by user) -------------------------------------


class VelocityState:
    """1-minute sliding count per user (Flink keyed state in production)."""

    def __init__(self, window_ms: int = 60_000):
        self.window_ms = window_ms
        self._events: dict[str, deque[int]] = defaultdict(deque)

    def add_and_count(self, user_id: str, ts_ms: int) -> int:
        dq = self._events[user_id]
        dq.append(ts_ms)
        while dq and ts_ms - dq[0] > self.window_ms:
            dq.popleft()
        return len(dq)


def enrich_and_score(txn: dict[str, Any], velocity: VelocityState) -> dict[str, Any]:
    feats = fetch_online_features(txn["user_id"])
    feats["amount_vnd"] = txn["amount_vnd"]
    feats["txn_count_1m"] = velocity.add_and_count(txn["user_id"], txn["ts_ms"])
    score, reasons = fraud_score(feats)
    return {
        "txn_id": txn["txn_id"],
        "user_id": txn["user_id"],
        "amount_vnd": txn["amount_vnd"],
        "fraud_score": round(score, 3),
        "decision": decide(score),
        "reasons": reasons,
    }


def sample_stream() -> list[dict[str, Any]]:
    return [
        {"txn_id": "T1", "user_id": "U_001", "amount_vnd": 200000, "ts_ms": 1750838100000},
        {"txn_id": "T2", "user_id": "U_002", "amount_vnd": 900000, "ts_ms": 1750838100500},
        {"txn_id": "T3", "user_id": "U_002", "amount_vnd": 950000, "ts_ms": 1750838101000},
        {"txn_id": "T4", "user_id": "U_002", "amount_vnd": 980000, "ts_ms": 1750838101500},
        {"txn_id": "T5", "user_id": "U_002", "amount_vnd": 990000, "ts_ms": 1750838102000},
        {"txn_id": "T6", "user_id": "U_002", "amount_vnd": 999000, "ts_ms": 1750838102500},
    ]


def run_simulation() -> None:
    velocity = VelocityState()
    for txn in sample_stream():
        out = enrich_and_score(txn, velocity)
        print(json.dumps(out, ensure_ascii=False))


def run_flink() -> None:  # pragma: no cover - requires a Flink cluster
    from pyflink.datastream import StreamExecutionEnvironment
    from pyflink.datastream.connectors.kafka import KafkaSource

    env = StreamExecutionEnvironment.get_execution_environment()
    # source = KafkaSource.builder()... .build()
    # env.from_source(...).key_by(lambda r: r["user_id"]).map(enrich_and_score)...
    raise NotImplementedError("Wire KafkaSource/Sink + keyed process function here.")


if __name__ == "__main__":
    print("[flink] real-time enrichment + fraud scoring")
    if DRY_RUN:
        run_simulation()
    else:
        run_flink()
