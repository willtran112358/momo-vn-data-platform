"""Watermarked incremental JDBC ingestion into the bronze layer.

Pulls only rows changed since the last successful run (high-watermark on
`updated_at`), writes immutable bronze partitions, and stamps lineage.

Designed to run locally with DRY_RUN=1 (no DB / cluster needed):

    DRY_RUN=1 python samples/ingestion/batch_jdbc_ingest.py
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

DRY_RUN = os.getenv("DRY_RUN", "1") == "1"


@dataclass
class IngestSpec:
    source: str
    table: str
    watermark_col: str = "updated_at"
    primary_key: str = "id"
    cost_tag: dict[str, str] = field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_watermark(spec: IngestSpec) -> str:
    """Last successfully ingested watermark (would be a metadata store)."""
    if DRY_RUN:
        # Pretend the last run stopped at start of day.
        return "2026-06-25T00:00:00+00:00"
    raise NotImplementedError("Wire to platform metadata store (e.g. Postgres).")


def extract_incremental(spec: IngestSpec, since: str) -> list[dict[str, Any]]:
    """SELECT rows where watermark_col > since. Mocked in DRY_RUN."""
    query = (
        f"SELECT * FROM {spec.table} "
        f"WHERE {spec.watermark_col} > '{since}' "
        f"ORDER BY {spec.watermark_col} ASC"
    )
    if DRY_RUN:
        print(f"[extract] would run: {query}")
        return [
            {"id": 1001, "user_id": "U_001", "amount_vnd": 250000,
             "status": "SETTLED", "updated_at": "2026-06-25T08:15:00+00:00"},
            {"id": 1002, "user_id": "U_002", "amount_vnd": -5000,
             "status": "REVERSED", "updated_at": "2026-06-25T08:20:00+00:00"},
        ]
    raise NotImplementedError("Use Spark JDBC / connector here.")


def stamp_lineage(rows: list[dict[str, Any]], run_id: str, source: str) -> list[dict[str, Any]]:
    load_ts = _now()
    for r in rows:
        r["_pipeline_run_id"] = run_id
        r["_source_system"] = source
        r["_load_ts"] = load_ts
    return rows


def write_bronze(rows: list[dict[str, Any]], spec: IngestSpec, run_id: str) -> str:
    dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = f"lake/bronze/{spec.source}/{spec.table}/dt={dt}/part-{run_id}.jsonl"
    if DRY_RUN:
        print(f"[write] would write {len(rows)} rows -> {path}")
        for r in rows:
            print("   ", json.dumps(r, ensure_ascii=False))
        return path
    raise NotImplementedError("Write Parquet to object store with atomic _SUCCESS marker.")


def commit_watermark(spec: IngestSpec, rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    new_wm = max(r[spec.watermark_col] for r in rows)
    if DRY_RUN:
        print(f"[watermark] advance {spec.table} -> {new_wm}")
    return new_wm


def run(spec: IngestSpec) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    since = read_watermark(spec)
    rows = extract_incremental(spec, since)
    rows = stamp_lineage(rows, run_id, spec.source)
    path = write_bronze(rows, spec, run_id)
    new_wm = commit_watermark(spec, rows)
    return {"run_id": run_id, "rows": len(rows), "path": path, "watermark": new_wm}


if __name__ == "__main__":
    spec = IngestSpec(
        source="payment_core",
        table="transactions",
        cost_tag={"team": "platform-data-eng", "project": "bronze-ingestion"},
    )
    result = run(spec)
    print("\n[result]", json.dumps(result, ensure_ascii=False))
