# 09 — Product portfolio & the data platform beneath it

> A visual map of MoMo's product surface and the data platform that powers each product.
> Product evolution is paraphrased from public information and a public **Head of Product –
> Financial Services** profile (13+ years across Product Owner → Head of Product). Educational use only.

---

## 1. Product evolution timeline

A decade of product, each wave generating new data needs the platform must serve.

```mermaid
timeline
    title MoMo product evolution (data-generating milestones)
    2013 : Payment platform for loan repayment
         : First referral program
         : Internal MIS (first reporting tool)
    2015 : Payment option for Uber, Facebook Ads
         : Lazada, Apple Store, Google Play
    2018 : Host-to-host with 30+ banks
         : Risk Team — fraud & risk prevention
    2020 : Cash loan in ~1 minute (Vay Nhanh)
         : Pay Later credit line in ~30s (Ví Trả Sau)
         : Túi Thần Tài, mutual fund, gold, online saving
    2022 : Product Development scale-up
    2025 : Head of Product — Financial Services
         : AI Financial Assistant era
```

> **Data reading of this timeline:** the platform's requirements grew from *batch
> reporting (MIS, 2013)* → *integration analytics (2015)* → *real-time risk (2018)*
> → *credit scoring & investment data (2020)* → *AI-first self-serve (2025)*. Each
> wave maps onto a layer in [`docs/03-to-be-architecture.md`](03-to-be-architecture.md).

---

## 2. Product portfolio (super-app surface)

```mermaid
mindmap
  root((MoMo<br/>super-app))
    Payments
      P2P transfer
      QR / in-store
      Bill pay
      Merchant / EDC
    Financial Services
      Vay Nhanh (cash loan ~1 min)
      Ví Trả Sau (Pay Later ~30s)
      Credit card marketplace
      Insurance (auto / moto)
      Túi Thần Tài
      Mutual fund / gold / saving
    Lifestyle
      Movie / bus tickets
      Travel
      Gaming
      Mobile data
      E-commerce
    Loyalty & Growth
      MoMo Xu rewards
      Referral program
      Targeted promotions
    AI layer
      Spending insights
      Personalized suggestions
      Fraud protection
```

---

## 3. Product → data product map

Every product line is backed by a data product on the platform.

```mermaid
flowchart LR
    classDef prod fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#880e4f
    classDef data fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20
    classDef plat fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1

    subgraph PRODUCTS["Products"]
        PAY["Payments / Transfer"]:::prod
        BNPL["Ví Trả Sau"]:::prod
        LOAN["Vay Nhanh"]:::prod
        INV["Túi Thần Tài / Fund"]:::prod
        XU["MoMo Xu / Loyalty"]:::prod
        AI["AI Assistant"]:::prod
    end

    subgraph DATAPROD["Data products"]
        FRAUD["Real-time fraud scoring"]:::data
        CREDIT["Credit scoring (point-in-time)"]:::data
        RECO["Recommendation / personalization"]:::data
        SEG["Segmentation & promo targeting"]:::data
        INVA["Investment behavior analytics"]:::data
    end

    subgraph PLATFORM["Platform foundation"]
        LAKE["Hybrid lakehouse"]:::plat
        SEM["Semantic layer / marts"]:::plat
        FS["Feature store"]:::plat
    end

    PAY --> FRAUD
    BNPL --> CREDIT
    LOAN --> CREDIT
    INV --> INVA
    XU --> SEG
    AI --> RECO

    FRAUD --> FS
    CREDIT --> FS
    RECO --> FS
    SEG --> SEM
    INVA --> SEM
    FS --> LAKE
    SEM --> LAKE
```

---

## 4. The data platform "under" the product (layered view)

```mermaid
flowchart TB
    classDef ux fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#e65100
    classDef app fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#880e4f
    classDef dp fill:#ede7f6,stroke:#5e35b1,stroke-width:2px,color:#311b92
    classDef plat fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20
    classDef found fill:#e0f7fa,stroke:#00838f,stroke-width:2px,color:#006064

    U["User taps a product in the MoMo app"]:::ux
    A["Product services<br/>(payments, FS, loyalty)"]:::app
    D["Decision / intelligence<br/>(fraud, credit, reco, promo)"]:::dp
    F["Feature store + semantic marts"]:::plat
    L["Hybrid lakehouse<br/>(bronze / silver / gold)"]:::plat
    G["Governance · quality · lineage · FinOps"]:::found

    U --> A --> D --> F --> L --> G
    G -.->|"trust + cost control"| L
    L -.->|"governed data"| F
    F -.->|"low-latency features"| D
    D -.->|"decision"| A
    A -.->|"experience"| U
```

