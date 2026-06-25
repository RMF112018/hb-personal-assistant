"""Phase F — POST /api/forecast/runs/db-native compute → certify → persist (gate ON, temp DB).

With the run-output DB-write gate enabled and a temp app DB seeded with the v59 financial spine, the
DB-native route persists a comprehensive forecast to the v63 tables and returns a path-free,
DB-persistence-aware response — and never falls back to package-backed generation. With the gate off
it refuses honestly (run_output_db_write_disabled), and unsupported kinds / no-basis projects fail
with coded reasons and write nothing. The real managed DB is never touched (autouse temp app-support).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics import (  # noqa: E402
    forecast_run_output_persistence_service as svc,
)
from hb_assistant.construction.analytics.forecast_db_config_run_service import (  # noqa: E402
    ForecastDbConfigRunService,
)
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.construction.analytics.forecast_runtime_config import (  # noqa: E402
    ENV_RUN_OUTPUT_DB_WRITE_ENABLED,
)
from hb_assistant.construction.forecast.source_domain_repository import (  # noqa: E402
    upsert_budget_detail,
    upsert_cost_entry,
    upsert_monthly_actual,
)
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402
from tests.schedule_project_test_helpers import seed_procore_ep_project  # noqa: E402

# CFR src on path for the lazy adapter import (the forecasting bundle sets PYTHONPATH itself).
_CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(_CFR_SRC) not in sys.path:
    sys.path.insert(0, str(_CFR_SRC))

_PKG = "twn_cost_forecast_json_package"
# run_id is a legitimate public lineage identifier (request-ledger DTO exposes it) — NOT forbidden.
_FORBIDDEN_PATHS = (
    "output_package",
    "package_path",
    "work_root",
    "data_root",
    "cfr_src",
    "source_path",
    "raw_json",
    "manifest_path",
    "evidence_package_path",
)


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _seed_v59(db: Path, project_key: str) -> None:
    conn = sqlite3.connect(str(db))
    try:
        budget = [
            {"budget_code_key": "01-100", "cost_code": "01-100", "category": "labor",
             "revised_budget": "1000.00", "projected_costs": "1200.00"},
            {"budget_code_key": "02-200", "cost_code": "02-200", "category": "material",
             "revised_budget": "500.00", "projected_costs": "100.00"},
        ]
        cost = [
            {"budget_code_key": "01-100", "accounting_month": "2026-05", "amount": "250.00"},
            {"budget_code_key": "01-100", "accounting_month": "2026-06", "amount": "100.00"},
            {"budget_code_key": "02-200", "accounting_month": "2026-05", "amount": "500.00"},
        ]
        monthly = [
            {"budget_code_key": "01-100", "month": "2026-05", "type": "actual", "amount": "250.00",
             "entry_count": 1},
        ]
        for i, row in enumerate(budget, start=1):
            upsert_budget_detail(conn, {
                "project_key": project_key, "budget_code_key": row["budget_code_key"],
                "source_package": _PKG, "cost_code": row["cost_code"], "category": row["category"],
                "source_row_number": i, "raw_json": json.dumps(row),
                "created_utc": "2026-06-20T00:00:00Z"})
        for i, row in enumerate(cost, start=1):
            upsert_cost_entry(conn, {
                "cost_entry_id": f"{project_key}|{_PKG}|{i}", "project_key": project_key,
                "source_package": _PKG, "source_row_number": i,
                "budget_code_key": row["budget_code_key"],
                "accounting_month": row["accounting_month"], "raw_json": json.dumps(row),
                "created_utc": "2026-06-20T00:00:00Z"})
        for i, row in enumerate(monthly, start=1):
            upsert_monthly_actual(conn, {
                "project_key": project_key, "budget_code_key": row["budget_code_key"],
                "month": row["month"], "type": row["type"], "source_package": _PKG,
                "amount": row["amount"], "entry_count": row["entry_count"], "source_row_number": i,
                "raw_json": json.dumps(row), "created_utc": "2026-06-20T00:00:00Z"})
        conn.commit()
    finally:
        conn.close()


def _app_db(tmp_path: Path, *, with_basis: bool = True) -> Path:
    db = tmp_path / "app" / "hb.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Resort")
    if with_basis:
        _seed_v59(db, "tropical")
    return db


def _client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, enabled: bool, with_basis: bool = True
) -> tuple[TestClient, Path]:
    db = _app_db(tmp_path, with_basis=with_basis)
    if enabled:
        monkeypatch.setenv(ENV_RUN_OUTPUT_DB_WRITE_ENABLED, "1")
    else:
        monkeypatch.delenv(ENV_RUN_OUTPUT_DB_WRITE_ENABLED, raising=False)
    return TestClient(create_app(db_path=str(db))), db


def _post(client: TestClient, **body) -> dict:
    body.setdefault("project_key", "tropical")
    body.setdefault("generator_kind", "comprehensive")
    return client.post("/api/forecast/runs/db-native", headers=_op(), json=body).json()


def _no_path_leaks(body: dict) -> None:
    assert find_redaction_leaks(body) == []
    for k in _FORBIDDEN_PATHS:
        assert k not in body, f"forbidden field leaked: {k}"


# -- generated comprehensive persists -----------------------------------------


def test_generated_comprehensive_persists_to_v63(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, db = _client(tmp_path, monkeypatch, enabled=True)
    body = _post(client)
    assert body["request_status"] == "completed"
    assert body["db_persisted"] is True
    assert body["persisted_output_ids"]
    assert body.get("failure_code") is None
    counts = svc.verify_run_output_persistence(db, "tropical")
    assert counts["forecast_outputs_count"] == 1
    assert counts["budget_code_rows_count"] == 2
    _no_path_leaks(body)


def test_re_post_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, db = _client(tmp_path, monkeypatch, enabled=True)
    first = _post(client)
    second = _post(client)
    assert first["persisted_output_ids"] == second["persisted_output_ids"]
    assert svc.verify_run_output_persistence(db, "tropical")["forecast_outputs_count"] == 1


def test_no_package_fallback_on_generated_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_a, **_k):
        raise AssertionError("package-backed generation must not run on the db-native route")

    monkeypatch.setattr(svc, "_run_generation", _boom)
    monkeypatch.setattr(svc, "generate_and_persist", _boom)
    monkeypatch.setattr(ForecastDbConfigRunService, "start_db_config_run", _boom)
    client, _ = _client(tmp_path, monkeypatch, enabled=True)
    body = _post(client)
    assert body["request_status"] == "completed"
    assert body["db_persisted"] is True


# -- monthly output: persisted when a forecast horizon is supplied -----------


def test_monthly_persisted_when_forecast_end_date_supplied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from decimal import Decimal

    client, db = _client(tmp_path, monkeypatch, enabled=True)
    body = _post(
        client,
        forecast_start_date="2026-05-01",
        forecast_cutoff_date="2026-05-31",
        forecast_end_date="2026-08-31",
    )
    assert body["request_status"] == "completed"
    assert body["db_persisted"] is True
    assert body["forecast_end_date"] == "2026-08-31"
    # One seeded actual (2026-05) + three even-spread forecast months (2026-06..2026-08).
    assert svc.verify_run_output_persistence(db, "tropical")["monthly_rows_count"] == 4

    output_id = body["persisted_output_ids"][0]
    detail = client.get(f"/api/forecast/db/outputs/{output_id}", headers=_viewer()).json()
    monthly = detail["monthly"]
    actual = [m for m in monthly if m["is_actual"] == 1]
    forecast = [m for m in monthly if m["is_actual"] == 0]
    assert len(actual) == 1 and len(forecast) == 3
    # Forecast monthly rows reconcile to the header cost_to_complete.
    assert sum(Decimal(m["value"]) for m in forecast) == Decimal(detail["cost_to_complete"])
    assert find_redaction_leaks(detail) == []


def test_monthly_empty_without_forecast_end_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No forecast horizon supplied: header + budget-code rows persist, monthly is honestly empty.
    client, db = _client(tmp_path, monkeypatch, enabled=True)
    body = _post(client)
    assert body["request_status"] == "completed"
    assert body["db_persisted"] is True
    assert svc.verify_run_output_persistence(db, "tropical")["monthly_rows_count"] == 0
    output_id = body["persisted_output_ids"][0]
    detail = client.get(f"/api/forecast/db/outputs/{output_id}", headers=_viewer()).json()
    assert detail["monthly"] == []


# -- gate off / unsupported / no-basis: coded refusal, nothing written --------


def test_gate_disabled_refuses_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, db = _client(tmp_path, monkeypatch, enabled=False)
    body = _post(client)
    assert body["request_status"] == "failed"
    assert body["failure_code"] == "run_output_db_write_disabled"
    # The legacy fail-closed code is gone now that Phase F wires the route.
    assert body["failure_code"] != "db_native_generation_not_implemented"
    assert body["db_persisted"] is False
    assert svc.verify_run_output_persistence(db, "tropical")["forecast_outputs_count"] == 0
    _no_path_leaks(body)


def test_unsupported_generator_kind_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, db = _client(tmp_path, monkeypatch, enabled=True)
    body = _post(client, generator_kind="monthly")
    assert body["request_status"] == "failed"
    assert body["failure_code"] == "db_native_generator_kind_unsupported"
    assert body["db_persisted"] is False
    assert svc.verify_run_output_persistence(db, "tropical")["forecast_outputs_count"] == 0


def test_insufficient_basis_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Project identity present, but no v59 financial rows → engine returns insufficient_basis.
    client, db = _client(tmp_path, monkeypatch, enabled=True, with_basis=False)
    body = _post(client)
    assert body["request_status"] == "failed"
    assert body["failure_code"] == "db_native_insufficient_basis"
    assert body["db_persisted"] is False
    assert svc.verify_run_output_persistence(db, "tropical")["forecast_outputs_count"] == 0
    _no_path_leaks(body)


# -- request-ledger lineage ---------------------------------------------------


def test_ledger_lineage_records_run_id_and_failure_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = _client(tmp_path, monkeypatch, enabled=True)
    _post(client)
    reqs = client.get(
        "/api/forecast/generation/requests", params={"project_key": "tropical"}, headers=_viewer()
    ).json()["requests"]
    completed = [r for r in reqs if r["request_status"] == "completed"]
    assert completed and completed[0].get("run_id"), "completed db-native request should carry run_id"
    assert find_redaction_leaks({"requests": reqs}) == []
