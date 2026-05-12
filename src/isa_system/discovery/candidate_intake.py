"""Candidate intake and deduplication services."""

from __future__ import annotations

from pathlib import Path

from isa_system.discovery.finviz_fetcher import FinvizFetcher
from isa_system.discovery.finviz_parser import parse_finviz_html
from isa_system.discovery.finviz_screeners import load_finviz_screeners
from isa_system.discovery.models import Candidate, CandidateDiscoveryResult, FinvizScreenerConfig
from isa_system.settings import Settings, get_settings
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc


class CandidateIntakeService:
    """Run curated discovery and deduplicate candidates by symbol."""

    def __init__(
        self,
        *,
        screeners: list[FinvizScreenerConfig] | None = None,
        fetcher: FinvizFetcher | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.screeners = screeners or load_finviz_screeners()
        cache_dir = Path(self.settings.artifacts_path) / "finviz_cache"
        self.fetcher = fetcher or FinvizFetcher(cache_dir=cache_dir)

    def run(
        self,
        *,
        fixture_html_by_screener: dict[str, str] | None = None,
        force_refresh: bool = False,
    ) -> CandidateDiscoveryResult:
        """Run discovery from fixtures or live Finviz pages."""

        discovered_at = now_utc()
        candidates_by_symbol: dict[str, Candidate] = {}
        warnings: list[str] = []

        for screener in self.screeners:
            try:
                html = (
                    fixture_html_by_screener[screener.name]
                    if fixture_html_by_screener and screener.name in fixture_html_by_screener
                    else self.fetcher.fetch(screener, force_refresh=force_refresh)
                )
            except Exception as exc:
                warnings.append(f"{screener.name}: fetch failed: {exc}")
                continue

            rows = parse_finviz_html(html)
            if not rows:
                warnings.append(f"{screener.name}: no parseable ticker rows")
                continue

            for row in rows:
                raw_fields = dict(row.raw_fields)
                if row.profile_url:
                    raw_fields["Finviz Profile"] = row.profile_url
                cache_key = sha256_digest(
                    {
                        "symbol": row.symbol,
                        "screener": screener.name,
                        "url": str(screener.url),
                    }
                )
                existing = candidates_by_symbol.get(row.symbol)
                if existing is None:
                    candidates_by_symbol[row.symbol] = Candidate(
                        symbol=row.symbol,
                        source_screener=screener.name,
                        source_screeners=[screener.name],
                        discovered_at_utc=discovered_at,
                        screener_rank=row.rank,
                        raw_fields=raw_fields,
                        cache_key=cache_key,
                    )
                    continue

                if screener.name not in existing.source_screeners:
                    existing.source_screeners.append(screener.name)
                existing.screener_appearance_count = len(existing.source_screeners)
                existing.multi_screener_boost = _multi_screener_boost(
                    existing.screener_appearance_count
                )

        candidates = sorted(
            candidates_by_symbol.values(),
            key=lambda candidate: (
                -candidate.screener_appearance_count,
                candidate.screener_rank or 9999,
                candidate.symbol,
            ),
        )
        return CandidateDiscoveryResult(
            run_id=sha256_digest({"discovered_at_utc": discovered_at, "count": len(candidates)})[
                :16
            ],
            discovered_at_utc=discovered_at,
            candidates=candidates,
            warnings=warnings,
        )


def _multi_screener_boost(appearance_count: int) -> float:
    """Return a small deterministic boost for appearing in multiple screeners."""

    return max(0.0, min(10.0, float((appearance_count - 1) * 5)))
