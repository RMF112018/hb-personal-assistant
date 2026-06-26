"""Project entry-page summary API."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app

FORBIDDEN = (
    "raw_json",
    "payload_sidecar_json",
    "canonical_hash",
    "source_package",
    "source_path",
    "record_key",
    "updated_utc",
    "is_current",
)


def _client(db_path: Path) -> TestClient:
    return TestClient(create_app(db_path=str(db_path)))


def _create_db(db_path: Path, *, include_status: bool = False, include_stage: bool = False) -> None:
    columns = [
        "record_key TEXT",
        "project_key TEXT",
        "project_id",
        "display_name TEXT",
        "address TEXT",
        "city TEXT",
        "state_code TEXT",
        "zip TEXT",
        "project_number TEXT",
        "is_current INTEGER",
        "updated_utc TEXT",
        "raw_json TEXT",
    ]
    if include_status:
        columns.append("status TEXT")
    if include_stage:
        columns.append("stage TEXT")
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(f"CREATE TABLE procore_ep_projects ({', '.join(columns)})")
        conn.commit()


def _insert_project(db_path: Path, **values: Any) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(procore_ep_projects)")]
        row = {
            "record_key": values.get("record_key", f"rk-{values.get('project_key', 'blank')}"),
            "project_key": values.get("project_key"),
            "project_id": values.get("project_id", "2525840"),
            "display_name": values.get("display_name"),
            "address": values.get("address"),
            "city": values.get("city"),
            "state_code": values.get("state_code"),
            "zip": values.get("zip"),
            "project_number": values.get("project_number"),
            "is_current": values.get("is_current", 1),
            "updated_utc": values.get("updated_utc", "2026-06-24T00:00:00Z"),
            "raw_json": values.get("raw_json", '{"secret":"not emitted"}'),
            "status": values.get("status"),
            "stage": values.get("stage"),
        }
        selected = [column for column in columns if column in row]
        placeholders = ", ".join("?" for _ in selected)
        conn.execute(
            f"INSERT INTO procore_ep_projects ({', '.join(selected)}) VALUES ({placeholders})",
            [row[column] for column in selected],
        )
        conn.commit()


def test_projects_summary_reads_safe_project_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "projects.sqlite"
    _create_db(db_path, include_stage=True)
    _insert_project(
        db_path,
        project_key="tropical",
        project_id=2525840,
        display_name="Tropical Resort",
        address="123 Main St",
        city="West Palm Beach",
        state_code="FL",
        zip="33401",
        project_number="PR-001",
        stage="active",
    )
    _insert_project(
        db_path,
        project_key="harbor",
        project_id="9002",
        display_name="Harbor Center",
        city="Palm Beach",
        state_code="FL",
        zip="33480",
        project_number="PR-002",
        stage="preconstruction",
    )

    response = _client(db_path).get("/api/projects")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "analytics.projects.list"
    assert payload["guardrails"]["read_only"] is True
    assert payload["guardrails"]["no_db_write"] is True
    assert [project["project_key"] for project in payload["projects"]] == ["harbor", "tropical"]
    tropical = payload["projects"][1]
    assert tropical == {
        "project_key": "tropical",
        "procore_project_id": "2525840",
        "display_name": "Tropical Resort",
        "address": "123 Main St",
        "city": "West Palm Beach",
        "state_code": "FL",
        "zip": "33401",
        "project_number": "PR-001",
        "status": "active",
    }
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_projects_summary_deduplicates_by_current_latest_record(tmp_path: Path) -> None:
    db_path = tmp_path / "projects.sqlite"
    _create_db(db_path)
    _insert_project(
        db_path,
        record_key="rk-old-current",
        project_key="tropical",
        display_name="Old Current",
        is_current=1,
        updated_utc="2026-06-20T00:00:00Z",
    )
    _insert_project(
        db_path,
        record_key="rk-new-not-current",
        project_key="tropical",
        display_name="New Non Current",
        is_current=0,
        updated_utc="2026-06-25T00:00:00Z",
    )
    _insert_project(
        db_path,
        record_key="rk-new-current",
        project_key="tropical",
        display_name="New Current",
        is_current=1,
        updated_utc="2026-06-24T00:00:00Z",
    )

    payload = _client(db_path).get("/api/projects").json()

    assert len(payload["projects"]) == 1
    assert payload["projects"][0]["display_name"] == "New Current"


def test_projects_summary_excludes_blank_project_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "projects.sqlite"
    _create_db(db_path)
    _insert_project(db_path, project_key="", display_name="Blank")
    _insert_project(db_path, project_key=None, display_name="Missing")
    _insert_project(db_path, project_key="summit", display_name="Summit")

    payload = _client(db_path).get("/api/projects").json()

    assert [project["project_key"] for project in payload["projects"]] == ["summit"]


def test_projects_summary_does_not_invent_status_when_optional_columns_absent(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "projects.sqlite"
    _create_db(db_path)
    _insert_project(db_path, project_key="tropical", display_name="Tropical")

    payload = _client(db_path).get("/api/projects").json()

    assert payload["projects"][0]["status"] is None


def test_projects_summary_prefers_status_column_over_stage(tmp_path: Path) -> None:
    db_path = tmp_path / "projects.sqlite"
    _create_db(db_path, include_status=True, include_stage=True)
    _insert_project(
        db_path,
        project_key="tropical",
        display_name="Tropical",
        status="open",
        stage="active",
    )

    payload = _client(db_path).get("/api/projects").json()

    assert payload["projects"][0]["status"] == "open"


def test_projects_summary_missing_table_returns_empty_list(tmp_path: Path) -> None:
    db_path = tmp_path / "projects.sqlite"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
        conn.commit()

    response = _client(db_path).get("/api/projects")

    assert response.status_code == 200
    assert response.json()["projects"] == []


def test_projects_summary_invalid_role_is_forbidden(tmp_path: Path) -> None:
    db_path = tmp_path / "projects.sqlite"
    _create_db(db_path)

    response = _client(db_path).get("/api/projects", headers={"X-HB-UI-Role": "writer"})

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid_ui_role"
