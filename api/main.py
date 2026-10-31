"""Metrics API over the gold layer.

Reads mart_zone_hourly_demand through Trino locally or Athena on AWS, selected by
URBANFLOW_TARGET, so the same endpoint serves both backends.
"""
from __future__ import annotations

import os
import re

from fastapi import FastAPI, Query

app = FastAPI(title="UrbanFlow Metrics API", version="0.1.0")

_PARAM = re.compile(r":([a-z_]+)\b")


def _target() -> str:
    return os.getenv("URBANFLOW_TARGET", "local").lower()


def _connect():
    """A DB-API connection to the gold schema, plus the driver's paramstyle."""
    if _target() == "aws":
        from pyathena import connect

        conn = connect(
            s3_staging_dir=os.environ["ATHENA_OUTPUT_S3"],
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            work_group=os.getenv("ATHENA_WORKGROUP", "urbanflow"),
            schema_name="gold",
        )
        return conn, "pyformat"

    import trino

    conn = trino.dbapi.connect(
        host=os.getenv("TRINO_HOST", "localhost"),
        port=int(os.getenv("TRINO_PORT", "8080")),
        user=os.getenv("TRINO_USER", "urbanflow"),
        catalog=os.getenv("TRINO_CATALOG", "iceberg"),
        schema="gold",
    )
    return conn, "qmark"


def _query(sql: str, params: dict | None = None) -> list[dict]:
    """Run ``sql`` with ``:name`` placeholders, bound the way the active driver
    expects (Trino: ``?`` positional, PyAthena: ``%(name)s``)."""
    params = params or {}
    conn, style = _connect()
    try:
        cur = conn.cursor()
        if style == "qmark":
            names = _PARAM.findall(sql)
            cur.execute(_PARAM.sub("?", sql), [params[n] for n in names])
        else:
            cur.execute(_PARAM.sub(r"%(\1)s", sql), params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "target": _target()}


@app.get("/metrics/zone-demand")
def zone_demand(
    zone_id: int = Query(..., ge=1, description="Pickup zone id"),
    limit: int = Query(24, ge=1, le=168),
) -> dict:
    rows = _query(
        """
        select pickup_hour, trip_count, revenue, avg_distance,
               temperature_2m, precipitation
        from mart_zone_hourly_demand
        where pickup_zone_id = :zone_id
        order by pickup_hour desc
        limit :limit
        """,
        {"zone_id": zone_id, "limit": limit},
    )
    return {"zone_id": zone_id, "rows": rows}
