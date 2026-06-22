"""FastAPI schedule import route tests (multipart upload)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.store.migrator import SQLiteMigrator

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"
GMA_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "gma_sample.xml"


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _client(tmp_path: Path, *, migrate: bool = True) -> TestClient:
    db = tmp_path / "api.db"
    if migrate:
        SQLiteMigrator(db_path=str(db)).apply()
    return TestClient(create_app(db_path=str(db)))


def _preview(client: TestClient, path: Path, *, project_key: str = "tropical") -> Any:
    data = path.read_bytes()
    return client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": (path.name, data, "application/xml")},
        data={"project_key": project_key},
    )


def _commit(client: TestClient, import_id: str, *, project_key: str = "tropical") -> Any:
    return client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": import_id, "project_key": project_key, "confirm": True},
    )


def test_import_preview_and_commit_flow(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _preview(client, FIXTURE)
    assert preview.status_code == 200
    body = preview.json()
    assert find_redaction_leaks(body) == []
    import_id = body["import_id"]
    assert body["activity_count"] == 2

    commit = _commit(client, import_id)
    assert commit.status_code == 200
    commit_body = commit.json()
    assert find_redaction_leaks(commit_body) == []
    svk = commit_body["schedule_version_key"]

    versions = client.get("/api/schedules/projects/tropical/versions")
    assert versions.status_code == 200
    assert any(v["schedule_version_key"] == svk for v in versions.json())

    acts = client.get(f"/api/schedules/versions/{svk}/activities")
    assert acts.status_code == 200
    body = acts.json()
    assert len(body["activities"]) == 2
    assert body["total_count"] == 2
    assert body["truncated"] is False


def test_schedule_routes_fail_closed_without_schema(tmp_path: Path) -> None:
    client = _client(tmp_path, migrate=False)
    resp = client.get("/api/schedules/projects")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "schedule_schema_not_ready"


def test_preview_stale_schema_returns_503(tmp_path: Path) -> None:
    """Simulate live DB at V62 while repo expects V63 — JSON 503 before upload work."""
    db = tmp_path / "stale.db"
    SQLiteMigrator(db_path=str(db)).apply()
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM schema_migrations WHERE version = 63")
        conn.commit()
        assert int(conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]) == 62

    client = TestClient(create_app(db_path=str(db)))
    resp = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": (FIXTURE.name, FIXTURE.read_bytes(), "application/xml")},
        data={"project_key": "tropical"},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "schedule_schema_not_ready"


def test_post_routes_require_operator(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post(
        "/api/schedules/import-preview",
        headers={"X-HB-UI-Role": "viewer"},
        files={"file": ("x.xml", FIXTURE.read_bytes(), "application/xml")},
        data={"project_key": "tropical"},
    )
    assert resp.status_code == 403


def test_import_commit_gma_real_sample(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _preview(client, GMA_FIXTURE)
    assert preview.status_code == 200
    assert preview.json()["activity_count"] == 189
    import_id = preview.json()["import_id"]
    commit = _commit(client, import_id)
    assert commit.status_code == 200
    svk = commit.json()["schedule_version_key"]
    acts = client.get(f"/api/schedules/versions/{svk}/activities")
    assert len(acts.json()["activities"]) == 189
    first = acts.json()["activities"][0]
    assert first.get("planned_start")
    assert first.get("activity_type")


def test_commit_without_confirm_is_400(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": "missing", "project_key": "tropical", "confirm": False},
    )
    assert resp.status_code == 400


def test_preview_file_too_large(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hb_assistant.construction.analytics.schedule_import_service.MAX_UPLOAD_BYTES",
        1024,
    )
    client = _client(tmp_path)
    resp = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": ("big.xml", b"x" * 1025, "application/xml")},
        data={"project_key": "tropical"},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "schedule_file_too_large"


def test_preview_duplicate_version(tmp_path: Path) -> None:
    client = _client(tmp_path)
    first = _preview(client, FIXTURE)
    assert first.status_code == 200
    assert _commit(client, first.json()["import_id"]).status_code == 200

    second = _preview(client, FIXTURE)
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["code"] == "duplicate_schedule_version"
    assert detail["activity_count"] == 2
    assert detail["relationship_count"] >= 0
    assert "view_path" in detail


def test_preview_failure_writes_no_db_rows(tmp_path: Path) -> None:
    client = _client(tmp_path)
    db = tmp_path / "api.db"

    def _count(table: str) -> int:
        with sqlite3.connect(db) as conn:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    before_imports = _count("schedule_file_imports")
    before_acts = _count("procore_ep_schedule_activities")

    resp = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": ("bad.xml", b"<not-valid", "application/xml")},
        data={"project_key": "tropical"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "schedule_parse_failed"
    assert _count("schedule_file_imports") == before_imports
    assert _count("procore_ep_schedule_activities") == before_acts


def test_unsupported_schedule_format(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"project_key": "tropical"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "unsupported_schedule_format"


def test_commit_duplicate_blocked(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _preview(client, FIXTURE)
    import_id = preview.json()["import_id"]
    assert _commit(client, import_id).status_code == 200

    preview2 = _preview(client, FIXTURE)
    assert preview2.status_code == 409