"""FastAPI route tests for the DB-backed forecast run-output + decision-support read-model (Phase 4).

Asserts the routes are role-aware, read-only, redaction-safe (the stamp-format run_id and
source_path never reach the client; navigation is by the hash-based output_id), fail closed when
the DB is unavailable, render gracefully empty on a migrated-but-unpopulated DB, and 404 on an
unknown output_id.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402

RUN_ID = "20260101_000000"  # stamp-format — must NEVER appear in any response body
OID = "fout-test0000000000000000000000000001"
TS = "2026-06-19T08:00:00+00:00"


def _seed(db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES (?,?,?)",
            (RUN_ID, "tropical", TS),
        )
        conn.execute(
            "INSERT INTO forecast_outputs (output_id, run_id, project_key, source_package, "
            "estimated_final_cost, cost_to_complete, variance_to_budget, variance_to_prior_forecast, "
            "source_path, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (OID, RUN_ID, "tropical", "forecast_analysis_package_tropical_20260101_000000",
             "500.00", "100.00", "10.00", "5.00", "/Users/bobbyfetting/secret/path", "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_output_budget_codes (id, output_id, project_key, budget_code_key, "
            "cost_code, category, forecast_action, recommended_projected_cost, recommended_cost_to_complete, "
            "confidence, source_row_number, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("bc1", OID, "tropical", "0000.03-01-025.MAT", "03-01-025", "MAT", "hold",
             "500.00", "100.00", "high", 1, "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_output_risks (id, output_id, project_key, risk_id, severity, "
            "budget_code_key, cost_code, category, risk_type, source_row_number, raw_json, created_utc) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("rk1", OID, "tropical", "R-0001", "low", "0000.03-01-025.MAT", "03-01-025", "MAT",
             "x", 1, "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_output_monthly (id, output_id, project_key, budget_code_key, month, "
            "value, is_actual, source_row_number, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("mo1", OID, "tropical", "0000.03-01-025.MAT", "2026-07", "100.00", 0, 1, "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_output_probability (id, output_id, project_key, scope, budget_code_key, "
            "p10, p50, p90, source_row_number, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("pb1", OID, "tropical", "budget_code", "0000.03-01-025.MAT", "90.00", "100.00", "120.00",
             1, "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_output_changes (id, output_id, project_key, budget_code_key, "
            "change_type, delta_amount, source_row_number, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
            ("ch1", OID, "tropical", "0000.03-01-025.MAT", "integrated_vs_accepted", "10.00", 1, "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_output_staffing (id, output_id, project_key, budget_code_key, role, "
            "month, headcount, cost_amount, source_row_number, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("st1", OID, "tropical", "0000.03-01-025.MAT", None, "2026-07", None, "50.00", 1, "{}", TS),
        )
        # raw_json carries redaction bait (a path + run-stamp) that must never reach the client.
        _bait = '{"source_path": "/Users/bobby/forecast/20260101_000000/x.jsonl"}'
        conn.execute(
            "INSERT INTO forecast_output_commitment_exposure (id, output_id, project_key, "
            "budget_code_key, committed_amount, exposure_amount, source_row_number, raw_json, created_utc) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("ce1", OID, "tropical", "0000.03-01-025.MAT", "1000.00", "750.00", 1, _bait, TS),
        )
        conn.execute(
            "INSERT INTO forecast_output_schedule_phasing (id, output_id, project_key, budget_code_key, "
            "phase, start_month, end_month, amount, source_row_number, raw_json, created_utc) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("sp1", OID, "tropical", "0000.03-01-025.MAT", "direct", "2026-07", "2026-08", "3000.00",
             1, _bait, TS),
        )
        # v66 decision-support, keyed by run_id
        conn.execute(
            "INSERT INTO forecast_project_maturity_snapshots (snapshot_id, run_id, project_key, "
            "maturity_tier, completed_month_count, nonzero_month_count, basis, raw_json, created_utc) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("ms1", RUN_ID, "tropical", "M2", 2, 2, "completed_month_count_thresholds", "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_data_availability_profiles (id, run_id, project_key, domain, "
            "availability, coverage, reason, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
            ("da1", RUN_ID, "tropical", "monthly_actuals", "available", "2", "rows present", "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_confidence_scorecards (scorecard_id, run_id, project_key, scope, "
            "scope_key, score, label, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
            ("sc1", RUN_ID, "tropical", "project", "project", None, "high", "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_confidence_factors (id, scorecard_id, run_id, project_key, factor_key, "
            "direction, magnitude, reason, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("ft1", "sc1", RUN_ID, "tropical", "confidence_high", "booster", "1",
             "1 budget codes at high confidence", "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_method_eligibility (id, run_id, project_key, method, status, weight, "
            "reason, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
            ("me1", RUN_ID, "tropical", "burn_rate", "eligible_weighted", None,
             "applicable for 1/1 budget codes", "{}", TS),
        )
        conn.execute(
            "INSERT INTO forecast_model_selection_decisions (id, run_id, project_key, method, contributed, "
            "weight, reason, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
            ("md1", RUN_ID, "tropical", "burn_rate", 1, "0.7000", "contributed to 1 budget codes",
             "{}", TS),
        )
        # P8 narratives — payloads carry stamp bait both as structured fields (forecast_period /
        # accuracy_package_stamp / prior_run_id) AND inside the free-text narrative, to prove the
        # read-model drops the keys AND scrubs the narrative string.
        _narr = [
            ("project", "header", json.dumps({
                "estimated_final_cost": "500.00", "forecast_at_completion": "500.00",
                "cost_to_complete": "100.00", "variance_to_budget": "10.00",
                "budget_code_count": 1, "risk_count": 1, "override_count": 1, "warning_count": 0,
                "narrative": "Forecast EAC 500.00 across 1 budget code(s)."})),
            ("budget_code", "0000.03-01-025.MAT", json.dumps({
                "budget_code_key": "0000.03-01-025.MAT", "recommended_projected_cost": "500.00",
                "recommended_cost_to_complete": "100.00", "forecast_action": "hold",
                "confidence": "high", "risk_count": 1, "overridden": True,
                "narrative": "Budget code 0000.03-01-025.MAT: projected cost 500.00, operator-overridden."})),
            ("human_override", "0000.03-01-025.MAT", json.dumps({
                "budget_code_key": "0000.03-01-025.MAT", "assumption_type": "escalation",
                "column": "recommended_projected_cost", "original": "450.00", "override": "500.00",
                "delta_amount": "50.00", "source": "operator", "applied_utc": TS,
                "narrative": "Operator override on 0000.03-01-025.MAT: 450.00 -> 500.00."})),
            ("source_qa", "analysis_package", json.dumps({
                "budget_code_count": 1, "null_projected_cost_count": 0, "zero_projected_cost_count": 0,
                "duplicate_budget_code_keys": [], "forecast_period": "20260101_000000",
                "narrative": "Source QA over 1 budget code(s); forecast period 20260101_000000."})),
            ("lineage", "package_sha256_chain", json.dumps({
                "context_sha256": "a" * 64, "analysis_sha256": "b" * 64, "output_sha256": "c" * 64,
                "methodology_sha256": "d" * 64, "accuracy_package_stamp": "20251201_120000",
                "prior_run_id": "20251201_120000",
                "narrative": "Package sha256 chain output=" + "c" * 64 + " prior_run=20251201_120000."})),
        ]
        for i, (scope, nkey, payload) in enumerate(_narr, start=1):
            conn.execute(
                "INSERT INTO forecast_output_narratives (id, output_id, project_key, scope, "
                "narrative_key, source_row_number, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?)",
                (f"nr{i}", OID, "tropical", scope, nkey, i, payload, TS),
            )
        conn.commit()
    finally:
        conn.close()


def _client(db: Path) -> TestClient:
    return TestClient(create_app(db_path=str(db)))


def _h(role: str = "viewer") -> dict[str, str]:
    return {"X-HB-UI-Role": role}


@pytest.fixture
def seeded(tmp_path) -> Path:
    db = tmp_path / "hb.sqlite"
    _seed(db)
    return db


def test_list_outputs(seeded):
    body = _client(seeded).get("/api/forecast/db/projects/tropical/outputs", headers=_h()).json()
    assert body["guardrails"]["read_only"] is True
    assert [o["output_id"] for o in body["outputs"]] == [OID]
    assert body["outputs"][0]["variance_to_prior_forecast"] == "5.00"  # P9: prior delta in list view
    assert find_redaction_leaks(body) == []


def test_list_projects(seeded):
    resp = _client(seeded).get("/api/forecast/db/projects", headers=_h())
    assert resp.status_code == 200
    body = resp.json()
    assert [p["project_key"] for p in body["projects"]] == ["tropical"]
    assert body["projects"][0]["output_count"] == 1
    assert body["projects"][0]["latest_display"] == "Jun 19, 2026"
    assert find_redaction_leaks(body) == []


def test_read_narratives(seeded):
    resp = _client(seeded).get(f"/api/forecast/db/outputs/{OID}/narratives", headers=_h())
    assert resp.status_code == 200
    body = resp.json()
    n = body["narratives"]
    # curated content present per scope
    assert n["project"][0]["estimated_final_cost"] == "500.00"
    assert n["project"][0]["budget_code_count"] == 1
    assert n["budget_code"][0]["overridden"] is True
    assert n["human_override"][0]["original"] == "450.00" and n["human_override"][0]["override"] == "500.00"
    assert n["human_override"][0]["applied_display"] == "Jun 19, 2026"  # friendly, not raw stamp
    assert n["lineage"][0]["context_sha256"] == "a" * 64  # sha256 hex is leak-safe
    # stamp-format structured keys dropped
    assert "applied_utc" not in n["human_override"][0]
    assert "forecast_period" not in n["source_qa"][0]
    assert "accuracy_package_stamp" not in n["lineage"][0]
    assert "prior_run_id" not in n["lineage"][0]
    # free-text narrative scrubbed of embedded stamps
    assert "[redacted]" in n["source_qa"][0]["narrative"]
    assert "[redacted]" in n["lineage"][0]["narrative"]
    # no-raw-leak: nothing stamp-format / no raw_json / no source_path reaches the client
    assert find_redaction_leaks(body) == []
    assert "20260101_000000" not in resp.text and "20251201_120000" not in resp.text
    assert RUN_ID not in resp.text


def test_narratives_unknown_output_404(seeded):
    resp = _client(seeded).get("/api/forecast/db/outputs/fout-nope/narratives", headers=_h())
    assert resp.status_code == 404
    assert resp.json()["detail"] == "forecast_output_not_found"


def test_read_output_with_all_children(seeded):
    resp = _client(seeded).get(f"/api/forecast/db/outputs/{OID}", headers=_h())
    assert resp.status_code == 200
    body = resp.json()
    assert body["output_id"] == OID and body["created_display"] == "Jun 19, 2026"
    assert len(body["budget_codes"]) == 1 and len(body["risks"]) == 1
    assert len(body["monthly"]) == 1 and len(body["probability"]) == 1
    assert len(body["changes"]) == 1 and len(body["staffing"]) == 1
    assert len(body["commitment_exposure"]) == 1 and len(body["schedule_phasing"]) == 1
    assert body["commitment_exposure"][0]["committed_amount"] == "1000.00"
    assert body["commitment_exposure"][0]["exposure_amount"] == "750.00"
    assert body["schedule_phasing"][0]["phase"] == "direct"
    assert body["schedule_phasing"][0]["start_month"] == "2026-07"
    assert find_redaction_leaks(body) == []  # no source_path, no run stamp (even from seeded raw_json bait)
    assert "source_path" not in resp.text and RUN_ID not in resp.text


def test_read_decision_support(seeded):
    resp = _client(seeded).get(f"/api/forecast/db/outputs/{OID}/decision-support", headers=_h())
    assert resp.status_code == 200
    body = resp.json()
    assert body["maturity"]["maturity_tier"] == "M2"
    assert body["data_availability"][0]["availability"] == "available"
    assert body["confidence_scorecards"][0]["label"] == "high"
    assert body["confidence_scorecards"][0]["factors"][0]["factor_key"] == "confidence_high"
    assert body["method_eligibility"][0]["status"] == "eligible_weighted"
    assert body["model_selection"][0]["weight"] == "0.7000"
    assert find_redaction_leaks(body) == []
    assert RUN_ID not in resp.text  # stamp-format run_id never surfaced


def test_graceful_empty(tmp_path):
    db = tmp_path / "empty.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()  # migrated, unpopulated
    body = _client(db).get("/api/forecast/db/projects/tropical/outputs", headers=_h()).json()
    assert body["outputs"] == []


def test_unknown_output_404(seeded):
    resp = _client(seeded).get("/api/forecast/db/outputs/fout-nope", headers=_h())
    assert resp.status_code == 404
    assert resp.json()["detail"] == "forecast_output_not_found"


def test_missing_db_503(tmp_path):
    resp = _client(tmp_path / "missing.sqlite").get(
        "/api/forecast/db/projects/tropical/outputs", headers=_h()
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "forecast_run_output_not_available"


def test_invalid_role_403(seeded):
    resp = _client(seeded).get(
        "/api/forecast/db/projects/tropical/outputs", headers={"X-HB-UI-Role": "root"}
    )
    assert resp.status_code == 403
