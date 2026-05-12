"""Configurable Finviz screener workbench helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from isa_system.discovery.candidate_intake import CandidateIntakeService
from isa_system.discovery.finviz_fetcher import FinvizFetcher
from isa_system.discovery.finviz_parser import finviz_profile_url, parse_finviz_html
from isa_system.discovery.finviz_screeners import load_finviz_screeners
from isa_system.discovery.models import (
    Candidate,
    CandidateDiscoveryResult,
    FinvizScreenerConfig,
    ParsedFinvizRow,
)
from isa_system.settings import Settings, get_settings
from isa_system.utils.hashing import sha256_digest
from isa_system.utils.time import now_utc

FINVIZ_BASE_URL = "https://finviz.com/screener.ashx"

PRINCIPAL_VALUATION_FIELDS = [
    "Market Cap",
    "P/E",
    "Forward P/E",
    "PEG",
    "P/S",
    "P/B",
    "P/C",
    "P/FCF",
    "EV/EBITDA",
    "EPS this Y",
    "EPS next Y",
    "EPS past 5Y",
    "EPS next 5Y",
    "Sales past 5Y",
    "Price",
    "Change",
    "Volume",
]


class FinvizFilterChoice(BaseModel):
    """One dropdown choice for a Finviz filter control."""

    model_config = ConfigDict(extra="forbid")

    label: str
    code: str | None = None


class FinvizFilterControl(BaseModel):
    """A Finviz-like dropdown control grouped by screener tab."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    category: str
    choices: list[FinvizFilterChoice]


class FinvizColumnOption(BaseModel):
    """One selectable results-table column."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    category: str


class FinvizFilterOption(BaseModel):
    """One supported Finviz filter code exposed to the operator UI."""

    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    group: str
    description: str


class FinvizScreenerPreset(BaseModel):
    """A configured screener preset plus parsed filter codes."""

    model_config = ConfigDict(extra="forbid")

    name: str
    purpose: str
    url: str
    filters: list[str]
    order_by: str = "PEG"
    order_direction: str = "asc"
    signal: str = "none"
    tickers: str = ""
    custom: bool = False


class FinvizScreenerSettings(BaseModel):
    """Settings payload for the Finviz screener workbench."""

    model_config = ConfigDict(extra="forbid")

    presets: list[FinvizScreenerPreset]
    filter_options: list[FinvizFilterOption]
    filter_controls: list[FinvizFilterControl]
    column_options: list[FinvizColumnOption]
    principal_valuation_fields: list[str] = Field(
        default_factory=lambda: PRINCIPAL_VALUATION_FIELDS
    )


class FinvizScreenerRunRequest(BaseModel):
    """Request to run one configurable Finviz screener."""

    model_config = ConfigDict(extra="forbid")

    name: str = "Custom Finviz Screener"
    purpose: str = "Operator-configured Finviz discovery run."
    filters: list[str] = Field(default_factory=list)
    order_by: str = "PEG"
    order_direction: str = "asc"
    signal: str = "none"
    tickers: str = ""
    use_fixtures: bool = False
    force_refresh: bool = False


class FinvizPresetSaveRequest(BaseModel):
    """Request to persist an operator-defined Finviz screener preset."""

    model_config = ConfigDict(extra="forbid")

    name: str
    purpose: str = "Operator-saved Finviz screener preset."
    filters: list[str] = Field(default_factory=list)
    order_by: str = "PEG"
    order_direction: str = "asc"
    signal: str = "none"
    tickers: str = ""


class FinvizScreenerTableRow(BaseModel):
    """One full Finviz table row returned to the operator UI."""

    model_config = ConfigDict(extra="forbid")

    rank: int | None = None
    symbol: str
    profile_url: str
    fields: dict[str, str] = Field(default_factory=dict)
    valuation: dict[str, str] = Field(default_factory=dict)


class FinvizScreenerRunResult(BaseModel):
    """Result from a configurable Finviz screener run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    discovered_at_utc: str
    name: str
    purpose: str
    url: str
    filters: list[str]
    filter_labels: list[str]
    rows: list[FinvizScreenerTableRow]
    candidates: list[Candidate]
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class FinvizWorkbenchResult:
    """Internal workbench result plus the candidate discovery shape."""

    screener: FinvizScreenerRunResult
    discovery: CandidateDiscoveryResult


