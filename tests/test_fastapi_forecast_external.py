"""FastAPI route tests for External-Forecast Evaluation (Implementation Phase 4).

Asserts: POST routes (preview/mapping/evaluate) are operator-gated and the GET result routes are
viewer-readable; every payload leaks no dev-internals; unconfigured fails closed (503); invalid
input is 400; unknown eval is 404; and the full preview->map->evaluate->list->read flow works.
"""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402

CSV = "Cost Code,Month,EAC,Remaining\n01-100,2026-06,900000,250000\n02-200,2026-06,520000,200000\n"


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _baseline_db(path: Path) -> None:
    SQLiteMigrator(db_path=str(path)).apply()
    c = sqlite3.connect(str(path))
    for code, rb, erp in (("01-100", "1000000", "600000"), ("02-200", "500000", "300000")):
        c.execute(
            "INSERT INTO forecast_budget_details (project_key,budget_code_key,source_package,raw_json,created_utc) "
            "VALUES (?,?,?,?,?)",
            ("tropical", code, "pkg",
             json.dumps({"budget_code_key": code, "amounts": {"revised_budget": rb, "erp_job_to_date_costs": erp}}),
             "t"),
        )
    for code, amt in (("01-100", "650000"), ("02-200", "320000")):
        c.execute(
            "INSERT INTO forecast_monthly_actuals_by_budget_code "
            "(project_key,budget_code_key,month,type,source_package,raw_json,created_utc) VALUES (?,?,?,?,?,?,?)",
            ("tropical", code, "2026-05", "actual", "pkg",
             json.dumps({"budget_code_key": code, "amount": amt}), "t"),
        )
    c.commit()
    c.close()


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _configured_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    eval_root = tmp_path / "eval"
    eval_root.mkdir()
    db = tmp_path / "base.sqlite"
    _baseline_db(db)
    monkeypatch.setenv("HB_FORECAST_EVAL_ROOT", str(eval_root))
    monkeypatch.setenv("HB_FORECAST_DB_PATH", str(db))
    monkeypatch.setenv("HB_FORECAST_PACKAGE_ROOTS", str(tmp_path / "packages"))
    return TestClient(create_app(db_path=str(tmp_path / "x.sqlite")))


def test_full_flow_operator_then_viewer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    prev = client.post(
        "/api/forecast/external/preview",
        json={"filename": "june.csv", "content_b64": _b64(CSV), "source_system": "manual", "period": "2026-06"},
        headers=_op(),
    )
    assert prev.status_code == 200
    pbody = prev.json()
    assert find_redaction_leaks(pbody) == []
    import_id = pbody["import_id"]

    mapping = client.post(
        "/api/forecast/external/mapping",
        json={"import_id": import_id, "project_key": "tropical"},
        headers=_op(),
    ).json()
    assert mapping["mapped_count"] == 2
    roles = mapping["proposed_column_roles"]

    ev = client.post(
        "/api/forecast/external/evaluate",
        json={"import_id": import_id, "column_roles": roles, "project_key": "tropical"},
        headers=_op(),
    )
    assert ev.status_code == 200
    ebody = ev.json()
    assert ebody["status"] == "succeeded"
    assert find_redaction_leaks(ebody) == []
    eval_id = ebody["eval_id"]

    listed = client.get("/api/forecast/external/evaluations", headers=_viewer())
    assert listed.status_code == 200
    assert any(e["eval_id"] == eval_id for e in listed.json()["evaluations"])
    assert find_redaction_leaks(listed.json()) == []

    detail = client.get(f"/api/forecast/external/evaluations/{eval_id}", headers=_viewer())
    assert detail.status_code == 200
    assert find_redaction_leaks(detail.json()) == []


def test_post_routes_require_operator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    for path, payload in (
        ("/api/forecast/external/preview", {"filename": "x.csv", "content_b64": _b64(CSV)}),
        ("/api/forecast/external/mapping", {"import_id": "x"}),
        ("/api/forecast/external/evaluate", {"import_id": "x", "column_roles": {}}),
    ):
        resp = client.post(path, json=payload, headers=_viewer())
        assert resp.status_code == 403


def test_invalid_input_is_400(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/forecast/external/preview",
        json={"filename": "x.txt", "content_b64": _b64("nope"), "source_system": "manual"},
        headers=_op(),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "forecast_external_invalid_input"


def test_unknown_eval_is_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configured_client(tmp_path, monkeypatch)
    resp = client.get("/api/forecast/external/evaluations/nope", headers=_viewer())
    assert resp.status_code == 404


def test_unconfigured_fails_closed_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_FORECAST_EVAL_ROOT", raising=False)
    # Isolate from the machine's persisted settings/managed default: the resolver falls back past the
    # env var, so simulate a truly-unconfigured runtime by forcing it to None (patched on the source
    # module, since api.py imports it locally at call time).
    monkeypatch.setattr(
        "hb_assistant.construction.analytics.forecast_runtime_config.resolve_eval_root_value",
        lambda explicit=None: None,
    )
    client = TestClient(create_app(db_path=str(tmp_path / "x.sqlite")))
    resp = client.get("/api/forecast/external/evaluations", headers=_viewer())
    assert resp.status_code == 503
    assert resp.json()["detail"] == "forecast_external_not_configured"
