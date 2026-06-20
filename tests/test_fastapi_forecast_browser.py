"""FastAPI route tests for the read-only forecast package browser (Implementation Phase 1).

Asserts: routes are role-aware and read-only, every response carries guardrails and
leaks no dev-internals, unconfigured roots fail closed (503), and unknown ids 404.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics.forecast_catalog import ENV_PACKAGE_ROOTS  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402

STAMP = "20260615_153920"

MANIFEST = {
    "package_name": f"forecast_comprehensive_package_tropical_{STAMP}",
    "manifest_version": "1.0.0",
    "project": {
        "project_key": "tropical",
        "project_name": "Tropical World Nursery",
        "job_reference": "23-435-01",
        "forecast_period": "2026-June",
    },
    "generation": {
        "generator": "construction_financial_review.forecast_comprehensive.generate_comprehensive_forecast_package",
        "command": "python3 -m construction_financial_review.cli forecast-comprehensive --project tropical",
        "package_stamp": STAMP,
    },
    "output_files": [
        {"path": "integrated_final_cost_recommendations.jsonl", "size_bytes": 100, "row_count": 1, "sha256": "x"},
    ],
}
VALIDATION = {"checks": {"actuals_floor_preserved": True}}
ROW = {
    "cost_code": "03-01-025",
    "budget_code_key": "0000.03-01-025.MAT",
    "accepted_recommended_final_cost": "3561.74",
    "integrated_cost_to_complete": "2401.29",
    "acceptance_status": "pending",
}


def _root_with_package(tmp_path: Path) -> Path:
    root = tmp_path / "2026-June"
    pkg = root / f"forecast_comprehensive_package_tropical_{STAMP}"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    (pkg / "validation_report.json").write_text(json.dumps(VALIDATION), encoding="utf-8")
    (pkg / "integrated_final_cost_recommendations.jsonl").write_text(json.dumps(ROW), encoding="utf-8")
    return root


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, configured: bool = True) -> TestClient:
    if configured:
        monkeypatch.setenv(ENV_PACKAGE_ROOTS, str(_root_with_package(tmp_path)))
    else:
        monkeypatch.delenv(ENV_PACKAGE_ROOTS, raising=False)
    return TestClient(create_app(db_path=str(tmp_path / "analytics.sqlite")))


def _h(role: str = "viewer") -> dict[str, str]:
    return {"X-HB-UI-Role": role}


def test_full_read_only_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)

    projects = client.get("/api/forecast/projects", headers=_h()).json()
    assert projects["guardrails"]["read_only"] is True
    assert any(p["project_key"] == "tropical" for p in projects["projects"])

    periods = client.get("/api/forecast/projects/tropical/periods", headers=_h()).json()
    assert periods["periods"][0]["period"] == "2026-June"

    packages = client.get(
        "/api/forecast/projects/tropical/periods/2026-June/packages", headers=_h()
    ).json()
    pid = packages["packages"][0]["package_id"]

    for suffix in ("summary", "validation", "manifest", "review-items", "forecast-rows"):
        resp = client.get(f"/api/forecast/packages/{pid}/{suffix}", headers=_h())
        assert resp.status_code == 200, suffix
        body = resp.json()
        assert body["guardrails"]["read_only"] is True
        assert find_redaction_leaks(body) == [], f"leak in {suffix}: {find_redaction_leaks(body)}"


def test_responses_contain_no_dev_internals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    packages = client.get(
        "/api/forecast/projects/tropical/periods/2026-June/packages", headers=_h()
    ).json()
    assert find_redaction_leaks(packages) == []


def test_not_configured_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch, configured=False)
    resp = client.get("/api/forecast/projects", headers=_h())
    assert resp.status_code == 503
    assert resp.json()["detail"] == "forecast_packages_not_configured"


def test_unknown_package_id_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/forecast/packages/0000000000000000/summary", headers=_h())
    assert resp.status_code == 404
    assert resp.json()["detail"] == "forecast_package_not_found"


def test_invalid_role_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/forecast/projects", headers={"X-HB-UI-Role": "root"})
    assert resp.status_code == 403
