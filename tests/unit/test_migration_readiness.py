"""Release-readiness checks for operational DB migrations."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "src" / "isa_system" / "db" / "migrations"
PAPER_CYCLES_MIGRATION = MIGRATIONS_DIR / "versions" / "0003_paper_cycles.py"
HEALTH_REPORTS_MIGRATION = MIGRATIONS_DIR / "versions" / "0006_holding_health_reports.py"


def test_paper_cycle_migration_is_discoverable_in_alembic_chain() -> None:
    """Alembic can find the paper-cycle migration in the packaged script directory."""

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(config)

    revision = script.get_revision("0003_paper_cycles")
    discovered_revisions = {item.revision for item in script.walk_revisions()}

    assert revision is not None
    assert Path(revision.path).name == PAPER_CYCLES_MIGRATION.name
    assert revision.down_revision == "0002_research_reviews"
    assert "0003_paper_cycles" in discovered_revisions


def test_holding_health_migration_is_discoverable_in_alembic_chain() -> None:
    """Alembic can find the holding-health report migration."""

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(config)

    revision = script.get_revision("0006_holding_health_reports")
    discovered_revisions = {item.revision for item in script.walk_revisions()}

    assert revision is not None
    assert Path(revision.path).name == HEALTH_REPORTS_MIGRATION.name
    assert revision.down_revision == "0005_research_reports"
    assert "0006_holding_health_reports" in discovered_revisions


def test_paper_cycle_migration_declares_expected_tables_indexes_and_downgrade() -> None:
    """The paper-cycle migration keeps the persisted evidence schema easy to audit."""

    tree = ast.parse(PAPER_CYCLES_MIGRATION.read_text(encoding="utf-8"))

    create_tables = _create_tables(tree)
    indexes = _create_indexes(tree)
    drop_tables = _drop_tables(tree)
    drop_indexes = _drop_indexes(tree)

    assert set(create_tables) == {
        "paper_cycles",
        "paper_intents",
        "paper_simulated_fills",
    }
    assert create_tables["paper_cycles"] >= {
        "id",
        "mode",
        "source_kind",
        "preview_source_hash",
        "simulation_hash",
        "workflow_status",
        "expected_vs_simulated_status",
        "selected_count",
        "preview_eligible_count",
        "simulated_fill_count",
        "total_expected_notional_gbp",
        "total_simulated_notional_gbp",
        "total_simulated_fees_gbp",
        "generated_at_utc",
        "warnings_json",
        "workflow_json",
        "created_at_utc",
    }
    assert create_tables["paper_intents"] >= {
        "id",
        "paper_cycle_id",
        "row_index",
        "symbol",
        "research_symbol",
        "broker_ticker",
        "side",
        "preview_eligible",
        "target_weight",
        "expected_notional_gbp",
        "expected_fees_gbp",
        "simulated_status",
        "expected_vs_simulated_status",
        "research_review_status",
        "blockers_json",
        "warnings_json",
        "next_action",
        "preview_row_hash",
        "created_at_utc",
    }
    assert create_tables["paper_simulated_fills"] >= {
        "id",
        "paper_cycle_id",
        "paper_intent_id",
        "simulated_fill_index",
        "symbol",
        "side",
        "source_kind",
        "status",
        "quantity",
        "fill_price_account",
        "notional_gbp",
        "estimated_fees_gbp",
        "notional_source_kind",
        "quantity_source_kind",
        "fill_price_source_kind",
        "note",
        "created_at_utc",
    }
    assert indexes >= {
        ("ix_paper_cycles_preview_source_hash", "paper_cycles", ("preview_source_hash",)),
        ("ix_paper_cycles_simulation_hash", "paper_cycles", ("simulation_hash",)),
        ("ix_paper_intents_cycle", "paper_intents", ("paper_cycle_id",)),
        ("ix_paper_intents_research_symbol", "paper_intents", ("research_symbol",)),
        ("ix_paper_simulated_fills_cycle", "paper_simulated_fills", ("paper_cycle_id",)),
        ("ix_paper_simulated_fills_intent", "paper_simulated_fills", ("paper_intent_id",)),
    }
    assert drop_tables == {"paper_cycles", "paper_intents", "paper_simulated_fills"}
    assert {
        name
        for name, table_name in drop_indexes
        if table_name in {"paper_cycles", "paper_intents", "paper_simulated_fills"}
    } == {name for name, _, _ in indexes}


def _create_tables(tree: ast.AST) -> dict[str, set[str]]:
    tables: dict[str, set[str]] = {}
    for call in _operation_calls(tree, "create_table"):
        table_name = _literal_arg(call, 0)
        if table_name is None:
            continue
        columns = {
            column_name
            for arg in call.args[1:]
            if isinstance(arg, ast.Call)
            for column_name in [_column_name(arg)]
            if column_name is not None
        }
        tables[table_name] = columns
    return tables


def _create_indexes(tree: ast.AST) -> set[tuple[str, str, tuple[str, ...]]]:
    indexes: set[tuple[str, str, tuple[str, ...]]] = set()
    for call in _operation_calls(tree, "create_index"):
        index_name = _literal_arg(call, 0)
        table_name = _literal_arg(call, 1)
        columns = _literal_list_arg(call, 2)
        if index_name is not None and table_name is not None and columns is not None:
            indexes.add((index_name, table_name, tuple(columns)))
    return indexes


def _drop_tables(tree: ast.AST) -> set[str]:
    return {
        table_name
        for call in _operation_calls(tree, "drop_table")
        for table_name in [_literal_arg(call, 0)]
        if table_name is not None
    }


def _drop_indexes(tree: ast.AST) -> set[tuple[str, str | None]]:
    drops: set[tuple[str, str | None]] = set()
    for call in _operation_calls(tree, "drop_index"):
        index_name = _literal_arg(call, 0)
        table_name = _literal_keyword(call, "table_name")
        if index_name is not None:
            drops.add((index_name, table_name))
    return drops


def _operation_calls(tree: ast.AST, operation_name: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _attribute_name(node.func) == operation_name
    ]


def _column_name(call: ast.Call) -> str | None:
    if _attribute_name(call.func) != "Column":
        return None
    return _literal_arg(call, 0)


def _attribute_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _literal_arg(call: ast.Call, index: int) -> str | None:
    if len(call.args) <= index:
        return None
    value = _literal(call.args[index])
    return value if isinstance(value, str) else None


def _literal_list_arg(call: ast.Call, index: int) -> list[str] | None:
    if len(call.args) <= index:
        return None
    value = _literal(call.args[index])
    return (
        value if isinstance(value, list) and all(isinstance(item, str) for item in value) else None
    )


def _literal_keyword(call: ast.Call, keyword_name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            value = _literal(keyword.value)
            return value if isinstance(value, str) else None
    return None


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None
