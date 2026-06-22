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
from tests.schedule_project_test_helpers import seed_procore_ep_project

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"
GMA_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "gma_sample.xml"
XER_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xer" / "minimal.xer"


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _client(tmp_path: Path, *, migrate: bool = True) -> TestClient:
    db = tmp_path / "api.db"
    if migrate:
        SQLiteMigrator(db_path=str(db)).apply()
        seed_procore_ep_project(
            db,
            project_key="tropical",
            display_name="Tropical Wind",
            project_number="TWNU18",
        )
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


def _preview_xer(client: TestClient, *, project_key: str = "tropical") -> Any:
    return client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": (XER_FIXTURE.name, XER_FIXTURE.read_bytes(), "application/octet-stream")},
        data={"project_key": project_key},
    )


def test_import_preview_and_commit_xer(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _preview_xer(client)
    assert preview.status_code == 200
    body = preview.json()
    assert body["source_format"] == "primavera_xer"
    assert body["activity_count"] == 2
    assert body["relationship_count"] == 1

    commit = _commit(client, body["import_id"])
    assert commit.status_code == 200
    svk = commit.json()["schedule_version_key"]
    acts = client.get(f"/api/schedules/versions/{svk}/activities")
    assert acts.status_code == 200
    assert len(acts.json()["activities"]) == 2


def test_xer_commit_persists_critical_path_fields(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _preview_xer(client)
    assert preview.status_code == 200
    commit = _commit(client, preview.json()["import_id"])
    assert commit.status_code == 200
    svk = commit.json()["schedule_version_key"]

    db = tmp_path / "api.db"
    with sqlite3.connect(db) as conn:
        driving = conn.execute(
            """
            SELECT activity_id, source_driving_path_flag, explicit_total_float_days
            FROM procore_ep_schedule_activities
            WHERE schedule_version_key = ? AND source_driving_path_flag = 1
            """,
            (svk,),
        ).fetchall()
        assert len(driving) == 1
        assert driving[0][0] == "A1000"
        assert driving[0][2] is not None


def test_xer_quality_critical_path_measurable_via_api(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _preview_xer(client)
    assert preview.status_code == 200
    commit = _commit(client, preview.json()["import_id"])
    assert commit.status_code == 200
    svk = commit.json()["schedule_version_key"]

    quality = client.get(f"/api/schedules/versions/{svk}/quality", headers=_op())
    assert quality.status_code == 200
    metrics = {m["metric_code"]: m for m in quality.json().get("metrics") or []}
    assert metrics["dcma_critical_path_test"]["status"] == "measured_from_xer_driving_path"


def test_import_commit_supersede_same_version_key(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview1 = _preview(client, FIXTURE)
    assert preview1.status_code == 200
    commit1 = _commit(client, preview1.json()["import_id"])
    assert commit1.status_code == 200
    svk = commit1.json()["schedule_version_key"]

    dup_preview = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": (FIXTURE.name, FIXTURE.read_bytes(), "application/xml")},
        data={"project_key": "tropical"},
    )
    assert dup_preview.status_code == 409

    preview2 = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": (FIXTURE.name, FIXTURE.read_bytes(), "application/xml")},
        data={"project_key": "tropical", "confirm_supersede": "true"},
    )
    assert preview2.status_code == 200
    supersede = client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={
            "import_id": preview2.json()["import_id"],
            "project_key": "tropical",
            "confirm": True,
            "confirm_supersede": True,
        },
    )
    assert supersede.status_code == 200
    assert supersede.json()["schedule_version_key"] == svk
    assert supersede.json().get("superseded_import_id") == commit1.json()["import_id"]


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


def test_schedule_routes_self_heal_stale_schema_version(tmp_path: Path) -> None:
    """Stale schema_migrations rows are repaired on first schedule route touch."""
    db = tmp_path / "stale.db"
    SQLiteMigrator(db_path=str(db)).apply()
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM schema_migrations WHERE version >= 63")
        conn.commit()
        assert int(conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]) == 62

    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))
    resp = client.get("/api/schedules/projects", headers=_op())
    assert resp.status_code == 200
    assert resp.json()["catalog_status"] == "ok"
    with sqlite3.connect(db) as conn:
        assert int(conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]) >= 63


def test_preview_self_heals_missing_v65_columns(tmp_path: Path) -> None:
    db = tmp_path / "drift.db"
    SQLiteMigrator(db_path=str(db)).apply()
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE procore_ep_schedule_activities DROP COLUMN remaining_early_finish")
        conn.commit()

    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))
    resp = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": (FIXTURE.name, FIXTURE.read_bytes(), "application/xml")},
        data={"project_key": "tropical"},
    )
    assert resp.status_code == 200
    with sqlite3.connect(db) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(procore_ep_schedule_activities)")}
        assert "remaining_early_finish" in cols


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