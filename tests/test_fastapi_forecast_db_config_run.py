"""FastAPI route tests for DB-config-backed comprehensive generation (Run Center).

Uses an injected FAKE CFR workflow (no real generation). Asserts: POST is operator-gated and GET is
viewer-readable; the default-OFF opt-in fails closed (503); not-configured fails closed (503); unknown
run 404; route ordering ("db-config" is not swallowed by {run_id}); and NO dev-internals leak.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.config.path_policy import PathPolicy  # noqa: E402
from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.construction.analytics.forecast_run_service import (  # noqa: E402
    ENV_DATA_ROOT,
    ENV_RUNS_ROOT,
)
from hb_assistant.construction.analytics.forecast_runtime_config import (  # noqa: E402
    ENV_DB_CONFIG_RUN_ENABLED,
)


def _fake_report(**kwargs):
    work_root = kwargs["work_root"]
    # Path-saturated report (like the real workflow) so the redaction scan is meaningful.
    return {
        "command": "forecast-db-config-backed-generate",
        "status": "generated",
        "config_snapshot_consumed": True,
        "config_snapshot_id": "abc123deadbeef",
        "snapshot_name": "tropical-phase16-live-config",
        "snapshot_item_count": 194,
        "fidelity_gate": {"passed": True, "snapshot_sha256_match": True, "item_count_match": True},
        "materialized_config_root": f"{work_root}/db_snapshot_config/materialized_config",
        "live_db_path": "/Users/bobbyfetting/Library/Application Support/HB/db/hb.sqlite",
        "data_root": "/Users/bobbyfetting/live/2026-June",
        "output_package": "/Users/bobbyfetting/x/forecast_comprehensive_package_tropical_20260101_000000",
        "validation_passed": True,
        "live_db_integrity": {"unchanged": True, "drift": []},
    }


class _FakeError(RuntimeError):
    pass


def _install_fake_workflow(monkeypatch: pytest.MonkeyPatch, *, report_fn=_fake_report) -> None:
    pkg = sys.modules.get("construction_financial_review") or types.ModuleType(
        "construction_financial_review"
    )
    wf = sys.modules.get("construction_financial_review.workflows") or types.ModuleType(
        "construction_financial_review.workflows"
    )
    mod = types.ModuleType(
        "construction_financial_review.workflows.forecast_db_config_backed_generation"
    )
    mod.run_forecast_db_config_backed_generation = report_fn  # type: ignore[attr-defined]
    mod.run_forecast_db_config_backed_generation_for_kind = report_fn  # type: ignore[attr-defined]
    mod.ForecastDbConfigGenerationError = _FakeError  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "construction_financial_review", pkg)
    monkeypatch.setitem(sys.modules, "construction_financial_review.workflows", wf)
    monkeypatch.setitem(
        sys.modules,
        "construction_financial_review.workflows.forecast_db_config_backed_generation",
        mod,
    )


def _make_live_db() -> None:
    db = Path(PathPolicy().get_db_path())
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_bytes(b"")  # only existence is required (the fake workflow does not read it)


def _configured_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, enabled: bool = True, report_fn=_fake_report
) -> TestClient:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv(ENV_DATA_ROOT, str(data))
    monkeypatch.setenv(ENV_RUNS_ROOT, str(tmp_path / "runs"))
    if enabled:
        monkeypatch.setenv(ENV_DB_CONFIG_RUN_ENABLED, "1")
    else:
        monkeypatch.delenv(ENV_DB_CONFIG_RUN_ENABLED, raising=False)
    _make_live_db()
    _install_fake_workflow(monkeypatch, report_fn=report_fn)
    return TestClient(create_app(db_path=str(PathPolicy().get_db_path())))


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def test_create_list_read_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    created = client.post("/api/forecast/runs/db-config", headers=_op())
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "generated"
    assert body["config_snapshot_consumed"] is True
    assert body["snapshot_display"] == "tropical-phase16-live-config"
    assert body["snapshot_item_count"] == 194
    assert body["fidelity_gate_passed"] is True
    assert body["guardrails"]["live_db_opened_read_only"] is True
    assert find_redaction_leaks(body) == []
    run_id = body["run_id"]

    listed = client.get("/api/forecast/runs/db-config", headers=_viewer()).json()
    assert any(r["run_id"] == run_id for r in listed["runs"])
    assert find_redaction_leaks(listed) == []

    detail = client.get(f"/api/forecast/runs/db-config/{run_id}", headers=_viewer())
    assert detail.status_code == 200
    assert find_redaction_leaks(detail.json()) == []
    # Route ordering: "db-config" was not swallowed by the {run_id} catch-all.
    assert detail.json()["config_snapshot_consumed"] is True


def test_post_requires_operator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    assert client.post("/api/forecast/runs/db-config", headers=_viewer()).status_code == 403


def test_disabled_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch, enabled=False)
    resp = client.post("/api/forecast/runs/db-config", headers=_op())
    assert resp.status_code == 503
    assert resp.json()["detail"] == "forecast_db_config_run_disabled"


def test_not_configured_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_DATA_ROOT, raising=False)
    monkeypatch.delenv(ENV_RUNS_ROOT, raising=False)
    monkeypatch.setenv(ENV_DB_CONFIG_RUN_ENABLED, "1")
    client = TestClient(create_app(db_path=str(tmp_path / "x.sqlite")))
    resp = client.post("/api/forecast/runs/db-config", headers=_op())
    assert resp.status_code == 503
    assert resp.json()["detail"] == "forecast_db_config_run_not_configured"


def test_unknown_run_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    resp = client.get("/api/forecast/runs/db-config/nope", headers=_viewer())
    assert resp.status_code == 404
    assert resp.json()["detail"] == "forecast_db_config_run_not_found"


def test_default_post_is_comprehensive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    body = client.post("/api/forecast/runs/db-config", headers=_op()).json()
    assert body["kind"] == "comprehensive"
    assert body["display_label"].startswith("Comprehensive forecast from live config")
    assert find_redaction_leaks(body) == []


def test_post_generator_kind_threads_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    created = client.post(
        "/api/forecast/runs/db-config", headers=_op(), json={"generator_kind": "monthly"}
    )
    assert created.status_code == 200
    body = created.json()
    assert body["kind"] == "monthly"
    assert body["display_label"].startswith("Monthly forecast from live config")
    assert find_redaction_leaks(body) == []
    run_id = body["run_id"]

    # The kind round-trips through list + detail, and remains redaction-clean.
    listed = client.get("/api/forecast/runs/db-config", headers=_viewer()).json()
    item = next(r for r in listed["runs"] if r["run_id"] == run_id)
    assert item["kind"] == "monthly"
    detail = client.get(f"/api/forecast/runs/db-config/{run_id}", headers=_viewer()).json()
    assert detail["kind"] == "monthly"
    assert find_redaction_leaks(listed) == [] and find_redaction_leaks(detail) == []


def test_post_invalid_kind_400(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/forecast/runs/db-config", headers=_op(), json={"generator_kind": "bogus"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "forecast_db_config_run_bad_kind"


def test_workflow_refusal_recorded_as_failed_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(**kwargs):
        raise _FakeError("cost_frequency_package_missing: forecast_cost_frequency package missing")

    client = _configured_client(tmp_path, monkeypatch, report_fn=_refuse)
    resp = client.post("/api/forecast/runs/db-config", headers=_op())
    assert resp.status_code == 200  # a controlled refusal is a failed RUN, not an HTTP error
    body = resp.json()
    assert body["status"] == "failed"
    assert body["config_snapshot_consumed"] is False
    assert "cost-frequency" in (body["message"] or "")
    assert find_redaction_leaks(body) == []
