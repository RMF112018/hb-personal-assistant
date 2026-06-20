"""Phase 19 — DB-backed config consumer proof for forecast_probability.

Runs the REAL deterministic forecast_probability generator twice — file-backed (CFR_CONFIG_ROOT unset) and
DB-snapshot-backed (CFR_CONFIG_ROOT = materialized snapshot) — and proves byte-exact parity. Uses a reduced
self-consistent config root (project json + owner-SOV crosswalk + controls/model/staffing so snapshot >
consumed) imported into a temp v60 DB, with cli.SUBPROJECT_ROOT and simulation_inputs.SUBPROJECT_ROOT
monkeypatched at it so the file-backed run reads it and the DB-backed run reads the snapshot of the same
config. The local inventory DB is monkeypatched to a non-existent path; the real live DB is never touched.
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
from construction_financial_review.forecast_intelligence import db_inventory  # noqa: E402
from construction_financial_review.forecast_probability import simulation_inputs as si  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    forecast_probability_db_config_proof as p19,
)

STAMP = "20260101_000000"
CODE = "1000.03-01-025.MAT"
RUNS = 64
SEED = 20260614


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(crootmod.ENV_CONFIG_ROOT, raising=False)


def _build_config_root(root: Path) -> Path:
    proj = {
        "project_key": "tropical",
        "project_name": "T",
        "job_reference": "23-435-01",
        "forecast_period": "2026-June",
        "default_data_root": str(root / "unused"),
        "owner_sov_scope_crosswalk": "config/crosswalks/tropical/xwalk.jsonl",
        "forecast_controls": {
            "enabled": False,
            "control_file": "config/forecast_controls/tropical/c.jsonl",
        },
        "forecast_model_controls": {
            "enabled": False,
            "control_file": "config/forecast_model_controls/tropical/m.jsonl",
        },
        "forecast_staffing_plan": {
            "enabled": False,
            "mapping_file": "config/forecast_staffing/tropical/s.jsonl",
        },
        "llm": {},
        "forecast_intelligence": {"db_path": str(root / "no_inv.sqlite")},
    }
    (root / "config" / "projects").mkdir(parents=True, exist_ok=True)
    (root / "config" / "projects" / "tropical.json").write_text(
        json.dumps(proj, indent=2), encoding="utf-8"
    )
    xw = root / "config" / "crosswalks" / "tropical" / "xwalk.jsonl"
    xw.parent.mkdir(parents=True, exist_ok=True)
    xw.write_text(
        json.dumps(
            {
                "owner_sov_code": "01-000",
                "owner_scope_description": "General",
                "covered_budget_code_keys": [CODE],
                "covered_budget_code_key_patterns": [],
                "covered_budget_code_exclusion_patterns": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    for rel, row in {
        "config/forecast_controls/tropical/c.jsonl": {
            "project_key": "tropical",
            "control_id": "c1",
        },
        "config/forecast_model_controls/tropical/m.jsonl": {
            "project_key": "tropical",
            "control_id": "m1",
        },
        "config/forecast_staffing/tropical/s.jsonl": {
            "project_key": "tropical",
            "source_cost_code": "03-01-025",
        },
    }.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return root


def _build_data_root(root: Path) -> Path:
    ac = root / "forecast_accuracy_next_package_tropical_20260101_000000"
    ac.mkdir(parents=True, exist_ok=True)
    (ac / "forecast_recommendations_by_budget_code.jsonl").write_text(
        json.dumps(
            {
                "budget_code_key": CODE,
                "budget_code_description": "Test",
                "actual_cost_all_source_to_date": "500.00",
                "recommended_cost_to_complete": "500.00",
                "worst_credible_cost_to_complete": "700.00",
                "recommended_final_cost": "1000.00",
                "worst_credible_final_cost": "1200.00",
                "current_projected_cost": "1000.00",
                "revised_budget": "1000.00",
                "committed_cost": "800.00",
                "confidence_score": "0.7",
                "overrun_confidence": "0.3",
                "model_divergence": "0.1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ac / "forecast_confidence_by_budget_code.jsonl").write_text("", encoding="utf-8")
    (ac / "trend_evidence_by_budget_code.jsonl").write_text("", encoding="utf-8")
    (ac / "model_backtest_results.json").write_text(
        json.dumps({"summary_by_method": []}), encoding="utf-8"
    )
    mo = root / "forecast_monthly_package_tropical_20260101_000000"
    (mo / "audit").mkdir(parents=True, exist_ok=True)
    (mo / "remaining_work_monthly_distribution_by_budget_code.jsonl").write_text(
        json.dumps(
            {
                "budget_code_key": CODE,
                "monthly_distribution_weights": [{"month": "2026-06", "weight": "1.0"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (mo / "monthly_forecast_confidence_by_budget_code.jsonl").write_text(
        json.dumps({"budget_code_key": CODE, "monthly_distribution_score": "0.6"}) + "\n",
        encoding="utf-8",
    )
    (mo / "project_monthly_cashflow_summary.json").write_text(
        json.dumps(
            {
                "forecast_months": ["2026-06"],
                "total_actual_to_date": "500.00",
                "total_current_projected_cost": "1000.00",
                "total_recommended_final_cost": "1000.00",
                "total_worst_credible_final_cost": "1200.00",
            }
        ),
        encoding="utf-8",
    )
    (mo / "audit" / "forecast_model_controls_applied.json").write_text(
        json.dumps({"applied_model_controls": []}), encoding="utf-8"
    )
    return root


def _setup(tmp_path: Path, monkeypatch):
    cfg_root = _build_config_root(tmp_path / "config_root")
    (tmp_path / "db").mkdir()
    db = tmp_path / "db" / "reg.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    cr.import_forecast_config_to_db(
        config_root=cfg_root, db_path=db, project_key="tropical", import_run_id="p19"
    )
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="p19", snapshot_reason="proof"
    )
    _c = sqlite3.connect(str(db))
    _c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    _c.close()
    data_root = _build_data_root(tmp_path / "data")
    monkeypatch.setattr(cli, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(si, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(db_inventory, "resolve_db_path", lambda cfg: tmp_path / "no_inv.sqlite")
    return db, snap, data_root, cfg_root


def _run(tmp_path, db, snap_id, data_root, cfg_root, **kw):
    kw.setdefault("require_item_count", None)
    kw.setdefault("preflight_stability_seconds", 0.0)
    kw.setdefault("runs", RUNS)
    kw.setdefault("seed", SEED)
    return p19.run_forecast_probability_db_config_proof(
        live_db_path=db,
        config_snapshot_id=snap_id,
        work_root=tmp_path / "work",
        run_stamp=STAMP,
        require_live_snapshot=False,
        data_root=data_root,
        source_config_root=cfg_root,
        **kw,
    )


# --- parity + consumed accounting + path-embedding ------------------------------------


def test_parity_ready(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p19.DECISION_READY
    assert rep["comparison"]["result"] == "pass" and rep["comparison"]["differences"] == []
    assert rep["not_ready_reason"] is None
    assert rep["probability_run"] == {"runs": RUNS, "seed": SEED, "forecast_start_month": None}


def test_consumed_accounting_evidence_backed(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    # full snapshot (project + crosswalk + controls + model + staffing) > consumed (project + crosswalk)
    assert rep["snapshot_item_count"] == 5
    assert rep["consumed_config_domains"] == ["owner_sov_crosswalk", "project"]
    assert rep["consumed_config_files"] == [
        "config/crosswalks/tropical/xwalk.jsonl",
        "config/projects/tropical.json",
    ]
    # counts come from materialized metadata (1 project row + 1 crosswalk row); the sibling .csv is excluded
    assert rep["consumed_snapshot_item_count"] == 2
    assert all("xwalk" not in f or f.endswith(".jsonl") for f in rep["consumed_config_files"])


def test_path_embedding_set_empty_confirmed(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert p19._PATH_EMBEDDING_FILES == ()
    assert rep["comparison"]["path_embedding_files"] == []
    assert rep["comparison"]["raw_diff_inspected"] is True
    # raw byte diff of every shared file is genuinely empty (no normalization needed)
    fp = Path(rep["file_backed_output_package"])
    dp = Path(rep["db_snapshot_backed_output_package"])
    shared = {str(p.relative_to(fp)) for p in fp.rglob("*") if p.is_file()}
    raw = [
        rel
        for rel in shared
        if (dp / rel).is_file() and (fp / rel).read_bytes() != (dp / rel).read_bytes()
    ]
    assert raw == []


def test_db_inventory_not_path_normalized():
    assert "audit/db_inventory.json" not in p19._PATH_EMBEDDING_FILES


# --- owner-SOV crosswalk bridge fix ----------------------------------------------------


def test_owner_scope_bridge_uses_materialized_crosswalk(tmp_path, monkeypatch):
    import os

    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    mat = cr.materialize_forecast_config_snapshot(
        db_path=db, config_snapshot_id=snap["config_snapshot_id"], out_root=tmp_path / "mat"
    )
    root = mat["materialized_config_root"]
    cfg = cli.load_project("tropical")  # cfg_root project (env unset)
    # With CFR_CONFIG_ROOT set to the materialized snapshot, _owner_scope_by_key resolves the crosswalk
    # UNDER that root (the Phase 19 bridge fix) and returns the materialized assignment.
    monkeypatch.setenv(crootmod.ENV_CONFIG_ROOT, str(root))
    try:
        assign = si._owner_scope_by_key(cfg, [CODE])
    finally:
        os.environ.pop(crootmod.ENV_CONFIG_ROOT, None)
    assert assign.get(CODE, {}).get("owner_sov_code") == "01-000"
    # and the resolved path is under the materialized root, not the subproject root
    assert si.resolve_config_base(Path(root)) == Path(root)


def test_owner_scope_crosswalk_tamper_causes_mismatch(tmp_path, monkeypatch):
    # tamper the materialized crosswalk so the DB-backed owner-scope differs -> proves DB-backed reads the
    # materialized crosswalk, and that a real semantic difference fails parity (config_parity_mismatch).
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real_mat = cr.materialize_forecast_config_snapshot

    def _tamper(**kw):
        out = real_mat(**kw)
        f = Path(out["materialized_config_root"]) / "config/crosswalks/tropical/xwalk.jsonl"
        f.write_text(
            json.dumps(
                {
                    "owner_sov_code": "99-999",
                    "owner_scope_description": "Tampered",
                    "covered_budget_code_keys": [CODE],
                    "covered_budget_code_key_patterns": [],
                    "covered_budget_code_exclusion_patterns": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return out

    monkeypatch.setattr(cr, "materialize_forecast_config_snapshot", _tamper)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p19.DECISION_NOT_READY
    assert rep["not_ready_reason"] == p19.NOT_READY_REASON_CONFIG_PARITY
    assert rep["comparison"]["differences"]


# --- probability did NOT run monthly ---------------------------------------------------


def test_probability_did_not_run_monthly(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    from construction_financial_review.forecast_monthly import (
        generate_monthly_forecast_package as mgen,
    )

    def _boom(*a, **k):
        raise AssertionError(
            "forecast_monthly generator must NOT be called by the probability proof"
        )

    monkeypatch.setattr(mgen, "generate", _boom)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p19.DECISION_READY
    s = rep["safety"]
    assert s["forecast_monthly_run"] is False and s["forecast_monthly_package_read"] is True
    assert s["forecast_comprehensive_run"] is False and s["integrated_csv_generated"] is False
    assert s["model_backed_llm_or_ollama_run"] is False and s["intelligence_workflow_run"] is False


def test_cfr_config_root_restored(tmp_path, monkeypatch):
    import os

    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert os.environ.get(crootmod.ENV_CONFIG_ROOT) in (None, "")
    assert rep["db_snapshot_backed"]["cfr_config_root_restored"] is True


def test_outputs_and_report_under_work_root_deterministic(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    work = (tmp_path / "work").resolve()
    assert Path(rep["report_path"]).resolve().is_relative_to(work)
    assert (tmp_path / "work" / p19.SUMMARY_NAME).is_file()
    raw = Path(rep["report_path"]).read_text(encoding="utf-8")
    assert raw == json.dumps(json.loads(raw), indent=2, sort_keys=True) + "\n"


# --- gate refusals (rc 3) --------------------------------------------------------------


def test_refuses_missing_live_db(tmp_path, monkeypatch):
    cfg_root = _build_config_root(tmp_path / "config_root")
    data_root = _build_data_root(tmp_path / "data")
    monkeypatch.setattr(cli, "SUBPROJECT_ROOT", cfg_root)
    with pytest.raises(p19.ForecastProbabilityDbConfigProofError, match="live DB not found"):
        p19.run_forecast_probability_db_config_proof(
            live_db_path=tmp_path / "nope.sqlite",
            config_snapshot_id="x",
            work_root=tmp_path / "w",
            require_live_snapshot=False,
            data_root=data_root,
            source_config_root=cfg_root,
            require_item_count=None,
            preflight_stability_seconds=0.0,
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
    with pytest.raises(p19.ForecastProbabilityDbConfigProofError, match="schema version 59 < 60"):
        p19.run_forecast_probability_db_config_proof(
            live_db_path=bad,
            config_snapshot_id="x",
            work_root=tmp_path / "w",
            require_live_snapshot=False,
            data_root=_build_data_root(tmp_path / "data"),
            source_config_root=cfg_root,
            require_item_count=None,
            preflight_stability_seconds=0.0,
        )


def test_refuses_missing_config_tables(tmp_path, monkeypatch):
    cfg_root = _build_config_root(tmp_path / "config_root")
    monkeypatch.setattr(cli, "SUBPROJECT_ROOT", cfg_root)
    (tmp_path / "db").mkdir()
    bad = tmp_path / "db" / "v60.sqlite"
    c = sqlite3.connect(str(bad))
    c.execute("CREATE TABLE schema_migrations(version INTEGER, name TEXT, applied_at TEXT)")
    c.execute("INSERT INTO schema_migrations VALUES(60, 'v60', 'x')")
    c.commit()
    c.close()
    with pytest.raises(
        p19.ForecastProbabilityDbConfigProofError, match="missing config registry table"
    ):
        p19.run_forecast_probability_db_config_proof(
            live_db_path=bad,
            config_snapshot_id="x",
            work_root=tmp_path / "w",
            require_live_snapshot=False,
            data_root=_build_data_root(tmp_path / "data"),
            source_config_root=cfg_root,
            require_item_count=None,
            preflight_stability_seconds=0.0,
        )


def test_refuses_missing_snapshot(tmp_path, monkeypatch):
    db, _snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    with pytest.raises(
        p19.ForecastProbabilityDbConfigProofError, match="config_snapshot_id not found"
    ):
        _run(tmp_path, db, "nope", data_root, cfg_root)


def test_refuses_wrong_project_snapshot(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    c = sqlite3.connect(str(db))
    c.execute(
        "UPDATE forecast_config_snapshots SET project_key='other' WHERE config_snapshot_id=?",
        (snap["config_snapshot_id"],),
    )
    c.commit()
    c.close()
    with pytest.raises(p19.ForecastProbabilityDbConfigProofError, match="snapshot project_key"):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)


def test_refuses_item_count_mismatch(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    with pytest.raises(p19.ForecastProbabilityDbConfigProofError, match="item_count"):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root, require_item_count=194)


def test_refuses_require_live_snapshot_on_temp_db(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: False)
    with pytest.raises(p19.ForecastProbabilityDbConfigProofError, match="not the live/default DB"):
        p19.run_forecast_probability_db_config_proof(
            live_db_path=db,
            config_snapshot_id=snap["config_snapshot_id"],
            work_root=tmp_path / "w",
            require_live_snapshot=True,
            data_root=data_root,
            source_config_root=cfg_root,
            require_item_count=None,
            preflight_stability_seconds=0.0,
        )


@pytest.mark.parametrize(
    "drop",
    [
        "forecast_accuracy_next_package_tropical_20260101_000000",
        "forecast_monthly_package_tropical_20260101_000000",
    ],
)
def test_refuses_missing_required_predecessor(tmp_path, monkeypatch, drop):
    import shutil

    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    shutil.rmtree(data_root / drop)
    with pytest.raises(
        p19.ForecastProbabilityDbConfigProofError, match="not found under data_root"
    ):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)


def test_refuses_work_root_under_source_config(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    with pytest.raises(
        p19.ForecastProbabilityDbConfigProofError, match="under the source config tree"
    ):
        p19.run_forecast_probability_db_config_proof(
            live_db_path=db,
            config_snapshot_id=snap["config_snapshot_id"],
            work_root=cfg_root / "w",
            require_live_snapshot=False,
            data_root=data_root,
            source_config_root=cfg_root,
            require_item_count=None,
            preflight_stability_seconds=0.0,
        )


def test_refuses_work_root_under_data_root(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    with pytest.raises(
        p19.ForecastProbabilityDbConfigProofError, match="data root / source packages"
    ):
        p19.run_forecast_probability_db_config_proof(
            live_db_path=db,
            config_snapshot_id=snap["config_snapshot_id"],
            work_root=data_root / "w",
            require_live_snapshot=False,
            data_root=data_root,
            source_config_root=cfg_root,
            require_item_count=None,
            preflight_stability_seconds=0.0,
        )


# --- CLI -------------------------------------------------------------------------------


def _cli_args(tmp_path, db, snap_id, cfg_root, data_root, *extra):
    return [
        "forecast-probability-db-config-proof",
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
        "--preflight-stability-seconds",
        "0",
        "--runs",
        str(RUNS),
        "--seed",
        str(SEED),
        *extra,
    ]


def test_cli_success_rc0(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rc = cli.main(_cli_args(tmp_path, db, snap["config_snapshot_id"], cfg_root, data_root))
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["decision"] == p19.DECISION_READY


def test_cli_refusal_rc3(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rc = cli.main(_cli_args(tmp_path, db, "missing-snapshot", cfg_root, data_root))
    assert rc == 3
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_cli_mismatch_rc1(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real_run = p19._run_probability

    def _perturb(*, cfg, data_root, run_stamp, out_root, runs, seed, forecast_start_month):
        meta = real_run(
            cfg=cfg,
            data_root=data_root,
            run_stamp=run_stamp,
            out_root=out_root,
            runs=runs,
            seed=seed,
            forecast_start_month=forecast_start_month,
        )
        if Path(out_root).name == p19.DB_BACKED_SUBDIR:
            f = Path(meta["output_package"]) / "audit" / "db_inventory.json"
            obj = json.loads(f.read_text(encoding="utf-8"))
            obj["__simulated_inventory_drift__"] = True
            f.write_text(json.dumps(obj), encoding="utf-8")
        return meta

    monkeypatch.setattr(p19, "_run_probability", _perturb)
    rc = cli.main(_cli_args(tmp_path, db, snap["config_snapshot_id"], cfg_root, data_root))
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "not_ready"
    assert any(d["file"] == "audit/db_inventory.json" for d in out["comparison"]["differences"])


def test_parser_has_phase19_args():
    a = cli.build_parser().parse_args(
        [
            "forecast-probability-db-config-proof",
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
    assert a.command == "forecast-probability-db-config-proof"
    assert a.runs == 10000 and a.seed == 20260614 and a.preflight_stability_seconds == 2.0
    assert a.expect_item_count == 194 and a.no_require_live_snapshot is False
