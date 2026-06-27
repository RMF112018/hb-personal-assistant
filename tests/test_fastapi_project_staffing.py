"""Phase 3 FastAPI project-scoped staffing API tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
try:
    from fastapi.testclient import TestClient
except RuntimeError as exc:  # pragma: no cover - environment guard
    pytest.skip(str(exc), allow_module_level=True)

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.store.migrator import SQLiteMigrator

PROJECT = "tropical"


def _client(db: Path) -> TestClient:
    SQLiteMigrator(db_path=str(db)).apply()
    return TestClient(create_app(db_path=str(db)))


def _h(role: str) -> dict[str, str]:
    return {"X-HB-UI-Role": role}


def _valid_row() -> dict:
    return {
        "role_title": "Superintendent", "person_name": "Jane Doe", "employment_type": "Full Time",
        "cost_code": "01-100", "rate_unit": "weekly", "lab_rate": "2500.00",
        "start_date": "2026-07-01", "finish_date": "2026-12-31",
    }


def _no_leaks(resp) -> None:
    assert find_redaction_leaks(resp.json()) == []
    assert "raw_json" not in resp.text
    assert "run_id" not in resp.text


def test_config_crud_and_validate_on_write(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    created = client.post(f"/api/projects/{PROJECT}/staffing/config", json=_valid_row(),
                          headers=_h("operator"))
    assert created.status_code == 200
    body = created.json()
    assert body["ok"] is True
    assert body["row"]["validation_status"] == "valid"
    cid = body["row"]["staffing_config_id"]
    _no_leaks(created)

    listed = client.get(f"/api/projects/{PROJECT}/staffing/config", headers=_h("viewer"))
    assert listed.status_code == 200
    assert any(r["staffing_config_id"] == cid for r in listed.json()["rows"])
    _no_leaks(listed)

    # invalid edit persists with field errors and stays visible (never rejected)
    patched = client.patch(f"/api/projects/{PROJECT}/staffing/config/{cid}",
                           json={"role_title": ""}, headers=_h("operator"))
    assert patched.status_code == 200
    assert patched.json()["row"]["validation_status"] == "invalid"
    codes = {e["code"] for e in patched.json()["row"]["validation_errors_json"]}
    assert "role_title_missing" in codes

    deleted = client.delete(f"/api/projects/{PROJECT}/staffing/config/{cid}", headers=_h("operator"))
    assert deleted.status_code == 200 and deleted.json()["row"]["active_status"] == "deactivated"


def test_assumptions_get_patch_and_bad_calendar(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    got = client.get(f"/api/projects/{PROJECT}/staffing/assumptions", headers=_h("viewer"))
    assert got.json()["assumptions"]["hours_per_business_day"] == "8.00"
    ok = client.patch(f"/api/projects/{PROJECT}/staffing/assumptions",
                      json={"holiday_calendar_id": "holcal-company_default_2026_2040"},
                      headers=_h("operator"))
    assert ok.json()["ok"] is True
    bad = client.patch(f"/api/projects/{PROJECT}/staffing/assumptions",
                       json={"holiday_calendar_id": "nope"}, headers=_h("operator"))
    assert bad.json()["ok"] is False
    assert bad.json()["errors"][0]["code"] == "holiday_calendar_invalid"


def test_readiness_states(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    empty = client.get(f"/api/projects/{PROJECT}/staffing/readiness", headers=_h("viewer"))
    assert empty.json()["readiness_status"] == "degraded"  # no rows
    client.post(f"/api/projects/{PROJECT}/staffing/config", json=_valid_row(), headers=_h("operator"))
    ready = client.get(f"/api/projects/{PROJECT}/staffing/readiness", headers=_h("viewer"))
    assert ready.json()["readiness_status"] == "ready"
    # an invalid row blocks
    client.post(f"/api/projects/{PROJECT}/staffing/config",
                json={**_valid_row(), "employment_type": "Bogus"}, headers=_h("operator"))
    blocked = client.get(f"/api/projects/{PROJECT}/staffing/readiness", headers=_h("viewer"))
    assert blocked.json()["readiness_status"] == "blocked"
    assert "employment_type_invalid" in blocked.json()["readiness_reasons"]


def _seed_cost_entries(db: Path) -> None:
    rows = [
        ("01-100", "LAB", 1000.0, "2026-06"),
        ("01-100", "LAB", 500.0, "2026-07"),
        ("03-01-025", "MAT", 300.0, "2026-06"),
    ]
    with sqlite3.connect(db) as conn:
        for i, (cc, cat, amt, month) in enumerate(rows, start=1):
            raw = {"cost_code": cc, "category": cat, "tran_type": "AP cost",
                   "accounting_month": month, "amount": amt, "description": "Labor",
                   "budget_code_key": f"0000.{cc}.{cat}"}
            conn.execute(
                "INSERT INTO forecast_cost_entries (cost_entry_id, project_key, source_package, "
                "source_row_number, budget_code_key, accounting_month, raw_json, created_utc) "
                "VALUES (?, ?, 'pkg', ?, ?, ?, ?, 't')",
                (f"ce-{i}", PROJECT, i, raw["budget_code_key"], month, json.dumps(raw)),
            )
        conn.commit()


def test_attribution_flow(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    client = _client(db)
    _seed_cost_entries(db)
    cfg = client.post(f"/api/projects/{PROJECT}/staffing/config", json=_valid_row(),
                      headers=_h("operator")).json()["row"]["staffing_config_id"]
    rebuilt = client.post(f"/api/projects/{PROJECT}/staffing/actuals/rebuild-projection",
                          headers=_h("operator"))
    assert rebuilt.json()["projected"] == 3
    unmatched = client.get(f"/api/projects/{PROJECT}/staffing/unmatched-actuals", headers=_h("viewer"))
    items = unmatched.json()["review_items"]
    assert len(items) == 1 and items[0]["cost_code"] == "01-100"
    _no_leaks(unmatched)
    # MAT summary, never in review
    mat = client.get(f"/api/projects/{PROJECT}/staffing/mat-summary", headers=_h("viewer"))
    assert mat.json()["materials"][0]["cost_code"] == "03-01-025"
    # resolve -> rule + re-match -> bucket empty
    resolved = client.post(
        f"/api/projects/{PROJECT}/staffing/attribution-review/{items[0]['review_item_id']}/resolve",
        json={"staffing_config_id": cfg, "resolved_by_role": "operator"}, headers=_h("operator"))
    assert resolved.json()["ok"] is True
    assert client.get(f"/api/projects/{PROJECT}/staffing/unmatched-actuals",
                      headers=_h("viewer")).json()["review_items"] == []
    assert len(client.get(f"/api/projects/{PROJECT}/staffing/attribution-rules",
                          headers=_h("viewer")).json()["rules"]) == 1


def test_absence_crud(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    client = _client(db)
    cfg = client.post(f"/api/projects/{PROJECT}/staffing/config", json=_valid_row(),
                      headers=_h("operator")).json()["row"]["staffing_config_id"]
    created = client.post(f"/api/projects/{PROJECT}/staffing/absence-overrides",
                          json={"staffing_config_id": cfg, "start_date": "2026-08-01",
                                "finish_date": "2026-08-05", "absence_hours": "40.00"},
                          headers=_h("operator"))
    assert created.json()["ok"] is True
    assert len(client.get(f"/api/projects/{PROJECT}/staffing/absence-overrides",
                          headers=_h("viewer")).json()["rows"]) == 1
    bad = client.post(f"/api/projects/{PROJECT}/staffing/absence-overrides",
                      json={"start_date": "2026-08-01", "finish_date": "2026-08-05",
                            "absence_hours": "0"}, headers=_h("operator"))
    assert bad.json()["ok"] is False  # ambiguous target + non-positive hours


def test_writes_require_operator_role(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    for method, path, payload in (
        ("post", f"/api/projects/{PROJECT}/staffing/config", _valid_row()),
        ("patch", f"/api/projects/{PROJECT}/staffing/assumptions", {"hours_per_business_day": "7"}),
        ("post", f"/api/projects/{PROJECT}/staffing/absence-overrides", {"person_name": "x"}),
        ("post", f"/api/projects/{PROJECT}/staffing/actuals/rebuild-projection", None),
    ):
        resp = getattr(client, method)(path, json=payload, headers=_h("viewer"))
        assert resp.status_code == 403
        assert resp.json()["detail"] == "operator_role_required"


def test_unavailable_db_fails_closed_503(tmp_path: Path) -> None:
    missing = tmp_path / "empty.sqlite"
    missing.write_bytes(b"")
    client = TestClient(create_app(db_path=str(missing)))
    resp = client.get(f"/api/projects/{PROJECT}/staffing/config", headers=_h("viewer"))
    assert resp.status_code == 503
    assert resp.json()["detail"] == "forecast_staffing_not_available"
