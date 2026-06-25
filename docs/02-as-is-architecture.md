# 02 — As-is architecture (pre-platform)

> The state a fast-growing fintech typically reaches before investing in a real data platform.

---

## 1. As-is landscape

```mermaid
flowchart TB
    classDef source fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#b71c1c
    classDef etl fill:#fff8e1,stroke:#f9a825,stroke-width:2px,color:#f57f17
    classDef store fill:#eceff1,stroke:#546e7a,stroke-width:2px,color:#263238
    classDef bi fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c

    subgraph SRC["Sources"]
        APPDB["Service DBs<br/>(MySQL/PostgreSQL)"]:::source
        KAFKA["Kafka (raw topics)"]:::source
        PART["Partner / bank files"]:::source
    end

    subgraph ETL["Ad-hoc movement"]
        CRON["Per-team cron scripts"]:::etl
        DUMP["Nightly DB dumps"]:::etl
        NB["Analyst notebooks"]:::etl
    end

    subgraph STORE["Team-owned stores"]
        RISK["Risk DB"]:::store
        GROWTH["Growth mart"]:::store
        FS["FS mart"]:::store
    end

    subgraph BI["Consumption"]
        DASH["Scattered dashboards"]:::bi
        XLS["Spreadsheets"]:::bi
    end

    APPDB --> DUMP --> RISK
    APPDB --> CRON --> GROWTH
    KAFKA --> CRON
    PART --> CRON --> FS
    NB --> RISK
    NB --> GROWTH
    RISK --> DASH
    GROWTH --> DASH
    FS --> XLS
```

---

## 2. What breaks at scale

| Symptom | Root cause | Downstream damage |
|---------|------------|-------------------|
| Duplicate ingestion of the same source | No shared bronze layer | 3× cost, drift between copies |
| Conflicting metrics | No semantic layer | Distrust in dashboards |
| Late dashboards | Brittle cron, no SLA | Missed campaigns, blind risk |
| No fraud streaming | Batch-only | Fraud detected post-settlement |
| Bad data in BI | DQ checked *after* publish | Wrong exec decisions |
| Bill shock | No cost tags | No accountability |
| Point-in-time leakage | Features pulled "as of now" | Over-optimistic credit models |

---

## 3. Anti-pattern spotlight — `NULL → 0` on income

```sql
-- as-is: optional income field silently coerced
SELECT user_id,
       COALESCE(declared_income, 0) AS income   -- ❌ pollutes credit features
FROM   raw_kyc;
```

A user who didn't declare income becomes a "0 income" user — which then feeds the credit model as if it were a real low-income signal. The to-be design keeps `declared_income` nullable and tracks `is_imputed` separately.

---

## 4. As-is data flow (the late-DQ trap)

```mermaid
flowchart LR
    classDef bad fill:#ffebee,stroke:#c62828,color:#b71c1c
    S["Source<br/>(optional field)"]:::bad --> E["ETL<br/>(null→0)"]:::bad --> M["Mart<br/>(accepted)"]:::bad --> B["BI<br/>(wrong segment)"]:::bad
    B -.->|"found weeks later"| S
```

No gate exists between source and mart, so quality issues surface only when a human notices a weird dashboard — often weeks later.

---

## 5. Why "just add more cron" fails

- Each new source multiplies maintenance, not capability.
- No lineage → every incident is a manual archaeology dig.
- No contracts → every schema change silently breaks downstream.
- No cost attribution → optimization has no owner.

This motivates the [to-be platform](03-to-be-architecture.md).
