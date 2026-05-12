"""OpenBB adapter used as the only app boundary to OpenBB APIs.

The strategy, risk, and execution layers should depend on the normalised
frames returned here rather than calling OpenBB directly.  That keeps
future upstream OpenBB changes contained to this module.
"""

from __future__ import annotations

from datetime import date, datetime
from importlib.util import find_spec
from typing import Any

import httpx
import pandas as pd
from pydantic import BaseModel

from isa_system.settings import Settings, get_settings
from isa_system.utils.time import now_utc


class OpenBBAdapterError(RuntimeError):
    """Raised when OpenBB cannot be imported or returns an unusable payload."""


class NormalisedPriceRequest(BaseModel):
    """Request parameters for normalised EOD prices."""

    symbols: list[str]
    start_date: date | None = None
    end_date: date | None = None
    provider: str = "yfinance"


class IsaOpenBBClient:
    """Small, testable facade over ODP/OpenBB data access."""

    def __init__(
        self,
        obb: Any | None = None,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._obb = obb
        self._settings = settings
        self._http_client = http_client
        self._credentials_applied = False

    @property
    def settings(self) -> Settings:
        """Return settings lazily so tests can pass isolated settings objects."""

        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    @property
    def backend(self) -> str:
        """Return the configured OpenBB boundary implementation."""

        if self._obb is not None:
            return "python"
        return self.settings.openbb_backend.lower()

    def status(self) -> dict[str, object]:
        """Return the configured OpenBB/ODP adapter status without secrets."""

        python_importable = self._python_importable()
        status: dict[str, object] = {
            "backend": self.backend,
            "python_importable": python_importable,
            "odp_api_base_url": self._odp_base_url,
            "odp_api_status": "not_configured",
            "odp_api_error": None,
        }
        try:
            response = self._odp_get_openapi()
        except OpenBBAdapterError as exc:
            status["odp_api_status"] = "unavailable"
            status["odp_api_error"] = str(exc)
        else:
            status["odp_api_status"] = "ok"
            status["odp_api_title"] = response.get("info", {}).get("title")
        return status

    @property
    def obb(self) -> Any:
        """Return an OpenBB interface, importing lazily for offline safety."""

        if self._obb is None:
            try:
                from openbb import obb as imported_obb
            except Exception as exc:  # pragma: no cover - depends on optional package
                raise OpenBBAdapterError(
                    "OpenBB is not importable. Install from vendor/OpenBB or pin a PyPI release."
                ) from exc
            self._obb = imported_obb
        self._apply_credentials()
        return self._obb

    def equity_search(self, query: str, *, provider: str = "fmp") -> list[dict[str, Any]]:
        """Search OpenBB's equity universe and return JSON-safe records."""

        if self.backend == "odp_rest":
            payload = self._odp_get("/equity/search", {"query": query, "provider": provider})
            return _to_records(payload)
        try:
            result = self.obb.equity.search(query=query, provider=provider)
        except AttributeError as exc:
            raise OpenBBAdapterError(
                "The configured OpenBB build does not expose equity.search."
            ) from exc
        except Exception as exc:
            raise OpenBBAdapterError(f"OpenBB equity.search failed: {exc}") from exc
        return _to_records(result)

    def equity_profile(self, symbol: str, *, provider: str = "yfinance") -> list[dict[str, Any]]:
        """Fetch company profile/context data from OpenBB."""

        if self.backend == "odp_rest":
            payload = self._odp_get("/equity/profile", {"symbol": symbol, "provider": provider})
            return _to_records(payload)
        try:
            result = self.obb.equity.profile(symbol=symbol, provider=provider)
        except AttributeError as exc:
            raise OpenBBAdapterError(
                "The configured OpenBB build does not expose equity.profile."
            ) from exc
        except Exception as exc:
            raise OpenBBAdapterError(f"OpenBB equity.profile failed: {exc}") from exc
        return _to_records(result)

    def equity_screener(
        self, *, provider: str = "yfinance", **filters: Any
    ) -> list[dict[str, Any]]:
        """Run OpenBB/ODP's equity screener and return JSON-safe rows."""

        clean_filters = {key: value for key, value in filters.items() if value is not None}
        if self.backend == "odp_rest":
            payload = self._odp_get("/equity/screener", {"provider": provider, **clean_filters})
            return _to_records(payload)
        try:
            result = self.obb.equity.screener(provider=provider, **clean_filters)
        except AttributeError as exc:
            raise OpenBBAdapterError(
                "The configured OpenBB build does not expose equity.screener."
            ) from exc
        except Exception as exc:
            raise OpenBBAdapterError(f"OpenBB equity.screener failed: {exc}") from exc
        return _to_records(result)

    def equity_daily_prices(
        self,
        symbols: list[str],
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        provider: str = "yfinance",
    ) -> pd.DataFrame:
        """Fetch and normalise daily equity/ETF bars from OpenBB providers."""

        frames: list[pd.DataFrame] = []
        for symbol in symbols:
            if self.backend == "odp_rest":
                result = self._odp_get(
                    "/equity/price/historical",
                    {
                        "symbol": symbol,
                        "start_date": start_date,
                        "end_date": end_date,
                        "provider": provider,
                    },
                )
            else:
                try:
                    result = self.obb.equity.price.historical(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        provider=provider,
                    )
                except AttributeError as exc:
                    raise OpenBBAdapterError(
                        "The configured OpenBB build does not expose equity.price.historical."
                    ) from exc
                except Exception as exc:
                    raise OpenBBAdapterError(
                        f"OpenBB equity.price.historical failed: {exc}"
                    ) from exc
            raw = _to_dataframe(result)
            if raw.empty:
                continue
            source = (
                f"openbb-odp:{provider}"
                if self.backend == "odp_rest"
                else f"openbb:{provider}"
            )
            frames.append(_normalise_price_frame(raw, symbol=symbol, source=source))
        if not frames:
            return pd.DataFrame(
                columns=[
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
            )
        return pd.concat(frames, ignore_index=True)

    def equity_fundamentals(
        self, symbols: list[str], *, provider: str = "yfinance"
    ) -> pd.DataFrame:
        """Fetch a best-effort fundamentals snapshot through OpenBB."""

        frames: list[pd.DataFrame] = []
        for symbol in symbols:
            if self.backend == "odp_rest":
                result = self._odp_get(
                    "/equity/fundamental/metrics",
                    {"symbol": symbol, "provider": provider},
                )
            else:
                try:
                    result = self.obb.equity.fundamental.metrics(symbol=symbol, provider=provider)
                except AttributeError as exc:
                    raise OpenBBAdapterError(
                        "The configured OpenBB build does not expose equity.fundamental.metrics."
                    ) from exc
                except Exception as exc:
                    raise OpenBBAdapterError(
                        f"OpenBB equity.fundamental.metrics failed: {exc}"
                    ) from exc
            raw = _to_dataframe(result)
            if raw.empty:
                continue
            raw = raw.copy()
            raw["symbol"] = symbol
            raw["source"] = (
                f"openbb-odp:{provider}" if self.backend == "odp_rest" else f"openbb:{provider}"
            )
            raw["retrieved_at_utc"] = now_utc()
            frames.append(raw)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def _apply_credentials(self) -> None:
        """Copy local provider keys into OpenBB's runtime settings when available."""

        if self._credentials_applied:
            return
        self._credentials_applied = True
        user = getattr(self._obb, "user", None)
        credentials = getattr(user, "credentials", None)
        if credentials is None:
            return
        settings = self.settings
        secret_mappings = {
            "alpha_vantage_api_key": settings.alpha_vantage_api_key,
            "fmp_api_key": settings.fmp_api_key,
            "fred_api_key": settings.fred_api_key,
        }
        for name, secret in secret_mappings.items():
            if secret is None or not hasattr(credentials, name):
                continue
            setattr(credentials, name, secret.get_secret_value())
        if settings.sec_user_agent and hasattr(credentials, "sec_user_agent"):
            credentials.sec_user_agent = settings.sec_user_agent

    @property
    def _odp_base_url(self) -> str:
        return self.settings.openbb_odp_api_base_url.rstrip("/")

    def _odp_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Call an ODP REST endpoint and return its JSON payload."""

        clean_params = {
            key: _param_value(value)
            for key, value in (params or {}).items()
            if value is not None and value != ""
        }
        url = f"{self._odp_base_url}/api/v1{path}"
        try:
            response = self._http().get(
                url,
                params=clean_params,
                headers={"accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise OpenBBAdapterError(
                f"ODP REST {path} failed with HTTP {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise OpenBBAdapterError(
                f"ODP REST backend is unavailable at {self._odp_base_url}. "
                "Start the OpenBB API backend in ODP Desktop."
            ) from exc
        except ValueError as exc:
            raise OpenBBAdapterError(f"ODP REST {path} returned invalid JSON.") from exc

    def _odp_get_openapi(self) -> dict[str, Any]:
        """Read the ODP OpenAPI document to verify the backend is reachable."""

        try:
            response = self._http().get(
                f"{self._odp_base_url}/openapi.json", headers={"accept": "application/json"}
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise OpenBBAdapterError(
                f"ODP REST /openapi.json failed with HTTP {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise OpenBBAdapterError(
                f"ODP REST backend is unavailable at {self._odp_base_url}."
            ) from exc
        except ValueError as exc:
            raise OpenBBAdapterError("ODP REST /openapi.json returned invalid JSON.") from exc
        return payload if isinstance(payload, dict) else {}

    def _http(self) -> httpx.Client:
        """Return a configured sync HTTP client for ODP REST calls."""

        if self._http_client is not None:
            return self._http_client
        auth: tuple[str, str] | None = None
        if self.settings.openbb_odp_api_username and self.settings.openbb_odp_api_password:
            auth = (
                self.settings.openbb_odp_api_username,
                self.settings.openbb_odp_api_password.get_secret_value(),
            )
        self._http_client = httpx.Client(
            timeout=self.settings.openbb_odp_timeout_seconds,
            auth=auth,
        )
        return self._http_client

    def _python_importable(self) -> bool:
        return find_spec("openbb") is not None


def _to_dataframe(result: Any) -> pd.DataFrame:
    """Convert common OpenBB result objects to a DataFrame."""

    if isinstance(result, pd.DataFrame):
        return result.copy()
    if isinstance(result, dict):
        if "results" in result:
            return pd.DataFrame([_model_to_dict(item) for item in _as_list(result["results"])])
        return pd.DataFrame([result])
    if isinstance(result, list):
        return pd.DataFrame([_model_to_dict(item) for item in result])
    if hasattr(result, "to_dataframe"):
        return result.to_dataframe().copy()
    if hasattr(result, "results"):
        return pd.DataFrame([_model_to_dict(item) for item in result.results])
    raise OpenBBAdapterError(f"Unsupported OpenBB result type: {type(result)!r}")


def _param_value(value: Any) -> Any:
    """Convert REST query parameter values into strings accepted by ODP."""

    if isinstance(value, date):
        return value.isoformat()
    return value


def _as_list(value: Any) -> list[Any]:
    """Treat single-result ODP payloads and list payloads consistently."""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _to_records(result: Any) -> list[dict[str, Any]]:
    """Convert OpenBB output into JSON-safe row dictionaries."""

    frame = _to_dataframe(result)
    return dataframe_to_records(frame)


def dataframe_to_records(frame: pd.DataFrame, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Convert a DataFrame into JSON-safe row dictionaries."""

    if frame.empty:
        return []
    rows = frame.head(limit).copy() if limit is not None else frame.copy()
    rows.columns = [str(col) for col in rows.columns]
    return [_clean_record(record) for record in rows.to_dict(orient="records")]


def _model_to_dict(item: Any) -> Any:
    """Return a plain mapping for common OpenBB/Pydantic result rows."""

    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "dict"):
        return item.dict()
    if hasattr(item, "__dict__"):
        return vars(item)
    return item


def _clean_record(record: dict[str, Any]) -> dict[str, Any]:
    """Clean NaN, pandas scalars, and datetimes for FastAPI JSON responses."""

    return {key: _clean_value(value) for key, value in record.items()}


def _clean_value(value: Any) -> Any:
    """Convert pandas/OpenBB values into JSON-safe Python values."""

    if value is None:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _clean_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean_value(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            return value
    return value


def _normalise_price_frame(raw: pd.DataFrame, *, symbol: str, source: str) -> pd.DataFrame:
    """Normalise OpenBB price output to the app's EOD bar schema."""

    frame = raw.reset_index().copy()
    frame.columns = [str(col).lower().replace(" ", "_") for col in frame.columns]
    date_col = next(
        (col for col in ("date", "datetime", "timestamp", "index") if col in frame),
        None,
    )
    if date_col is None:
        raise OpenBBAdapterError("OpenBB price data did not include a date-like column.")
    for required in ("open", "high", "low", "close"):
        if required not in frame:
            raise OpenBBAdapterError(f"OpenBB price data is missing required column: {required}")
    return pd.DataFrame(
        {
            "symbol": frame.get("symbol", symbol),
            "ts_utc": pd.to_datetime(frame[date_col], utc=True),
            "open": frame["open"],
            "high": frame["high"],
            "low": frame["low"],
            "close": frame["close"],
            "adj_close": frame.get("adj_close", frame["close"]),
            "volume": frame.get("volume", 0),
            "source": source,
            "retrieved_at_utc": now_utc(),
        }
    )
