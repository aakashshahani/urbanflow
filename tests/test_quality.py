"""The bronze trip suite must pass clean data and fail dirty data."""
from __future__ import annotations

import pandas as pd
import pytest

from quality.expectations.trip_suite import assert_valid, validate_df

CLEAN = pd.DataFrame(
    {
        "tpep_pickup_datetime": ["2024-01-01 00:00:00", "2024-01-01 01:00:00"],
        "pulocationid": [100, 132],
        "total_amount": [18.5, 42.0],
        "trip_distance": [3.1, 9.4],
        "passenger_count": [1, 2],
    }
)

DIRTY = pd.DataFrame(
    {
        "tpep_pickup_datetime": ["2024-01-01 00:00:00", None],   # missing key
        "pulocationid": [100, 132],
        "total_amount": [18.5, 42.0],
        "trip_distance": [3.1, 5000.0],   # corrupt distance, past sanity bound
        "passenger_count": [1, 99],       # corrupt count, past sanity bound
    }
)


def test_clean_data_passes():
    assert validate_df(CLEAN).success is True


def test_dirty_data_fails():
    assert validate_df(DIRTY).success is False


def test_assert_valid_raises_on_dirty():
    with pytest.raises(ValueError):
        assert_valid(DIRTY)


class _Scan:
    def __init__(self, table):
        self._table = table

    def to_arrow(self):
        return self._table


class _Table:
    def __init__(self, arrow):
        self.arrow = arrow
        self.scan_kwargs = None

    def scan(self, **kwargs):
        self.scan_kwargs = kwargs
        return _Scan(self.arrow)


class _Catalog:
    def __init__(self, table):
        self.table = table

    def table_exists(self, ident):
        return True

    def load_table(self, ident):
        return self.table


def _bronze(months):
    import pyarrow as pa

    n = len(months)
    return pa.table({
        "tpep_pickup_datetime": ["2024-01-01 00:00:00"] * n,
        "PULocationID": [100] * n,   # TLC's own casing
        "total_amount": [18.5] * n,
        "trip_distance": [3.1] * n,
        "passenger_count": [1] * n,
        "_source_month": months,
    })


def test_gate_scans_only_requested_months_case_insensitively(monkeypatch):
    from quality import run_checks

    table = _Table(_bronze(["2024-01", "2024-01"]))
    monkeypatch.setattr(run_checks, "load_catalog", lambda: _Catalog(table))
    run_checks.run_all(["2024-01"])
    assert table.scan_kwargs["case_sensitive"] is False
    assert "row_filter" in table.scan_kwargs


def test_gate_fails_when_a_requested_month_is_missing(monkeypatch):
    from quality import run_checks

    table = _Table(_bronze(["2024-01"]))
    monkeypatch.setattr(run_checks, "load_catalog", lambda: _Catalog(table))
    with pytest.raises(run_checks.QualityError, match="2024-02"):
        run_checks.run_all(["2024-01", "2024-02"])
