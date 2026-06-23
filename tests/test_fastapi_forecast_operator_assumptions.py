"""FastAPI route tests for the operator-assumptions capture write surface (v66).

Asserts the routes are role-aware (GET viewer, POST/PATCH operator-guarded), persist to the managed
DB, round-trip create→list, are redaction-safe (no raw_json/run_id reach the client), are idempotent
for required-assumptions, and fail closed (503) when the DB is unavailable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402

PROJECT = "tropical"


def _client(db: Path) -> TestClient:
    SQLiteMigrator(db_path=str(db)).apply()
    return TestClient(create_app(db_path=str(db)))


def _h(role: str) -> dict[str, str]:
    return {"X-HB-UI-Role": role}


def test_operator_assumption_create_list_roundtrip_is_redaction_safe(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    created = client.post(
        f"/api/forecast/db/projects/{PROJECT}/operator-assumptions",
        json={"assumption_type": "labor_rate", "value": "125.00", "confidence_impact": "raises"},
        headers=_h("operator"),
    )
    assert created.status_code == 200
    assert created.json()["ok"] is True
    aid = created.json()["assumption_id"]

    listed = client.get(
        f"/api/forecast/db/projects/{PROJECT}/operator-assumptions", headers=_h("viewer")
    )
    assert listed.status_code == 200
    body = listed.json()
    assert any(a["assumption_id"] == aid for a in body["assumptions"])
    assert find_redaction_leaks(body) == []
    assert "raw_json" not in listed.text
    assert "run_id" not in listed.text


def test_operator_assumption_edit_and_unknown(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    aid = client.post(
        f"/api/forecast/db/projects/{PROJECT}/operator-assumptions",
        json={"assumption_type": "labor_rate", "value": "100.00"},
        headers=_h("operator"),
    ).json()["assumption_id"]

    edited = client.patch(
        f"/api/forecast/db/operator-assumptions/{aid}",
        json={"value": "175.00", "overridden": True},
        headers=_h("operator"),
    )
    assert edited.status_code == 200 and edited.json()["kind"] == "assumption_updated"

    unknown = client.patch(
        "/api/forecast/db/operator-assumptions/nope",
        json={"value": "1"},
        headers=_h("operator"),
    )
    assert unknown.status_code == 200 and unknown.json()["kind"] == "assumption_not_found"


def test_required_assumption_create_satisfy_and_idempotent(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    first = client.post(
        f"/api/forecast/db/projects/{PROJECT}/required-assumptions",
        json={"assumption_type": "escalation_rate", "reason": "trade coverage"},
        headers=_h("operator"),
    ).json()
    second = client.post(
        f"/api/forecast/db/projects/{PROJECT}/required-assumptions",
        json={"assumption_type": "escalation_rate", "reason": "revised"},
        headers=_h("operator"),
    ).json()
    assert first["id"] == second["id"]  # idempotent

    listed = client.get(
        f"/api/forecast/db/projects/{PROJECT}/required-assumptions", headers=_h("viewer")
    ).json()
    assert len([r for r in listed["required"] if r["assumption_type"] == "escalation_rate"]) == 1

    satisfied = client.patch(
        f"/api/forecast/db/required-assumptions/{first['id']}",
        json={"satisfied": True},
        headers=_h("operator"),
    )
    assert satisfied.status_code == 200 and satisfied.json()["satisfied"] is True


def test_write_routes_require_operator_role(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    for method, path, payload in (
        (
            "post",
            f"/api/forecast/db/projects/{PROJECT}/operator-assumptions",
            {"assumption_type": "x"},
        ),
        ("patch", "/api/forecast/db/operator-assumptions/abc", {"value": "1"}),
        (
            "post",
            f"/api/forecast/db/projects/{PROJECT}/required-assumptions",
            {"assumption_type": "x"},
        ),
        ("patch", "/api/forecast/db/required-assumptions/abc", {"satisfied": True}),
    ):
        resp = getattr(client, method)(path, json=payload, headers=_h("viewer"))
        assert resp.status_code == 403
        assert resp.json()["detail"] == "operator_role_required"


def test_create_rejects_empty_type(tmp_path: Path) -> None:
    client = _client(tmp_path / "db.sqlite")
    resp = client.post(
        f"/api/forecast/db/projects/{PROJECT}/operator-assumptions",
        json={"assumption_type": "   "},
        headers=_h("operator"),
    )
    assert resp.status_code == 200 and resp.json()["ok"] is False


def test_unavailable_db_fails_closed_503(tmp_path: Path) -> None:
    # An un-migrated DB path → schema gate trips → 503.
    missing = tmp_path / "empty.sqlite"
    missing.write_bytes(b"")
    client = TestClient(create_app(db_path=str(missing)))
    resp = client.get(
        f"/api/forecast/db/projects/{PROJECT}/operator-assumptions", headers=_h("viewer")
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "forecast_assumptions_not_available"
