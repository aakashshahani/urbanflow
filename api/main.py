"""Metrics API over the gold layer.

Reads mart_zone_hourly_demand through Trino locally or Athena on AWS, selected by
URBANFLOW_TARGET, so the same endpoint serves both backends.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Query

app = FastAPI(title="UrbanFlow Metrics API", version="0.1.0")


def _query(sql: str, params: list | None = None) -> list[dict]:
    import trino

    conn = trino.dbapi.connect(
        host=os.getenv("TRINO_HOST", "localhost"),
        port=int(os.getenv("TRINO_PORT", "8080")),
        user=os.getenv("TRINO_USER", "urbanflow"),
        catalog=os.getenv("TRINO_CATALOG", "iceberg"),
        schema="gold",
    )
    cur = conn.cursor()
    cur.execute(sql, params or [])
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "target": os.getenv("URBANFLOW_TARGET", "local")}


@app.get("/metrics/zone-demand")
def zone_demand(
    zone_id: int = Query(..., description="Pickup zone id"),
    limit: int = Query(24, le=168),
) -> dict:
    rows = _query(
        """
        select pickup_hour, trip_count, revenue, avg_distance,
               temperature_2m, precipitation
        from mart_zone_hourly_demand
        where pickup_zone_id = ?
        order by pickup_hour desc
        limit ?
        """,
        [zone_id, limit],
    )
    return {"zone_id": zone_id, "rows": rows}
