"""Target-aware configuration and Iceberg catalog factory.

One switch (``URBANFLOW_TARGET``) flips the whole pipeline between the free local
stack (MinIO + Iceberg REST + Trino) and real AWS (S3 + Glue + Athena). Ingestion
and dbt both read this so the same code path runs in both places.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

TARGET = os.getenv("URBANFLOW_TARGET", "local").lower()
BRONZE_NAMESPACE = "bronze"


@dataclass(frozen=True)
class Settings:
    target: str
    bucket: str
    region: str
    s3_endpoint: str | None
    access_key: str
    secret_key: str
    catalog_uri: str | None
    glue_database: str


def load_settings() -> Settings:
    return Settings(
        target=TARGET,
        bucket=os.getenv("WAREHOUSE_BUCKET", "urbanflow"),
        region=os.getenv("AWS_REGION", "us-east-1"),
        s3_endpoint=os.getenv("S3_ENDPOINT") if TARGET == "local" else None,
        access_key=os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
        secret_key=os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"),
        catalog_uri=os.getenv("ICEBERG_CATALOG_URI", "http://localhost:8181"),
        glue_database=os.getenv("GLUE_DATABASE", "urbanflow"),
    )


def load_catalog(settings: Settings | None = None):
    """Return a pyiceberg catalog wired for the active target.

    Local  -> Iceberg REST catalog backed by MinIO.
    AWS    -> Glue Data Catalog backed by S3.
    """
    from pyiceberg.catalog import load_catalog as _load

    s = settings or load_settings()
    warehouse = f"s3://{s.bucket}/warehouse"

    if s.target == "local":
        return _load(
            "urbanflow",
            **{
                "type": "rest",
                "uri": s.catalog_uri,
                "warehouse": warehouse,
                "s3.endpoint": s.s3_endpoint,
                "s3.access-key-id": s.access_key,
                "s3.secret-access-key": s.secret_key,
                "s3.path-style-access": "true",
            },
        )
    return _load(
        "urbanflow",
        **{
            "type": "glue",
            "warehouse": warehouse,
            "region_name": s.region,
        },
    )
