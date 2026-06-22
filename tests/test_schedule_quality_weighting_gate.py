"""Cost weighting gate requires a completed schedule quality scorecard."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _client(tmp_path: Path) -> TestClient:
    db = tmp_path / "weighting_gate.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return TestClient(create_app(db_path=str(db)))


def _import_without_quality_processing(client: TestClient) -> str:
    with patch(
        "hb_assistant.construction.analytics.schedule_quality_worker.poll_and_process",
        return_value=[],
    ):
        preview = client.post(
            "/api/schedules/import-preview",
            headers=_op(),
            files={"file": ("minimal_schedule.xml", FIXTURE.read_bytes(), "application/xml")},
            data={"project_key": "tropical"},
        )
        import_id = preview.json()["import_id"]
        commit = client.post(
            "/api/schedules/import-commit",
            headers=_op(),
            json={"import_id": import_id, "project_key": "tropical", "confirm": True},
        )
    assert commit.status_code == 200
    return commit.json()["schedule_version_key"]


def test_cost_mapping_approve_blocked_without_completed_quality(tmp_path: Path) -> None:
    client = _client(tmp_path)
    svk = _import_without_quality_processing(client)

    run = client.post(
        "/api/schedules/cost-mapping/runs",
        headers=_op(),
        json={
            "project_key": "tropical",
            "schedule_version_key": svk,
            "operator_objective": "association_only",
        },
    )
    assert run.status_code == 200
    run_id = run.json()["mapping_run_id"]

    cands = client.get(f"/api/schedules/cost-mapping/runs/{run_id}/candidates").json()["candidates"]
    for c in cands:
        client.post(
            f"/api/schedules/cost-mapping/candidates/{c['id']}/review",
            headers=_op(),
            json={"operator_status": "approved"},
        )

    approve = client.post(f"/api/schedules/cost-mapping/runs/{run_id}/approve", headers=_op())
    assert approve.status_code == 409
    assert approve.json()["detail"] == "schedule_quality_not_ready"


def test_cost_mapping_approve_succeeds_after_quality_completes(tmp_path: Path) -> None:
    client = _client(tmp_path)
    svk = _import_without_quality_processing(client)

    from hb_assistant.construction.analytics.schedule_quality_worker import poll_and_process

    results = poll_and_process(db_path=str(tmp_path / "weighting_gate.db"), limit=1)
    assert results and results[0]["status"] == "completed"

    run = client.post(
        "/api/schedules/cost-mapping/runs",
        headers=_op(),
        json={
            "project_key": "tropical",
            "schedule_version_key": svk,
            "operator_objective": "association_only",
        },
    )
    run_id = run.json()["mapping_run_id"]
    cands = client.get(f"/api/schedules/cost-mapping/runs/{run_id}/candidates").json()["candidates"]
    for c in cands:
        client.post(
            f"/api/schedules/cost-mapping/candidates/{c['id']}/review",
            headers=_op(),
            json={"operator_status": "approved"},
        )

    approve = client.post(f"/api/schedules/cost-mapping/runs/{run_id}/approve", headers=_op())
    assert approve.status_code == 200

    weighting = client.get("/api/schedules/cost-weighting/tropical")
    assert len(weighting.json()["weighting_results"]) >= 1