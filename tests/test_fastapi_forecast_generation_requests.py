"""FastAPI route tests for the P-C generation-request contract + persistence.

Uses an injected FAKE CFR db-config workflow (no real generation) and a migrated+seeded temp app DB.
Asserts: a valid request persists a row + returns request_id; project_key is required; unknown
project / bad dates / start>cutoff are rejected (coded, no generation); generator_kind + cutoff basis
persist; controlled failure / disabled update the row; GET /generation/requests filters + is
redaction-safe.
"""

from __future__ import annotations

import sqlite3
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
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402
from tests.schedule_project_test_helpers import seed_procore_ep_project  # noqa: E402

TS = "2026-06-19T08:00:00+00:00"


def _fake_report(**kwargs):
    return {
        "command": "forecast-db-config-backed-generate",
        "status": "generated",
        "config_snapshot_consumed": True,
        "snapshot_name": "tropical-phase16-live-config",
        "snapshot_item_count": 194,
        "fidelity_gate": {"passed": True, "snapshot_sha256_match": True, "item_count_match": True},
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


def _seed_ready_tropical(db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Resort")
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO schedule_file_imports (import_id, project_key, source_type, source_format, "
            "import_status, activity_count, relationship_count, wbs_count, calendar_count, "
            "code_count, udf_count, cost_loaded_status, schedule_version_key, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("imp-t", "tropical", "xer", "primavera_xer", "committed", 1, 0, 0, 0, 0, 0,
             "not_cost_loaded", "tropical|S1|2026-01-01", TS),
        )
        conn.execute(
            "INSERT INTO procore_ep_schedule_activities (project_key, schedule_id, "
            "schedule_version_key, import_id, source_type, source_format, activity_id) "
            "VALUES (?,?,?,?,?,?,?)",
            ("tropical", "S1", "tropical|S1|2026-01-01", "imp-t", "xer", "primavera_xer", "A1"),
        )
        conn.execute(
            "INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES (?,?,?)",
            ("20260101_000000", "tropical", TS),
        )
        conn.execute(
            "INSERT INTO forecast_outputs (output_id, run_id, project_key, source_package, "
            "raw_json, created_utc) VALUES (?,?,?,?,?,?)",
            ("fout-req000000000000000000000000001", "20260101_000000", "tropical",
             "forecast_analysis_package_tropical_20260101_000000", "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_config_snapshots (config_snapshot_id, project_key, snapshot_name, "
            "snapshot_created_utc, snapshot_reason, source_mode, item_count, snapshot_sha256, "
            "created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
            ("snap-t", "tropical", "tropical-config", TS, "initial", "db", 5, "deadbeef", TS),
        )
        conn.execute(
            "INSERT INTO forecast_budget_details (project_key, budget_code_key, source_package, "
            "raw_json, created_utc) VALUES (?,?,?,?,?)",
            ("tropical", "0000.03.MAT", "pkg-t", "{}", TS),
        )
        # Actual cost so readiness is full_context/ready (budget + cost + schedule + prior + config).
        conn.execute(
            "INSERT INTO forecast_cost_entries (cost_entry_id, project_key, source_package, "
            "source_row_number, budget_code_key, raw_json, created_utc) VALUES (?,?,?,?,?,?,?)",
            ("ce-req-1", "tropical", "pkg-t", 1, "0000.03.MAT", "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_monthly_actuals_by_budget_code (project_key, budget_code_key, "
            "month, type, source_package, amount, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?)",
            ("tropical", "0000.03.MAT", "2026-01", "actual", "pkg-t", 1500.0, "{}", TS),
        )
        conn.commit()
    finally:
        conn.close()


def _client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, enabled: bool = True, report_fn=_fake_report
) -> TestClient:
    monkeypatch.setenv(ENV_DATA_ROOT, str(tmp_path / "data"))
    (tmp_path / "data").mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_RUNS_ROOT, str(tmp_path / "runs"))
    if enabled:
        monkeypatch.setenv(ENV_DB_CONFIG_RUN_ENABLED, "1")
    else:
        monkeypatch.delenv(ENV_DB_CONFIG_RUN_ENABLED, raising=False)
    db = Path(PathPolicy().get_db_path())
    db.parent.mkdir(parents=True, exist_ok=True)
    _seed_ready_tropical(db)
    _install_fake_workflow(monkeypatch, report_fn=report_fn)
    return TestClient(create_app(db_path=str(db)))


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _post_db(client: TestClient, **body):
    return client.post("/api/forecast/runs/db-config", headers=_op(), json=body)


def test_valid_request_persists_row_and_returns_request_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    resp = _post_db(
        client,
        project_key="tropical",
        generator_kind="comprehensive",
        forecast_start_date="2026-06-01",
        forecast_cutoff_date="2026-06-24",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["request_id"]
    assert body["generation_mode"] == "db_config"
    assert body["generator_kind"] == "comprehensive"
    assert body["request_status"] == "completed"
    assert body["validation_status"] == "valid"
    assert body["forecast_start_date"] == "2026-06-01"
    assert body["forecast_cutoff_date"] == "2026-06-24"
    assert body["forecast_cutoff_date_basis"] == "operator_supplied"
    assert body["readiness_status_at_request"] == "ready"
    assert body["status"] == "generated"  # underlying generation summary preserved (additive)
    assert find_redaction_leaks(body) == []

    listed = client.get(
        "/api/forecast/generation/requests", params={"project_key": "tropical"}, headers=_viewer()
    ).json()
    assert listed["surface"] == "analytics.forecast_generation_requests"
    item = next(r for r in listed["requests"] if r["request_id"] == body["request_id"])
    assert item["project_key"] == "tropical"
    assert item["generator_kind"] == "comprehensive"
    assert item["request_status"] == "completed"
    assert item["run_id"]
    assert find_redaction_leaks(listed) == []


def test_missing_project_key_400_no_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    resp = _post_db(client, generator_kind="comprehensive")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "missing_project_key"
    listed = client.get("/api/forecast/generation/requests", headers=_viewer()).json()
    assert listed["requests"] == []


def test_unknown_project_rejected_and_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    resp = _post_db(client, project_key="ghost", generator_kind="comprehensive")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "unknown_project_key"
    listed = client.get(
        "/api/forecast/generation/requests", params={"project_key": "ghost"}, headers=_viewer()
    ).json()
    assert len(listed["requests"]) == 1
    assert listed["requests"][0]["request_status"] == "rejected"
    assert listed["requests"][0]["validation_status"] == "invalid"


def test_invalid_date_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    resp = _post_db(client, project_key="tropical", forecast_start_date="06/01/2026")
    assert resp.status_code == 422
    assert resp.json()["detail"] == "invalid_forecast_start_date"


def test_start_after_cutoff_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    resp = _post_db(
        client, project_key="tropical", forecast_start_date="2026-07-01",
        forecast_cutoff_date="2026-06-01",
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "forecast_start_after_cutoff"


def test_db_config_persists_generator_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    body = _post_db(client, project_key="tropical", generator_kind="monthly").json()
    assert body["generator_kind"] == "monthly"
    item = client.get(
        "/api/forecast/generation/requests", params={"project_key": "tropical"}, headers=_viewer()
    ).json()["requests"][0]
    assert item["generator_kind"] == "monthly"


def test_controlled_failure_marks_request_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _refuse(**kwargs):
        raise _FakeError("cost_frequency_package_missing: forecast_cost_frequency package missing")

    client = _client(tmp_path, monkeypatch, report_fn=_refuse)
    body = _post_db(client, project_key="tropical", generator_kind="comprehensive").json()
    assert body["status"] == "failed"  # controlled refusal => failed RUN, HTTP 200
    assert body["request_status"] == "failed"
    item = client.get(
        "/api/forecast/generation/requests", params={"project_key": "tropical"}, headers=_viewer()
    ).json()["requests"][0]
    assert item["request_status"] == "failed"


def test_disabled_fails_closed_and_records_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch, enabled=False)
    resp = _post_db(client, project_key="tropical", generator_kind="comprehensive")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "forecast_db_config_run_disabled"  # existing contract preserved
    item = client.get(
        "/api/forecast/generation/requests", params={"project_key": "tropical"}, headers=_viewer()
    ).json()["requests"][0]
    assert item["request_status"] == "rejected"
    assert item["failure_code"] == "generation_disabled"


def test_requests_list_filters_by_project_and_clamps_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    _post_db(client, project_key="tropical", generator_kind="comprehensive")
    _post_db(client, project_key="tropical", generator_kind="monthly")
    all_reqs = client.get(
        "/api/forecast/generation/requests", params={"limit": 1}, headers=_viewer()
    ).json()
    assert len(all_reqs["requests"]) == 1  # limit honored
    trop = client.get(
        "/api/forecast/generation/requests", params={"project_key": "tropical"}, headers=_viewer()
    ).json()
    assert all(r["project_key"] == "tropical" for r in trop["requests"])
    assert find_redaction_leaks(trop) == []


# -- P-D: schedule-derived cut-off basis verification -------------------------


def test_accepted_schedule_data_date_basis_persists_with_version_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The seeded committed import encodes data date 2026-01-01 (schedule_version_key tropical|S1|...).
    client = _client(tmp_path, monkeypatch)
    body = _post_db(
        client,
        project_key="tropical",
        generator_kind="comprehensive",
        forecast_cutoff_date="2026-01-01",
        forecast_cutoff_date_basis="schedule_data_date",
    ).json()
    assert body["forecast_cutoff_date_basis"] == "schedule_data_date"
    assert body["schedule_version_key"] == "tropical|S1|2026-01-01"
    item = client.get(
        "/api/forecast/generation/requests", params={"project_key": "tropical"}, headers=_viewer()
    ).json()["requests"][0]
    assert item["forecast_cutoff_date_basis"] == "schedule_data_date"
    assert item["schedule_version_key"] == "tropical|S1|2026-01-01"


def test_operator_edited_cutoff_persists_operator_supplied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    body = _post_db(
        client,
        project_key="tropical",
        generator_kind="comprehensive",
        forecast_cutoff_date="2026-05-05",
        forecast_cutoff_date_basis="operator_supplied",
    ).json()
    assert body["forecast_cutoff_date_basis"] == "operator_supplied"


def test_mismatched_schedule_basis_downgrades_to_operator_supplied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Claims schedule_data_date but the date does not match the resolver → deterministic downgrade.
    client = _client(tmp_path, monkeypatch)
    body = _post_db(
        client,
        project_key="tropical",
        generator_kind="comprehensive",
        forecast_cutoff_date="2099-12-31",
        forecast_cutoff_date_basis="schedule_data_date",
    ).json()
    assert body["forecast_cutoff_date_basis"] == "operator_supplied"
    assert body["schedule_version_key"] is None


def test_invalid_cutoff_basis_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    resp = _post_db(
        client,
        project_key="tropical",
        forecast_cutoff_date="2026-01-01",
        forecast_cutoff_date_basis="bogus_basis",
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_forecast_cutoff_date_basis"
