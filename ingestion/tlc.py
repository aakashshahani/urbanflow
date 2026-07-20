"""Ingest NYC TLC trip records (public Parquet) into bronze Iceberg.

Usage:
    python -m ingestion.tlc --months 2024-01 2024-02 --dataset yellow
"""
from __future__ import annotations

import argparse
import io
import os
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import requests

from ingestion.io_utils import write_bronze

TLC_BASE = "https://d37ci6vzurychx.cloudfront.net/trip-data"
DATASETS = {"yellow", "green", "fhvhv"}


def _url(dataset: str, month: str) -> str:
    return f"{TLC_BASE}/{dataset}_tripdata_{month}.parquet"


def fetch_month(dataset: str, month: str) -> pa.Table:
    """Download one month of trip data as a PyArrow table."""
    url = _url(dataset, month)
    print(f"  fetching {url}", flush=True)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    table = pq.read_table(io.BytesIO(resp.content))
    # Stamp lineage columns so bronze rows are traceable to their source partition.
    n = table.num_rows
    table = table.append_column("_source_dataset", pa.array([dataset] * n))
    table = table.append_column("_source_month", pa.array([month] * n))
    print(f"    {n:,} rows", flush=True)
    return table


def ingest(dataset: str, months: list[str]) -> None:
    if dataset not in DATASETS:
        raise SystemExit(f"unknown dataset {dataset!r}; choose from {sorted(DATASETS)}")
    for month in months:
        table = fetch_month(dataset, month)
        identifier = write_bronze(f"{dataset}_trips", table)
        print(f"  -> appended to {identifier}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest NYC TLC trips into bronze Iceberg")
    parser.add_argument("--dataset", default=os.getenv("TLC_DATASET", "yellow"))
    parser.add_argument(
        "--months",
        nargs="+",
        default=[os.getenv("TLC_MONTHS", "2024-01")],
        help="one or more YYYY-MM values",
    )
    args = parser.parse_args(argv)
    ingest(args.dataset, args.months)
    return 0


if __name__ == "__main__":
    sys.exit(main())
