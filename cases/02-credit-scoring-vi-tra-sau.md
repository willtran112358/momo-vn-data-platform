# Case study 02 — Credit scoring for Ví Trả Sau (BNPL)

> How the platform supports a regulated, explainable credit decision without
> leaking the future into the model. Composite, educational scenario.

---

## 1. Problem

**Ví Trả Sau** (Pay Later / BNPL) needs a fast, fair approval decision: should we
extend a credit line, and how much? Two data risks dominate:

1. **Leakage** — using information that wasn't known at application time inflates
   offline accuracy and collapses in production.
2. **Imputed attributes** — treating a missing declared income as `0` (or
   silently filling it) corrupts the model and is a compliance problem.

```mermaid
flowchart LR
    classDef bad fill:#ffebee,stroke:#c62828,color:#b71c1c
    classDef good fill:#e8f5e9,stroke:#388e3c,color:#1b5e20
    L1["null income -> 0"]:::bad --> L2["model thinks<br/>'real low income'"]:::bad
    G1["null income kept null<br/>is_income_imputed=true"]:::good --> G2["flagged for review,<br/>not silently scored"]:::good
```

---

## 2. Point-in-time feature assembly

```mermaid
sequenceDiagram
    autonumber
    participant APP as BNPL application
    participant DIM as dim_user (SCD2)
    participant FCT as repayment history
    participant FS as Feature set
    Note over APP,FS: application_time = T
    APP->>DIM: user attributes valid at T (not now)
    APP->>FCT: repayments where event_ts < T
    DIM->>FS: kyc_tier, declared_income, is_imputed (as of T)
    FCT->>FS: repaid_ratio, tenure, avg_balance (<= T)
    Note over FS: ✅ zero future leakage
```

The SCD2 user dimension ([`dim_user_scd2.sql`](../samples/transform/dim_user_scd2.sql))
makes "the user as they were at T" a simple as-of join.

---

## 3. Features & model

| Feature | Meaning | Note |
|---------|---------|------|
| `tenure_months` | account age | thin-file risk |
| `repaid_ratio` | historical on-time repayment | strongest signal |
| `avg_balance_vnd` | wallet balance trend | liquidity proxy |
| `declared_income_vnd` | user-declared income | nullable |
| `is_income_imputed` | was income missing? | regulated flag |

Training + explainability: [`samples/ml/credit_scoring_train.py`](../samples/ml/credit_scoring_train.py)

---

## 4. Explainable decision

Every decision returns **reason codes** ranked by contribution:

```text
applicant: tenure 4m, repaid 0.45, balance 150k, income missing(imputed)
-> p_repay 0.0  DECLINE
   reasons: [tenure_months:-, declared_income_vnd:-, repaid_ratio:-]
   note: income imputed -> flagged for manual review per credit policy
```

Imputed income never silently drives an approval — it routes to manual review.

---

## 5. Governance & audit

| Control | Implementation |
|---------|----------------|
| Lineage | Every feature traces to source table + `pipeline_run_id` |
| Regulated attribute | `declared_income` + `is_income_imputed` kept separate |
| Reproducibility | `model_version` + feature snapshot stored |
| Auditability | Reason codes logged per decision |
| Fairness review | Periodic distribution checks by segment |

---

## 6. Lifecycle

```mermaid
flowchart LR
    classDef x fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    DATA["Point-in-time features"]:::x --> TRAIN["Train + validate"]:::x
    TRAIN --> BT["Backtest on holdout vintages"]:::x
    BT --> SHIP["Shadow -> canary -> prod"]:::x
    SHIP --> MON["Monitor drift + repayment outcomes"]:::x
    MON --> DATA
```

---

## 7. Role mapping

| Role | Contribution |
|------|--------------|
| Data Engineering | SCD2 dims, feature tables, point-in-time joins |
| Data Science (FS) | Model, calibration, reason codes |
| Manager – Data (FS) | Governance, policy alignment, sign-off |
| Governance | Regulated-attribute lineage & audit |
