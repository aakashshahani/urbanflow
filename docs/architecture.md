# UrbanFlow: Architecture and Decisions

## Goal
A batch lakehouse that closes the resume's data-engineering gap (orchestration, warehouse
modeling, AWS) with defensible, quantified work. It is framed as urban-mobility marketplace
analytics so the dimensional model is genuinely load-bearing rather than decorative.

## Data sources
| Source | Role | Why |
|--------|------|-----|
| NYC TLC trip records (Parquet) | Fact volume anchor (100M+ rows) | Real scale, so partition and file tuning actually matter |
| Open-Meteo historical weather API | Enrichment dimension | Demand versus weather is a real marketplace signal |
| TLC taxi-zone lookup | SCD Type 2 dimension | Zones get renamed and added over time, so Type 2 history is real |

NYC TLC is a common portfolio dataset. UrbanFlow differentiates on execution depth (Iceberg,
quality gates, measured cost tuning, SCD2, backfills), the multi-source marketplace framing, and
the quantified metrics, not on dataset novelty.

## Medallion layers
- **Bronze.** Raw, append-only Iceberg tables written by PyArrow, Hive-partitioned by pickup date.
- **Silver.** dbt: typed, cleaned, deduped, conformed keys, with late or dirty records quarantined.
- **Gold.** dbt: a star schema.
  - `fact_trips`, grain of one trip
  - `dim_date`, `dim_zone` (SCD2), `dim_weather`
  - `mart_zone_hourly_demand`, trips and revenue per zone per hour against weather, the marketplace metric

## Table format: Apache Iceberg, not Delta
The query engine is Athena, whose native ACID table format is Iceberg, with first-class Glue and
Athena support (AWS S3 Tables are Iceberg-based too). Iceberg is also the higher-signal 2026
keyword for the target companies: Netflix created it, and Amazon, Airbnb, and Stripe use it. Delta
solves the same ACID, time-travel, and schema-evolution problem in the Databricks and Azure world,
and a Delta variant is a small follow-up if Microsoft or Databricks becomes the primary target.

Iceberg features the project actually exercises, each an interview talking point:
- Hidden partitioning and partition evolution
- Schema evolution, adding or renaming a column without a rewrite
- Time travel, querying a prior snapshot
- `MERGE INTO` for idempotent upserts and backfills
- Compaction, rewriting small files, measured as a bytes-scanned reduction

## Local and AWS parity
The same Iceberg SQL runs both places, and only the backend swaps.

| | Local (free) | AWS (final deploy) |
|-|--------------|--------------------|
| Object store | MinIO | S3 |
| Catalog | Iceberg REST | Glue Data Catalog |
| Engine | Trino | Athena |
| dbt adapter | `dbt-trino` | `dbt-athena` |

## Cost model, and why local first
Serverless plus tiny data means coffee money, provided the traps are avoided:
- Never MWAA (around $350 a month). Airflow runs locally in docker compose.
- Never Redshift (around $180 a month if left on). Athena is serverless and pay-per-query.
- No VPC or NAT gateway (around $32 a month). S3, Athena, and Glue are API-based, so Terraform provisions none.
- Watch Athena full-table scans ($5 per TB). Partitioning plus a `LIMIT` in development keeps scans in the megabytes.
- Always `terraform destroy` after capturing the demo.

Realistic total for the one-time AWS deploy window is under two dollars: storage in pennies, a few
dozen Athena queries under a dollar, and the Glue catalog in free tier.

## Orchestration (Airflow, modern patterns)
Data-aware scheduling with Datasets, SLAs, exponential-backoff retries, dynamic task mapping over
months, and safe backfills via idempotent `MERGE INTO`. Operators are unit-tested with pytest.

## Data quality (gates, not dashboards)
Great Expectations suites and dbt tests (including dbt unit tests and model contracts) run inside
the DAG and fail it before bad data reaches gold: freshness, row-volume anomaly, schema, null and
uniqueness on keys, and referential integrity on dimension keys.

## Serving
- Metabase dashboards on the gold marts.
- FastAPI `/metrics` over `mart_zone_hourly_demand`, parameterized by zone and date.

## Lineage and docs
OpenLineage events from Airflow and dbt give column-level lineage, alongside a published dbt docs site.