def finviz_screener_settings(settings: Settings | None = None) -> FinvizScreenerSettings:
    """Return Finviz presets and a curated capability map for UI controls."""

    settings = settings or get_settings()
    presets = [
        FinvizScreenerPreset(
            name=screener.name,
            purpose=screener.purpose,
            url=str(screener.url),
            filters=parse_filter_codes(str(screener.url)),
        )
        for screener in load_finviz_screeners()
    ]
    presets.extend(_load_custom_presets(settings))
    return FinvizScreenerSettings(
        presets=presets,
        filter_options=finviz_filter_options(),
        filter_controls=finviz_filter_controls(),
        column_options=finviz_column_options(),
    )


def finviz_filter_options() -> list[FinvizFilterOption]:
    """Return supported Finviz filter codes exposed to the operator UI."""

    options: dict[str, FinvizFilterOption] = {}
    for control in finviz_filter_controls():
        for choice in control.choices:
            if not choice.code:
                continue
            options.setdefault(
                choice.code,
                FinvizFilterOption(
                    group=control.category,
                    code=choice.code,
                    label=f"{control.label}: {choice.label}",
                    description=f"{control.category} filter for {control.label}.",
                ),
            )
    return sorted(options.values(), key=lambda item: (item.group, item.label, item.code))


def finviz_filter_controls() -> list[FinvizFilterControl]:
    """Return broad dropdown controls inspired by Finviz's own screener."""

    def any_choice() -> FinvizFilterChoice:
        return FinvizFilterChoice(label="Any", code=None)

    def choices(rows: list[tuple[str, str]]) -> list[FinvizFilterChoice]:
        return [FinvizFilterChoice(label=label, code=code) for label, code in rows]

    def under_over(prefix: str, values: list[str]) -> list[tuple[str, str]]:
        return [(f"Under {value}", f"{prefix}_u{value}") for value in values] + [
            (f"Over {value}", f"{prefix}_o{value}") for value in values
        ]

    def over_pct(prefix: str, values: list[str]) -> list[tuple[str, str]]:
        return [(f"Over {value}%", f"{prefix}_o{value}") for value in values]

    def under_over_pct(prefix: str, values: list[str]) -> list[tuple[str, str]]:
        return [(f"Under {value}%", f"{prefix}_u{value}") for value in values] + [
            (f"Over {value}%", f"{prefix}_o{value}") for value in values
        ]

    controls = [
        (
            "Descriptive",
            "market_cap",
            "Market Cap",
            [
                ("Mega", "cap_mega"),
                ("Large", "cap_large"),
                ("Mid", "cap_mid"),
                ("Small", "cap_small"),
                ("Micro", "cap_micro"),
                ("Large or larger", "cap_largeover"),
                ("Mid or larger", "cap_midover"),
                ("Small or larger", "cap_smallover"),
                ("Micro or larger", "cap_microover"),
                ("Mid or smaller", "cap_midunder"),
                ("Small or smaller", "cap_smallunder"),
                ("Micro or smaller", "cap_microunder"),
            ],
        ),
        (
            "Descriptive",
            "avg_volume",
            "Average Volume",
            [
                ("Over 50k", "sh_avgvol_o50"),
                ("Over 100k", "sh_avgvol_o100"),
                ("Over 200k", "sh_avgvol_o200"),
                ("Over 300k", "sh_avgvol_o300"),
                ("Over 500k", "sh_avgvol_o500"),
                ("Over 750k", "sh_avgvol_o750"),
                ("Over 1M", "sh_avgvol_o1000"),
                ("Over 2M", "sh_avgvol_o2000"),
            ],
        ),
        (
            "Descriptive",
            "price",
            "Price",
            under_over("sh_price", ["1", "2", "5", "10", "15", "20", "30", "40", "50"]),
        ),
        (
            "Descriptive",
            "sector",
            "Sector",
            [
                ("Basic Materials", "sec_basicmaterials"),
                ("Communication Services", "sec_communicationservices"),
                ("Consumer Cyclical", "sec_consumercyclical"),
                ("Consumer Defensive", "sec_consumerdefensive"),
                ("Energy", "sec_energy"),
                ("Financial", "sec_financial"),
                ("Healthcare", "sec_healthcare"),
                ("Industrials", "sec_industrials"),
                ("Real Estate", "sec_realestate"),
                ("Technology", "sec_technology"),
                ("Utilities", "sec_utilities"),
            ],
        ),
        (
            "Fundamental",
            "pe",
            "P/E",
            under_over("fa_pe", ["5", "10", "15", "20", "25", "30", "35", "40", "45", "50"]),
        ),
        (
            "Fundamental",
            "forward_pe",
            "Forward P/E",
            under_over("fa_fpe", ["5", "10", "15", "20", "25", "30", "35", "40", "45", "50"]),
        ),
        (
            "Fundamental",
            "peg",
            "PEG",
            under_over("fa_peg", ["0.5", "1", "1.5", "2", "3"]),
        ),
        (
            "Fundamental",
            "ps",
            "P/S",
            under_over("fa_ps", ["1", "2", "3", "4", "5", "10"]),
        ),
        (
            "Fundamental",
            "pb",
            "P/B",
            under_over("fa_pb", ["1", "2", "3", "4", "5", "10"]),
        ),
        (
            "Fundamental",
            "pc",
            "Price/Cash",
            under_over("fa_pc", ["1", "2", "3", "4", "5", "10", "20", "50"]),
        ),
        (
            "Fundamental",
            "pfcf",
            "Price/Free Cash Flow",
            under_over("fa_pfcf", ["5", "10", "15", "20", "25", "30", "40", "50"]),
        ),
        (
            "Fundamental",
            "eps_growth_this_year",
            "EPS Growth This Year",
            over_pct("fa_epsyoy", ["5", "10", "15", "20", "25", "30"]),
        ),
        (
            "Fundamental",
            "eps_growth_qoq",
            "EPS Growth Qtr Over Qtr",
            over_pct("fa_epsqoq", ["5", "10", "15", "20", "25", "30"]),
        ),
        (
            "Fundamental",
            "eps_growth_past_5y",
            "EPS Growth Past 5 Years",
            over_pct("fa_eps5years", ["5", "10", "15", "20", "25", "30"]),
        ),
        (
            "Fundamental",
            "eps_growth_next_5y",
            "EPS Growth Next 5 Years",
            over_pct("fa_epsnext5years", ["5", "10", "15", "20", "25", "30"]),
        ),
        (
            "Fundamental",
            "sales_growth_qoq",
            "Sales Growth Qtr Over Qtr",
            over_pct("fa_salesqoq", ["5", "10", "15", "20", "25", "30"]),
        ),
        (
            "Fundamental",
            "sales_growth_past_5y",
            "Sales Growth Past 5 Years",
            over_pct("fa_sales5years", ["5", "10", "15", "20", "25", "30"]),
        ),
        (
            "Fundamental",
            "sales_growth_this_year",
            "Sales Growth This Year",
            over_pct("fa_salesyoy", ["5", "10", "15", "20", "25", "30"]),
        ),
        (
            "Fundamental",
            "roe",
            "Return on Equity",
            over_pct("fa_roe", ["5", "10", "15", "20", "25", "30"]),
        ),
        (
            "Fundamental",
            "roa",
            "Return on Assets",
            over_pct("fa_roa", ["5", "10", "15", "20", "25"]),
        ),
        (
            "Fundamental",
            "roi",
            "Return on Investment",
            over_pct("fa_roi", ["5", "10", "15", "20", "25", "30"]),
        ),
        (
            "Fundamental",
            "gross_margin",
            "Gross Margin",
            over_pct("fa_grossmargin", ["10", "20", "30", "40", "50", "60"]),
        ),
        (
            "Fundamental",
            "operating_margin",
            "Operating Margin",
            over_pct("fa_opermargin", ["5", "10", "15", "20", "25", "30"]),
        ),
        (
            "Fundamental",
            "net_margin",
            "Net Profit Margin",
            over_pct("fa_netmargin", ["5", "10", "15", "20", "25", "30"]),
        ),
        (
            "Fundamental",
            "debt_equity",
            "Debt/Equity",
            under_over("fa_debteq", ["0.1", "0.5", "1", "2"]),
        ),
        (
            "Fundamental",
            "current_ratio",
            "Current Ratio",
            under_over("fa_curratio", ["0.5", "1", "1.5", "2", "3"]),
        ),
        (
            "Fundamental",
            "quick_ratio",
            "Quick Ratio",
            under_over("fa_quickratio", ["0.5", "1", "1.5", "2", "3"]),
        ),
        (
            "Fundamental",
            "insider_ownership",
            "Insider Ownership",
            over_pct("sh_insiderown", ["5", "10", "20", "30", "40", "50"]),
        ),
        (
            "Fundamental",
            "institutional_ownership",
            "Institutional Ownership",
            over_pct("sh_instown", ["10", "20", "30", "40", "50", "60", "70", "80", "90"]),
        ),
        (
            "Technical",
            "sma20",
            "20-Day SMA",
            [("Price above SMA20", "ta_sma20_pa"), ("Price below SMA20", "ta_sma20_pb")],
        ),
        (
            "Technical",
            "sma50",
            "50-Day SMA",
            [("Price above SMA50", "ta_sma50_pa"), ("Price below SMA50", "ta_sma50_pb")],
        ),
        (
            "Technical",
            "sma200",
            "200-Day SMA",
            [("Price above SMA200", "ta_sma200_pa"), ("Price below SMA200", "ta_sma200_pb")],
        ),
        (
            "Technical",
            "perf_week",
            "Performance Week",
            under_over_pct("ta_perf1w", ["5", "10", "20"]),
        ),
        (
            "Technical",
            "perf4w",
            "Performance Month",
            under_over_pct("ta_perf4w", ["5", "8", "10", "20", "30"]),
        ),
        (
            "Technical",
            "perf13w",
            "Performance Quarter",
            under_over_pct("ta_perf13w", ["5", "10", "20", "30"]),
        ),
        (
            "Technical",
            "perf26w",
            "Performance Half Year",
            under_over_pct("ta_perf26w", ["5", "10", "20", "30", "50"]),
        ),
        (
            "Technical",
            "perf52w",
            "Performance Year",
            under_over_pct("ta_perf52w", ["5", "10", "20", "30", "50", "100"]),
        ),
        (
            "Technical",
            "daily_change",
            "Daily Change",
            under_over_pct("ta_change", ["1", "2", "3", "4", "5", "10"]),
        ),
        (
            "Technical",
            "rsi",
            "RSI",
            [
                ("Oversold 20", "ta_rsi_os20"),
                ("Oversold 30", "ta_rsi_os30"),
                ("Overbought 70", "ta_rsi_ob70"),
                ("Overbought 80", "ta_rsi_ob80"),
            ],
        ),
        (
            "Technical",
            "gap",
            "Gap",
            [
                ("Up", "ta_gap_u"),
                ("Down", "ta_gap_d"),
                ("Up 5%", "ta_gap_u5"),
                ("Down 5%", "ta_gap_d5"),
            ],
        ),
    ]
    return [
        FinvizFilterControl(
            category=category,
            key=key,
            label=label,
            choices=[any_choice(), *choices(choice_rows)],
        )
        for category, key, label, choice_rows in controls
    ]


