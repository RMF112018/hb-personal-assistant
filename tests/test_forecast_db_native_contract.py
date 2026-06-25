"""Phase B — DB-native generation contract & routing boundary.

Proves the new explicit `db_native` mode: the route/service is fail-closed and package-free (never
calls package-backed generation), its request/response contract + public DTO are path-free, and the
existing `db_config` / `file_config` behaviors are unchanged. No DB-native engine exists yet.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.config.path_policy import PathPolicy  # noqa: E402
from hb_assistant.construction.analytics import (  # noqa: E402
    create_app,  # noqa: E402
    forecast_db_config_run_service,
    forecast_run_output_persistence_service,
)
from hb_assistant.construction.analytics.forecast_db_native_generation_service import (  # noqa: E402
    DbNativeGenerationRequest,
    generate_db_native,
)
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.construction.analytics.forecast_generation_modes import (
    GenerationMode,  # noqa: E402
)
from hb_assistant.construction.analytics.forecast_generation_request_dto import (  # noqa: E402
    validate_request,
)
from hb_assistant.construction.analytics.forecast_run_service import (  # noqa: E402
    ENV_DATA_ROOT,
    ENV_RUNS_ROOT,
)
from hb_assistant.construction.analytics.forecast_runtime_config import (  # noqa: E402
    ENV_DB_CONFIG_RUN_ENABLED,
)
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402
from tests.schedule_project_test_helpers import seed_procore_ep_project  # noqa: E402


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _seed_live_db() -> None:
    db = Path(PathPolicy().get_db_path())
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Resort")


def _db_native_client() -> TestClient:
    # The db-native route fails closed before any generation/storage work, so it needs only a
    # migrated + seeded app DB (request persistence + the project resolver).
    _seed_live_db()
    return TestClient(create_app(db_path=str(PathPolicy().get_db_path())))


# -- enum + validation boundary -----------------------------------------------


def test_generation_mode_enum_values() -> None:
    # Three distinct modes; wire/stored values are stable strings.
    assert GenerationMode.FILE_CONFIG.value == "file_config"
    assert GenerationMode.DB_CONFIG_PACKAGE.value == "db_config"  # back-compat value (not db_config_package)
    assert GenerationMode.DB_NATIVE.value == "db_native"
    # StrEnum members behave as plain strings on the wire.
    assert GenerationMode.DB_NATIVE == "db_native"


def test_validate_request_generator_kind_by_mode() -> None:
    body = {"project_key": "tropical", "generator_kind": "monthly"}
    # file_config ignores generator_kind (legacy run); db_config + db_native validate it.
    assert validate_request(body, mode="file_config")[0]["generator_kind"] is None
    assert validate_request(body, mode="db_config")[0]["generator_kind"] == "monthly"
    assert validate_request(body, mode="db_native")[0]["generator_kind"] == "monthly"
    # An invalid kind is rejected on the db_native path too.
    _, errors = validate_request({"project_key": "tropical", "generator_kind": "bogus"}, mode="db_native")
    assert "invalid_generator_kind" in errors


def test_validate_request_forecast_end_date_and_ordering() -> None:
    base = {"project_key": "tropical"}
    # Valid optional forecast_end_date is parsed through.
    parsed, errors = validate_request(
        {**base, "forecast_cutoff_date": "2026-06-30", "forecast_end_date": "2026-12-31"},
        mode="db_native",
    )
    assert errors == []
    assert parsed["forecast_end_date"] == "2026-12-31"
    # Absent forecast_end_date is None (degraded monthly downstream, not an error).
    parsed, errors = validate_request(base, mode="db_native")
    assert parsed["forecast_end_date"] is None and errors == []
    # Malformed end date is rejected.
    _, errors = validate_request({**base, "forecast_end_date": "2026-13-40"}, mode="db_native")
    assert "invalid_forecast_end_date" in errors
    # cutoff after end is rejected.
    _, errors = validate_request(
        {**base, "forecast_cutoff_date": "2026-12-31", "forecast_end_date": "2026-06-30"},
        mode="db_native",
    )
    assert "forecast_cutoff_after_end" in errors
    # start after end is rejected.
    _, errors = validate_request(
        {**base, "forecast_start_date": "2027-01-01", "forecast_end_date": "2026-06-30"},
        mode="db_native",
    )
    assert "forecast_start_after_end" in errors


# -- service-level fail-closed seam -------------------------------------------


def test_generate_db_native_is_fail_closed_and_path_free() -> None:
    # Phase F: with the run-output DB-write gate OFF (default), the seam refuses honestly rather than
    # computing-and-dropping — and never reports the legacy db_native_generation_not_implemented.
    result = generate_db_native(
        DbNativeGenerationRequest(project_key="tropical", generator_kind="comprehensive")
    )
    assert result.request_status == "failed"
    assert result.db_persisted is False
    assert result.failure_code == "run_output_db_write_disabled"
    assert result.failure_message  # curated, present
    assert result.persisted_output_ids == ()
    assert result.mode == "db_native"
    assert find_redaction_leaks({"failure_message": result.failure_message}) == []


def test_db_native_service_module_has_no_package_generation_dependency() -> None:
    # Import/call boundary guard: the seam must not REFERENCE any package-backed generation symbol.
    # AST-based so the module's own docstring (which names what it must not call) is not a false hit —
    # only real identifiers, attribute accesses, and import paths are inspected.
    import ast

    src = Path(
        "src/hb_assistant/construction/analytics/forecast_db_native_generation_service.py"
    ).read_text()
    names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    forbidden = (
        "_run_generation",
        "generate_and_persist",
        "start_db_config_run",
        "run_controlled_context_analysis_workflow",
        "run_controlled_live_db_run_output_projection",
        "package_resolution",
        "construction_financial_review",
    )
    leaked = [tok for tok in forbidden if any(tok in name for name in names)]
    assert leaked == [], f"db-native seam references package-generation symbols: {leaked}"


# -- route: fail-closed, path-free, package-free ------------------------------


def test_db_native_route_fails_closed_path_free() -> None:
    client = _db_native_client()
    resp = client.post(
        "/api/forecast/runs/db-native", headers=_op(), json={"project_key": "tropical"}
    )
    assert resp.status_code == 200  # fail-closed is a failed REQUEST, not an HTTP error
    body = resp.json()
    assert body["generation_mode"] == "db_native"
    assert body["request_status"] == "failed"
    # Phase F: gate OFF by default → honest run_output_db_write_disabled refusal (no compute/persist).
    assert body["failure_code"] == "run_output_db_write_disabled"
    assert body["db_persisted"] is False
    assert body["package_generated"] is False
    assert body["persisted_output_ids"] == []
    assert body["source_snapshot_id"] is None
    assert body["failure_message"]
    assert find_redaction_leaks(body) == []


def test_db_native_route_requires_operator() -> None:
    client = _db_native_client()
    assert (
        client.post(
            "/api/forecast/runs/db-native", headers=_viewer(), json={"project_key": "tropical"}
        ).status_code
        == 403
    )


def test_db_native_route_echoes_source_snapshot_id() -> None:
    client = _db_native_client()
    body = client.post(
        "/api/forecast/runs/db-native",
        headers=_op(),
        json={"project_key": "tropical", "source_snapshot_id": "snap-xyz"},
    ).json()
    # Phase B: provenance is a pass-through contract field (not persisted).
    assert body["source_snapshot_id"] == "snap-xyz"
    assert find_redaction_leaks(body) == []


def test_db_native_route_invalid_kind_400() -> None:
    client = _db_native_client()
    resp = client.post(
        "/api/forecast/runs/db-native",
        headers=_op(),
        json={"project_key": "tropical", "generator_kind": "bogus"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_generator_kind"


def test_db_native_route_does_not_call_package_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    # Every package-backed generation seam is rigged to explode if invoked. The fail-closed route
    # must still return cleanly, proving it never reaches package generation.
    def _boom(*_a, **_k):
        raise AssertionError("package-backed generation must not be called on the db-native path")

    monkeypatch.setattr(forecast_run_output_persistence_service, "generate_and_persist", _boom)
    monkeypatch.setattr(forecast_run_output_persistence_service, "_run_generation", _boom)
    monkeypatch.setattr(
        forecast_db_config_run_service.ForecastDbConfigRunService, "start_db_config_run", _boom
    )
    # A CFR import on this path would itself be a violation; make any such import fail loudly.
    monkeypatch.setitem(sys.modules, "construction_financial_review", types.ModuleType("blocked"))

    client = _db_native_client()
    body = client.post(
        "/api/forecast/runs/db-native", headers=_op(), json={"project_key": "tropical"}
    ).json()
    assert body["request_status"] == "failed"
    # Gate OFF (default): the route refuses before any compute/import, so package generation and a
    # CFR import are never reached.
    assert body["failure_code"] == "run_output_db_write_disabled"


def test_db_native_request_recorded_in_public_dto_path_free() -> None:
    client = _db_native_client()
    client.post("/api/forecast/runs/db-native", headers=_op(), json={"project_key": "tropical"})
    listed = client.get(
        "/api/forecast/generation/requests?project_key=tropical", headers=_viewer()
    ).json()
    row = next(r for r in listed["requests"] if r["generation_mode"] == "db_native")
    assert row["request_status"] == "failed"
    assert row["failure_code"] == "run_output_db_write_disabled"
    assert find_redaction_leaks(listed) == []


# -- existing modes unchanged (boundary is additive) --------------------------


def _fake_db_config_report(**kwargs):
    return {
        "command": "forecast-db-config-backed-generate",
        "status": "generated",
        "config_snapshot_consumed": True,
        "snapshot_name": "tropical-live-config",
        "snapshot_item_count": 7,
        "fidelity_gate": {"passed": True},
        "validation_passed": True,
        "live_db_integrity": {"unchanged": True, "drift": []},
    }


def _install_fake_db_config_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = sys.modules.get("construction_financial_review") or types.ModuleType(
        "construction_financial_review"
    )
    wf = sys.modules.get("construction_financial_review.workflows") or types.ModuleType(
        "construction_financial_review.workflows"
    )
    mod = types.ModuleType(
        "construction_financial_review.workflows.forecast_db_config_backed_generation"
    )
    mod.run_forecast_db_config_backed_generation = _fake_db_config_report  # type: ignore[attr-defined]
    mod.run_forecast_db_config_backed_generation_for_kind = _fake_db_config_report  # type: ignore[attr-defined]
    mod.ForecastDbConfigGenerationError = RuntimeError  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "construction_financial_review", pkg)
    monkeypatch.setitem(sys.modules, "construction_financial_review.workflows", wf)
    monkeypatch.setitem(
        sys.modules,
        "construction_financial_review.workflows.forecast_db_config_backed_generation",
        mod,
    )


def test_db_config_route_still_records_db_config_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The db-config package route is unchanged: it still records generation_mode "db_config" (NOT
    # "db_config_package") and succeeds via the package workflow.
    (tmp_path / "data").mkdir()
    monkeypatch.setenv(ENV_DATA_ROOT, str(tmp_path / "data"))
    monkeypatch.setenv(ENV_RUNS_ROOT, str(tmp_path / "runs"))
    monkeypatch.setenv(ENV_DB_CONFIG_RUN_ENABLED, "1")
    _seed_live_db()
    _install_fake_db_config_workflow(monkeypatch)
    client = TestClient(create_app(db_path=str(PathPolicy().get_db_path())))
    body = client.post(
        "/api/forecast/runs/db-config", headers=_op(), json={"project_key": "tropical"}
    ).json()
    assert body["generation_mode"] == "db_config"
    assert body["status"] == "generated"
    listed = client.get(
        "/api/forecast/generation/requests?project_key=tropical", headers=_viewer()
    ).json()
    assert any(r["generation_mode"] == "db_config" for r in listed["requests"])
    assert not any(r["generation_mode"] == "db_config_package" for r in listed["requests"])
