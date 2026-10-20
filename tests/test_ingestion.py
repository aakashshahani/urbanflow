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


class _FakeTable:
    def __init__(self):
        self.calls = []

    def append(self, data):
        self.calls.append(("append", data.num_rows, None))

    def overwrite(self, data, overwrite_filter):
        self.calls.append(("overwrite", data.num_rows, overwrite_filter))


class _FakeCatalog:
    def __init__(self):
        self.tables: dict[str, _FakeTable] = {}

    def list_namespaces(self):
        return [("bronze",)]

    def create_namespace(self, ns):
        pass

    def table_exists(self, ident):
        return ident in self.tables

    def create_table(self, ident, schema):
        self.tables[ident] = _FakeTable()
        return self.tables[ident]

    def load_table(self, ident):
        return self.tables[ident]


def test_rerunning_a_month_replaces_instead_of_appending():
    import pyarrow as pa
    from pyiceberg.expressions import EqualTo

    from ingestion.io_utils import write_bronze

    catalog = _FakeCatalog()
    data = pa.table({"x": [1, 2], "_source_month": ["2024-01", "2024-01"]})
    write_bronze("t", data, replace_month="2024-01", catalog=catalog)
    write_bronze("t", data, replace_month="2024-01", catalog=catalog)

    calls = catalog.tables["bronze.t"].calls
    assert calls[0][:2] == ("append", 2)          # first load creates + appends
    assert calls[1][0] == "overwrite"             # re-run replaces that month only
    assert calls[1][2] == EqualTo("_source_month", "2024-01")
