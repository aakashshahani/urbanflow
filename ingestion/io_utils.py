"""Helpers to land a PyArrow table into a bronze Iceberg table idempotently."""
from __future__ import annotations

import pyarrow as pa

from ingestion.config import BRONZE_NAMESPACE, load_catalog, load_settings


def ensure_namespace(catalog, namespace: str = BRONZE_NAMESPACE) -> None:
    existing = {".".join(ns) for ns in catalog.list_namespaces()}
    if namespace not in existing:
        catalog.create_namespace(namespace)


def write_bronze(
    table_name: str,
    data: pa.Table,
    partition_cols: list[str] | None = None,
    replace_month: str | None = None,
    catalog=None,
) -> str:
    """Land ``data`` in ``bronze.<table_name>``.

    With ``replace_month`` the write is idempotent: rows already loaded for that
    ``_source_month`` are replaced in one atomic Iceberg overwrite, so re-running a
    month (a retry, a backfill, or the daily schedule) never duplicates bronze rows.
    Without it the data is appended. Partitioning is applied at table-create time
    (Iceberg hidden partitioning) so re-runs stay cheap to scan.
    """
    if catalog is None:
        catalog = load_catalog(load_settings())
    ensure_namespace(catalog)

    identifier = f"{BRONZE_NAMESPACE}.{table_name}"
    if not catalog.table_exists(identifier):
        table = catalog.create_table(identifier, schema=data.schema)
        # NOTE: partition spec (e.g. day(pickup_ts)) is added in a follow-up once the
        # schema is frozen, kept explicit so the tuning step is a measured change.
        table.append(data)
        return identifier

    table = catalog.load_table(identifier)
    if replace_month is not None:
        from pyiceberg.expressions import EqualTo

        table.overwrite(data, overwrite_filter=EqualTo("_source_month", replace_month))
    else:
        table.append(data)
    return identifier
