"""FastAPI route tests for the Forecast Run Center (Implementation Phase 3).

Uses an injected FAKE CFR workflow (no real generation). Asserts: POST is operator-gated and
GET is viewer-readable, responses carry the honest guardrails + leak no dev-internals, not-
configured fails closed (503), and unknown run 404.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.construction.analytics.forecast_run_service import (  # noqa: E402
    ENV_DATA_ROOT,
    ENV_RUNS_ROOT,
)
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402
from tests.schedule_project_test_helpers import seed_procore_ep_project  # noqa: E402


def _fake_report(**kwargs):
    stamp = kwargs["context_stamp"]
    return {
        "schema_version": 1,
        "project_key": "tropical",
        "mode": "file",
        "data_root": "/Users/bobbyfetting/live/2026-June",
        "work_root": str(kwargs["work_root"]),
        "context_stamp": stamp,
        "db_backed": False,
        "db_path": None,
        "context_package": f"/Users/bobbyfetting/x/forecast_context_package_tropical_{stamp}",
        "context_package_stamp": stamp,
        "analysis_package": "/Users/bobbyfetting/x/forecast_analysis_package_tropical_20260101_000000",
        "analysis_package_stamp": "20260101_000000",
        "chain_manifest": "/Users/bobbyfetting/x/chain.json",
        "safety_checks": {
            "project_key_supported": True,
            "data_root_is_dir": True,
            "work_root_outside_live_root": True,
            "explicit_context_stamp": True,
            "explicit_paths_only": True,
            "no_latest_glob": True,
            "db_path_required_for_db_mode": True,
            "db_path_rejected_in_file_mode": True,
        },
        "status": "ok",
        "report_path": "/Users/bobbyfetting/x/report.json",
    }


def _install_fake_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = types.ModuleType("construction_financial_review")
    wf = types.ModuleType("construction_financial_review.workflows")
    mod = types.ModuleType("construction_financial_review.workflows.controlled_db_context_analysis")
    mod.run_controlled_context_analysis_workflow = _fake_report  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "construction_financial_review", pkg)
    monkeypatch.setitem(sys.modules, "construction_financial_review.workflows", wf)
    monkeypatch.setitem(
        sys.modules, "construction_financial_review.workflows.controlled_db_context_analysis", mod
    )


def _configured_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv(ENV_DATA_ROOT, str(data))
    monkeypatch.setenv(ENV_RUNS_ROOT, str(tmp_path / "runs"))
    _install_fake_workflow(monkeypatch)
    # P-C: migrate + seed the app DB so request persistence + the project resolver work.
    db = tmp_path / "x.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Resort")
    return TestClient(create_app(db_path=str(db)))


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def test_create_list_read_run_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    created = client.post("/api/forecast/runs", headers=_op(), json={"project_key": "tropical"})
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "succeeded"
    assert body["guardrails"]["no_live_db_write"] is True
    assert find_redaction_leaks(body) == []
    run_id = body["run_id"]

    listed = client.get("/api/forecast/runs", headers=_viewer()).json()
    assert any(r["run_id"] == run_id for r in listed["runs"])
    assert find_redaction_leaks(listed) == []

    detail = client.get(f"/api/forecast/runs/{run_id}", headers=_viewer())
    assert detail.status_code == 200
    assert find_redaction_leaks(detail.json()) == []


def test_post_requires_operator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    resp = client.post("/api/forecast/runs", headers=_viewer())
    assert resp.status_code == 403


def test_not_configured_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_DATA_ROOT, raising=False)
    monkeypatch.delenv(ENV_RUNS_ROOT, raising=False)
    db = tmp_path / "x.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Resort")
    client = TestClient(create_app(db_path=str(db)))
    resp = client.post("/api/forecast/runs", headers=_op(), json={"project_key": "tropical"})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "forecast_runs_not_configured"


def test_unknown_run_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    resp = client.get("/api/forecast/runs/nope", headers=_viewer())
    assert resp.status_code == 404
    assert resp.json()["detail"] == "forecast_run_not_found"


def test_invalid_role_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    resp = client.get("/api/forecast/runs", headers={"X-HB-UI-Role": "root"})
    assert resp.status_code == 403
