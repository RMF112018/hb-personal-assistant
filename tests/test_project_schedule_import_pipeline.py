"""Project-scoped schedule import pipeline tests (Phase A1)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics.api import create_app
from hb_assistant.construction.analytics.project_schedule_driver_analysis_service import (
    ProjectScheduleDriverAnalysisService,
)
from hb_assistant.construction.analytics.project_schedule_narrative_qa import validate_summary
from hb_assistant.construction.analytics.schedule_cpm_read_service import ScheduleCpmReadService
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

XER = Path(__file__).parent / "fixtures" / "schedules" / "xer" / "minimal.xer"


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _client(tmp_path: Path) -> TestClient:
    db = tmp_path / "project_import.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return TestClient(create_app(db_path=str(db)))


def _project_preview(client: TestClient, *, project_key: str = "tropical") -> dict:
    resp = client.post(
        f"/api/projects/{project_key}/schedule/import-preview",
        headers=_op(),
        files={"file": ("minimal.xer", XER.read_bytes(), "application/xml")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _project_commit(client: TestClient, preview: dict, *, project_key: str = "tropical") -> dict:
    resp = client.post(
        f"/api/projects/{project_key}/schedule/import-commit",
        headers=_op(),
        json={
            "import_id": preview["import_id"],
            "project_key": project_key,
            "confirm": True,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_project_import_preview_requires_operator(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post(
        "/api/projects/tropical/schedule/import-preview",
        headers=_viewer(),
        files={"file": ("minimal.xer", XER.read_bytes(), "application/xml")},
    )
    assert resp.status_code == 403


def test_project_import_preview_locks_route_project(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _project_preview(client, project_key="tropical")
    assert preview["project_key"] == "tropical"
    assert preview["pipeline_scope"] == "project_schedule_import"
    assert preview["activity_count"] == 2
    assert "trust_preview" in preview
    assert preview["analytics_trust"]["analytics_trust_status"] in {"ready", "degraded", "blocked"}


def test_zip_html_companion_is_ignored_not_parsed(tmp_path: Path) -> None:
    client = _client(tmp_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        zf.writestr("minimal.xer", XER.read_bytes())
        zf.writestr(
            "report.html",
            b"<html><body><h1>Schedule report</h1></body></html>",
        )
    resp = client.post(
        "/api/projects/tropical/schedule/import-preview",
        headers=_op(),
        files={"file": ("package-with-html.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["package_mode"] == "zip_package"
    assert any(w["code"] == "unsupported_package_file_ignored" for w in body["warnings"])
    trust = body.get("analytics_trust") or {}
    joined = " ".join(trust.get("trust_reasons") or [])
    assert "report.html" in joined or any(
        "report.html" in str(row.get("filename") or "")
        for row in trust.get("ignored_companion_files") or []
    )
    assert body["activity_count"] == 2


def test_project_body_project_mismatch_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _project_preview(client)
    resp = client.post(
        "/api/projects/tropical/schedule/import-commit",
        headers=_op(),
        json={
            "import_id": preview["import_id"],
            "project_key": "other-project",
            "confirm": True,
        },
    )
    assert resp.status_code == 400


def test_project_commit_triggers_cpm_recompute(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _project_preview(client)
    commit = _project_commit(client, preview)
    assert commit["cpm_recompute_triggered"] is True
    assert commit["cpm_recompute_status"] in {"complete", "partial"}
    summary = ScheduleCpmReadService(db_path=str(tmp_path / "project_import.db")).cpm_summary(
        commit["schedule_version_key"]
    )
    assert summary["available"] is True
    assert summary["runs"]["forward_pass"]["available"] is True
    assert summary["runs"]["criticality"]["available"] is True


def test_project_import_status_exposes_pipeline_stages(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _project_preview(client)
    commit = _project_commit(client, preview)
    status = client.get(
        f"/api/projects/tropical/schedule/imports/{commit['import_id']}/status",
        headers=_viewer(),
    ).json()
    assert status["import_id"] == commit["import_id"]
    stage_keys = [stage["stage"] for stage in status["stages"]]
    assert "cpm_recompute" in stage_keys
    cpm_stage = next(s for s in status["stages"] if s["stage"] == "cpm_recompute")
    assert cpm_stage["status"] in {"complete", "partial", "pending"}


def test_project_cpm_retry_is_operator_gated(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = _project_preview(client)
    commit = _project_commit(client, preview)
    denied = client.post(
        f"/api/projects/tropical/schedule/imports/{commit['import_id']}/recompute-cpm",
        headers=_viewer(),
    )
    assert denied.status_code == 403
    ok = client.post(
        f"/api/projects/tropical/schedule/imports/{commit['import_id']}/recompute-cpm",
        headers=_op(),
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["cpm_recompute_triggered"] is True


def test_standalone_import_also_triggers_cpm(tmp_path: Path) -> None:
    client = _client(tmp_path)
    preview = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": ("minimal.xer", XER.read_bytes(), "application/xml")},
        data={"project_key": "tropical"},
    ).json()
    commit = client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": preview["import_id"], "project_key": "tropical", "confirm": True},
    ).json()
    assert commit["cpm_recompute_triggered"] is True
    assert commit["cpm_recompute_status"] in {"complete", "partial"}


def test_build_narrative_never_emits_zero_day_movement() -> None:
    service = ProjectScheduleDriverAnalysisService(db_path=":memory:")
    narrative = service.build_narrative(
        {
            "available": True,
            "top_drivers": [
                {
                    "activity_id": "A100",
                    "activity_name": "Pour Concrete",
                    "display_wbs": "1.2",
                    "finish_delta_days": 0,
                    "start_delta_days": 0,
                    "downstream_moved_later_count": 4,
                    "movement_basis": "downstream_cluster",
                    "context_quality": "high",
                }
            ],
        }
    )
    text = narrative["primary_driver_narrative"].lower()
    assert "0 days" not in text
    assert "did not move materially" in text


def test_narrative_qa_flags_zero_day_movement() -> None:
    qa = validate_summary(
        {
            "schedule_story": {
                "primary_driver_narrative": "Activity A moved or extended by 0 days and appears connected.",
            },
            "command_summary": {},
            "change_impact": {"available": False},
            "change_driver_analysis": {"available": False},
            "review_workbench": {"available": False},
        }
    )
    assert qa["passed"] is False
    assert any(v["code"] == "zero_day_movement" for v in qa["violations"])