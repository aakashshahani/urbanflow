"""Ingest historical hourly weather (Open-Meteo, free, no key) into bronze Iceberg.

Enrichment dimension for demand-vs-weather marketplace analytics.

Usage:
    python -m ingestion.weather --months 2024-01
"""
from __future__ import annotations

import argparse
import calendar
import os
import sys

import pyarrow as pa
import requests

from ingestion.io_utils import write_bronze

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = "temperature_2m,precipitation,wind_speed_10m,weather_code"


def _month_bounds(month: str) -> tuple[str, str]:
    year, mon = (int(x) for x in month.split("-"))
    last = calendar.monthrange(year, mon)[1]
    return f"{month}-01", f"{month}-{last:02d}"


def fetch_month(lat: float, lon: float, month: str) -> pa.Table:
    start, end = _month_bounds(month)
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": HOURLY_VARS,
        "timezone": "America/New_York",
    }
    print(f"  fetching weather {month} @ ({lat},{lon})", flush=True)
    resp = requests.get(ARCHIVE_URL, params=params, timeout=60)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]
    table = pa.table(
        {
            "observed_at": pa.array(hourly["time"]),
            "temperature_2m": pa.array(hourly["temperature_2m"], pa.float64()),
            "precipitation": pa.array(hourly["precipitation"], pa.float64()),
            "wind_speed_10m": pa.array(hourly["wind_speed_10m"], pa.float64()),
            "weather_code": pa.array(hourly["weather_code"], pa.int64()),
            "_source_month": pa.array([month] * len(hourly["time"])),
        }
    )
    print(f"    {table.num_rows:,} hourly rows", flush=True)
    return table


def ingest(lat: float, lon: float, months: list[str]) -> None:
    for month in months:
        table = fetch_month(lat, lon, month)
        identifier = write_bronze("weather_hourly", table)
        print(f"  -> appended to {identifier}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest hourly weather into bronze Iceberg")
    parser.add_argument("--lat", type=float, default=float(os.getenv("WEATHER_LAT", "40.7128")))
    parser.add_argument("--lon", type=float, default=float(os.getenv("WEATHER_LON", "-74.0060")))
    parser.add_argument("--months", nargs="+", default=[os.getenv("TLC_MONTHS", "2024-01")])
    args = parser.parse_args(argv)
    ingest(args.lat, args.lon, args.months)
    return 0


if __name__ == "__main__":
    sys.exit(main())
