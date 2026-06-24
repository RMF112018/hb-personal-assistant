"""FastAPI route tests for the generation-ready project read model (Phase P-B).

Asserts: discovery unions procore_ep_projects + committed schedule imports + forecast_outputs;
per-project availability + ready/degraded/blocked readiness with coded reasons; generation_disabled
when the opt-in is off; viewer-readable; and NO dev-internals leak.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.construction.analytics.forecast_runtime_config import (  # noqa: E402
    ENV_DB_CONFIG_RUN_ENABLED,
)
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402
from tests.schedule_project_test_helpers import seed_procore_ep_project  # noqa: E402

TS = "2026-06-19T08:00:00+00:00"


def _seed(db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    # tropical — fully populated (identity + committed schedule + activities + output + config + budget).
    seed_procore_ep_project(
        db, project_key="tropical", display_name="Tropical Resort", project_number="PR-001"
    )
    # harbor — identity only (no schedule / output / config / budget).
    seed_procore_ep_project(
        db, project_key="harbor", display_name="Harbor Tower", project_number="PR-002"
    )
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO schedule_file_imports (import_id, project_key, source_type, source_format, "
            "import_status, activity_count, relationship_count, wbs_count, calendar_count, "
            "code_count, udf_count, cost_loaded_status, schedule_version_key, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("imp-trop", "tropical", "xer", "primavera_xer", "committed", 1, 0, 0, 0, 0, 0,
             "not_cost_loaded", "tropical|TWNU18|2026-01-01", TS),
        )
        # schedule-only project: committed import, NO procore_ep_projects row, NO output.
        conn.execute(
            "INSERT INTO schedule_file_imports (import_id, project_key, source_type, source_format, "
            "import_status, activity_count, relationship_count, wbs_count, calendar_count, "
            "code_count, udf_count, cost_loaded_status, schedule_version_key, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("imp-delta", "delta", "xer", "primavera_xer", "committed", 1, 0, 0, 0, 0, 0,
             "not_cost_loaded", "delta|S1|2026-02-01", TS),
        )
        conn.execute(
            "INSERT INTO procore_ep_schedule_activities (project_key, schedule_id, "
            "schedule_version_key, import_id, source_type, source_format, activity_id) "
            "VALUES (?,?,?,?,?,?,?)",
            ("tropical", "TWNU18", "tropical|TWNU18|2026-01-01", "imp-trop", "xer",
             "primavera_xer", "A1000"),
        )
        conn.execute(
            "INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES (?,?,?)",
            ("20260101_000000", "tropical", TS),
        )
        conn.execute(
            "INSERT INTO forecast_outputs (output_id, run_id, project_key, source_package, "
            "estimated_final_cost, cost_to_complete, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?)",
            ("fout-test0000000000000000000000000001", "20260101_000000", "tropical",
             "forecast_analysis_package_tropical_20260101_000000", "500.00", "100.00", "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_config_snapshots (config_snapshot_id, project_key, snapshot_name, "
            "snapshot_created_utc, snapshot_reason, source_mode, item_count, snapshot_sha256, "
            "created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
            ("snap-trop", "tropical", "tropical-config", TS, "initial", "db", 5, "deadbeef", TS),
        )
        conn.execute(
            "INSERT INTO forecast_budget_details (project_key, budget_code_key, source_package, "
            "raw_json, created_utc) VALUES (?,?,?,?,?)",
            ("tropical", "0000.03-01-001.MAT", "pkg-trop", "{}", TS),
        )
        conn.commit()
    finally:
        conn.close()


def _client(db: Path) -> TestClient:
    return TestClient(create_app(db_path=str(db)))


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _by_key(body: dict) -> dict[str, dict]:
    return {p["project_key"]: p for p in body["projects"]}


@pytest.fixture
def seeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(ENV_DB_CONFIG_RUN_ENABLED, "1")  # generation enabled by default for these tests
    db = tmp_path / "hb.sqlite"
    _seed(db)
    return db


def test_discovers_and_unions_all_sources(seeded: Path) -> None:
    resp = _client(seeded).get("/api/forecast/generation/projects", headers=_viewer())
    assert resp.status_code == 200
    body = resp.json()
    assert body["generation_enabled"] is True
    keys = {p["project_key"] for p in body["projects"]}
    # tropical+harbor from procore_ep_projects, delta from committed schedule import (no procore row).
    assert keys == {"tropical", "harbor", "delta"}
    assert find_redaction_leaks(body) == []


def test_tropical_is_ready_with_full_metadata(seeded: Path) -> None:
    p = _by_key(_client(seeded).get("/api/forecast/generation/projects", headers=_viewer()).json())[
        "tropical"
    ]
    assert p["readiness_status"] == "ready"
    assert p["readiness_reasons"] == []
    assert p["display_name"] == "Tropical Resort"
    assert p["procore_project_id"] == "9001"
    assert p["has_schedule_data"] is True
    assert p["has_activity_data"] is True
    assert p["latest_schedule_version_key"] == "tropical|TWNU18|2026-01-01"
    assert p["latest_schedule_date"] is None  # deferred to P-D
    assert p["has_prior_forecast_output"] is True
    assert p["latest_forecast_status"] == "generated"
    assert p["latest_forecast_display"] == "Jun 19, 2026"
    assert p["has_budget_cost_data"] is True
    assert p["config_snapshot_available"] is True


def test_identity_only_project_is_blocked(seeded: Path) -> None:
    p = _by_key(_client(seeded).get("/api/forecast/generation/projects", headers=_viewer()).json())[
        "harbor"
    ]
    assert p["readiness_status"] == "blocked"
    assert "missing_config_snapshot" in p["readiness_reasons"]
    assert "missing_budget_cost_data" in p["readiness_reasons"]
    assert p["has_schedule_data"] is False
    assert p["has_prior_forecast_output"] is False


def test_schedule_only_project_appears_without_prior_forecast(seeded: Path) -> None:
    p = _by_key(_client(seeded).get("/api/forecast/generation/projects", headers=_viewer()).json())[
        "delta"
    ]
    assert p["has_schedule_data"] is True
    assert p["has_prior_forecast_output"] is False
    assert p["display_name"] is None  # no procore identity row
    assert p["readiness_status"] == "blocked"  # no config/budget
    assert "missing_config_snapshot" in p["readiness_reasons"]


def test_generation_disabled_blocks_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_DB_CONFIG_RUN_ENABLED, raising=False)
    db = tmp_path / "hb.sqlite"
    _seed(db)
    body = _client(db).get("/api/forecast/generation/projects", headers=_viewer()).json()
    assert body["generation_enabled"] is False
    assert all(p["readiness_status"] == "blocked" for p in body["projects"])
    assert all("generation_disabled" in p["readiness_reasons"] for p in body["projects"])
    assert find_redaction_leaks(body) == []


def test_viewer_readable_and_redaction_clean(seeded: Path) -> None:
    resp = _client(seeded).get("/api/forecast/generation/projects", headers=_viewer())
    assert resp.status_code == 200
    body = resp.json()
    assert body["guardrails"]["read_only"] is True
    assert find_redaction_leaks(body) == []
