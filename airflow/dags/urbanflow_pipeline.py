"""UrbanFlow daily pipeline: ingest bronze, gate quality, build dbt marts.

Modern Airflow patterns on show: dynamic task mapping over months for backfills,
SLAs, exponential-backoff retries, and a quality gate that fails the run before
dbt writes the gold layer.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.operators.bash import BashOperator

DEFAULT_ARGS = {
    "owner": "urbanflow",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
}
# SLA is set on the final non-mapped task below: Airflow forbids SLAs on the
# dynamically mapped ingest tasks.


@dag(
    dag_id="urbanflow_pipeline",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["urbanflow", "lakehouse"],
    # Which TLC months to load. Trigger with {"months": ["2023-11", "2023-12"]} to
    # backfill; ingestion replaces a month on re-run, so scheduled runs are idempotent.
    params={
        "months": Param(
            os.getenv("TLC_MONTHS", "2024-01").split(),
            type="array",
            items={"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}$"},
        ),
    },
)
def urbanflow_pipeline():
    @task
    def months_to_load(params: dict | None = None) -> list[str]:
        # Dynamic mapping fans out one ingest task per requested month.
        return list((params or {}).get("months") or [])

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
    def quality_gate(months: list[str]) -> None:
        # Fails the DAG before dbt runs if a Great Expectations suite fails.
        # Checks only the months this run loaded.
        from quality.run_checks import run_all

        run_all(months)

    months = months_to_load()
    trips = ingest_trips.expand(month=months)
    weather = ingest_weather.expand(month=months)

    gate = quality_gate(months)

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="cd /opt/airflow/dbt/urbanflow && dbt build --target local",
        sla=timedelta(hours=2),
    )

    [trips, weather] >> gate >> dbt_build


urbanflow_pipeline()
