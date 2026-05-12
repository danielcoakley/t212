"""Finviz HTML parsing with graceful layout-change handling."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from isa_system.discovery.models import ParsedFinvizRow

BLOCKED_MARKERS = (
    "access denied",
    "forbidden",
    "captcha",
    "blocked",
    "too many requests",
)


DEFAULT_FINVIZ_COLUMNS = [
    "No.",
    "Ticker",
    "Company",
    "Sector",
    "Industry",
    "Country",
    "Market Cap",
    "P/E",
    "Price",
    "Change",
    "Volume",
]


@dataclass
class _FinvizCell:
    text_parts: list[str] = field(default_factory=list)
    symbol: str | None = None
    href: str | None = None
    attrs: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return _clean_text(" ".join(self.text_parts))


class _FinvizTickerParser(HTMLParser):
    """Extract ticker symbols and best-effort table cells from Finviz HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.symbols: list[str] = []
        self.rows: list[list[_FinvizCell]] = []
        self.headers: list[str] = []
        self._current_row: list[_FinvizCell] | None = None
        self._current_cell: _FinvizCell | None = None
        self._table_depth = 0
        self._screener_table_depth: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Capture ticker symbols encoded in quote links."""

        tag_name = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag_name == "table":
            self._table_depth += 1
            classes = attrs_dict.get("class", "")
            if "screener_table" in classes.split():
                self._screener_table_depth = self._table_depth
            return
        if tag_name == "tr" and self._inside_screener_table:
            self._finish_current_row()
            self._current_row = []
            return
        if tag_name in {"td", "th"} and self._current_row is not None:
            self._current_cell = _FinvizCell(attrs=attrs_dict)
            return
        if tag_name != "a":
            return

        href = attrs_dict.get("href", "")
        symbol = _symbol_from_href(href)
        if symbol:
            self.symbols.append(symbol)
            if self._current_cell is not None:
                self._current_cell.symbol = symbol
                self._current_cell.href = href

    def handle_data(self, data: str) -> None:
        """Collect cell text."""

        if self._current_cell is not None:
            self._current_cell.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Close rows/cells and detect the nearest table header."""

        tag_name = tag.lower()
        if tag_name in {"td", "th"} and self._current_row is not None:
            if self._current_cell is not None:
                self._current_row.append(self._current_cell)
            self._current_cell = None
            return
        if tag_name in {"thead", "tbody", "table"}:
            self._finish_current_row()
        if tag_name == "table":
            if self._screener_table_depth == self._table_depth:
                self._screener_table_depth = None
            self._table_depth = max(0, self._table_depth - 1)
            return
        if tag_name != "tr" or self._current_row is None:
            return

        self._finish_current_row()

    def _finish_current_row(self) -> None:
        """Close the current row; Finviz sometimes omits explicit </tr> tags."""

        if self._current_row is None:
            return
        cells = [cell for cell in self._current_row if cell.text or cell.symbol]
        if cells:
            if any(cell.symbol for cell in cells):
                self.rows.append(cells)
            else:
                header_cells = [cell.text for cell in cells if cell.text]
                if _looks_like_header(header_cells):
                    self.headers = header_cells
        self._current_row = None
        self._current_cell = None

    @property
    def _inside_screener_table(self) -> bool:
        return (
            self._screener_table_depth is not None
            and self._table_depth >= self._screener_table_depth
        )


def parse_finviz_html(html: str) -> list[ParsedFinvizRow]:
    """Parse ticker rows from Finviz HTML without raising on blocked/empty pages."""

    if not html or _looks_blocked(html):
        return []

    parser = _FinvizTickerParser()
    try:
        parser.feed(html)
    except Exception:
        return []

    parsed_rows = _rows_from_table(parser.rows, parser.headers)
    if not parsed_rows:
        parsed_rows = [
            ParsedFinvizRow(symbol=normalize_symbol(symbol), rank=index + 1)
            for index, symbol in enumerate(parser.symbols)
        ]

    seen: set[str] = set()
    deduped: list[ParsedFinvizRow] = []
    for row in parsed_rows:
        normalized = normalize_symbol(row.symbol)
        if normalized in seen:
            continue
        seen.add(normalized)
        raw_fields = dict(row.raw_fields)
        raw_fields.setdefault("Ticker", normalized)
        deduped.append(
            ParsedFinvizRow(
                symbol=normalized,
                rank=row.rank or len(deduped) + 1,
                raw_fields=raw_fields,
                profile_url=row.profile_url or finviz_profile_url(normalized),
            )
        )
    return deduped


