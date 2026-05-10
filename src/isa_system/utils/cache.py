"""Small disk-cache helpers for raw provider payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc


class DiskJsonCache:
    """Store raw provider payloads under deterministic keys."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, provider: str, dataset: str, key: str) -> Path:
        """Return a cache path for a provider payload."""

        digest = sha256_digest({"provider": provider, "dataset": dataset, "key": key})
        return self.root / f"provider={provider}" / f"dataset={dataset}" / f"{digest}.json"

    def write(self, provider: str, dataset: str, key: str, payload: Any) -> Path:
        """Write a payload with a retrieval timestamp."""

        path = self.path_for(provider, dataset, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"retrieved_at_utc": now_utc().isoformat(), "payload": payload}, indent=2),
            encoding="utf-8",
        )
        return path

    def read(self, provider: str, dataset: str, key: str) -> Any | None:
        """Read a cached payload if it exists."""

        path = self.path_for(provider, dataset, key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
