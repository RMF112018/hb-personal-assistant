"""Schedule project association API tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project, seed_procore_ep_project_row

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _client(tmp_path: Path) -> TestClient:
    db = tmp_path / "proj.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(
        db,
        project_key="tropical",
        display_name="Tropical Wind",
        project_number="TWNU18",
    )
    seed_procore_ep_project(
        db,
        project_key="hilltop",
        display_name="Hilltop Gardens",
        project_number="HG01",
        project_id="9002",
    )
    return TestClient(create_app(db_path=str(db)))


def _preview(client: TestClient, path: Path, *, project_key: str) -> Any:
    return client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": (path.name, path.read_bytes(), "application/xml")},
        data={"project_key": project_key},
    )


def _commit(client: TestClient, import_id: str, *, project_key: str) -> Any:
    return client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": import_id, "project_key": project_key, "confirm": True},
    )


def test_projects_endpoint_lists_ep_and_browse_keys(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _preview(client, FIXTURE, project_key="tropical")
    assert preview.status_code == 200
    commit = _commit(client, preview.json()["import_id"], project_key="tropical")
    assert commit.status_code == 200

    resp = client.get("/api/schedules/projects", headers=_op())
    assert resp.status_code == 200
    body = resp.json()
    assert body["catalog_status"] == "ok"
    keys = {p["project_key"] for p in body["projects"]}
    assert "tropical" in keys
    assert "hilltop" in keys
    tropical = next(p for p in body["projects"] if p["project_key"] == "tropical")
    assert tropical["display_name"] == "Tropical Wind"
    assert tropical["has_schedule_imports"] is True
    assert tropical["project_identity_label"].startswith("tropical —")
    for project in body["projects"]:
        if project.get("selectable_for_import"):
            assert project["project_identity_label"].startswith(f"{project['project_key']} —")


def test_import_requires_project_key(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": "missing", "confirm": True},
    )
    assert resp.status_code == 422


def test_import_rejects_unknown_project_key(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = _preview(client, FIXTURE, project_key="unknown_project")
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "schedule_project_unknown"


def test_same_file_different_projects_do_not_collide(tmp_path: Path) -> None:
    client = _client(tmp_path)
    p1 = _preview(client, FIXTURE, project_key="tropical")
    c1 = _commit(client, p1.json()["import_id"], project_key="tropical")
    assert c1.status_code == 200
    svk_tropical = c1.json()["schedule_version_key"]

    p2 = _preview(client, FIXTURE, project_key="hilltop")
    assert p2.status_code == 200
    c2 = _commit(client, p2.json()["import_id"], project_key="hilltop")
    assert c2.status_code == 200
    svk_hilltop = c2.json()["schedule_version_key"]
    assert svk_tropical != svk_hilltop
    assert svk_tropical.startswith("tropical|")
    assert svk_hilltop.startswith("hilltop|")


def test_versions_filter_by_project_key(tmp_path: Path) -> None:
    client = _client(tmp_path)
    p1 = _preview(client, FIXTURE, project_key="tropical")
    _commit(client, p1.json()["import_id"], project_key="tropical")
    p2 = _preview(client, FIXTURE, project_key="hilltop")
    _commit(client, p2.json()["import_id"], project_key="hilltop")

    all_versions = client.get("/api/schedules/versions", headers=_op())
    assert all_versions.status_code == 200
    assert len(all_versions.json()) == 2

    tropical_only = client.get("/api/schedules/versions?project_key=tropical", headers=_op())
    assert tropical_only.status_code == 200
    rows = tropical_only.json()
    assert len(rows) == 1
    assert rows[0]["project_key"] == "tropical"

    hilltop_only = client.get("/api/schedules/versions?project_key=hilltop", headers=_op())
    assert len(hilltop_only.json()) == 1
    assert hilltop_only.json()[0]["project_key"] == "hilltop"


def test_quality_list_filters_by_project(tmp_path: Path) -> None:
    client = _client(tmp_path)
    p1 = _preview(client, FIXTURE, project_key="tropical")
    c1 = _commit(client, p1.json()["import_id"], project_key="tropical")
    p2 = _preview(client, FIXTURE, project_key="hilltop")
    _commit(client, p2.json()["import_id"], project_key="hilltop")

    resp = client.get("/api/schedules/quality?project_key=tropical", headers=_op())
    assert resp.status_code == 200
    evals = resp.json()["evaluations"]
    assert len(evals) == 1
    assert evals[0]["project_key"] == "tropical"
    assert evals[0]["schedule_version_key"] == c1.json()["schedule_version_key"]


def test_project_labels_remain_distinct_for_duplicate_display_metadata(tmp_path: Path) -> None:
    db = tmp_path / "dup.db"
    SQLiteMigrator(db_path=str(db)).apply()
    shared_name = "25-745-01 - RYBOVICH-SAFE HARBOR"
    shared_number = "25-745-01"
    seed_procore_ep_project_row(
        db,
        project_key="rybovich",
        display_name=shared_name,
        project_number=shared_number,
        project_id="3133242",
    )
    seed_procore_ep_project_row(
        db,
        project_key="tropical",
        display_name=shared_name,
        project_number=shared_number,
        project_id="2525840",
    )
    client = TestClient(create_app(db_path=str(db)))
    resp = client.get("/api/schedules/projects", headers=_op())
    assert resp.status_code == 200
    labels = {
        p["project_key"]: p["project_identity_label"]
        for p in resp.json()["projects"]
        if p["selectable_for_import"]
    }
    assert labels["rybovich"].startswith("rybovich —")
    assert labels["tropical"].startswith("tropical —")
    assert labels["rybovich"] != labels["tropical"]
    for project in resp.json()["projects"]:
        if project["project_key"] in {"rybovich", "tropical"}:
            assert "duplicate_display_metadata_across_project_keys" in (
                project.get("identity_warning") or ""
            )


def test_multi_row_project_key_uses_newest_current_metadata(tmp_path: Path) -> None:
    db = tmp_path / "multi.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project_row(
        db,
        project_key="rybovich",
        display_name="Older Name",
        project_number="OLD-01",
        project_id="3133242",
        record_key="rk-rybovich-old",
        updated_utc="2026-06-20T00:00:00Z",
    )
    seed_procore_ep_project_row(
        db,
        project_key="rybovich",
        display_name="25-745-01 - RYBOVICH-SAFE HARBOR",
        project_number="25-745-01",
        project_id="3133242",
        record_key="rk-rybovich-new",
        updated_utc="2026-06-22T00:00:00Z",
    )
    client = TestClient(create_app(db_path=str(db)))
    resp = client.get("/api/schedules/projects", headers=_op())
    project = next(p for p in resp.json()["projects"] if p["project_key"] == "rybovich")
    assert project["display_name"] == "25-745-01 - RYBOVICH-SAFE HARBOR"
    assert project["project_number"] == "25-745-01"
    assert project["record_key"] == "rk-rybovich-new"
    assert "inconsistent_display_metadata_within_project_key" in (project.get("identity_warning") or "")
    assert "multiple_current_rows" in (project.get("identity_warning") or "")


def test_historical_tropical_version_readable(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _preview(client, FIXTURE, project_key="tropical")
    commit = _commit(client, preview.json()["import_id"], project_key="tropical")
    svk = commit.json()["schedule_version_key"]

    summary = client.get(f"/api/schedules/versions/{svk}/summary", headers=_op())
    assert summary.status_code == 200
    assert summary.json()["project_key"] == "tropical"

    quality = client.get(f"/api/schedules/versions/{svk}/quality", headers=_op())
    assert quality.status_code == 200
    assert quality.json()["project_key"] == "tropical"