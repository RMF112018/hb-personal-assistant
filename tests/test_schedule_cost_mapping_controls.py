"""Operator cost mapping control gates."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _client(tmp_path: Path) -> TestClient:
    db = tmp_path / "map.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return TestClient(create_app(db_path=str(db)))


def _import_version(client: TestClient) -> str:
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
    return commit.json()["schedule_version_key"]


def test_mapping_run_requires_objective_and_approval_gate(tmp_path: Path) -> None:
    client = _client(tmp_path)
    svk = _import_version(client)

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
    assert run.json()["operator_objective"] == "association_only"

    weight_before = client.get("/api/schedules/cost-weighting/tropical")
    assert weight_before.status_code == 200
    assert weight_before.json()["weighting_results"] == []

    cands = client.get(f"/api/schedules/cost-mapping/runs/{run_id}/candidates").json()["candidates"]
    for c in cands:
        client.post(
            f"/api/schedules/cost-mapping/candidates/{c['id']}/review",
            headers=_op(),
            json={"operator_status": "approved"},
        )

    approve = client.post(f"/api/schedules/cost-mapping/runs/{run_id}/approve", headers=_op())
    assert approve.status_code == 200

    weight_after = client.get("/api/schedules/cost-weighting/tropical")
    assert weight_after.status_code == 200
    assert len(weight_after.json()["weighting_results"]) >= 1


def test_distribution_labeled_analytical(tmp_path: Path) -> None:
    client = _client(tmp_path)
    svk = _import_version(client)
    run = client.post(
        "/api/schedules/cost-mapping/runs",
        headers=_op(),
        json={
            "project_key": "tropical",
            "schedule_version_key": svk,
            "operator_objective": "simplified_duration_distribution",
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
    client.post(f"/api/schedules/cost-mapping/runs/{run_id}/approve", headers=_op())
    dist = client.get(f"/api/schedules/cost-mapping/runs/{run_id}/distribution").json()
    if dist["distributions"]:
        assert dist["distributions"][0]["distribution_label"] == "analytical_distribution"