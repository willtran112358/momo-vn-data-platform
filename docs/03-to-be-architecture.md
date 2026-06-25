# 03 — To-be architecture: self-serve hybrid data platform

> A next-generation, multi-cloud, self-serve platform aligned to MoMo's published Data Platform mission.

---

## 1. Design principles

| # | Principle | Why it matters at MoMo |
|---|-----------|------------------------|
| 1 | **Self-serve first** | Business/Product/partners answer their own questions via governed marts + semantic layer |
| 2 | **Hybrid multi-cloud** | BigQuery + AWS + on-prem K8s; route by cost, latency, residency |
| 3 | **Medallion lakehouse** | Bronze → Silver → Gold, immutable raw, conformed core, serving marts |
| 4 | **Stream + batch** | Flink for real-time risk; Spark for batch marts; one logical model |
| 5 | **Shift-left quality** | Contracts + gates; bad data never reaches gold |
| 6 | **Lineage everywhere** | `pipeline_run_id` per row; column-level catalog |
| 7 | **FinOps native** | Every job tagged → cost rolls up to team/project/department |
| 8 | **Data as a product** | Datasets owned, documented, SLA'd like software |

---

## 2. Full platform architecture

```mermaid
flowchart TB
    classDef src fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#b71c1c
    classDef ingest fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#e65100
    classDef lake fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20
    classDef proc fill:#ede7f6,stroke:#5e35b1,stroke-width:2px,color:#311b92
    classDef serve fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1
    classDef gov fill:#e0f7fa,stroke:#00838f,stroke-width:2px,color:#006064

    subgraph SRC["Sources"]
        DB["Service DBs<br/>PostgreSQL / MySQL"]:::src
        EV["Event streams<br/>Kafka"]:::src
        EXT["Partner / bank<br/>API · SFTP"]:::src
        APP["App telemetry"]:::src
    end

    subgraph ING["Ingestion — pull + push, batch + stream"]
        CDC["CDC (Debezium)"]:::ingest
        JDBC["Batch JDBC<br/>(watermarked)"]:::ingest
        SINK["Kafka → lake sink"]:::ingest
        WH["Webhook / API<br/>(n8n / service)"]:::ingest
    end

    subgraph LAKE["Hybrid lakehouse"]
        BR["Bronze<br/>raw immutable"]:::lake
        SV["Silver<br/>conformed + typed"]:::lake
        GD["Gold<br/>StarRocks / BigQuery marts"]:::lake
    end

    subgraph PROC["Processing"]
        SPARK["Spark<br/>(batch ETL)"]:::proc
        FLINK["Flink<br/>(stream)"]:::proc
        DBT["dbt / semantic"]:::proc
    end

    subgraph GOV["Governance & ops"]
        DQ["DQ gates + contracts"]:::gov
        CAT["Catalog + lineage"]:::gov
        COST["Cost metering"]:::gov
    end

    subgraph SERVE["Self-serve consumption"]
        BI["Superset / Looker /<br/>Data Studio"]:::serve
        FEAT["Feature store<br/>online + offline"]:::serve
        API["Data APIs /<br/>datasets / streams"]:::serve
        ML["ML training / scoring"]:::serve
    end

    DB --> CDC --> BR
    DB --> JDBC --> BR
    EV --> SINK --> BR
    EXT --> WH --> BR
    APP --> SINK

    BR --> SPARK --> SV
    EV --> FLINK
    SV --> DBT --> GD
    SV --> DQ
    DQ -->|pass| GD

    GD --> BI
    GD --> FEAT --> ML
    GD --> API
    FLINK --> FEAT

    CAT -.-> BR
    CAT -.-> SV
    CAT -.-> GD
    COST -.-> SPARK
    COST -.-> FLINK
    COST -.-> GD
```

---

## 3. Ingestion matrix