def save_finviz_preset(
    request: FinvizPresetSaveRequest, *, settings: Settings | None = None
) -> FinvizScreenerPreset:
    """Persist a custom Finviz preset in local artifacts."""

    settings = settings or get_settings()
    name = request.name.strip()
    if not name:
        raise ValueError("Preset name is required.")
    builtin_names = {screener.name.lower() for screener in load_finviz_screeners()}
    if name.lower() in builtin_names:
        raise ValueError("Use a different name from the built-in presets.")
    filters = normalize_filter_codes(request.filters)
    if not filters:
        raise ValueError("At least one filter is required to save a preset.")
    preset = FinvizScreenerPreset(
        name=name,
        purpose=request.purpose.strip() or "Operator-saved Finviz screener preset.",
        filters=filters,
        order_by=request.order_by,
        order_direction=request.order_direction,
        signal=request.signal,
        tickers=request.tickers.strip().upper(),
        custom=True,
        url=build_finviz_url(
            filters,
            order_by=request.order_by,
            order_direction=request.order_direction,
            signal=request.signal,
            tickers=request.tickers,
        ),
    )
    custom_presets = [
        existing
        for existing in _load_custom_presets(settings)
        if existing.name.lower() != preset.name.lower()
    ]
    custom_presets.append(preset)
    _write_custom_presets(settings, custom_presets)
    return preset