def normalize_symbol(symbol: str) -> str:
    """Normalize a discovered ticker symbol for symbol-level dedupe."""

    return symbol.strip().upper().replace("-", ".")


def finviz_profile_url(symbol: str) -> str:
    """Return the Finviz profile URL for a normalized symbol."""

    return f"https://finviz.com/quote.ashx?t={normalize_symbol(symbol)}&p=d"


def _looks_blocked(html: str) -> bool:
    lower = html.lower()
    return any(marker in lower for marker in BLOCKED_MARKERS)


def _symbol_from_href(href: str) -> str | None:
    match = re.search(r"(?:[?&]t=|quote\.ashx\?t=)([A-Za-z0-9.\-]+)", href)
    if not match:
        return None
    return match.group(1)


def _rows_from_table(rows: list[list[_FinvizCell]], headers: list[str]) -> list[ParsedFinvizRow]:
    parsed_rows: list[ParsedFinvizRow] = []
    for row in rows:
        symbol_cells = [cell for cell in row if cell.symbol]
        symbol_cell = next(
            (
                cell
                for cell in symbol_cells
                if cell.symbol is not None
                and normalize_symbol(cell.text) == normalize_symbol(cell.symbol)
            ),
            symbol_cells[0] if symbol_cells else None,
        )
        if symbol_cell is None or symbol_cell.symbol is None:
            continue
        symbol = normalize_symbol(symbol_cell.symbol)
        columns = _columns_for_row(headers, len(row))
        raw_fields = {
            _column_name(columns, index): cell.text or normalize_symbol(cell.symbol or "")
            for index, cell in enumerate(row)
        }
        raw_fields.update(_metadata_fields(symbol_cell))
        raw_fields["Ticker"] = symbol
        rank = _parse_rank(raw_fields)
        parsed_rows.append(
            ParsedFinvizRow(
                symbol=symbol,
                rank=rank or len(parsed_rows) + 1,
                raw_fields=raw_fields,
                profile_url=finviz_profile_url(symbol),
            )
        )
    return parsed_rows


def _columns_for_row(headers: list[str], length: int) -> list[str]:
    if len(headers) == length:
        return [_normalize_header(header) for header in headers]
    if length <= len(DEFAULT_FINVIZ_COLUMNS):
        return DEFAULT_FINVIZ_COLUMNS[:length]
    return [*DEFAULT_FINVIZ_COLUMNS, *[f"Field {index}" for index in range(12, length + 1)]]


def _column_name(columns: list[str], index: int) -> str:
    if index < len(columns):
        return columns[index]
    return f"Field {index + 1}"


def _parse_rank(raw_fields: dict[str, str]) -> int | None:
    for key in ("No.", "No", "#"):
        value = raw_fields.get(key)
        if not value:
            continue
        match = re.search(r"\d+", value)
        if match:
            return int(match.group(0))
    return None


def _looks_like_header(cells: list[str]) -> bool:
    header_text = {cell.lower() for cell in cells}
    return bool({"ticker", "company", "sector", "p/e", "market cap"} & header_text)


def _normalize_header(header: str) -> str:
    text = _clean_text(header)
    aliases = {
        "market cap.": "Market Cap",
        "eps this y": "EPS this Y",
        "eps next y": "EPS next Y",
        "eps past 5y": "EPS past 5Y",
        "eps next 5y": "EPS next 5Y",
        "sales past 5y": "Sales past 5Y",
    }
    if text.lower() in {"no", "#"}:
        return "No."
    if text.lower() in {"ticker", "symbol"}:
        return "Ticker"
    return aliases.get(text.lower(), text)


def _metadata_fields(symbol_cell: _FinvizCell) -> dict[str, str]:
    metadata = {
        "Company": symbol_cell.attrs.get("data-boxover-company", ""),
        "Industry": symbol_cell.attrs.get("data-boxover-industry", ""),
        "Country": symbol_cell.attrs.get("data-boxover-country", ""),
    }
    return {key: _clean_text(value) for key, value in metadata.items() if value}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
