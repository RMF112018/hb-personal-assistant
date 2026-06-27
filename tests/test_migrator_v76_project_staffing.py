"""V76 Project Staffing foundation migration tests (schema + holiday seed)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.store.forecast_staffing_tables import V76_TABLES
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_SEEDED_TABLES = {"staffing_holiday_calendars", "staffing_holiday_calendar_dates"}
_EMPTY_TABLES = tuple(t for t in V76_TABLES if t not in _SEEDED_TABLES)


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _indexes(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}


def test_v76_version_and_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    assert _migrate(db) == LATEST_SCHEMA_VERSION >= 76
    # Re-apply must not error and must land on the same version (self-heal safe).
    assert _migrate(db) == LATEST_SCHEMA_VERSION


def test_v76_all_staffing_tables_present(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    _migrate(db)
    with sqlite3.connect(db) as conn:
        present = _tables(conn)
    assert len(V76_TABLES) == 13
    for table in V76_TABLES:
        assert table in present, table


def test_v76_key_indexes_present(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    _migrate(db)
    with sqlite3.connect(db) as conn:
        idx = _indexes(conn)
    for expected in (
        "idx_forecast_project_staffing_config_project",
        "idx_forecast_project_staffing_config_cost_code",
        "idx_forecast_project_staffing_config_person",
        "idx_forecast_project_staffing_config_template",
        "idx_staffing_holiday_calendar_dates_calendar_year",
    ):
        assert expected in idx, expected


def test_v76_matrix_row_staffing_columns_added(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    _migrate(db)
    with sqlite3.connect(db) as conn:
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(forecast_output_monthly_table_rows)")
        }
    for col in (
        "row_type",
        "staffing_config_id",
        "role_title",
        "person_name",
        "employee_name_normalized",
        "source_budget_code_key",
        "attribution_status",
    ):
        assert col in cols, col


def test_v76_non_seeded_tables_ship_empty(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    _migrate(db)
    with sqlite3.connect(db) as conn:
        for table in _EMPTY_TABLES:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == 0, f"{table} should ship empty, found {count}"


def test_v76_default_holiday_calendar_seeded(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    _migrate(db)
    with sqlite3.connect(db) as conn:
        cal = conn.execute(
            "SELECT holiday_calendar_id, calendar_name FROM staffing_holiday_calendars "
            "WHERE calendar_key = 'company_default_2026_2040'"
        ).fetchone()
        assert cal is not None
        assert cal[1] == "Company Holiday Calendar"
        # 2026-2040 inclusive = 15 years x 10 holidays.
        total = conn.execute(
            "SELECT COUNT(*) FROM staffing_holiday_calendar_dates WHERE holiday_calendar_id = ?",
            (cal[0],),
        ).fetchone()[0]
        assert total == 150
        years = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT calendar_year FROM staffing_holiday_calendar_dates"
            )
        }
        assert years == set(range(2026, 2041))


def test_v76_holiday_seed_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    _migrate(db)
    with sqlite3.connect(db) as conn:
        before = conn.execute(
            "SELECT holiday_date_id, created_utc FROM staffing_holiday_calendar_dates "
            "ORDER BY holiday_date_id"
        ).fetchall()
    _migrate(db)  # re-apply
    with sqlite3.connect(db) as conn:
        after = conn.execute(
            "SELECT holiday_date_id, created_utc FROM staffing_holiday_calendar_dates "
            "ORDER BY holiday_date_id"
        ).fetchall()
    assert before == after  # no new rows, no churned timestamps


def test_v76_foreign_keys_wired(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    _migrate(db)
    with sqlite3.connect(db) as conn:
        fk = {
            row[2]  # referenced table
            for row in conn.execute(
                "PRAGMA foreign_key_list(staffing_holiday_calendar_dates)"
            )
        }
        assert "staffing_holiday_calendars" in fk
        fk2 = {
            row[2]
            for row in conn.execute(
                "PRAGMA foreign_key_list(forecast_project_staffing_absence_overrides)"
            )
        }
        assert "forecast_project_staffing_config" in fk2


def test_v76_lifecycle_contract_count(tmp_path: Path) -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
    )
    contract = json.loads(contract_path.read_text())
    assert contract["table_count"] == 471
    assert contract["table_count"] == len(contract["tables"])
    # The two attribution tables were reshaped to the cost_code+category model in V81.
    _reshaped_v81 = {
        "forecast_project_staffing_attribution_rules",
        "forecast_project_staffing_attribution_review_items",
    }
    for table in V76_TABLES:
        assert table in contract["tables"], table
        entry = contract["tables"][table]
        assert entry["v"] == ("V81" if table in _reshaped_v81 else "V76")
        assert entry["table_family"] == "project_staffing_v76"