def finviz_column_options() -> list[FinvizColumnOption]:
    """Return sorted selectable result columns grouped like Finviz tabs."""

    rows = [
        ("Descriptive", "Ticker"),
        ("Descriptive", "Company"),
        ("Descriptive", "Sector"),
        ("Descriptive", "Industry"),
        ("Descriptive", "Country"),
        ("Descriptive", "Market Cap"),
        ("Fundamental", "P/E"),
        ("Fundamental", "Forward P/E"),
        ("Fundamental", "PEG"),
        ("Fundamental", "P/S"),
        ("Fundamental", "P/B"),
        ("Fundamental", "P/C"),
        ("Fundamental", "P/FCF"),
        ("Fundamental", "EV/EBITDA"),
        ("Fundamental", "EPS this Y"),
        ("Fundamental", "EPS next Y"),
        ("Fundamental", "EPS past 5Y"),
        ("Fundamental", "EPS next 5Y"),
        ("Fundamental", "Sales past 5Y"),
        ("Fundamental", "Sales Q/Q"),
        ("Fundamental", "EPS Q/Q"),
        ("Fundamental", "ROE"),
        ("Fundamental", "ROA"),
        ("Fundamental", "ROI"),
        ("Fundamental", "Gross Margin"),
        ("Fundamental", "Operating Margin"),
        ("Fundamental", "Net Profit Margin"),
        ("Fundamental", "Debt/Eq"),
        ("Technical", "Price"),
        ("Technical", "Change"),
        ("Technical", "Volume"),
        ("Technical", "Perf Week"),
        ("Technical", "Perf Month"),
        ("Technical", "Perf Quarter"),
        ("Technical", "Perf Half Y"),
        ("Technical", "Perf Year"),
        ("Technical", "SMA20"),
        ("Technical", "SMA50"),
        ("Technical", "SMA200"),
        ("Technical", "RSI"),
    ]
    return [
        FinvizColumnOption(category=category, key=label, label=label)
        for category, label in sorted(rows, key=lambda item: (item[0], item[1]))
    ]


