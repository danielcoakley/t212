"""Constants shared across the ISA system."""

from __future__ import annotations

from pathlib import Path

UTC_NAME = "UTC"
LONDON_TZ_NAME = "Europe/London"
DEFAULT_DATA_LAKE_PATH = Path("data_lake")
DEFAULT_ARTIFACTS_PATH = Path("artifacts")
DEFAULT_SQLITE_DSN = "sqlite:///./artifacts/isa_system.sqlite3"
DEFAULT_ACCOUNT_CURRENCY = "GBP"
