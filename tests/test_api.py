"""The metrics API binds parameters correctly for both backends (no database)."""
from __future__ import annotations

import pytest

from api import main


class _Cursor:
    description = [("pickup_hour",), ("trip_count",)]

    def __init__(self, log):
        self.log = log

    def execute(self, sql, params):
        self.log.append((sql, params))

    def fetchall(self):
        return [("2024-01-01 08:00", 12)]


class _Conn:
    def __init__(self, log):
        self.log = log
        self.closed = False

    def cursor(self):
        return _Cursor(self.log)

    def close(self):
        self.closed = True


@pytest.mark.parametrize("style", ["qmark", "pyformat"])
def test_zone_demand_binds_params_per_driver(monkeypatch, style):
    log: list = []
    conn = _Conn(log)
    monkeypatch.setattr(main, "_connect", lambda: (conn, style))

    out = main.zone_demand(zone_id=132, limit=5)

    assert out == {"zone_id": 132, "rows": [{"pickup_hour": "2024-01-01 08:00", "trip_count": 12}]}
    sql, params = log[0]
    if style == "qmark":
        assert "pickup_zone_id = ?" in sql and "limit ?" in sql and params == [132, 5]
    else:
        assert "%(zone_id)s" in sql and "%(limit)s" in sql and params == {"zone_id": 132, "limit": 5}
    assert conn.closed
