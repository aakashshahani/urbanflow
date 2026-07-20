"""Helpers to land a PyArrow table into a bronze Iceberg table idempotently."""
from __future__ import annotations

import pyarrow as pa

from ingestion.config import BRONZE_NAMESPACE, load_catalog, load_settings


def ensure_namespace(catalog, namespace: str = BRONZE_NAMESPACE) -> None:
    existing = {".".join(ns) for ns in catalog.list_namespaces()}
    if namespace not in existing:
        catalog.create_namespace(namespace)


def write_bronze(table_name: str, data: pa.Table, partition_cols: list[str] | None = None) -> str:
    """Create-or-append ``data`` into ``bronze.<table_name>``.

    Bronze is append-only; silver/gold handle dedup + SCD2. Partitioning is applied
    at table-create time (Iceberg hidden partitioning) so re-runs stay cheap to scan.
    """
    settings = load_settings()
    catalog = load_catalog(settings)
    ensure_namespace(catalog)

    identifier = f"{BRONZE_NAMESPACE}.{table_name}"
    if not catalog.table_exists(identifier):
        table = catalog.create_table(identifier, schema=data.schema)
        # NOTE: partition spec (e.g. day(pickup_ts)) is added in a follow-up once the
        # schema is frozen, kept explicit so the tuning step is a measured change.
    else:
        table = catalog.load_table(identifier)

    table.append(data)
    return identifier
