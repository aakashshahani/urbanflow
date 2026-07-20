"""Run the bronze-layer quality gates. Raises (fails the DAG) on any violation.

Reads the bronze Iceberg trips table, checks it exists and is non-empty, then runs
the Great Expectations suite in quality/expectations/ over the rows. Any failure
raises before dbt builds the gold layer, so a bad load never reaches the marts.
"""
from __future__ import annotations

import sys

from ingestion.config import BRONZE_NAMESPACE, load_catalog
from quality.expectations.trip_suite import assert_valid


class QualityError(RuntimeError):
    pass


def run_all() -> None:
    catalog = load_catalog()

    trips_id = f"{BRONZE_NAMESPACE}.yellow_trips"
    if not catalog.table_exists(trips_id):
        raise QualityError(f"missing bronze table {trips_id}")

    trips = catalog.load_table(trips_id).scan().to_arrow()
    if trips.num_rows == 0:
        raise QualityError("yellow_trips: zero rows (volume anomaly)")

    try:
        assert_valid(trips.to_pandas())
    except ValueError as exc:
        raise QualityError(str(exc)) from exc

    print(f"quality gate passed: {trips.num_rows:,} bronze trip rows", flush=True)


if __name__ == "__main__":
    try:
        run_all()
    except QualityError as exc:
        print(f"QUALITY GATE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
