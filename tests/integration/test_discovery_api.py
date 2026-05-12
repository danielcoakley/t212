"""Discovery API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from isa_system.api.main import app


def test_discovery_run_and_candidates_latest_from_fixtures() -> None:
    """Discovery routes produce and expose deduplicated fixture candidates."""

    client = TestClient(app)

    run_response = client.post("/discovery/run", json={"use_fixtures": True})
    candidates_response = client.get("/candidates/latest")

    assert run_response.status_code == 200
    assert candidates_response.status_code == 200
    run_payload = run_response.json()
    candidates_payload = candidates_response.json()
    assert len(run_payload["candidates"]) == 7
    assert len(candidates_payload) == 7
    assert any(candidate["symbol"] == "MSFT" for candidate in candidates_payload)


def test_finviz_screener_settings_and_fixture_run() -> None:
    """Configurable Finviz screener route exposes settings and table rows."""

    client = TestClient(app)

    settings_response = client.get("/discovery/finviz/settings")
    assert settings_response.status_code == 200
    settings_payload = settings_response.json()
    assert {preset["name"] for preset in settings_payload["presets"]} >= {
        "Elite GARP Compounders",
        "Hidden Compounders",
    }
    assert any(option["code"] == "fa_pe_u40" for option in settings_payload["filter_options"])
    assert any(
        control["label"] == "P/E" and control["category"] == "Fundamental"
        for control in settings_payload["filter_controls"]
    )
    assert any(
        column["key"] == "Forward P/E" and column["category"] == "Fundamental"
        for column in settings_payload["column_options"]
    )

    run_response = client.post(
        "/discovery/finviz/screener",
        json={
            "name": "Test Screener",
            "filters": ["cap_smallover", "fa_pe_u40", "ta_sma50_pa"],
            "order_by": "PEG",
            "order_direction": "asc",
            "use_fixtures": True,
        },
    )

    assert run_response.status_code == 200
    payload = run_response.json()
    assert "fa_pe_u40" in payload["filters"]
    assert "v=121" in payload["url"]
    assert "o=peg" in payload["url"]
    assert payload["rows"][0]["symbol"] == "AAPL"
    assert payload["rows"][0]["profile_url"] == "https://finviz.com/quote.ashx?t=AAPL&p=d"
    assert payload["candidates"][0]["symbol"] == "AAPL"


def test_finviz_custom_preset_can_be_saved(monkeypatch, tmp_path) -> None:
    """Custom Finviz presets persist to local artifacts and reload in settings."""

    monkeypatch.setenv("ISA_ARTIFACTS_PATH", str(tmp_path))
    from isa_system.settings import clear_settings_cache

    clear_settings_cache()
    client = TestClient(app)

    save_response = client.post(
        "/discovery/finviz/presets",
        json={
            "name": "Operator GARP Test",
            "filters": ["cap_smallover", "fa_pe_u40", "fa_peg_u1"],
            "order_by": "PEG",
            "order_direction": "asc",
        },
    )
    settings_response = client.get("/discovery/finviz/settings")
    clear_settings_cache()

    assert save_response.status_code == 200
    payload = save_response.json()
    assert payload["custom"] is True
    assert payload["filters"] == ["cap_smallover", "fa_pe_u40", "fa_peg_u1"]
    assert settings_response.status_code == 200
    assert "Operator GARP Test" in {
        preset["name"] for preset in settings_response.json()["presets"]
    }
