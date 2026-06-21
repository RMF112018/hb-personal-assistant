"""Phase 4 — external-forecast ingest/mapping/evaluation service tests.

Builds a synthetic eval-root, a read-only v59 baseline DB, and a backend model package, then
exercises preview -> propose mapping -> evaluate end-to-end. Asserts: structural redaction is
clean on every payload, the evaluation writes ONLY under the isolated eval-root (per-run eval
SQLite + evidence package), the baseline DB is left untouched, fail-closed config, and that a
second evaluation can use the first as its prior-external baseline.
"""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.analytics.forecast_external_dto import find_redaction_leaks
from hb_assistant.construction.analytics.forecast_external_eval_service import (
    ForecastExternalEvalService,
)
from hb_assistant.construction.analytics.forecast_external_ingest import (
    ForecastExternalError,
    ForecastExternalIngestService,
)
from hb_assistant.construction.analytics.forecast_external_mapping import (
    ForecastExternalMappingService,
)
from hb_assistant.store.migrator import SQLiteMigrator

CSV = (
    "Cost Code,Month,EAC,Remaining\n"
    "01-100,2026-06,900000,250000\n"  # below model P50 -> anomaly
    "02-200,2026-06,520000,200000\n"
)


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _baseline_db(path: Path) -> None:
    SQLiteMigrator(db_path=str(path)).apply()
    c = sqlite3.connect(str(path))
    for code, rb, erp in (("01-100", "1000000", "600000"), ("02-200", "500000", "300000")):
        c.execute(
            "INSERT INTO forecast_budget_details (project_key,budget_code_key,source_package,raw_json,created_utc) "
            "VALUES (?,?,?,?,?)",
            (
                "tropical",
                code,
                "pkg",
                json.dumps(
                    {"budget_code_key": code, "amounts": {"revised_budget": rb, "erp_job_to_date_costs": erp}}
                ),
                "t",
            ),
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


def _model_package(root: Path) -> Path:
    pkg = root / "forecast_comprehensive_package_tropical_20260615_010101"
    pkg.mkdir(parents=True)
    (pkg / "integrated_final_cost_recommendations.jsonl").write_text(
        json.dumps({"budget_code_key": "01-100", "integrated_recommended_final_cost": "1050000"})
        + "\n"
        + json.dumps({"budget_code_key": "02-200", "integrated_recommended_final_cost": "520000"})
        + "\n"
    )
    (pkg / "integrated_probability_by_budget_code.jsonl").write_text(
        json.dumps({"budget_code_key": "01-100", "integrated_p50": "1040000", "integrated_p80": "1090000"})
        + "\n"
        + json.dumps({"budget_code_key": "02-200", "integrated_p50": "515000", "integrated_p80": "535000"})
        + "\n"
    )
    return pkg


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    eval_root = tmp_path / "eval"
    eval_root.mkdir()
    db = tmp_path / "base.sqlite"
    _baseline_db(db)
    pkg_root = tmp_path / "packages"
    pkg_root.mkdir()
    _model_package(pkg_root)
    monkeypatch.setenv("HB_FORECAST_EVAL_ROOT", str(eval_root))
    monkeypatch.setenv("HB_FORECAST_DB_PATH", str(db))
    monkeypatch.setenv("HB_FORECAST_PACKAGE_ROOTS", str(pkg_root))
    return {"eval_root": eval_root, "db": db}


def _run(env: dict[str, Path]) -> dict:
    prev = ForecastExternalIngestService().preview("june.csv", _b64(CSV), "manual", "2026-06")
    prop = ForecastExternalMappingService().propose_mapping(prev["import_id"])
    return ForecastExternalEvalService().evaluate(prev["import_id"], prop["proposed_column_roles"])


def test_preview_redacted_and_parsed(env: dict[str, Path]) -> None:
    prev = ForecastExternalIngestService().preview("june.csv", _b64(CSV), "manual", "2026-06")
    assert prev["columns"] == ["Cost Code", "Month", "EAC", "Remaining"]
    assert prev["row_count"] == 2
    assert len(prev["file_sha256"]) == 64
    assert find_redaction_leaks(prev) == []


def test_preview_rejects_bad_input(env: dict[str, Path]) -> None:
    svc = ForecastExternalIngestService()
    with pytest.raises(ForecastExternalError):
        svc.preview("bad.txt", _b64("x"), "manual", None)  # unsupported type
    with pytest.raises(ForecastExternalError):
        svc.preview("x.csv", "not_base64!!", "manual", None)  # invalid base64


def test_mapping_matches_canonical_codes(env: dict[str, Path]) -> None:
    prev = ForecastExternalIngestService().preview("june.csv", _b64(CSV), "manual", "2026-06")
    prop = ForecastExternalMappingService().propose_mapping(prev["import_id"])
    assert prop["proposed_column_roles"]["budget_code"] == "Cost Code"
    assert prop["mapped_count"] == 2 and prop["unmapped_count"] == 0
    assert find_redaction_leaks(prop) == []


def test_evaluate_compares_all_baselines_and_flags_anomaly(env: dict[str, Path]) -> None:
    res = _run(env)
    assert res["status"] == "succeeded"
    assert set(res["baselines_compared"]) >= {
        "Actuals to date", "Current budget", "ERP job-to-date",
        "Backend model forecast", "Backend model P50", "Backend model P80",
    }
    flags = {a["flag_code"] for a in res["anomalies"]}
    assert "external_below_model_p50" in flags
    assert res["guardrails"]["no_live_db_write"] is True
    assert find_redaction_leaks(res) == []


def test_evaluate_writes_only_isolated_eval_root_and_leaves_db_untouched(env: dict[str, Path]) -> None:
    res = _run(env)
    eid = res["eval_id"]
    eval_dir = env["eval_root"] / "evaluations" / eid
    # Per-run eval SQLite populated.
    edb = eval_dir / "eval.sqlite"
    assert edb.exists()
    ec = sqlite3.connect(str(edb))
    try:
        assert ec.execute("SELECT COUNT(*) FROM forecast_external_forecasts").fetchone()[0] == 1
        assert ec.execute("SELECT COUNT(*) FROM forecast_external_forecast_rows").fetchone()[0] == 2
        assert ec.execute("SELECT COUNT(*) FROM forecast_evidence_packages").fetchone()[0] == 1
        origin = ec.execute("SELECT forecast_origin FROM forecast_external_forecasts").fetchone()[0]
        assert origin == "external"
    finally:
        ec.close()
    # Evidence package written under the eval-root only.
    pkgs = list(eval_dir.glob("external_forecast_evaluation_package_*"))
    assert len(pkgs) == 1
    assert (pkgs[0] / "manifest.json").exists()
    assert (pkgs[0] / "comparison_results.csv").exists()
    # The baseline DB was opened read-only — its external tables stay empty.
    base = sqlite3.connect(f"file:{env['db']}?mode=ro", uri=True)
    try:
        assert base.execute("SELECT COUNT(*) FROM forecast_external_forecasts").fetchone()[0] == 0
    finally:
        base.close()


def test_list_and_read_round_trip(env: dict[str, Path]) -> None:
    res = _run(env)
    listing = ForecastExternalEvalService().list_evaluations()
    assert any(e["eval_id"] == res["eval_id"] for e in listing["evaluations"])
    assert find_redaction_leaks(listing) == []
    detail = ForecastExternalEvalService().read_evaluation(res["eval_id"])
    assert detail["eval_id"] == res["eval_id"]
    assert find_redaction_leaks(detail) == []


def test_second_evaluation_uses_prior_external_baseline(env: dict[str, Path]) -> None:
    _run(env)
    second = _run(env)
    assert "Prior external forecast" in second["baselines_compared"]


def test_read_unknown_eval_fails_closed(env: dict[str, Path]) -> None:
    with pytest.raises(ForecastExternalError):
        ForecastExternalEvalService().read_evaluation("does-not-exist")


def test_eval_root_unconfigured_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_FORECAST_EVAL_ROOT", raising=False)
    with pytest.raises(ForecastExternalError):
        ForecastExternalIngestService().preview("x.csv", _b64(CSV), "manual", None)


def test_eval_root_under_data_root_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "live"
    data.mkdir()
    monkeypatch.setenv("HB_FORECAST_DATA_ROOT", str(data))
    monkeypatch.setenv("HB_FORECAST_EVAL_ROOT", str(data / "eval"))
    with pytest.raises(ForecastExternalError):
        ForecastExternalIngestService().preview("x.csv", _b64(CSV), "manual", None)