Read top-down: a tap becomes a product action, which calls an intelligence layer,
fed by features and marts, materialized from the lakehouse, all governed and cost-tracked.

---

## 5. Product lifecycle ↔ data lifecycle

How a Product Manager's launch loop is mirrored by the platform.

```mermaid
flowchart LR
    classDef p fill:#fce4ec,stroke:#c2185b,color:#880e4f
    classDef d fill:#e8f5e9,stroke:#388e3c,color:#1b5e20

    subgraph PM["Product loop"]
        IDEA["Idea / hypothesis"]:::p
        BUILD["Build feature"]:::p
        LAUNCH["Launch + A/B"]:::p
        LEARN["Learn / iterate"]:::p
    end
    subgraph DATA["Data loop"]
        INSTR["Instrument events"]:::d
        PIPE["Pipelines + marts"]:::d
        METRIC["Governed metrics"]:::d
        INSIGHT["Insight + model retrain"]:::d
    end

    IDEA --> INSTR
    BUILD --> PIPE
    LAUNCH --> METRIC
    LEARN --> INSIGHT
    INSIGHT --> IDEA
```

---

## 6. Example: a Pay Later (Ví Trả Sau) journey end-to-end

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant APP as MoMo app
    participant CR as Credit decisioning
    participant FS as Feature store
    participant LK as Lakehouse
    participant BI as Self-serve BI

    U->>APP: open Ví Trả Sau
    APP->>CR: request credit line
    CR->>FS: point-in-time features (tenure, repaid_ratio, income*)
    FS-->>CR: feature vector
    CR-->>APP: approved limit (~30s) + reason codes
    APP-->>U: credit line ready
    APP->>LK: emit events (offer, approval, usage)
    LK->>BI: governed marts (adoption, NPL, GMV)
    Note over BI: Product & FS leaders monitor the launch on one set of metrics
```

`*income` follows the declared-vs-imputed rule — see
[`cases/02-credit-scoring-vi-tra-sau.md`](../cases/02-credit-scoring-vi-tra-sau.md).

---

## 7. Product KPIs the platform serves (illustrative)

```mermaid
flowchart TB
    classDef k fill:#f3e5f5,stroke:#7b1fa2,color:#4a148c
    GMV["GMV / txn volume"]:::k
    MAU["MAU / active users"]:::k
    ADOPT["FS product adoption"]:::k
    NPL["NPL / repayment rate"]:::k
    RET["Retention / cohort"]:::k
    CAC["Acquisition cost / referral ROI"]:::k

    GMV --- MAU --- ADOPT
    NPL --- RET --- CAC
```

| Product area | Primary KPI | Served by |
|--------------|-------------|-----------|
| Payments | GMV, txn count, active users | `gold.fct_transaction_daily` |
| Ví Trả Sau / Vay Nhanh | approval rate, NPL, utilization | credit marts + feature store |
| Túi Thần Tài | AUM, order count, retention | investment analytics marts |
| MoMo Xu / referral | reward ROI, viral coefficient | growth marts |
| AI Assistant | suggestion CTR, insight engagement | personalization features |

---

## 8. Why this matters to Product leadership

A Head of Product who launched *"cash loan in one minute"* and *"Pay Later approved in
30 seconds"* depends on the platform for three things:

1. **Speed of decision** — sub-second features make a 30-second approval possible.
2. **One source of truth** — Product, FS, and Finance read the same governed KPIs.
3. **Safe iteration** — A/B + point-in-time data let new products ship without
   leakage, fraud blind spots, or metric disputes.

That is the through-line from [`docs/01-business-context.md`](01-business-context.md)
to the [engineering samples](../samples/README.md): **products generate data, the
platform turns it into trustworthy decisions, and those decisions power the next product.**
