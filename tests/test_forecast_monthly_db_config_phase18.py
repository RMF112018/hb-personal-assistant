"""Phase 18 — DB-backed config consumer proof for forecast_monthly.

Runs the REAL deterministic ``forecast_monthly`` generator twice — file-backed (CFR_CONFIG_ROOT unset)
and DB-snapshot-backed (CFR_CONFIG_ROOT = materialized snapshot) — and proves path-normalized parity.

Uses a self-consistent REDUCED config root (project json + minimal control/model/staffing/crosswalk
files at the default relative paths) imported into a temp v60 DB, with the two ``SUBPROJECT_ROOT``
constants monkeypatched at it so the file-backed run reads it while the DB-backed run reads the snapshot
of the same config. The local inventory DB is monkeypatched to a non-existent temp path so the real live
DB is never opened. The real 194-item live proof is a separate operator action.

The forecast data root is a minimal synthetic 3-package set; the proof asserts file-backed ≡ DB-backed
equivalence (not a valid forecast), so ``validation_passed`` may be False on both sides — that is itself
parity evidence. Covers gates, work-root isolation, scoped env restore, parity pass + mismatch, exact
consumed-domain accounting, the read/no-write safety block, no mutation, and CLI rc 0/1/3.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from hb_assistant.construction.forecast import source_domain_engine as dbeng
from hb_assistant.store.migrator import SQLiteMigrator

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review import config_registry as cr  # noqa: E402
from construction_financial_review.common import config_root as crootmod  # noqa: E402
from construction_financial_review.forecast_controls import load_controls as fctl_load  # noqa: E402
from construction_financial_review.forecast_intelligence import db_inventory  # noqa: E402
from construction_financial_review.forecast_monthly import (  # noqa: E402
    generate_monthly_forecast_package as mgen,
)
from construction_financial_review.workflows import (  # noqa: E402
    forecast_monthly_db_config_proof as p18,
)

STAMP = "20260101_000000"
CODE = "1000.03-01-025.MAT"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(crootmod.ENV_CONFIG_ROOT, raising=False)


# --------------------------------------------------------------------------- fixture builders


def _build_config_root(root: Path) -> Path:
    """A self-consistent reduced config root: project json + the four config domains + crosswalk.

    Integrations are DISABLED so the files are read through the resolve_config_base bridge (consumed) and
    materialized, but not validated/applied (no crash on the minimal data root). The crosswalk is present
    so the snapshot holds it but forecast_monthly never reads it through the bridge (full > consumed).
    """
    proj = {
        "project_key": "tropical",
        "project_name": "Tropical World Nursery",
        "job_reference": "23-435-01",
        "forecast_period": "2026-June",
        "default_data_root": str(root / "unused"),
        "forecast_controls": {
            "enabled": False,
            "control_file": "config/forecast_controls/tropical/code_forecast_controls.jsonl",
        },
        "forecast_model_controls": {
            "enabled": False,
            "control_file": "config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl",
            "fail_on_unknown_budget_code_key": True,
        },
        "forecast_staffing_plan": {
            "enabled": False,
            "package_glob": "staffing_json_package_tropical_*",
            "mapping_file": "config/forecast_staffing/tropical/staffing_budget_code_mapping.jsonl",
        },
        "llm": {},
        "forecast_intelligence": {"db_path": str(root / "no_inventory.sqlite")},
        "owner_sov_scope_crosswalk": "config/owner_sov_scope_crosswalk.jsonl",
    }
    (root / "config" / "projects").mkdir(parents=True, exist_ok=True)
    (root / "config" / "projects" / "tropical.json").write_text(
        json.dumps(proj, indent=2), encoding="utf-8"
    )
    rows = {
        "config/forecast_controls/tropical/code_forecast_controls.jsonl": {
            "project_key": "tropical",
            "control_id": "p18-ctl-1",
            "budget_code_key": CODE,
            "cost_code": None,
            "control_type": "forecast_stop_date",
            "stop_month": "2026-08",
            "acceptance_status": "pending",
            "requires_human_acceptance": True,
            "accepted_by": None,
            "accepted_at": None,
            "reason": "p18 fixture",
            "notes": "p18 fixture",
        },
        "config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl": {
            "project_key": "tropical",
            "control_id": "p18-mc-1",
            "budget_code_key": CODE,
            "cost_code": None,
            "control_type": "forecast_model_control",
            "effective_month": "2026-06",
            "forecast_start_policy": "current_month_start",
            "forecast_end_policy": "latest_project_schedule_date",
            "value_constraint_policy": "equal_to_reference",
            "reference_source": "projected_cost",
            "model_type": "existing_model",
            "acceptance_status": "pending",
            "requires_human_acceptance": True,
            "accepted_by": None,
            "accepted_at": None,
            "reason": "p18 fixture",
            "notes": "p18 fixture",
        },
        "config/forecast_staffing/tropical/staffing_budget_code_mapping.jsonl": {
            "project_key": "tropical",
            "source_cost_code": "03-01-025",
            "target_budget_code_key": CODE,
            "mapping_type": "operator_approved",
            "allocation_share": "1.0000",
            "effective_start": "2026-06-01",
            "effective_end": None,
            "acceptance_status": "accepted",
            "accepted_by": "x",
            "accepted_at": None,
            "reason": "p18 fixture",
            "notes": "p18 fixture",
        },
    }
    for rel, row in rows.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(row) + "\n", encoding="utf-8")
    xw = root / "config" / "owner_sov_scope_crosswalk.jsonl"
    xw.write_text(
        json.dumps({"owner_sov_code": "01-000", "scope": "General"}) + "\n", encoding="utf-8"
    )
    return root


def _build_data_root(root: Path) -> Path:
    ctx = root / "forecast_context_package_tropical_20260101_000000"
    (ctx / "canonical").mkdir(parents=True, exist_ok=True)
    (ctx / "summaries").mkdir(parents=True, exist_ok=True)
    (ctx / "canonical" / "budget_codes.jsonl").write_text(
        json.dumps(
            {
                "budget_code_key": CODE,
                "cost_code": "03-01-025",
                "category": "MAT",
                "budget_code_description": "Test",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ctx / "summaries" / "budget_code_forecast_context.jsonl").write_text(
        json.dumps(
            {
                "budget_code_key": CODE,
                "actuals": {"actual_cost_all_source_to_date": "500.00", "monthly_actuals": []},
                "budget_amounts": {
                    "projected_budget": "1000.00",
                    "revised_budget": "1000.00",
                    "current_projected_cost": "1000.00",
                },
                "burn": {"avg_monthly_burn": "100.00"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    analysis = root / "forecast_analysis_package_tropical_crosswalk_v2_20260101_000000"
    analysis.mkdir(parents=True, exist_ok=True)
    (analysis / "forecast_recommendations_by_budget_code.jsonl").write_text(
        json.dumps({"budget_code_key": CODE, "assigned_owner_sov_code": "01-000"}) + "\n",
        encoding="utf-8",
    )
    accepted = root / "forecast_accuracy_next_package_tropical_20260101_000000"
    accepted.mkdir(parents=True, exist_ok=True)
    (accepted / "forecast_recommendations_by_budget_code.jsonl").write_text(
        json.dumps(
            {
                "budget_code_key": CODE,
                "actual_cost_all_source_to_date": "500.00",
                "recommended_cost_to_complete": "500.00",
                "worst_credible_cost_to_complete": "500.00",
                "recommended_final_cost": "1000.00",
                "worst_credible_final_cost": "1000.00",
                "current_projected_cost": "1000.00",
                "revised_budget": "1000.00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (accepted / "schedule_forecast_evidence_by_budget_code.jsonl").write_text(
        json.dumps({"budget_code_key": CODE, "schedule_association": "none"}) + "\n",
        encoding="utf-8",
    )
    return root


def _setup(tmp_path: Path, monkeypatch):
    """Reduced config root imported into a temp v60 DB + snapshot; minimal 3-package data root."""
    cfg_root = _build_config_root(tmp_path / "config_root")
    (tmp_path / "db").mkdir()
    db = tmp_path / "db" / "reg.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    cr.import_forecast_config_to_db(
        config_root=cfg_root, db_path=db, project_key="tropical", import_run_id="p18"
    )
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="p18", snapshot_reason="proof"
    )
    # Flush the WAL into the main file so the no-mutation byte check isolates real writes from a
    # WAL checkpoint of already-committed setup rows (the materialize reader only runs SELECTs).
    _c = sqlite3.connect(str(db))
    _c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    _c.close()
    data_root = _build_data_root(tmp_path / "data")
    # File-backed resolution reads the reduced config root; never open the real live inventory DB.
    monkeypatch.setattr(cli, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(mgen, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(
        db_inventory, "resolve_db_path", lambda cfg: tmp_path / "no_inventory.sqlite"
    )
    return db, snap, data_root, cfg_root


def _run(tmp_path, db, snap_id, data_root, cfg_root, **kw):
    kw.setdefault("require_item_count", None)
    return p18.run_forecast_monthly_db_config_proof(
        live_db_path=db,
        config_snapshot_id=snap_id,
        work_root=tmp_path / "work",
        run_stamp=STAMP,
        require_live_snapshot=False,
        data_root=data_root,
        source_config_root=cfg_root,
        **kw,
    )


# --- 1-6, 22-23. gate refusals (rc 3) --------------------------------------------------


def test_refuses_missing_live_db(tmp_path, monkeypatch):
    cfg_root = _build_config_root(tmp_path / "config_root")
    data_root = _build_data_root(tmp_path / "data")
    monkeypatch.setattr(cli, "SUBPROJECT_ROOT", cfg_root)
    with pytest.raises(p18.ForecastMonthlyDbConfigProofError, match="live DB not found"):
        p18.run_forecast_monthly_db_config_proof(
            live_db_path=tmp_path / "nope.sqlite",
            config_snapshot_id="x",
            work_root=tmp_path / "work",
            require_live_snapshot=False,
            data_root=data_root,
            source_config_root=cfg_root,
            require_item_count=None,
        )


def test_refuses_schema_below_v60(tmp_path, monkeypatch):
    cfg_root = _build_config_root(tmp_path / "config_root")
    monkeypatch.setattr(cli, "SUBPROJECT_ROOT", cfg_root)
    (tmp_path / "db").mkdir()
    bad = tmp_path / "db" / "old.sqlite"
    c = sqlite3.connect(str(bad))
    c.execute("CREATE TABLE schema_migrations(version INTEGER, name TEXT, applied_at TEXT)")
    c.execute("INSERT INTO schema_migrations VALUES(59, 'v59', 'x')")
    c.commit()
    c.close()
    with pytest.raises(p18.ForecastMonthlyDbConfigProofError, match="schema version 59 < 60"):
        p18.run_forecast_monthly_db_config_proof(
            live_db_path=bad,
            config_snapshot_id="x",
            work_root=tmp_path / "work",
            require_live_snapshot=False,
            data_root=_build_data_root(tmp_path / "data"),
            source_config_root=cfg_root,
            require_item_count=None,
        )


def test_refuses_missing_config_tables(tmp_path, monkeypatch):
    cfg_root = _build_config_root(tmp_path / "config_root")
    monkeypatch.setattr(cli, "SUBPROJECT_ROOT", cfg_root)
    (tmp_path / "db").mkdir()
    bad = tmp_path / "db" / "v60_no_tables.sqlite"
    c = sqlite3.connect(str(bad))
    c.execute("CREATE TABLE schema_migrations(version INTEGER, name TEXT, applied_at TEXT)")
    c.execute("INSERT INTO schema_migrations VALUES(60, 'v60', 'x')")
    c.commit()
    c.close()
    with pytest.raises(
        p18.ForecastMonthlyDbConfigProofError, match="missing config registry table"
    ):
        p18.run_forecast_monthly_db_config_proof(
            live_db_path=bad,
            config_snapshot_id="x",
            work_root=tmp_path / "work",
            require_live_snapshot=False,
            data_root=_build_data_root(tmp_path / "data"),
            source_config_root=cfg_root,
            require_item_count=None,
        )


def test_refuses_missing_snapshot(tmp_path, monkeypatch):
    db, _snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    with pytest.raises(p18.ForecastMonthlyDbConfigProofError, match="config_snapshot_id not found"):
        _run(tmp_path, db, "does-not-exist", data_root, cfg_root)


def test_refuses_wrong_project_snapshot(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    c = sqlite3.connect(str(db))
    c.execute(
        "UPDATE forecast_config_snapshots SET project_key='other' WHERE config_snapshot_id=?",
        (snap["config_snapshot_id"],),
    )
    c.commit()
    c.close()
    with pytest.raises(p18.ForecastMonthlyDbConfigProofError, match="snapshot project_key"):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)


def test_refuses_item_count_mismatch(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    with pytest.raises(p18.ForecastMonthlyDbConfigProofError, match="item_count"):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root, require_item_count=999)


def test_refuses_require_live_snapshot_on_temp_db(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: False)
    with pytest.raises(p18.ForecastMonthlyDbConfigProofError, match="not the live/default DB"):
        p18.run_forecast_monthly_db_config_proof(
            live_db_path=db,
            config_snapshot_id=snap["config_snapshot_id"],
            work_root=tmp_path / "work",
            require_live_snapshot=True,
            data_root=data_root,
            source_config_root=cfg_root,
            require_item_count=None,
        )


def test_refuses_missing_required_upstream_package(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    # remove the accepted-intelligence package -> required predecessor missing -> controlled refusal
    import shutil

    shutil.rmtree(data_root / "forecast_accuracy_next_package_tropical_20260101_000000")
    with pytest.raises(
        p18.ForecastMonthlyDbConfigProofError,
        match="accepted_forecast_intelligence_package not found",
    ):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)


# --- 24-25. work-root artifact isolation (data_root may be the live root; artifacts may not) ---


def test_refuses_work_root_under_live_forecast_root(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    live = tmp_path / "live_forecast_root"
    live.mkdir()
    monkeypatch.setattr(p18, "_LIVE_ROOT", live)
    with pytest.raises(p18.ForecastMonthlyDbConfigProofError, match="under the live forecast root"):
        p18.run_forecast_monthly_db_config_proof(
            live_db_path=db,
            config_snapshot_id=snap["config_snapshot_id"],
            work_root=live / "work",
            require_live_snapshot=False,
            data_root=data_root,
            source_config_root=cfg_root,
            require_item_count=None,
        )


def test_refuses_work_root_under_source_config_tree(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    with pytest.raises(p18.ForecastMonthlyDbConfigProofError, match="under the source config tree"):
        p18.run_forecast_monthly_db_config_proof(
            live_db_path=db,
            config_snapshot_id=snap["config_snapshot_id"],
            work_root=cfg_root / "work",
            require_live_snapshot=False,
            data_root=data_root,
            source_config_root=cfg_root,
            require_item_count=None,
        )


def test_data_root_may_be_live_forecast_root(tmp_path, monkeypatch):
    """The data root is read-only input and is NOT rejected for being the live forecast root."""
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(p18, "_LIVE_ROOT", data_root)  # data_root IS the live root now
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p18.DECISION_READY


# --- 7-12. happy path: parity + materialize + scoped env + consumption -----------------


def test_parity_ready(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p18.DECISION_READY
    assert rep["comparison"]["result"] == "pass"
    assert rep["comparison"]["differences"] == []
    # parity holds even though the minimal fixture does not produce a fully valid forecast
    assert rep["file_backed"]["validation_passed"] == rep["db_snapshot_backed"]["validation_passed"]


def test_materializes_under_work_root(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert (tmp_path / "work" / p18.MATERIALIZE_SUBDIR / "materialized_config").is_dir()
    assert Path(rep["materialized_config_root"]).is_dir()


def test_cfr_config_root_scoped_and_restored(tmp_path, monkeypatch):
    import os

    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    assert crootmod.ENV_CONFIG_ROOT not in os.environ
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert os.environ.get(crootmod.ENV_CONFIG_ROOT) in (None, "")  # restored
    assert rep["db_snapshot_backed"]["cfr_config_root_restored"] is True
    assert rep["file_backed"]["cfr_config_root"] is None


def test_file_backed_default_reader_unchanged_when_unset(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    # with CFR_CONFIG_ROOT unset the reader resolves under the (patched) repo root, unchanged
    p = fctl_load.control_file_path({}, cfg_root)
    assert str(p).startswith(str(cfg_root))


def test_db_backed_consumes_materialized_config(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    block = rep["db_snapshot_backed"]
    assert block["config_snapshot_consumed"] is True
    assert block["config_snapshot_id"] == snap["config_snapshot_id"]
    work = (tmp_path / "work").resolve()
    assert Path(rep["file_backed"]["output_package"]).resolve().is_relative_to(work)
    assert Path(block["output_package"]).resolve().is_relative_to(work)


def test_consumed_domains_and_counts_accurate(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    # full snapshot (5: project + controls + model + staffing + crosswalk) > consumed (4 via bridge)
    assert rep["snapshot_item_count"] == 5
    assert rep["consumed_snapshot_item_count"] == 4
    assert rep["consumed_config_domains"] == [
        "forecast_controls",
        "forecast_model_controls",
        "forecast_staffing",
        "project",
    ]
    # the owner-SOV crosswalk is NOT claimed as bridge-consumed
    assert "owner_sov_crosswalk" not in rep["consumed_config_domains"]
    assert all("owner_sov" not in f for f in rep["db_snapshot_consumed_files"])
    assert rep["db_snapshot_consumed_files"] == [
        "config/forecast_controls/tropical/code_forecast_controls.jsonl",
        "config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl",
        "config/forecast_staffing/tropical/staffing_budget_code_mapping.jsonl",
        "config/projects/tropical.json",
    ]


def test_outputs_and_report_under_work_root_deterministic(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    work = (tmp_path / "work").resolve()
    assert Path(rep["report_path"]).resolve().is_relative_to(work)
    assert (tmp_path / "work" / p18.SUMMARY_NAME).is_file()
    raw = Path(rep["report_path"]).read_text(encoding="utf-8")
    loaded = json.loads(raw)
    assert raw == json.dumps(loaded, indent=2, sort_keys=True) + "\n"


# --- 13. mismatch -> rc 1 with exact differences ----------------------------------------


def test_parity_mismatch_reports_differences(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real_run = p18._run_monthly

    def _perturbed(*, project_key, cfg, data_root, run_stamp, out_root):
        meta = real_run(
            project_key=project_key,
            cfg=cfg,
            data_root=data_root,
            run_stamp=run_stamp,
            out_root=out_root,
        )
        if Path(out_root).name == p18.DB_BACKED_SUBDIR:  # perturb ONE real semantic value db-side
            f = Path(meta["output_package"]) / "monthly_forecast_by_budget_code.jsonl"
            f.write_text(
                f.read_text(encoding="utf-8").replace("1000.00", "2000.00"), encoding="utf-8"
            )
        return meta

    monkeypatch.setattr(p18, "_run_monthly", _perturbed)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == "not_ready"
    assert rep["comparison"]["result"] == "fail"
    diffs = rep["comparison"]["differences"]
    assert diffs
    assert any(d["file"] == "monthly_forecast_by_budget_code.jsonl" for d in diffs)
    for d in diffs:
        assert {
            "file",
            "key_or_path",
            "file_backed_value",
            "db_backed_value",
            "normalized_rules",
        } <= set(d)


# --- 14-18. safety / no mutation / no out-of-scope -------------------------------------


def test_safety_block_reads_not_writes(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    s = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)["safety"]
    assert s["live_db_written"] is False and s["live_db_migrated"] is False
    assert s["live_db_imported"] is False
    assert s["live_db_snapshot_read"] is True and s["monthly_db_inventory_read"] is True
    assert s["db_snapshot_config_consumed"] is True and s["file_backed_default_preserved"] is True
    assert (
        s["cfr_config_root_default_changed"] is False and s["production_defaults_changed"] is False
    )
    assert s["source_config_mutated"] is False and s["source_package_mutated"] is False
    assert s["forecast_monthly_run"] is True


def test_no_out_of_scope_workflows(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    s = rep["safety"]
    assert s["forecast_comprehensive_run"] is False and s["forecast_probability_run"] is False
    assert s["integrated_csv_generated"] is False
    assert s["model_backed_llm_or_ollama_run"] is False
    # the accepted accuracy package is an INPUT read, not an intelligence-workflow run
    assert s["intelligence_workflow_run"] is False
    assert s["forecast_accuracy_next_package_read"] is True
    # no integrated CSV is emitted by the monthly packages
    for which in ("file_backed", "db_snapshot_backed"):
        pkg = Path(rep[which]["output_package"])
        assert not list(pkg.rglob("*integrated*forecast*.csv"))


def test_no_llm_or_ollama_import_applied(tmp_path, monkeypatch):
    # the workflow runs the generator with with_llm=False; the LLM advisory stays the deterministic mock
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    receipts = (
        Path(rep["file_backed"]["output_package"]) / "llm" / "monthly_narrative_receipts.jsonl"
    )
    # advisory narratives are off (deterministic) -> no ollama_http receipts
    for line in receipts.read_text(encoding="utf-8").splitlines():
        if line.strip():
            assert json.loads(line).get("backend") != "ollama_http"


def test_live_db_and_sources_not_mutated(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    db_before = db.read_bytes()
    cfg_before = {
        str(p.relative_to(cfg_root)): p.read_bytes()
        for p in sorted(cfg_root.rglob("*"))
        if p.is_file()
    }
    data_before = {
        str(p.relative_to(data_root)): p.read_bytes()
        for p in sorted(data_root.rglob("*"))
        if p.is_file()
    }
    _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert db.read_bytes() == db_before  # live/registry DB read-only -> unchanged
    cfg_after = {
        str(p.relative_to(cfg_root)): p.read_bytes()
        for p in sorted(cfg_root.rglob("*"))
        if p.is_file()
    }
    data_after = {
        str(p.relative_to(data_root)): p.read_bytes()
        for p in sorted(data_root.rglob("*"))
        if p.is_file()
    }
    assert cfg_after == cfg_before  # source config tree untouched
    assert data_after == data_before  # source/data packages untouched


# --- 19-21, 26. CLI -------------------------------------------------------------------


def _cli_args(tmp_path, db, snap_id, cfg_root, data_root, *extra):
    return [
        "forecast-monthly-db-config-proof",
        "--project",
        "tropical",
        "--live-db-path",
        str(db),
        "--config-snapshot-id",
        snap_id,
        "--work-root",
        str(tmp_path / "work"),
        "--run-stamp",
        STAMP,
        "--data-root",
        str(data_root),
        "--source-config-root",
        str(cfg_root),
        "--expect-item-count",
        "-1",
        "--no-require-live-snapshot",
        *extra,
    ]


def test_cli_success_rc0(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rc = cli.main(_cli_args(tmp_path, db, snap["config_snapshot_id"], cfg_root, data_root))
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["decision"] == p18.DECISION_READY


def test_cli_refusal_rc3(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rc = cli.main(_cli_args(tmp_path, db, "missing-snapshot", cfg_root, data_root))
    assert rc == 3
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_cli_mismatch_rc1(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real_run = p18._run_monthly

    def _perturbed(*, project_key, cfg, data_root, run_stamp, out_root):
        meta = real_run(
            project_key=project_key,
            cfg=cfg,
            data_root=data_root,
            run_stamp=run_stamp,
            out_root=out_root,
        )
        if Path(out_root).name == p18.DB_BACKED_SUBDIR:
            f = Path(meta["output_package"]) / "monthly_forecast_by_budget_code.jsonl"
            f.write_text(
                f.read_text(encoding="utf-8").replace("1000.00", "2000.00"), encoding="utf-8"
            )
        return meta

    monkeypatch.setattr(p18, "_run_monthly", _perturbed)
    rc = cli.main(_cli_args(tmp_path, db, snap["config_snapshot_id"], cfg_root, data_root))
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["decision"] == "not_ready"


def test_existing_commands_still_route():
    parser = cli.build_parser()
    a = parser.parse_args(
        [
            "forecast-monthly-db-config-proof",
            "--project",
            "tropical",
            "--live-db-path",
            "/d",
            "--config-snapshot-id",
            "s",
            "--work-root",
            "/w",
        ]
    )
    assert a.command == "forecast-monthly-db-config-proof"
    assert a.expect_item_count == 194 and a.no_require_live_snapshot is False
    assert (
        parser.parse_args(
            [
                "forecast-model-controls-db-config-proof",
                "--project",
                "tropical",
                "--live-db-path",
                "/d",
                "--config-snapshot-id",
                "s",
                "--work-root",
                "/w",
            ]
        ).command
        == "forecast-model-controls-db-config-proof"
    )
