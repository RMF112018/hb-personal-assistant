"""P8 — explainability/audit-trail narratives in the run-output projector.

Proves: when explainability is enabled the projector populates ``forecast_output_narratives`` with
a project header narrative, one per budget code, a human-override audit row per operator override,
and a source-QA row; with the flag off (the default) NO narrative rows are planned/written and the
planned output is byte-identical to baseline (``source_sha256`` stays null); the apply bridge
persists the narratives, proves parity, and is idempotent on re-apply. No network, no CFR import,
no live-DB write.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.analytics.forecast_runtime_config import (
    ENV_EXPLAINABILITY_ENABLED,
)
from hb_assistant.construction.forecast import output_projection_engine as eng
from hb_assistant.store.migrator import SQLiteMigrator

PROJECT_KEY = "tropical"
FIXED_NOW = "2026-01-01T00:00:00+00:00"


def _default_recs() -> list[dict]:
    return [
        {
            "project_key": PROJECT_KEY,
            "budget_code_key": "01-100",
            "cost_code": "01-100",
            "category": "GC",
            "forecast_action": "increase_forecast",
            "budget_amount": "100000.00",
            "recommended_projected_cost": "125000.00",
            "recommended_cost_to_complete": "25000.00",
            "confidence": "high",
        },
        {
            "project_key": PROJECT_KEY,
            "budget_code_key": "02-200",
            "cost_code": "02-200",
            "category": "Concrete",
            "forecast_action": "hold",
            "budget_amount": "80000.00",
            "recommended_projected_cost": "80000.00",
            "recommended_cost_to_complete": "0.00",
            "confidence": "moderate",
        },
    ]


def _make_analysis_package(root: Path, *, stamp: str = "20260622_120000", recs=None) -> Path:
    pkg = root / f"forecast_analysis_package_tropical_{stamp}"
    (pkg / "summaries").mkdir(parents=True)
    (pkg / "manifest.json").write_text(
        json.dumps({"project_key": PROJECT_KEY, "stamp": stamp}), encoding="utf-8"
    )
    (pkg / "summaries" / "project_forecast_analysis.json").write_text(
        json.dumps({"total_budget_codes": 2, "risk_count": 0}), encoding="utf-8"
    )
    (pkg / "forecast_recommendations_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in (recs if recs is not None else _default_recs())) + "\n",
        encoding="utf-8",
    )
    (pkg / "forecast_risk_register.jsonl").write_text("", encoding="utf-8")
    return pkg


def _override(atype: str, *, code, value) -> dict:
    return {"assumption_type": atype, "budget_code_key": code, "value": value, "source": "op-test"}


def _migrated_db(path: Path) -> Path:
    SQLiteMigrator(db_path=str(path)).apply()
    # forecast_outputs.run_id has a FK to forecast_runs; seed the parent row for "run-1".
    conn = sqlite3.connect(str(path))
    conn.execute(
        "INSERT OR IGNORE INTO forecast_runs (run_id, project_key, status, created_utc) "
        "VALUES (?,?,?,?)",
        ("run-1", PROJECT_KEY, "complete", "t"),
    )
    conn.commit()
    conn.close()
    return path


def _narratives_by_scope(planned: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for row in planned["narratives"]:
        out.setdefault(row["scope"], []).append(row)
    return out


# --- planner-level narratives -----------------------------------------------------------


def test_narratives_present_when_enabled() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        plan = eng.plan_run_output_projection(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            now_utc=FIXED_NOW,
            explainability_enabled=True,
        )
    by_scope = _narratives_by_scope(plan["planned"])
    # one project header, one per budget code (2), one source-QA; no overrides => no human_override
    assert len(by_scope["project"]) == 1
    assert by_scope["project"][0]["narrative_key"] == "header"
    assert {r["narrative_key"] for r in by_scope["budget_code"]} == {"01-100", "02-200"}
    assert len(by_scope["source_qa"]) == 1
    assert "human_override" not in by_scope
    # project narrative quotes the effective header + counts
    proj = json.loads(by_scope["project"][0]["raw_json"])
    assert proj["estimated_final_cost"] == "205000.00"
    assert proj["budget_code_count"] == 2
    assert proj["risk_count"] == 0
    assert proj["override_count"] == 0
    # deterministic id scheme
    output_id = plan["output_id"]
    assert by_scope["project"][0]["id"] == eng.output_narrative_builder._narrative_id(
        output_id, "project", "header"
    )


def test_flag_off_byte_identical() -> None:
    # Same package + same now_utc; the only variable is the explainability flag.
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        base = eng.plan_run_output_projection(
            analysis_package=pkg, project_key=PROJECT_KEY, now_utc=FIXED_NOW
        )
        off = eng.plan_run_output_projection(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            now_utc=FIXED_NOW,
            explainability_enabled=False,
        )
    # default == explicit-off, and both write no narratives / leave source_sha256 null
    assert json.dumps(base["planned"], sort_keys=True) == json.dumps(off["planned"], sort_keys=True)
    assert base["planned"]["narratives"] == []
    assert base["planned"]["outputs"][0]["source_sha256"] is None


def test_human_override_narrative() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        plan = eng.plan_run_output_projection(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            now_utc=FIXED_NOW,
            explainability_enabled=True,
            operator_assumptions=[
                _override("projected_cost_override", code="01-100", value="150000")
            ],
        )
    by_scope = _narratives_by_scope(plan["planned"])
    assert len(by_scope["human_override"]) == 1
    ho = json.loads(by_scope["human_override"][0]["raw_json"])
    assert ho["budget_code_key"] == "01-100"
    assert ho["original"] == "125000.00"
    assert ho["override"] == "150000.00"
    assert ho["delta_amount"] == "25000.00"
    # the per-code narrative records that the code was overridden
    bc = next(r for r in by_scope["budget_code"] if r["narrative_key"] == "01-100")
    assert json.loads(bc["raw_json"])["overridden"] is True


# --- apply + parity ---------------------------------------------------------------------


def test_apply_persists_narratives_and_parity(monkeypatch) -> None:
    monkeypatch.setenv(ENV_EXPLAINABILITY_ENABLED, "1")
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        out = _migrated_db(Path(td) / "v63_out.db")
        plan = eng.project_run_output(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            apply=True,
            db_path=out,
            parity=True,
            run_id="run-1",
            now_utc=FIXED_NOW,
        )
        assert plan["ok"] is True
        assert plan["parity"]["proven"] is True
        assert plan["parity"]["by_table"]["narratives"]["match"] is True
        conn = sqlite3.connect(str(out))
        scopes = [
            r[0]
            for r in conn.execute(
                "SELECT scope FROM forecast_output_narratives ORDER BY source_row_number"
            )
        ]
        conn.close()
    # 4 plan-phase scopes + the apply-phase lineage row
    assert scopes == ["project", "budget_code", "budget_code", "source_qa", "lineage"]
    assert plan["written"]["narratives"] == 5


def test_reapply_is_idempotent(monkeypatch) -> None:
    monkeypatch.setenv(ENV_EXPLAINABILITY_ENABLED, "1")
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        out = _migrated_db(Path(td) / "v63_out.db")
        for _ in range(2):
            eng.project_run_output(
                analysis_package=pkg,
                project_key=PROJECT_KEY,
                apply=True,
                db_path=out,
                run_id="run-1",
                now_utc=FIXED_NOW,
            )
        conn = sqlite3.connect(str(out))
        count = conn.execute("SELECT COUNT(*) FROM forecast_output_narratives").fetchone()[0]
        conn.close()
    assert count == 5  # stable across re-apply (UNIQUE(output_id, scope, narrative_key))


def test_flag_off_writes_no_narratives(monkeypatch) -> None:
    monkeypatch.delenv(ENV_EXPLAINABILITY_ENABLED, raising=False)
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        out = _migrated_db(Path(td) / "v63_out.db")
        eng.project_run_output(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            apply=True,
            db_path=out,
            run_id="run-1",
            now_utc=FIXED_NOW,
        )
        conn = sqlite3.connect(str(out))
        count = conn.execute("SELECT COUNT(*) FROM forecast_output_narratives").fetchone()[0]
        sha = conn.execute("SELECT source_sha256 FROM forecast_outputs").fetchone()[0]
        conn.close()
    assert count == 0  # flag off -> byte-identical output, no audit trail
    assert sha is None
