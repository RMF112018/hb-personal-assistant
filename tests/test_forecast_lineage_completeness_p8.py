"""P8 — package-sha256 lineage chain (context -> analysis -> output) completeness.

Proves: with explainability enabled the run-output projector sets ``forecast_outputs.source_sha256``
(the analysis-package digest, previously always null) and writes a ``lineage`` narrative carrying the
context/analysis/output sha chain; the model-version (methodology) sha is folded in when a
``forecast_run_model_versions`` provenance row exists for the run and degrades to null otherwise; the
chain is deterministic across two identical runs. No network, no CFR import, no live-DB write.
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


def _recs() -> list[dict]:
    return [
        {
            "project_key": PROJECT_KEY,
            "budget_code_key": "01-100",
            "budget_amount": "100000.00",
            "recommended_projected_cost": "125000.00",
            "recommended_cost_to_complete": "25000.00",
            "confidence": "high",
            "forecast_action": "increase_forecast",
        }
    ]


def _make_analysis_package(root: Path, *, stamp: str = "20260622_120000") -> Path:
    pkg = root / f"forecast_analysis_package_tropical_{stamp}"
    (pkg / "summaries").mkdir(parents=True)
    (pkg / "manifest.json").write_text(
        json.dumps({"project_key": PROJECT_KEY, "stamp": stamp}), encoding="utf-8"
    )
    (pkg / "summaries" / "project_forecast_analysis.json").write_text(
        json.dumps({"total_budget_codes": 1}), encoding="utf-8"
    )
    (pkg / "forecast_recommendations_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in _recs()) + "\n", encoding="utf-8"
    )
    (pkg / "forecast_risk_register.jsonl").write_text("", encoding="utf-8")
    return pkg


def _make_context_package(root: Path) -> Path:
    pkg = root / "forecast_context_package_tropical"
    (pkg / "canonical").mkdir(parents=True)
    (pkg / "canonical" / "budget_codes.jsonl").write_text(
        json.dumps({"budget_code_key": "01-100", "amounts": {"committed_costs": "1000"}}) + "\n",
        encoding="utf-8",
    )
    return pkg


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


def _lineage_row(db: Path) -> dict:
    conn = sqlite3.connect(str(db))
    try:
        raw = conn.execute(
            "SELECT raw_json FROM forecast_output_narratives WHERE scope='lineage'"
        ).fetchone()
    finally:
        conn.close()
    assert raw is not None, "expected a lineage narrative row"
    return json.loads(raw[0])


def test_source_sha256_set_and_chain_present(monkeypatch) -> None:
    monkeypatch.setenv(ENV_EXPLAINABILITY_ENABLED, "1")
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        out = _migrated_db(Path(td) / "out.db")
        eng.project_run_output(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            apply=True,
            db_path=out,
            run_id="run-1",
            now_utc=FIXED_NOW,
        )
        conn = sqlite3.connect(str(out))
        sha = conn.execute("SELECT source_sha256 FROM forecast_outputs").fetchone()[0]
        conn.close()
        chain = _lineage_row(out)
    assert sha is not None  # analysis sha now written (was always null)
    assert chain["analysis_sha256"] == sha
    assert chain["output_sha256"] is not None
    assert chain["context_sha256"] is None  # no context package supplied
    assert chain["methodology_sha256"] is None  # no governance provenance row


def test_context_sha_present_with_context_package(monkeypatch) -> None:
    monkeypatch.setenv(ENV_EXPLAINABILITY_ENABLED, "1")
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        ctx = _make_context_package(Path(td))
        out = _migrated_db(Path(td) / "out.db")
        eng.project_run_output(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            apply=True,
            db_path=out,
            context_package=ctx,
            run_id="run-1",
            now_utc=FIXED_NOW,
        )
        chain = _lineage_row(out)
    assert chain["context_sha256"] is not None


def test_methodology_sha_folded_in_from_governance(monkeypatch) -> None:
    monkeypatch.setenv(ENV_EXPLAINABILITY_ENABLED, "1")
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        out = _migrated_db(Path(td) / "out.db")
        # Seed a model-version provenance row for the run (FK enforcement off on this connection).
        conn = sqlite3.connect(str(out))
        conn.execute(
            "INSERT INTO forecast_run_model_versions "
            "(run_id, model_version_id, project_key, methodology_sha256, accuracy_package_stamp, "
            " raw_json, created_utc) VALUES (?,?,?,?,?,?,?)",
            (
                "run-1",
                "abc123",
                PROJECT_KEY,
                "abc123",
                "20260620_000000",
                json.dumps({"run_id": "run-1", "model_version_id": "abc123"}),
                "t",
            ),
        )
        conn.commit()
        conn.close()
        eng.project_run_output(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            apply=True,
            db_path=out,
            run_id="run-1",
            now_utc=FIXED_NOW,
        )
        chain = _lineage_row(out)
    assert chain["methodology_sha256"] == "abc123"
    assert chain["accuracy_package_stamp"] == "20260620_000000"


def test_lineage_chain_is_deterministic(monkeypatch) -> None:
    monkeypatch.setenv(ENV_EXPLAINABILITY_ENABLED, "1")
    chains = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as td:
            pkg = _make_analysis_package(Path(td))
            out = _migrated_db(Path(td) / "out.db")
            eng.project_run_output(
                analysis_package=pkg,
                project_key=PROJECT_KEY,
                apply=True,
                db_path=out,
                run_id="run-1",
                now_utc=FIXED_NOW,
            )
            chains.append(_lineage_row(out))
    assert chains[0] == chains[1]  # same inputs + now_utc -> identical sha chain
