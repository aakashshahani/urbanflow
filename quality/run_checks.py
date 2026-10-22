"""Run the bronze-layer quality gates. Raises (fails the DAG) on any violation.

Reads the bronze Iceberg trips table, checks it exists and is non-empty, then runs
the Great Expectations suite in quality/expectations/ over the rows. Any failure
raises before dbt builds the gold layer, so a bad load never reaches the marts.

Only the months just loaded are scanned (when given), and only the columns the
suite checks, so the gate's cost stays flat as bronze accumulates history.
"""
from __future__ import annotations

import argparse
import sys

from ingestion.config import BRONZE_NAMESPACE, load_catalog
from quality.expectations.trip_suite import CHECKED_COLUMNS, assert_valid


class QualityError(RuntimeError):
    pass


def run_all(months: list[str] | None = None) -> None:
    catalog = load_catalog()

    trips_id = f"{BRONZE_NAMESPACE}.yellow_trips"
    if not catalog.table_exists(trips_id):
        raise QualityError(f"missing bronze table {trips_id}")

    table = catalog.load_table(trips_id)
    # case_sensitive=False: TLC files spell it "PULocationID"; the suite and the
    # SQL layer use lowercase names.
    scan_kwargs: dict = {
        "selected_fields": (*CHECKED_COLUMNS, "_source_month"),
        "case_sensitive": False,
    }
    if months:
        from pyiceberg.expressions import In

        scan_kwargs["row_filter"] = In("_source_month", months)
    trips = table.scan(**scan_kwargs).to_arrow()

    if trips.num_rows == 0:
        raise QualityError("yellow_trips: zero rows (volume anomaly)")
    if months:
        loaded = set(trips.column("_source_month").unique().to_pylist())
        missing = sorted(set(months) - loaded)
        if missing:
            raise QualityError(f"yellow_trips: no rows for {missing} (volume anomaly)")

    df = trips.to_pandas()
    df.columns = [c.lower() for c in df.columns]
    try:
        assert_valid(df)
    except ValueError as exc:
        raise QualityError(str(exc)) from exc

    scope = ", ".join(months) if months else "all months"
    print(f"quality gate passed: {trips.num_rows:,} bronze trip rows ({scope})", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the bronze quality gate")
    parser.add_argument("--months", nargs="*", help="YYYY-MM months to check (default: all)")
    args = parser.parse_args(argv)
    try:
        run_all(args.months or None)
    except QualityError as exc:
        print(f"QUALITY GATE FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
