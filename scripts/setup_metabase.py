"""Provision Metabase against the local Trino lakehouse, idempotently.

Waits for Metabase, runs first-time setup (or logs in), registers the Trino database,
syncs the gold schema, then creates the mobility questions and a dashboard. Safe to
re-run: it looks things up by name before creating them.

    python -m scripts.setup_metabase
"""
from __future__ import annotations

import os
import sys
import time

import requests

BASE = os.getenv("METABASE_URL", "http://localhost:3000")
# Local-only defaults; override with env vars rather than editing the script.
ADMIN = {
    "first_name": "Aakash",
    "last_name": "Shahani",
    "email": os.getenv("METABASE_ADMIN_EMAIL", "admin@urbanflow.local"),
}
PASSWORD = os.getenv("METABASE_ADMIN_PASSWORD", "Lakehouse!2026aak")
DB_NAME = "UrbanFlow Lakehouse"


def _json(resp: requests.Response):
    """Body of a successful Metabase response; a clear error instead of a KeyError
    on a failed one."""
    if not resp.ok:
        raise SystemExit(f"Metabase {resp.request.method} {resp.url} -> {resp.status_code}: {resp.text[:300]}")
    return resp.json()

# (name, display, sql, viz_settings). Explicit dimensions/metrics keep charts from
# guessing axes when both columns are numeric.
CARDS = [
    (
        "Top pickup zones by trips",
        "bar",
        "select z.zone_name, sum(m.trip_count) as trips "
        "from gold.mart_zone_hourly_demand m "
        "join gold.dim_zone z on m.pickup_zone_id = z.zone_id and z.is_current "
        "group by z.zone_name order by trips desc limit 10",
        {"graph.dimensions": ["zone_name"], "graph.metrics": ["trips"]},
    ),
    (
        "Trips by hour of day",
        "bar",
        "select hour(pickup_hour) as hour_of_day, sum(trip_count) as trips "
        "from gold.mart_zone_hourly_demand group by 1 order by 1",
        {"graph.dimensions": ["hour_of_day"], "graph.metrics": ["trips"]},
    ),
    (
        "Daily trips vs temperature",
        "line",
        "select cast(pickup_hour as date) as day, sum(trip_count) as trips, "
        "round(avg(temperature_2m), 1) as avg_temp_c "
        "from gold.mart_zone_hourly_demand group by 1 order by 1",
        {"graph.dimensions": ["day"], "graph.metrics": ["trips", "avg_temp_c"]},
    ),
]


def wait_health() -> None:
    for _ in range(30):
        try:
            if requests.get(f"{BASE}/api/health", timeout=5).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(10)
    raise SystemExit("Metabase did not become healthy in time")


def session() -> str:
    props = requests.get(f"{BASE}/api/session/properties", timeout=30).json()
    token = props.get("setup-token")
    if token:
        payload = {
            "token": token,
            "user": {**ADMIN, "password": PASSWORD, "site_name": "UrbanFlow"},
            "prefs": {"site_name": "UrbanFlow", "allow_tracking": False},
        }
        resp = requests.post(f"{BASE}/api/setup", json=payload, timeout=60)
        if resp.status_code == 200:
            return resp.json()["id"]
        # setup already completed (stale token): fall through to a normal login
    login = {"username": ADMIN["email"], "password": PASSWORD}
    return _json(requests.post(f"{BASE}/api/session", json=login, timeout=60))["id"]


def ensure_database(h: dict) -> int:
    dbs = _json(requests.get(f"{BASE}/api/database", headers=h, timeout=30))["data"]
    for db in dbs:
        if db["name"] == DB_NAME:
            return db["id"]
    body = {
        "engine": "starburst",
        "name": DB_NAME,
        "details": {"host": "trino", "port": 8080, "user": "urbanflow", "catalog": "iceberg", "ssl": False},
    }
    return _json(requests.post(f"{BASE}/api/database", json=body, headers=h, timeout=60))["id"]


def wait_gold(h: dict, db_id: int) -> None:
    requests.post(f"{BASE}/api/database/{db_id}/sync_schema", headers=h, timeout=30)
    for _ in range(18):
        time.sleep(10)
        meta = _json(requests.get(f"{BASE}/api/database/{db_id}/metadata", headers=h, timeout=30))
        if sum(1 for t in meta["tables"] if t["schema"] == "gold") >= 4:
            return
    raise SystemExit("gold tables did not sync in time")


def ensure_cards(h: dict, db_id: int) -> list[int]:
    existing = {c["name"]: c["id"] for c in _json(requests.get(f"{BASE}/api/card", headers=h, timeout=30))}
    ids = []
    for name, display, sql, viz in CARDS:
        if name in existing:
            ids.append(existing[name])
            continue
        body = {
            "name": name,
            "display": display,
            "visualization_settings": viz,
            "dataset_query": {"type": "native", "database": db_id, "native": {"query": sql}},
        }
        ids.append(_json(requests.post(f"{BASE}/api/card", json=body, headers=h, timeout=60))["id"])
    return ids


def ensure_dashboard(h: dict, card_ids: list[int]) -> int:
    for d in _json(requests.get(f"{BASE}/api/dashboard", headers=h, timeout=30)):
        if d["name"] == "UrbanFlow Mobility":
            return d["id"]
    dash_id = _json(requests.post(
        f"{BASE}/api/dashboard", json={"name": "UrbanFlow Mobility"}, headers=h, timeout=30
    ))["id"]
    layout = [
        {"id": -1, "card_id": card_ids[0], "row": 0, "col": 0, "size_x": 24, "size_y": 7},
        {"id": -2, "card_id": card_ids[1], "row": 7, "col": 0, "size_x": 12, "size_y": 7},
        {"id": -3, "card_id": card_ids[2], "row": 7, "col": 12, "size_x": 12, "size_y": 7},
    ]
    _json(requests.put(f"{BASE}/api/dashboard/{dash_id}", json={"dashcards": layout}, headers=h, timeout=40))
    return dash_id


def main() -> int:
    wait_health()
    h = {"X-Metabase-Session": session()}
    db_id = ensure_database(h)
    wait_gold(h, db_id)
    dash_id = ensure_dashboard(h, ensure_cards(h, db_id))
    print(f"Metabase ready: {BASE}/dashboard/{dash_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
