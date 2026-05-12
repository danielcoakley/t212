"""Integration tests for OpenBB control-plane routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from isa_system.api.main import app
from isa_system.api.routers import openbb as openbb_router


def test_openbb_status_route() -> None:
    """OpenBB status route reports the pinned vendor checkout."""

    response = TestClient(app).get("/openbb/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_revision"]
    assert payload["locked_revision"]
    assert payload["matches_lock"] is True


def test_openbb_ticker_context_route(monkeypatch) -> None:
    """Ticker context is assembled through the OpenBB adapter boundary."""

    class FakeOpenBBClient:
        def equity_profile(self, symbol: str, *, provider: str):
            return [{"symbol": symbol, "name": "Apple Inc.", "sector": "Technology"}]

        def equity_fundamentals(self, symbols: list[str], *, provider: str):
            import pandas as pd

            return pd.DataFrame([{"symbol": symbols[0], "market_cap": 1_000_000}])

        def equity_daily_prices(self, symbols: list[str], **kwargs):
            import pandas as pd

            return pd.DataFrame(
                [
                    {
                        "symbol": symbols[0],
                        "ts_utc": pd.Timestamp("2026-05-08", tz="UTC"),
                        "open": 100.0,
                        "high": 102.0,
                        "low": 99.0,
                        "close": 101.0,
                        "adj_close": 101.0,
                        "volume": 12345,
                        "source": "openbb:yfinance",
                        "retrieved_at_utc": pd.Timestamp("2026-05-11", tz="UTC"),
                    }
                ]
            )

    monkeypatch.setattr(openbb_router, "IsaOpenBBClient", FakeOpenBBClient)

    response = TestClient(app).get("/openbb/ticker/aapl/context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["symbol"] == "AAPL"
    assert payload["profile"][0]["name"] == "Apple Inc."
    assert payload["prices"]["rows"] == 1
