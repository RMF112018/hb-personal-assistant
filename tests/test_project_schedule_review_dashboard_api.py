"""Phase 18 schedule review dashboard API tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_portfolio_review import _seed_current_schedule


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "dashboard-api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def test_dashboard_api_invalid_status_filter(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    client = TestClient(create_app(db_path=str(db)))
    response = client.get(
        "/api/projects/schedule-review-dashboard",
        headers=_viewer(),
        params={"status": "not-a-status"},
    )
    assert response.status_code == 400


def test_dashboard_export_csv_and_json(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_current_schedule(db)
    client = TestClient(create_app(db_path=str(db)))
    csv_resp = client.get(
        "/api/projects/schedule-review-dashboard/export",
        headers=_viewer(),
        params={"format": "csv"},
    )
    assert csv_resp.status_code == 200
    assert "project_label" in csv_resp.text
    json_resp = client.get(
        "/api/projects/schedule-review-dashboard/export",
        headers=_viewer(),
        params={"format": "json"},
    )
    assert json_resp.status_code == 200
    assert "portfolio_summary" in json_resp.json()
