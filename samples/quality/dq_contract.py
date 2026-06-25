"""Declarative data-quality contract engine (shift-left gate).

Loads a list of checks, evaluates them against a dataset, and returns a verdict.
CRITICAL failures block the gold publish; WARN failures alert but pass.

This is intentionally dependency-light (works on a list[dict]) so it runs in CI
and locally:  DRY_RUN=1 python samples/quality/dq_contract.py
"""

from __future__ import annotations

import os
import statistics
from dataclasses import dataclass
from typing import Any, Callable

DRY_RUN = os.getenv("DRY_RUN", "1") == "1"

Rows = list[dict[str, Any]]


@dataclass
class Check:
    name: str
    severity: str  # CRITICAL | WARN | INFO
    fn: Callable[[Rows], bool]
    detail: str = ""


# --- reusable check builders ----------------------------------------------


def not_null(col: str) -> Callable[[Rows], bool]:
    return lambda rows: all(r.get(col) is not None for r in rows)


def non_negative(col: str) -> Callable[[Rows], bool]:
    return lambda rows: all((r.get(col) or 0) >= 0 for r in rows)


def unique_grain(*cols: str) -> Callable[[Rows], bool]:
    def _check(rows: Rows) -> bool:
        keys = [tuple(r.get(c) for c in cols) for r in rows]
        return len(keys) == len(set(keys))
    return _check


def null_rate_between(col: str, lo: float, hi: float) -> Callable[[Rows], bool]:
    def _check(rows: Rows) -> bool:
        if not rows:
            return True
        nulls = sum(1 for r in rows if r.get(col) is None)
        rate = nulls / len(rows)
        return lo <= rate <= hi
    return _check


def value_within_stddev(col: str, max_z: float = 4.0) -> Callable[[Rows], bool]:
    def _check(rows: Rows) -> bool:
        vals = [r[col] for r in rows if isinstance(r.get(col), (int, float))]
        if len(vals) < 2:
            return True
        mu, sigma = statistics.mean(vals), statistics.pstdev(vals) or 1
        return all(abs((v - mu) / sigma) <= max_z for v in vals)
    return _check


# --- contract for gold.fct_transaction_daily ------------------------------

CONTRACT: list[Check] = [
    Check("pk_unique", "CRITICAL", unique_grain("dt", "service_code", "kyc_tier")),
    Check("gmv_non_negative", "CRITICAL", non_negative("gmv_vnd")),
    Check("active_users_present", "CRITICAL", not_null("active_users")),
    Check("income_null_rate", "WARN", null_rate_between("declared_income", 0.0, 0.6)),
    Check("ticket_outliers", "WARN", value_within_stddev("avg_ticket_vnd", 4.0)),
]


def evaluate(rows: Rows, contract: list[Check]) -> dict[str, Any]:
    results = []
    blocked = False
    for c in contract:
        ok = c.fn(rows)
        if not ok and c.severity == "CRITICAL":
            blocked = True
        results.append({"check": c.name, "severity": c.severity,
                        "status": "PASS" if ok else "FAIL"})
    return {"publish": not blocked, "results": results}


def sample_gold() -> Rows:
    return [
        {"dt": "2026-06-25", "service_code": "TRANSFER", "kyc_tier": "FULL",
         "gmv_vnd": 1_200_000_000, "active_users": 5300, "avg_ticket_vnd": 226000,
         "declared_income": 20_000_000},
        {"dt": "2026-06-25", "service_code": "BILL", "kyc_tier": "BASIC",
         "gmv_vnd": 340_000_000, "active_users": 2100, "avg_ticket_vnd": 162000,
         "declared_income": None},
        {"dt": "2026-06-25", "service_code": "BNPL", "kyc_tier": "FULL",
         "gmv_vnd": 88_000_000, "active_users": 410, "avg_ticket_vnd": 214000,
         "declared_income": 15_000_000},
    ]


if __name__ == "__main__":
    verdict = evaluate(sample_gold(), CONTRACT)
    for r in verdict["results"]:
        mark = "OK " if r["status"] == "PASS" else "XX "
        print(f"{mark}[{r['severity']:<8}] {r['check']}: {r['status']}")
    print("\nPUBLISH GOLD:" , "YES" if verdict["publish"] else "NO (blocked by CRITICAL)")
    raise SystemExit(0 if verdict["publish"] else 1)