| Source type | Mechanism | Mode | Tool | Sample |
|-------------|-----------|------|------|--------|
| OLTP service DBs | CDC | Stream (push) | Debezium → Kafka | [`cdc_debezium_to_lake.py`](../samples/ingestion/cdc_debezium_to_lake.py) |
| Reference / dimension tables | JDBC | Batch (pull) | Spark JDBC | [`batch_jdbc_ingest.py`](../samples/ingestion/batch_jdbc_ingest.py) |
| Product events | Topic sink | Stream | Kafka Connect / Flink | [`flink_txn_enrichment.py`](../samples/streaming/flink_txn_enrichment.py) |
| Partner / bank | API / SFTP | Batch + webhook | n8n / service | `docs/04` |

---

## 4. Storage & engine choices

```mermaid
flowchart LR
    classDef a fill:#e8f5e9,stroke:#388e3c,color:#1b5e20
    classDef b fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    classDef c fill:#fff3e0,stroke:#ef6c00,color:#e65100

    LAKE["Object store<br/>(lake: bronze/silver)"]:::a
    SR["StarRocks<br/>(fast OLAP marts)"]:::b
    BQ["BigQuery<br/>(elastic warehouse)"]:::b
    CH["ClickHouse<br/>(event analytics)"]:::b
    DD["DuckDB<br/>(local / embedded)"]:::c

    LAKE --> SR
    LAKE --> BQ
    LAKE --> CH
    LAKE --> DD
```

| Engine | Sweet spot |
|--------|-----------|
| **Object store + Spark** | Cheap, immutable bronze/silver; heavy batch transforms |
| **StarRocks** | Sub-second self-serve marts, high-concurrency BI |
| **BigQuery** | Elastic, serverless warehouse; ML-adjacent SQL |
| **ClickHouse** | High-cardinality event/funnel analytics |
| **DuckDB** | Local dev, unit tests, lightweight extracts |

---

## 5. Medallion contract

```mermaid
flowchart LR
    classDef bronze fill:#d7ccc8,stroke:#5d4037,color:#3e2723
    classDef silver fill:#b0bec5,stroke:#37474f,color:#263238
    classDef gold fill:#ffd54f,stroke:#f57f17,color:#e65100

    B["Bronze<br/>raw, append-only,<br/>schema-on-read"]:::bronze
    S["Silver<br/>typed, deduped,<br/>SCD2 dims"]:::silver
    G["Gold<br/>marts + metrics,<br/>self-serve"]:::gold

    B -->|"Spark conform + quarantine"| S
    S -->|"dbt + DQ gate"| G
```

| Layer | Guarantees | Owner |
|-------|------------|-------|
| Bronze | Exactly what arrived, immutable, lineage stamped | Data Engineering |
| Silver | Conformed types, dedup, SCD2, PII tagged | Data Engineering |
| Gold | Business metrics, documented, SLA'd | Analytics Engineering |

---

## 6. Self-serve & semantic layer

```mermaid
flowchart TB
    classDef s fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    GOLD["Gold marts"]:::s
    SEM["Semantic layer<br/>(one definition per metric)"]:::s
    BI["BI tools"]:::s
    NB["Notebooks / SQL"]:::s
    PART["Partner data APIs"]:::s
    GOLD --> SEM
    SEM --> BI
    SEM --> NB
    SEM --> PART
```

One governed definition of `active_user`, `gmv`, `npl_rate` consumed identically by every tool — killing the "five definitions" problem from [`01-business-context.md`](01-business-context.md).

---

## 7. As-is → to-be summary

| Dimension | As-is | To-be |
|-----------|-------|-------|
| Ingestion | Per-team cron | Shared CDC + batch + stream |
| Storage | Team marts | Medallion lakehouse |
| Quality | After BI | Shift-left contracts + gates |
| Metrics | 5 definitions | 1 semantic layer |
| Fraud | Batch T+1 | Real-time Flink lane |
| Cost | Monthly surprise | Per-job FinOps tags |
| Lineage | Tribal knowledge | Column-level catalog |
| Access | DE tickets | Self-serve marts + APIs |
