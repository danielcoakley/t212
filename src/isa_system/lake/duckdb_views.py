"""DuckDB view registration helpers."""

from __future__ import annotations

from pathlib import Path

import duckdb


def register_parquet_view(
    connection: duckdb.DuckDBPyConnection, view_name: str, path: Path
) -> None:
    """Register a Parquet glob as a DuckDB view."""

    escaped = str(path).replace("\\", "/")
    connection.execute(
        f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{escaped}')"
    )
