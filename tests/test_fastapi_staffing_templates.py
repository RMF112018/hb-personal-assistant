"""Phase 3c FastAPI staffing-templates + holiday-calendars (Forecasting-Config) tests."""

from __future__ import annotations

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

_CAL = "holcal-company_default_2026_2040"
_T = "/api/forecast/config/staffing-templates"
_H = "/api/forecast/config/holiday-calendars"


def _client(db: Path) -> TestClient:
    SQLiteMigrator(db_path=str(db)).apply()
    return TestClient(create_app(db_path=str(db)))


def _hdr(role: str) -> dict[str, str]:
    return {"X-HB-UI-Role": role}


def _no_leaks(resp) -> None:
    assert find_redaction_leaks(resp.json()) == []
    assert "raw_json" not in resp.text


def test_template_crud_and_versions(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    created = client.post(_T, json={"template_key": "super-fl", "template_name": "FL Super"},
                          headers=_hdr("operator"))
    assert created.status_code == 200 and created.json()["ok"] is True
    tid = created.json()["template"]["template_id"]
    _no_leaks(created)

    assert any(t["template_id"] == tid for t in client.get(_T, headers=_hdr("viewer")).json()["templates"])

    v1 = client.post(f"{_T}/{tid}/versions",
                     json={"cost_code": "01-100", "default_lab_rate": "2400"}, headers=_hdr("operator"))
    v2 = client.post(f"{_T}/{tid}/versions",
                     json={"cost_code": "01-100", "default_lab_rate": "2500"}, headers=_hdr("operator"))
    assert v1.json()["version"]["version_number"] == 1
    assert v2.json()["version"]["version_number"] == 2

    got = client.get(f"{_T}/{tid}", headers=_hdr("viewer"))
    assert len(got.json()["versions"]) == 2
    assert got.json()["current_version"]["default_lab_rate"] == "2500"
    _no_leaks(got)
    assert len(client.get(f"{_T}/{tid}/versions", headers=_hdr("viewer")).json()["versions"]) == 2

    deactivated = client.delete(f"{_T}/{tid}", headers=_hdr("operator"))
    assert deactivated.json()["ok"] is True
    assert client.get(_T, headers=_hdr("viewer")).json()["templates"] == []


def test_add_version_without_cost_code_is_ok_false(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    tid = client.post(_T, json={"template_key": "k", "template_name": "n"},
                      headers=_hdr("operator")).json()["template"]["template_id"]
    resp = client.post(f"{_T}/{tid}/versions", json={"default_lab_rate": "100"},
                       headers=_hdr("operator"))
    assert resp.status_code == 200  # not 500/503
    assert resp.json()["ok"] is False
    assert resp.json()["errors"][0]["code"] == "cost_code_missing"


def test_holiday_calendars_read(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    listed = client.get(_H, headers=_hdr("viewer"))
    assert any(c["calendar_key"] == "company_default_2026_2040" for c in listed.json()["calendars"])
    _no_leaks(listed)
    got = client.get(f"{_H}/{_CAL}", headers=_hdr("viewer"))
    assert got.json()["calendar"]["holiday_calendar_id"] == _CAL
    assert len(got.json()["dates"]) == 150
    missing = client.get(f"{_H}/nope", headers=_hdr("viewer"))
    assert missing.json()["ok"] is False


def test_writes_require_operator_role(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    for method, path, payload in (
        ("post", _T, {"template_key": "k", "template_name": "n"}),
        ("delete", f"{_T}/abc", None),
        ("post", f"{_T}/abc/versions", {"cost_code": "01-100"}),
    ):
        kwargs = {"headers": _hdr("viewer")}
        if payload is not None:
            kwargs["json"] = payload
        resp = getattr(client, method)(path, **kwargs)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "operator_role_required"


def test_unavailable_db_fails_closed_503(tmp_path: Path) -> None:
    missing = tmp_path / "empty.sqlite"
    missing.write_bytes(b"")
    client = TestClient(create_app(db_path=str(missing)))
    resp = client.get(_T, headers=_hdr("viewer"))
    assert resp.status_code == 503
    assert resp.json()["detail"] == "forecast_staffing_not_available"
