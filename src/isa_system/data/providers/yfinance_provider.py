"""yfinance convenience provider for research bars.

yfinance is a convenience and research feed. It is not the sole truth
layer for live risk decisions.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from isa_system.utils.time import now_utc
from isa_system.utils.validation import validate_unique_sorted_timestamps


class YFinanceProvider:
    """Download and normalise daily yfinance bars for UK `.L` and US tickers."""

    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path

    def daily_prices(self, symbols: list[str], period: str = "2y") -> pd.DataFrame:
        """Fetch daily bars and return a normalised DataFrame."""

        try:
            import yfinance as yf
        except ModuleNotFoundError as exc:
            raise RuntimeError("Install yfinance to use this convenience provider.") from exc
        frames: list[pd.DataFrame] = []
        for symbol in symbols:
            raw = yf.download(
                symbol, period=period, interval="1d", auto_adjust=False, progress=False
            )
            if raw.empty:
                continue
            raw = raw.reset_index()
            raw.columns = [str(col).lower().replace(" ", "_") for col in raw.columns]
            date_col = "date" if "date" in raw.columns else "datetime"
            frame = pd.DataFrame(
                {
                    "symbol": symbol,
                    "ts_utc": pd.to_datetime(raw[date_col], utc=True),
                    "open": raw["open"],
                    "high": raw["high"],
                    "low": raw["low"],
                    "close": raw["close"],
                    "adj_close": raw.get("adj_close", raw["close"]),
                    "volume": raw["volume"],
                    "source": "yfinance",
                    "retrieved_at_utc": now_utc(),
                }
            )
            frames.append(validate_unique_sorted_timestamps(frame, "ts_utc"))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def write_cache(self, df: pd.DataFrame) -> Path:
        """Write curated yfinance bars to Parquet."""

        path = self.cache_path / "provider=yfinance" / "dataset=daily_prices"
        path.mkdir(parents=True, exist_ok=True)
        out = path / "prices.parquet"
        df.to_parquet(out, index=False)
        return out
