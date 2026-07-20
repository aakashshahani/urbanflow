"""UrbanFlow daily pipeline: ingest bronze, gate quality, build dbt marts.

Modern Airflow patterns on show: dynamic task mapping over months for backfills,
SLAs, exponential-backoff retries, and a quality gate that fails the run before
dbt writes the gold layer.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

DEFAULT_ARGS = {
    "owner": "urbanflow",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "sla": timedelta(hours=2),
}


@dag(
    dag_id="urbanflow_pipeline",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["urbanflow", "lakehouse"],
)
def urbanflow_pipeline():
    @task
    def months_to_load() -> list[str]:
        # In a backfill this expands; dynamic mapping fans out one task per month.
        return ["2024-01"]

    @task
    def ingest_trips(month: str) -> str:
        from ingestion.tlc import ingest

        ingest("yellow", [month])
        return month

    @task
    def ingest_weather(month: str) -> str:
        from ingestion.weather import ingest

        ingest(40.7128, -74.0060, [month])
        return month

    @task
    def quality_gate() -> None:
        # Fails the DAG before dbt runs if a Great Expectations suite fails.
        from quality.run_checks import run_all

        run_all()

    months = months_to_load()
    trips = ingest_trips.expand(month=months)
    weather = ingest_weather.expand(month=months)

    gate = quality_gate()

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="cd /opt/airflow/dbt/urbanflow && dbt build --target local",
    )

    [trips, weather] >> gate >> dbt_build


urbanflow_pipeline()
