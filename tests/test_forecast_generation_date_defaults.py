"""P-D — schedule-derived date-default resolver unit tests (temp SQLite DB only)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.analytics.forecast_generation_date_defaults import (
    resolve_forecast_generation_date_defaults,
)
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

TS = "2026-04-15T08:00:00+00:00"


def _db(td: str) -> sqlite3.Connection:
    db = Path(td) / "d.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Resort")
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def _import(conn, *, version_key, created_at=TS, import_id="imp1", project="tropical", status="committed"):
    conn.execute(
        "INSERT INTO schedule_file_imports (import_id, project_key, source_type, source_format, "
        "import_status, activity_count, relationship_count, wbs_count, calendar_count, code_count, "
        "udf_count, cost_loaded_status, schedule_version_key, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (import_id, project, "xer", "primavera_xer", status, 1, 0, 0, 0, 0, 0,
         "not_cost_loaded", version_key, created_at),
    )
    conn.commit()


def _activity(conn, *, import_id="imp1", version_key, activity_id="A1", **dates):
    cols = ["project_key", "schedule_id", "schedule_version_key", "import_id", "source_type",
            "source_format", "activity_id"]
    vals = ["tropical", "S1", version_key, import_id, "xer", "primavera_xer", activity_id]
    for k, v in dates.items():
        cols.append(k)
        vals.append(v)
    conn.execute(
        f"INSERT INTO procore_ep_schedule_activities ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)})",
        vals,
    )
    conn.commit()


def test_p1_uses_schedule_data_date_from_version_key() -> None:
    with tempfile.TemporaryDirectory() as td:
        conn = _db(td)
        _import(conn, version_key="tropical|S1|2026-06-01")
        d = resolve_forecast_generation_date_defaults(conn, "tropical")
        assert d.forecast_cutoff_date == "2026-06-01"
        assert d.forecast_cutoff_date_basis == "schedule_data_date"
        assert d.schedule_data_date == "2026-06-01"
        assert d.schedule_data_date_basis == "schedule_version_key"
        assert d.schedule_source_status == "available"
        assert d.schedule_version_key == "tropical|S1|2026-06-01"
        assert find_redaction_leaks(d.warnings) == []


def test_p1_picks_latest_committed_version() -> None:
    with tempfile.TemporaryDirectory() as td:
        conn = _db(td)
        _import(conn, version_key="tropical|S1|2026-01-01", created_at="2026-01-02T00:00:00+00:00", import_id="old")
        _import(conn, version_key="tropical|S1|2026-06-01", created_at="2026-06-02T00:00:00+00:00", import_id="new")
        d = resolve_forecast_generation_date_defaults(conn, "tropical")
        assert d.forecast_cutoff_date == "2026-06-01"


def test_never_uses_finish_horizon() -> None:
    with tempfile.TemporaryDirectory() as td:
        conn = _db(td)
        _import(conn, version_key="tropical|S1|2026-06-01")
        # Activities carry far-future finish/horizon dates that must NOT become the cut-off.
        _activity(conn, version_key="tropical|S1|2026-06-01", planned_finish="2030-12-31",
                  late_finish="2031-01-01", finish_date="2030-11-30", actual_finish="2026-05-01")
        d = resolve_forecast_generation_date_defaults(conn, "tropical")
        assert d.forecast_cutoff_date == "2026-06-01"  # schedule data date, not 2030/2031


def test_p2_falls_back_to_import_created_at() -> None:
    with tempfile.TemporaryDirectory() as td:
        conn = _db(td)
        _import(conn, version_key="tropical|S1|notadate", created_at="2026-04-15T00:00:00+00:00")
        d = resolve_forecast_generation_date_defaults(conn, "tropical")
        assert d.forecast_cutoff_date == "2026-04-15"
        assert d.forecast_cutoff_date_basis == "schedule_import_created_at"
        assert d.schedule_data_date is None
        assert d.schedule_source_status == "degraded"
        assert "schedule_data_date_missing_using_import_date" in d.warnings
        assert "invalid_schedule_dates_ignored" in d.warnings


def test_p3_falls_back_to_latest_actual_activity_date() -> None:
    with tempfile.TemporaryDirectory() as td:
        conn = _db(td)
        # version_key data date invalid AND created_at invalid → drop to activity actuals.
        _import(conn, version_key="tropical|S1|notadate", created_at="not-a-real-date")
        _activity(conn, version_key="tropical|S1|notadate", actual_finish="2026-03-20",
                  actual_start="2025-09-01")
        d = resolve_forecast_generation_date_defaults(conn, "tropical")
        assert d.forecast_cutoff_date == "2026-03-20"
        assert d.forecast_cutoff_date_basis == "latest_actual_activity_date"
        assert d.schedule_source_status == "degraded"
        assert "schedule_data_date_missing_using_activity_actual_date" in d.warnings


def test_p4_no_default_when_no_schedule() -> None:
    with tempfile.TemporaryDirectory() as td:
        conn = _db(td)  # project exists, no committed imports / activities
        d = resolve_forecast_generation_date_defaults(conn, "tropical")
        assert d.forecast_cutoff_date is None
        assert d.forecast_cutoff_date_basis is None
        assert d.schedule_source_status == "missing"
        assert "no_schedule_cutoff_default_available" in d.warnings
        assert "project_has_no_schedule_versions" in d.warnings


def test_start_date_from_prior_request() -> None:
    with tempfile.TemporaryDirectory() as td:
        conn = _db(td)
        _import(conn, version_key="tropical|S1|2026-06-01")
        conn.execute(
            "INSERT INTO forecast_generation_requests (request_id, project_key, generation_mode, "
            "request_status, validation_status, forecast_start_date, created_utc, updated_utc) "
            "VALUES (?,?,?,?,?,?,?,?)",
            ("req1", "tropical", "db_config", "completed", "valid", "2025-02-01", TS, TS),
        )
        conn.commit()
        d = resolve_forecast_generation_date_defaults(conn, "tropical")
        assert d.forecast_start_date == "2025-02-01"
        assert d.forecast_start_date_basis == "prior_generation_request"


def test_start_date_from_earliest_actual_cost_month() -> None:
    with tempfile.TemporaryDirectory() as td:
        conn = _db(td)
        _import(conn, version_key="tropical|S1|2026-06-01")
        for month in ("2025-03", "2025-01", "2025-07"):
            conn.execute(
                "INSERT INTO forecast_monthly_actuals_by_budget_code (project_key, budget_code_key, "
                "month, type, source_package, raw_json, created_utc) VALUES (?,?,?,?,?,?,?)",
                ("tropical", "0000.03.MAT", month, "actual", "pkg", "{}", TS),
            )
        conn.commit()
        d = resolve_forecast_generation_date_defaults(conn, "tropical")
        assert d.forecast_start_date == "2025-01-01"  # MIN month -> first of month
        assert d.forecast_start_date_basis == "earliest_actual_cost_month"
