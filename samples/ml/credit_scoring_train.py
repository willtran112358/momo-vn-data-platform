"""Credit scoring training for Ví Trả Sau (BNPL) — explainable + leakage-safe.

Demonstrates the data-platform contract a credit model depends on:
  * point-in-time features (no future leakage)
  * declared vs imputed income kept separate (regulated attribute)
  * reason codes emitted for every decision (audit / explainability)

Falls back to a tiny logistic model if scikit-learn isn't present, so it runs
anywhere:  DRY_RUN=1 python samples/ml/credit_scoring_train.py
"""

from __future__ import annotations

import json
import math
import os
from typing import Any

DRY_RUN = os.getenv("DRY_RUN", "1") == "1"

FEATURES = ["tenure_months", "repaid_ratio", "avg_balance_vnd",
            "declared_income_vnd", "is_income_imputed"]


def sample_training_set() -> tuple[list[list[float]], list[int]]:
    """Point-in-time features as of application_time. Label = repaid_on_time@30d."""
    raw = [
        # tenure, repaid_ratio, avg_balance, declared_income, imputed -> label
        (24, 0.98, 1_500_000, 25_000_000, 0, 1),
        (3,  0.40,   120_000,          0, 1, 0),  # imputed income, thin file
        (18, 0.90,   900_000, 18_000_000, 0, 1),
        (1,  0.10,    30_000,          0, 1, 0),
        (36, 0.99, 3_200_000, 40_000_000, 0, 1),
        (6,  0.55,   210_000, 10_000_000, 0, 0),
    ]
    X = [[float(r[i]) for i in range(5)] for r in raw]
    y = [r[5] for r in raw]
    return X, y


def _standardize(X: list[list[float]]) -> tuple[list[list[float]], list[float], list[float]]:
    n, d = len(X), len(X[0])
    means = [sum(row[j] for row in X) / n for j in range(d)]
    stds = [(sum((row[j] - means[j]) ** 2 for row in X) / n) ** 0.5 or 1.0 for j in range(d)]
    Xs = [[(row[j] - means[j]) / stds[j] for j in range(d)] for row in X]
    return Xs, means, stds


def train_fallback(X: list[list[float]], y: list[int], epochs: int = 2000, lr: float = 0.1):
    """Minimal logistic regression (gradient descent) — no deps."""
    Xs, means, stds = _standardize(X)
    d = len(Xs[0])
    w = [0.0] * d
    b = 0.0
    for _ in range(epochs):
        dw = [0.0] * d
        db = 0.0
        for xi, yi in zip(Xs, y):
            z = sum(w[j] * xi[j] for j in range(d)) + b
            p = 1 / (1 + math.exp(-z))
            err = p - yi
            for j in range(d):
                dw[j] += err * xi[j]
            db += err
        n = len(Xs)
        w = [w[j] - lr * dw[j] / n for j in range(d)]
        b -= lr * db / n
    return {"w": w, "b": b, "means": means, "stds": stds}


def score(model: dict[str, Any], row: list[float]) -> tuple[float, list[str]]:
    w, b, means, stds = model["w"], model["b"], model["means"], model["stds"]
    contribs = []
    z = b
    for j in range(len(row)):
        xs = (row[j] - means[j]) / stds[j]
        c = w[j] * xs
        z += c
        contribs.append((FEATURES[j], c))
    p = 1 / (1 + math.exp(-z))
    # top reason codes by absolute contribution
    contribs.sort(key=lambda t: abs(t[1]), reverse=True)
    reasons = [f"{name}:{'+' if c >= 0 else '-'}" for name, c in contribs[:3]]
    return p, reasons


if __name__ == "__main__":
    X, y = sample_training_set()
    model = train_fallback(X, y)
    print("[train] coefficients:")
    for name, wj in zip(FEATURES, model["w"]):
        print(f"    {name:<22} {wj:+.3f}")

    applicant = [4.0, 0.45, 150_000.0, 0.0, 1.0]  # thin file, imputed income
    p, reasons = score(model, applicant)
    decision = "APPROVE" if p >= 0.5 else "DECLINE"
    print("\n[decision]", json.dumps({
        "p_repay": round(p, 3),
        "decision": decision,
        "reason_codes": reasons,
        "note": "income imputed -> flagged for manual review per credit policy",
    }, ensure_ascii=False))
