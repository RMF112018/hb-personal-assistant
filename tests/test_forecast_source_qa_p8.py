"""P8 — source-data QA rationale in the run-output ``source_qa`` narrative.

Proves: when explainability is enabled the projector emits one ``source_qa`` narrative summarizing
null / zero projected-cost values, duplicate budget-code keys, and the forecast-period staleness
signal over the analysis-package recommendation rows. (The decision-support availability QA columns
are populated by P5 already and are unchanged by P8.) No network, no CFR import, no live-DB write.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.construction.forecast import output_projection_engine as eng

PROJECT_KEY = "tropical"
FIXED_NOW = "2026-01-01T00:00:00+00:00"


def _make_analysis_package(root: Path, recs: list[dict], *, stamp: str = "20260622_120000") -> Path:
    pkg = root / f"forecast_analysis_package_tropical_{stamp}"
    (pkg / "summaries").mkdir(parents=True)
    (pkg / "manifest.json").write_text(
        json.dumps({"project_key": PROJECT_KEY, "stamp": stamp}), encoding="utf-8"
    )
    (pkg / "summaries" / "project_forecast_analysis.json").write_text(
        json.dumps({"total_budget_codes": len(recs)}), encoding="utf-8"
    )
    (pkg / "forecast_recommendations_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8"
    )
    (pkg / "forecast_risk_register.jsonl").write_text("", encoding="utf-8")
    return pkg


def _source_qa(plan: dict) -> dict:
    rows = [r for r in plan["planned"]["narratives"] if r["scope"] == "source_qa"]
    assert len(rows) == 1
    return json.loads(rows[0]["raw_json"])


def test_source_qa_reports_null_zero_dup_and_staleness() -> None:
    recs = [
        {"budget_code_key": "01-100", "recommended_projected_cost": "125000.00"},  # ok
        {"budget_code_key": "02-200", "recommended_projected_cost": None},  # null
        {"budget_code_key": "03-300", "recommended_projected_cost": "0.00"},  # zero
        {"budget_code_key": "01-100", "recommended_projected_cost": "9000.00"},  # duplicate key
    ]
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td), recs, stamp="20260101_000000")
        plan = eng.plan_run_output_projection(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            now_utc=FIXED_NOW,
            explainability_enabled=True,
        )
    qa = _source_qa(plan)
    assert qa["budget_code_count"] == 4
    assert qa["null_projected_cost_count"] == 1
    assert qa["zero_projected_cost_count"] == 1
    assert qa["duplicate_budget_code_keys"] == ["01-100"]
    assert qa["forecast_period"] == "20260101_000000"  # staleness signal from the manifest stamp


def test_source_qa_clean_package_has_no_findings() -> None:
    recs = [
        {"budget_code_key": "01-100", "recommended_projected_cost": "125000.00"},
        {"budget_code_key": "02-200", "recommended_projected_cost": "80000.00"},
    ]
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td), recs)
        plan = eng.plan_run_output_projection(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            now_utc=FIXED_NOW,
            explainability_enabled=True,
        )
    qa = _source_qa(plan)
    assert qa["null_projected_cost_count"] == 0
    assert qa["zero_projected_cost_count"] == 0
    assert qa["duplicate_budget_code_keys"] == []
