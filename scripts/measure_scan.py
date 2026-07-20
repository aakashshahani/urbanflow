"""Benchmark bytes scanned for the same query before and after optimization.

Runs a representative gold query and reports bytes scanned, the number that drives
Athena cost. Run it once on the unpartitioned bronze table and again after
partitioning plus Iceberg compaction to get the resume metric (the reduction).

On Trino the figure comes from the query's completed-stats; on Athena it comes from
DataScannedInBytes. The delta between the two runs is the headline.
"""
from __future__ import annotations

import os

QUERY = """
select pickup_zone_id, count(*) as trips, sum(total_amount) as revenue
from iceberg.gold.mart_zone_hourly_demand
group by pickup_zone_id
"""


def measure_trino(sql: str) -> int:
    import trino

    conn = trino.dbapi.connect(
        host=os.getenv("TRINO_HOST", "localhost"),
        port=int(os.getenv("TRINO_PORT", "8080")),
        user=os.getenv("TRINO_USER", "urbanflow"),
    )
    cur = conn.cursor()
    cur.execute(sql)
    cur.fetchall()
    stats = getattr(cur, "stats", {}) or {}
    return int(stats.get("processedBytes", 0))


def main() -> None:
    scanned = measure_trino(QUERY)
    print(f"bytes scanned: {scanned:,} ({scanned / 1e6:.1f} MB)")
    print("Re-run after partitioning + compaction and compare to compute the reduction.")


if __name__ == "__main__":
    main()
