"""Track and validate the vendored OpenBB upstream checkout."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from isa_system.utils.time import now_utc


@dataclass(frozen=True)
class OpenBBUpstreamStatus:
    """Current status of the vendored OpenBB checkout."""

    vendor_path: Path
    lock_path: Path
    current_revision: str | None
    locked_revision: str | None
    remote_url: str | None
    dirty: bool

    @property
    def matches_lock(self) -> bool:
        """Return whether the checkout matches the pinned lock revision."""

        return bool(self.current_revision and self.current_revision == self.locked_revision)


class OpenBBUpstreamManager:
    """Read, update, and lock the OpenBB submodule revision."""

    def __init__(
        self,
        root: Path | None = None,
        vendor_path: Path | None = None,
        lock_path: Path | None = None,
    ) -> None:
        self.root = root or _project_root()
        self.vendor_path = vendor_path or self.root / "vendor" / "OpenBB"
        self.lock_path = lock_path or self.root / "configs" / "openbb.lock.json"

    def status(self) -> OpenBBUpstreamStatus:
        """Return the current vendor checkout status."""

        lock = self.read_lock()
        return OpenBBUpstreamStatus(
            vendor_path=self.vendor_path,
            lock_path=self.lock_path,
            current_revision=self.current_revision(),
            locked_revision=lock.get("revision"),
            remote_url=self.remote_url(),
            dirty=self.is_dirty(),
        )

    def read_lock(self) -> dict[str, Any]:
        """Read the OpenBB lock file."""

        if not self.lock_path.exists():
            return {}
        return json.loads(self.lock_path.read_text(encoding="utf-8"))

    def write_lock(self, *, notes: str | None = None) -> dict[str, Any]:
        """Record the current vendor revision in the lock file."""

        revision = self.current_revision()
        if revision is None:
            raise RuntimeError(f"OpenBB vendor checkout not found at {self.vendor_path}")
        payload = {
            "remote": self.remote_url(),
            "path": str(self.vendor_path.relative_to(self.root)),
            "revision": revision,
            "updated_at_utc": now_utc().isoformat(),
            "notes": notes or "Pinned after compatibility tests.",
        }
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload

    def current_revision(self) -> str | None:
        """Return `HEAD` for the vendor checkout."""

        return self._git("rev-parse", "HEAD")

    def remote_url(self) -> str | None:
        """Return the configured upstream URL."""

        return self._git("remote", "get-url", "origin")

    def is_dirty(self) -> bool:
        """Return whether the vendor checkout has local modifications."""

        status = self._git("status", "--porcelain")
        return bool(status)

    def _git(self, *args: str) -> str | None:
        """Run a read-only git command in the vendor checkout."""

        if not self.vendor_path.exists():
            return None
        result = subprocess.run(
            ["git", "-C", str(self.vendor_path), *args],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()


def _project_root() -> Path:
    """Find the project root from this file."""

    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / "pyproject.toml").exists() and (parent / "src" / "isa_system").exists():
            return parent
    raise RuntimeError("Could not locate isa-system project root.")