def run_finviz_workbench_screener(
    request: FinvizScreenerRunRequest,
    *,
    settings: Settings | None = None,
    fetcher: FinvizFetcher | None = None,
    fixture_html: str | None = None,
) -> FinvizWorkbenchResult:
    """Run one operator-configured screener and return table rows plus candidates."""

    settings = settings or get_settings()
    filters = normalize_filter_codes(request.filters)
    screener = FinvizScreenerConfig(
        name=request.name.strip() or "Custom Finviz Screener",
        purpose=request.purpose.strip() or "Operator-configured Finviz discovery run.",
        url=HttpUrl(
            build_finviz_url(
                filters,
                order_by=request.order_by,
                order_direction=request.order_direction,
                signal=request.signal,
                tickers=request.tickers,
            )
        ),
    )
    html = fixture_html
    warnings: list[str] = []
    if html is None and request.use_fixtures:
        html = _load_first_fixture_html()
    if html is None:
        cache_dir = Path(settings.artifacts_path) / "finviz_cache"
        html = (fetcher or FinvizFetcher(cache_dir=cache_dir)).fetch(
            screener,
            force_refresh=request.force_refresh,
        )

    rows = parse_finviz_html(html)
    if not rows:
        warnings.append(f"{screener.name}: no parseable ticker rows")

    discovery = CandidateIntakeService(
        screeners=[screener],
        fetcher=fetcher,
        settings=settings,
    ).run(
        fixture_html_by_screener={screener.name: html},
        force_refresh=request.force_refresh,
    )
    warnings.extend(discovery.warnings)
    table_rows = [_table_row(row) for row in rows]
    discovered_at = now_utc()
    run_id = sha256_digest(
        {
            "name": screener.name,
            "filters": filters,
            "discovered_at_utc": discovered_at.isoformat(),
            "count": len(table_rows),
        }
    )[:16]
    result = FinvizScreenerRunResult(
        run_id=run_id,
        discovered_at_utc=discovered_at.isoformat(),
        name=screener.name,
        purpose=screener.purpose,
        url=str(screener.url),
        filters=filters,
        filter_labels=_labels_for_filters(filters),
        rows=table_rows,
        candidates=discovery.candidates,
        warnings=warnings,
    )
    return FinvizWorkbenchResult(screener=result, discovery=discovery)


