"""Consume Debezium CDC events from Kafka and land them in bronze, idempotently.

Handles the three Debezium op types (c=create, u=update, d=delete) and applies
last-writer-wins upsert semantics keyed by primary key + source LSN/ts, so
replays and out-of-order delivery do not corrupt bronze.

Run locally:  DRY_RUN=1 python samples/ingestion/cdc_debezium_to_lake.py
"""

from __future__ import annotations

import json
import os
from typing import Any

DRY_RUN = os.getenv("DRY_RUN", "1") == "1"


def sample_cdc_events() -> list[dict[str, Any]]:
    """A few Debezium-shaped envelopes (mocked)."""
    return [
        {"op": "c", "ts_ms": 1750838100000,
         "source": {"table": "wallet_user", "lsn": 1001},
         "after": {"user_id": "U_001", "kyc_tier": "BASIC", "updated_at": "2026-06-25T08:15:00Z"}},
        {"op": "u", "ts_ms": 1750838200000,
         "source": {"table": "wallet_user", "lsn": 1005},
         "after": {"user_id": "U_001", "kyc_tier": "FULL", "updated_at": "2026-06-25T08:16:40Z"}},
        # out-of-order replay of an older state — must be ignored:
        {"op": "u", "ts_ms": 1750838150000,
         "source": {"table": "wallet_user", "lsn": 1003},
         "after": {"user_id": "U_001", "kyc_tier": "BASIC", "updated_at": "2026-06-25T08:15:50Z"}},
        {"op": "d", "ts_ms": 1750838300000,
         "source": {"table": "wallet_user", "lsn": 1010},
         "before": {"user_id": "U_999"}, "after": None},
    ]


def apply_upserts(events: list[dict[str, Any]], pk: str = "user_id") -> dict[str, dict[str, Any]]:
    """Last-writer-wins by source LSN. Tombstones (op=d) remove the key."""
    state: dict[str, dict[str, Any]] = {}
    seen_lsn: dict[str, int] = {}

    for ev in events:
        lsn = ev["source"]["lsn"]
        if ev["op"] == "d":
            key = ev["before"][pk]
            if lsn >= seen_lsn.get(key, -1):
                state.pop(key, None)
                seen_lsn[key] = lsn
                state[key] = {pk: key, "_deleted": True, "_lsn": lsn}
            continue

        row = ev["after"]
        key = row[pk]
        if lsn < seen_lsn.get(key, -1):
            print(f"[cdc] skip out-of-order lsn={lsn} for {key} (have {seen_lsn[key]})")
            continue
        seen_lsn[key] = lsn
        state[key] = {**row, "_lsn": lsn, "_deleted": False}

    return state


def write_bronze_cdc(state: dict[str, dict[str, Any]]) -> None:
    if DRY_RUN:
        print(f"[write] bronze upsert {len(state)} keys:")
        for k, v in state.items():
            print("   ", json.dumps(v, ensure_ascii=False))
        return
    raise NotImplementedError("MERGE into bronze table (Iceberg/Delta/Hudi).")


if __name__ == "__main__":
    events = sample_cdc_events()
    print(f"[cdc] consumed {len(events)} events")
    state = apply_upserts(events)
    write_bronze_cdc(state)
