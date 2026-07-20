"""Run the bronze-layer quality gates. Raises (fails the DAG) on any violation.

Kept dependency-light for now: reads the bronze Iceberg tables and asserts the
invariants that must hold before dbt builds gold. The Great Expectations suites in
quality/expectations/ layer on top of these as the schema stabilizes.
"""
from __future__ import annotations

import sys

from ingestion.config import BRONZE_NAMESPACE, load_catalog


class QualityError(RuntimeError):
    pass


def run_all() -> None:
    catalog = load_catalog()
    failures: list[str] = []

    trips_id = f"{BRONZE_NAMESPACE}.yellow_trips"
    if not catalog.table_exists(trips_id):
        raise QualityError(f"missing bronze table {trips_id}")

    trips = catalog.load_table(trips_id).scan().to_arrow()
    if trips.num_rows == 0:
        failures.append("yellow_trips: zero rows (volume anomaly)")

    total = trips.column("total_amount").to_pylist() if "total_amount" in trips.column_names else []
    if total and min(total) < 0:
        failures.append("yellow_trips: negative total_amount leaked past ingestion")

    if failures:
        raise QualityError("; ".join(failures))
    print(f"quality gate passed: {trips.num_rows:,} bronze trip rows", flush=True)


if __name__ == "__main__":
    try:
        run_all()
    except QualityError as exc:
        print(f"QUALITY GATE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
