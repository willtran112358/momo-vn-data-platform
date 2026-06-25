# 05 — ML & AI data products

> How the platform feeds MoMo's ML products: recommendation, personalization, risk/fraud,
> credit scoring, targeted promotions, and financial services.

---

## 1. From data platform to ML products

```mermaid
flowchart LR
    classDef data fill:#e8f5e9,stroke:#388e3c,color:#1b5e20
    classDef feat fill:#fff3e0,stroke:#ef6c00,color:#e65100
    classDef model fill:#ede7f6,stroke:#5e35b1,color:#311b92
    classDef serve fill:#e3f2fd,stroke:#1565c0,color:#0d47a1

    GOLD["Gold marts + streams"]:::data
    OFF["Offline feature store<br/>(BigQuery / Spark)"]:::feat
    ON["Online feature store<br/>(low-latency)"]:::feat

    FRAUD["Fraud scoring"]:::model
    CREDIT["Credit scoring"]:::model
    RECO["Recommendation"]:::model
    PROMO["Promo targeting"]:::model

    APP["MoMo app / APIs"]:::serve
    AB["A/B + experiment insights"]:::serve

    GOLD --> OFF & ON
    OFF --> FRAUD & CREDIT & RECO & PROMO
    ON --> FRAUD & RECO
    FRAUD & CREDIT & RECO & PROMO --> APP --> AB --> GOLD
```

---

## 2. Online / offline feature parity

The #1 cause of "great offline, bad online" models is **training/serving skew**. The platform enforces a single feature definition used in both paths.

```mermaid
flowchart TB
    classDef d fill:#fff3e0,stroke:#ef6c00,color:#e65100
    DEF["Feature definition<br/>(single source)"]:::d
    OFFP["Offline: batch backfill<br/>(point-in-time correct)"]:::d
    ONP["Online: streaming update<br/>(<10ms read)"]:::d
    DEF --> OFFP
    DEF --> ONP
    OFFP -->|train| MODEL["Model"]
    ONP -->|serve| MODEL
```

See [`samples/ml/feature_pipeline_fraud.py`](../samples/ml/feature_pipeline_fraud.py).

---

## 3. ML data-product catalog

| Product | Decision | Latency | Key features | Governance note |
|---------|----------|---------|--------------|-----------------|
| **Real-time fraud** | allow / step-up / block | < 100 ms | velocity, device, amount-vs-history | Audit every block reason |
| **Credit scoring (Ví Trả Sau)** | approve / limit | seconds | repayment history, tenure, income (declared) | Explainable; `is_imputed` tracked |
| **Quick loan (Vay Nhanh)** | approve / price | seconds | same + behavioral | Regulated; lineage required |
| **Recommendation** | which service next | < 200 ms | recent activity, segment | A/B gated |
| **Promo targeting (MoMo Xu)** | who/what/when | minutes | propensity, budget cap | Budget guardrails |

---

## 4. Point-in-time correctness (no leakage)

```mermaid
sequenceDiagram
    autonumber
    participant E as Event log
    participant FS as Feature store
    participant T as Training set
    Note over E,T: Label = repaid on time at day 30
    E->>FS: features AS OF application_time
    FS->>T: join features (no future data)
    Note over T: ✅ uses only data available at decision time
```

A credit model must only see what was knowable **at application time**. The platform's SCD2 dims + as-of joins guarantee this. See [`samples/ml/credit_scoring_train.py`](../samples/ml/credit_scoring_train.py).

---

## 5. Experimentation loop

```mermaid
flowchart LR
    classDef x fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    H["Hypothesis"]:::x --> EXP["A/B assignment<br/>(gold-logged)"]:::x
    EXP --> METRIC["Metric pipeline<br/>(semantic layer)"]:::x
    METRIC --> READ["Readout + stat test"]:::x
    READ --> SHIP["Ship / rollback"]:::x
    SHIP --> H
```

Assignment and exposure events flow into gold, so every experiment uses the **same governed metrics** as the rest of the business — no bespoke math per test.

---

## 6. MLOps guardrails

| Concern | Platform control |
|---------|------------------|
| Training/serving skew | Shared feature definitions, parity tests |
| Data leakage | As-of joins on SCD2 dims |
| Model drift | Monitor feature & score distributions |
| Reproducibility | `model_version` + feature snapshot lineage |
| Fairness / audit | Reason codes logged for credit & fraud decisions |
