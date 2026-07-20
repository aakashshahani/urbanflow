"""Unit tests for the pure ingestion logic (no network, no stack)."""
from __future__ import annotations

import pytest

from ingestion import tlc, weather


def test_tlc_url_shape():
    url = tlc._url("yellow", "2024-01")
    assert url.endswith("/yellow_tripdata_2024-01.parquet")
    assert url.startswith("https://")


def test_unknown_dataset_rejected():
    with pytest.raises(SystemExit):
        tlc.ingest("purple", ["2024-01"])


@pytest.mark.parametrize(
    "month,expected",
    [
        ("2024-01", ("2024-01-01", "2024-01-31")),
        ("2024-02", ("2024-02-01", "2024-02-29")),  # leap year
        ("2023-02", ("2023-02-01", "2023-02-28")),
        ("2024-04", ("2024-04-01", "2024-04-30")),
    ],
)
def test_month_bounds(month, expected):
    assert weather._month_bounds(month) == expected