def build_finviz_url(
    filters: list[str],
    *,
    order_by: str = "PEG",
    order_direction: str = "asc",
    signal: str = "none",
    tickers: str = "",
) -> str:
    """Build one Finviz screener URL from filter codes."""

    query = {"v": "121", "f": ",".join(normalize_filter_codes(filters)), "ft": "2"}
    sort_code = _sort_code(order_by)
    if sort_code:
        query["o"] = f"-{sort_code}" if order_direction.lower() == "desc" else sort_code
    if signal and signal != "none":
        query["s"] = signal
    if tickers.strip():
        query["t"] = tickers.strip().upper()
    return f"{FINVIZ_BASE_URL}?{urlencode(query)}"


def parse_filter_codes(url: str) -> list[str]:
    """Extract Finviz filter codes from a screener URL."""

    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("f", [])
    if not values:
        return []
    return normalize_filter_codes(values[0].split(","))


def normalize_filter_codes(filters: list[str]) -> list[str]:
    """Normalize filter codes while preserving operator-selected order."""

    seen: set[str] = set()
    normalized: list[str] = []
    for item in filters:
        code = item.strip().lower()
        if not code or code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized


def _labels_for_filters(filters: list[str]) -> list[str]:
    labels_by_code = {option.code: option.label for option in finviz_filter_options()}
    return [labels_by_code.get(code, code) for code in filters]


def _sort_code(label: str) -> str:
    sort_codes = {
        "Ticker": "ticker",
        "Market Cap": "marketcap",
        "P/E": "pe",
        "Forward P/E": "forwardpe",
        "PEG": "peg",
        "P/S": "ps",
        "P/B": "pb",
        "P/C": "pc",
        "P/FCF": "pfcf",
        "EV/EBITDA": "evebitda",
        "Price": "price",
        "Change": "change",
        "Volume": "volume",
    }
    return sort_codes.get(label, "")


def _table_row(row: ParsedFinvizRow) -> FinvizScreenerTableRow:
    fields = dict(row.raw_fields)
    fields.pop("Finviz Profile", None)
    valuation = {
        field: fields.get(field, "") for field in PRINCIPAL_VALUATION_FIELDS if fields.get(field)
    }
    return FinvizScreenerTableRow(
        rank=row.rank,
        symbol=row.symbol,
        profile_url=row.profile_url or finviz_profile_url(row.symbol),
        fields=fields,
        valuation=valuation,
    )


def _load_first_fixture_html() -> str:
    fixture_dir = Path("tests/fixtures")
    for file_name in (
        "finviz_elite_garp.html",
        "finviz_hidden_compounders.html",
        "finviz_post_earnings.html",
    ):
        path = fixture_dir / file_name
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def _custom_presets_path(settings: Settings) -> Path:
    return Path(settings.artifacts_path) / "finviz_custom_presets.json"


def _load_custom_presets(settings: Settings) -> list[FinvizScreenerPreset]:
    path = _custom_presets_path(settings)
    if not path.exists():
        return []
    try:
        payload = path.read_text(encoding="utf-8")
        return [FinvizScreenerPreset.model_validate(item) for item in json.loads(payload)]
    except (OSError, ValueError, TypeError):
        return []


def _write_custom_presets(settings: Settings, presets: list[FinvizScreenerPreset]) -> None:
    path = _custom_presets_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        preset.model_dump(mode="json")
        for preset in sorted(presets, key=lambda item: item.name.lower())
    ]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
