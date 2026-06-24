"""FastAPI route tests for GET /api/forecast/generation/date-defaults (Phase P-D)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.config.path_policy import PathPolicy  # noqa: E402
from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402
from tests.schedule_project_test_helpers import seed_procore_ep_project  # noqa: E402

TS = "2026-04-15T08:00:00+00:00"


def _client(*, with_schedule: bool) -> TestClient:
    db = Path(PathPolicy().get_db_path())
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Resort")
    if with_schedule:
        conn = sqlite3.connect(str(db))
        conn.execute(
            "INSERT INTO schedule_file_imports (import_id, project_key, source_type, source_format, "
            "import_status, activity_count, relationship_count, wbs_count, calendar_count, code_count, "
            "udf_count, cost_loaded_status, schedule_version_key, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("imp1", "tropical", "xer", "primavera_xer", "committed", 1, 0, 0, 0, 0, 0,
             "not_cost_loaded", "tropical|S1|2026-06-01", TS),
        )
        conn.commit()
        conn.close()
    return TestClient(create_app(db_path=str(db)))


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def test_available_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(with_schedule=True)
    resp = client.get(
        "/api/forecast/generation/date-defaults", params={"project_key": "tropical"}, headers=_viewer()
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["surface"] == "analytics.forecast_generation_date_defaults"
    assert body["forecast_cutoff_date"] == "2026-06-01"
    assert body["forecast_cutoff_date_basis"] == "schedule_data_date"
    assert body["schedule_data_date"] == "2026-06-01"
    assert body["schedule_source_status"] == "available"
    assert body["guardrails"]["read_only"] is True
    assert find_redaction_leaks(body) == []


def test_missing_project_key_422(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(with_schedule=True)
    assert client.get("/api/forecast/generation/date-defaults", headers=_viewer()).status_code == 422
    # Empty value is also rejected.
    assert (
        client.get(
            "/api/forecast/generation/date-defaults", params={"project_key": ""}, headers=_viewer()
        ).status_code
        == 422
    )


def test_unknown_project_404(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(with_schedule=True)
    resp = client.get(
        "/api/forecast/generation/date-defaults", params={"project_key": "ghost"}, headers=_viewer()
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "unknown_project_key"


def test_project_without_schedule_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(with_schedule=False)
    body = client.get(
        "/api/forecast/generation/date-defaults", params={"project_key": "tropical"}, headers=_viewer()
    ).json()
    assert body["forecast_cutoff_date"] is None
    assert body["schedule_source_status"] == "missing"
    assert "no_schedule_cutoff_default_available" in body["warnings"]
    assert find_redaction_leaks(body) == []
