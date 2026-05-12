"""Tests for the narrow OpenBB adapter boundary."""

from __future__ import annotations

from datetime import date

import httpx
import pandas as pd

from isa_system.openbb_adapter import IsaOpenBBClient, OpenBBUpstreamManager
from isa_system.settings import Settings


class _FakeResult:
    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-05-08"]),
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [12345],
            }
        )


class _FakeRowsResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.results = rows


class _FakeHistorical:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def historical(self, **kwargs: object) -> _FakeResult:
        self.calls.append(kwargs)
        return _FakeResult()


class _FakePrice:
    def __init__(self) -> None:
        self.historical_client = _FakeHistorical()

    def historical(self, **kwargs: object) -> _FakeResult:
        return self.historical_client.historical(**kwargs)


class _FakeEquity:
    def __init__(self) -> None:
        self.price = _FakePrice()
        self.fundamental = self

    def search(self, **kwargs: object) -> _FakeRowsResult:
        return _FakeRowsResult(
            [{"symbol": kwargs["query"], "name": "Apple Inc.", "exchange": "NASDAQ"}]
        )

    def profile(self, **kwargs: object) -> _FakeRowsResult:
        return _FakeRowsResult(
            [
                {
                    "symbol": kwargs["symbol"],
                    "name": "Apple Inc.",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                }
            ]
        )

    def screener(self, **kwargs: object) -> _FakeRowsResult:
        return _FakeRowsResult(
            [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "market_cap": kwargs.get("mktcap_min"),
                }
            ]
        )

    def metrics(self, **kwargs: object) -> _FakeRowsResult:
        return _FakeRowsResult([{"symbol": kwargs["symbol"], "market_cap": 1_000_000}])


class _FakeOBB:
    def __init__(self) -> None:
        self.equity = _FakeEquity()


def test_openbb_price_adapter_normalises_output() -> None:
    """OpenBB price data is converted to the app EOD schema."""

    fake = _FakeOBB()
    frame = IsaOpenBBClient(obb=fake).equity_daily_prices(
        ["AAPL"],
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 8),
        provider="yfinance",
    )

    assert list(frame.columns) == [
        "symbol",
        "ts_utc",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "source",
        "retrieved_at_utc",
    ]
    assert frame.loc[0, "symbol"] == "AAPL"
    assert frame.loc[0, "source"] == "openbb:yfinance"


def test_openbb_profile_adapter_returns_json_safe_records() -> None:
    """OpenBB profile data is exposed as dashboard-ready records."""

    records = IsaOpenBBClient(obb=_FakeOBB()).equity_profile("AAPL", provider="yfinance")

    assert records == [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
        }
    ]


def test_openbb_search_adapter_returns_records() -> None:
    """OpenBB symbol search stays behind the adapter boundary."""

    records = IsaOpenBBClient(obb=_FakeOBB()).equity_search("AAPL", provider="fmp")

    assert records[0]["symbol"] == "AAPL"
    assert records[0]["exchange"] == "NASDAQ"


def test_openbb_screener_adapter_returns_records() -> None:
    """OpenBB screener data stays behind the adapter boundary."""

    records = IsaOpenBBClient(obb=_FakeOBB()).equity_screener(
        provider="yfinance",
        country="us",
        mktcap_min=1_000_000_000,
    )

    assert records == [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market_cap": 1_000_000_000,
        }
    ]


def test_openbb_odp_rest_adapter_normalises_prices() -> None:
    """ODP Desktop REST output can replace direct OpenBB Python calls."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/equity/price/historical"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "date": "2026-05-08",
                        "open": 100.0,
                        "high": 102.0,
                        "low": 99.0,
                        "close": 101.0,
                        "volume": 12345,
                    }
                ],
                "provider": "yfinance",
            },
        )

    client = IsaOpenBBClient(
        settings=Settings(
            openbb_backend="odp_rest",
            openbb_odp_api_base_url="http://openbb.test",
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    frame = client.equity_daily_prices(["AAPL"], provider="yfinance")

    assert len(frame) == 1
    assert frame.loc[0, "source"] == "openbb-odp:yfinance"


def test_openbb_odp_rest_adapter_returns_screener_records() -> None:
    """ODP Desktop screener output can seed the market scan universe."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/equity/screener"
        assert request.url.params["provider"] == "yfinance"
        assert request.url.params["country"] == "us"
        assert request.url.params["mktcap_min"] == "1000000000"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "symbol": "AAPL",
                        "name": "Apple Inc.",
                        "market_cap": 3_000_000_000_000,
                    }
                ],
                "provider": "yfinance",
            },
        )

    client = IsaOpenBBClient(
        settings=Settings(
            openbb_backend="odp_rest",
            openbb_odp_api_base_url="http://openbb.test",
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    rows = client.equity_screener(
        provider="yfinance",
        country="us",
        mktcap_min=1_000_000_000,
    )

    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["market_cap"] == 3_000_000_000_000


def test_openbb_upstream_lock_matches_vendor_checkout() -> None:
    """The checked-out vendor revision is visible through the manager."""

    status = OpenBBUpstreamManager().status()

    assert status.vendor_path.name == "OpenBB"
    assert status.current_revision
    assert status.locked_revision
    assert status.matches_lock
