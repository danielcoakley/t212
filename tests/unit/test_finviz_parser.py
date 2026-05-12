"""Finviz parser tests."""

from __future__ import annotations

from pathlib import Path

from isa_system.discovery.finviz_parser import parse_finviz_html


def test_parse_ticker_symbols_from_fixture_html() -> None:
    """Parser extracts symbols from Finviz quote links."""

    html = Path("tests/fixtures/finviz_elite_garp.html").read_text(encoding="utf-8")

    rows = parse_finviz_html(html)

    assert [row.symbol for row in rows] == ["AAPL", "MSFT", "NVDA"]
    assert [row.rank for row in rows] == [1, 2, 3]
    assert rows[0].profile_url == "https://finviz.com/quote.ashx?t=AAPL&p=d"


def test_blocked_or_empty_html_returns_no_rows() -> None:
    """Blocked or empty pages are handled gracefully."""

    assert parse_finviz_html("") == []
    assert parse_finviz_html("<html><title>Access denied</title>captcha</html>") == []


def test_parse_full_finviz_table_fields() -> None:
    """Parser keeps full screener-table fields when Finviz exposes them."""

    html = """
    <html><body>
      <table class="screener_table">
        <tr>
          <th>No.</th><th>Ticker</th><th>Company</th><th>Sector</th>
          <th>Industry</th><th>Country</th><th>Market Cap</th>
          <th>P/E</th><th>Forward P/E</th><th>PEG</th><th>Price</th>
        </tr>
        <tr>
          <td>1</td><td><a href="quote.ashx?t=MSFT&p=d">MSFT</a></td>
          <td>Microsoft Corporation</td><td>Technology</td><td>Software</td>
          <td>USA</td><td>3.1T</td><td>36.2</td><td>28.4</td><td>2.1</td><td>420.20</td>
        </tr>
      </table>
    </body></html>
    """

    rows = parse_finviz_html(html)

    assert len(rows) == 1
    assert rows[0].symbol == "MSFT"
    assert rows[0].raw_fields["Company"] == "Microsoft Corporation"
    assert rows[0].raw_fields["Market Cap"] == "3.1T"
    assert rows[0].raw_fields["Forward P/E"] == "28.4"


def test_parse_live_valuation_table_shape_and_metadata() -> None:
    """Parser ignores filter-form rows and maps valuation columns correctly."""

    html = """
    <html><body>
      <table>
        <tr><td>P/E</td><td>Any Under 20 Under 40</td><td>Forward P/E</td><td>Any</td></tr>
      </table>
      <table class="styled-table-new screener_table">
        <thead>
          <tr>
            <th>No.</th><th>Ticker</th><th>Market Cap</th><th>P/E</th>
            <th>Forward P/E</th><th>PEG</th><th>P/S</th><th>P/B</th>
            <th>P/C</th><th>P/FCF</th><th>EPS This Y</th><th>EPS Next Y</th>
            <th>EPS Past 5Y</th><th>EPS Next 5Y</th><th>Sales Past 5Y</th>
            <th>Price</th><th>Change</th><th>Volume</th>
          </tr>
        </thead>
        <tr>
          <td>1</td>
          <td data-boxover-company="Micron Technology Inc"
              data-boxover-industry="Semiconductors"
              data-boxover-country="USA"><a href="quote?t=MU&ty=c&p=d&b=1">MU</a></td>
          <td>896.92B</td><td>37.55</td><td>8.15</td><td>0.07</td><td>15.43</td>
          <td>12.38</td><td>61.37</td><td>87.24</td><td>599.28%</td>
          <td>68.40%</td><td>26.19%</td><td>117.74%</td><td>11.76%</td>
          <td>795.33</td><td>6.50%</td><td>70,971,680</td>
        </tr>
      </table>
    </body></html>
    """

    rows = parse_finviz_html(html)

    assert len(rows) == 1
    fields = rows[0].raw_fields
    assert fields["Ticker"] == "MU"
    assert fields["Company"] == "Micron Technology Inc"
    assert fields["Industry"] == "Semiconductors"
    assert fields["Country"] == "USA"
    assert fields["Market Cap"] == "896.92B"
    assert fields["P/E"] == "37.55"
    assert fields["Forward P/E"] == "8.15"
    assert fields["EPS this Y"] == "599.28%"
    assert fields["Volume"] == "70,971,680"
