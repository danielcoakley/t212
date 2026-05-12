"""FastAPI-served operator command centre."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])


def assets_dir() -> Path:
    """Return the packaged dashboard asset directory."""

    return Path(__file__).resolve().parents[2] / "web"


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def command_centre() -> HTMLResponse:
    """Serve the local operator command centre dashboard."""

    return HTMLResponse((assets_dir() / "index.html").read_text(encoding="utf-8"))
