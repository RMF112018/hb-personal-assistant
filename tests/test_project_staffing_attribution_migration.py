"""V81 attribution reshape migration tests (cost_code+category model)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.store.migrator import (
    LATEST_SCHEMA_VERSION,
    SQLiteMigrator,
    StaffingMigrationError,
)

_RULES = "forecast_project_staffing_attribution_rules"
_REVIEW = "forecast_project_staffing_attribution_review_items"


def _db(td: str) -> str:
    path = Path(td) / "v81.db"
    SQLiteMigrator(db_path=str(path)).apply()
    return str(path)


def _cols(db: str, table: str) -> set[str]:
    with sqlite3.connect(db) as conn:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_v81_version_and_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION >= 81


def test_v81_reshaped_columns() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        rule_cols = _cols(db, _RULES)
        assert "employee_name_source" not in rule_cols
        assert "employee_name_normalized" not in rule_cols
        assert {"cost_code", "category", "staffing_config_id", "match_source"} <= rule_cols
        review_cols = _cols(db, _REVIEW)
        assert "employee_name_source" not in review_cols
        assert "description_label" in review_cols
        assert {"cost_code", "category", "review_status"} <= review_cols


def test_v81_contract_count_unchanged() -> None:
    import json

    contract = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
        ).read_text()
    )
    assert contract["table_count"] == len(contract["tables"]) == 475
    assert contract["tables"][_RULES]["v"] == "V81"
    assert contract["tables"][_REVIEW]["v"] == "V81"


def test_v81_aborts_if_nonempty() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        # Seed a config + a rule, then force the v81 block to run again with data present.
        with sqlite3.connect(db) as conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute(
                f"INSERT INTO {_RULES} (attribution_rule_id, project_key, cost_code, category, "
                "staffing_config_id, match_source, active_status, created_utc, updated_utc) "
                "VALUES ('r1','tropical','01-100','LAB','c1','manual','active','t','t')"
            )
            conn.execute("DELETE FROM schema_migrations WHERE version = 81")
            conn.commit()
        with pytest.raises(StaffingMigrationError):
            SQLiteMigrator(db_path=db).apply()
