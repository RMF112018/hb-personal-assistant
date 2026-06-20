"""Phase 20 — DB-backed config consumer proof for forecast_comprehensive.

Runs the REAL deterministic forecast_comprehensive generator twice — file-backed (CFR_CONFIG_ROOT unset) and
DB-snapshot-backed (CFR_CONFIG_ROOT = materialized snapshot) — and proves byte-exact parity. Uses a reduced
self-consistent config root (project + forecast_controls/forecast_model_controls disabled minimal files +
staffing/crosswalk so snapshot > consumed) imported into a temp v60 DB, with cli.SUBPROJECT_ROOT and the
comprehensive generator's SUBPROJECT_ROOT monkeypatched at it; a data_root with the required context +
intelligence + monthly packages AND a cost-frequency package (so comprehensive consumes, never generates).
The local inventory DB is monkeypatched away; the real live DB is never touched.
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
from construction_financial_review.forecast_comprehensive import (  # noqa: E402
    generate_comprehensive_forecast_package as gen,
)
from construction_financial_review.forecast_intelligence import db_inventory  # noqa: E402
from construction_financial_review.forecast_model_controls import load_controls  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    forecast_comprehensive_db_config_proof as p20,
)

STAMP = "20260101_000000"
CODE = "1000.03-01-025.MAT"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(crootmod.ENV_CONFIG_ROOT, raising=False)


def _w(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(rows, list):
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    else:
        path.write_text(json.dumps(rows), encoding="utf-8")


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
        "forecast_comprehensive": {},
        "llm": {},
        "forecast_intelligence": {"db_path": str(root / "no_inv.sqlite")},
    }
    _w(root / "config" / "projects" / "tropical.json", proj)
    _w(
        root / "config" / "crosswalks" / "tropical" / "xwalk.jsonl",
        [
            {
                "owner_sov_code": "01-000",
                "owner_scope_description": "G",
                "covered_budget_code_keys": [CODE],
                "covered_budget_code_key_patterns": [],
                "covered_budget_code_exclusion_patterns": [],
            }
        ],
    )
    _w(
        root / "config" / "forecast_controls" / "tropical" / "c.jsonl",
        [{"project_key": "tropical", "control_id": "c1"}],
    )
    _w(
        root / "config" / "forecast_model_controls" / "tropical" / "m.jsonl",
        [{"project_key": "tropical", "control_id": "m1"}],
    )
    _w(
        root / "config" / "forecast_staffing" / "tropical" / "s.jsonl",
        [{"project_key": "tropical", "source_cost_code": "03-01-025"}],
    )
    return root


def _manifest(name):
    return {"manifest_version": "1.0.0", "package_name": name, "output_files": []}


def _build_data_root(root: Path, *, with_cost_freq: bool = True) -> Path:
    ctx = root / "forecast_context_package_tropical_20260101_000000"
    _w(
        ctx / "canonical" / "budget_codes.jsonl",
        [{"budget_code_key": CODE, "cost_code": "03-01-025", "category": "MAT"}],
    )
    _w(
        ctx / "summaries" / "budget_code_forecast_context.jsonl",
        [
            {
                "budget_code_key": CODE,
                "actuals": {"actual_cost_all_source_to_date": "500.00", "monthly_actuals": []},
                "budget_amounts": {
                    "projected_budget": "1000.00",
                    "revised_budget": "1000.00",
                    "current_projected_cost": "1000.00",
                    "committed_costs": "800.00",
                    "original_budget_amount": "1000.00",
                    "projected_costs": "1000.00",
                    "estimated_cost_at_completion": "1000.00",
                    "forecast_to_complete": "500.00",
                },
                "recommended_cost_to_complete": "500.00",
            }
        ],
    )
    _w(ctx / "manifest.json", _manifest(ctx.name))
    intel = root / "forecast_accuracy_next_package_tropical_20260101_000000"
    _w(
        intel / "forecast_recommendations_by_budget_code.jsonl",
        [
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
            }
        ],
    )
    for f in (
        "dormant_code_status_by_budget_code.jsonl",
        "trend_evidence_by_budget_code.jsonl",
        "schedule_forecast_evidence_by_budget_code.jsonl",
        "forecast_confidence_by_budget_code.jsonl",
    ):
        _w(intel / f, [])
    _w(intel / "manifest.json", _manifest(intel.name))
    mo = root / "forecast_monthly_package_tropical_20260101_000000"
    _w(
        mo / "monthly_forecast_confidence_by_budget_code.jsonl",
        [{"budget_code_key": CODE, "monthly_distribution_score": "0.6"}],
    )
    _w(
        mo / "remaining_work_monthly_distribution_by_budget_code.jsonl",
        [
            {
                "budget_code_key": CODE,
                "monthly_distribution_weights": [{"month": "2026-06", "weight": "1.0"}],
            }
        ],
    )
    _w(mo / "manifest.json", _manifest(mo.name))
    if with_cost_freq:
        cf = root / "forecast_cost_frequency_package_tropical_20260101_000000"
        for f in (
            "cost_frequency_by_budget_code.jsonl",
            "frequency_adjusted_monthly_phasing_by_budget_code.jsonl",
            "internal_staffing_daily_rate_by_budget_code.jsonl",
        ):
            _w(cf / f, [{"budget_code_key": CODE}])
        _w(cf / "manifest.json", _manifest(cf.name))
    return root


def _setup(tmp_path: Path, monkeypatch, *, with_cost_freq: bool = True):
    cfg_root = _build_config_root(tmp_path / "config_root")
    (tmp_path / "db").mkdir()
    db = tmp_path / "db" / "reg.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    cr.import_forecast_config_to_db(
        config_root=cfg_root, db_path=db, project_key="tropical", import_run_id="p20"
    )
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="p20", snapshot_reason="proof"
    )
    _c = sqlite3.connect(str(db))
    _c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    _c.close()
    data_root = _build_data_root(tmp_path / "data", with_cost_freq=with_cost_freq)
    monkeypatch.setattr(cli, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(gen, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(db_inventory, "resolve_db_path", lambda cfg: tmp_path / "no_inv.sqlite")
    return db, snap, data_root, cfg_root


def _run(tmp_path, db, snap_id, data_root, cfg_root, **kw):
    kw.setdefault("require_item_count", None)
    kw.setdefault("preflight_stability_seconds", 0.0)
    return p20.run_forecast_comprehensive_db_config_proof(
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
    assert rep["decision"] == p20.DECISION_READY
    assert rep["comparison"]["result"] == "pass" and rep["comparison"]["differences"] == []
    assert rep["not_ready_reason"] is None


def test_consumed_accounting_evidence_backed(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["snapshot_item_count"] == 5  # project+controls+model+staffing+crosswalk
    assert rep["consumed_config_domains"] == [
        "forecast_controls",
        "forecast_model_controls",
        "project",
    ]
    assert rep["consumed_config_files"] == [
        "config/forecast_controls/tropical/c.jsonl",
        "config/forecast_model_controls/tropical/m.jsonl",
        "config/projects/tropical.json",
    ]
    assert rep["consumed_snapshot_item_count"] == 3  # 1 row each, from materialized metadata


def test_path_embedding_set_empty_raw_diff_confirmed(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert p20._PATH_EMBEDDING_FILES == ()
    assert (
        rep["comparison"]["path_embedding_files"] == []
        and rep["comparison"]["raw_diff_inspected"] is True
    )
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
    assert "audit/db_inventory.json" not in p20._PATH_EMBEDDING_FILES


# --- amendment #1: DB-backed run resolves the MATERIALIZED control files ----------------


def test_db_backed_reads_materialized_control_files(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    mat_root = Path(rep["materialized_config_root"])
    db_resolved = rep["db_snapshot_backed"]["resolved_config_paths"]
    assert rep["db_snapshot_backed"]["reads_materialized_config"] is True
    for p in db_resolved.values():
        assert Path(p).is_relative_to(mat_root)
    # the file-backed run resolves the SAME control files under the (reduced) repo root, not materialized
    for p in rep["file_backed"]["resolved_config_paths"].values():
        assert Path(p).is_relative_to(cfg_root) and not Path(p).is_relative_to(mat_root)


def test_generator_actually_reads_materialized_model_control(tmp_path, monkeypatch):
    # monkeypatch the model-control path resolver to RECORD every path the generator resolves; assert the
    # materialized model-control file path was resolved during the run (proving the DB-backed read).
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real = load_controls.control_file_path
    seen: list[str] = []

    def _record(cfg, subproject_root, override_path=None):
        p = real(cfg, subproject_root, override_path)
        seen.append(str(p))
        return p

    monkeypatch.setattr(load_controls, "control_file_path", _record)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    mat_root = str(Path(rep["materialized_config_root"]))
    assert any(s.startswith(mat_root) for s in seen)  # the generator resolved the materialized file


# --- cost-frequency guard --------------------------------------------------------------


def test_refuses_when_cost_frequency_missing_and_enabled(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch, with_cost_freq=False)
    with pytest.raises(
        p20.ForecastComprehensiveDbConfigProofError,
        match="required_predecessor_package_missing: forecast_cost_frequency",
    ):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)


def test_passes_when_cost_frequency_present(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch, with_cost_freq=True)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p20.DECISION_READY
    assert rep["safety"]["forecast_cost_frequency_package_read"] is True


def test_cost_frequency_generator_never_called(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch, with_cost_freq=True)
    from construction_financial_review.forecast_cost_frequency import (
        generate_forecast_cost_frequency_package as fcfgen,
    )

    def _boom(*a, **k):
        raise AssertionError("Phase 20 must NEVER generate a cost-frequency package")

    monkeypatch.setattr(fcfgen, "generate", _boom)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p20.DECISION_READY
    assert rep["safety"]["forecast_cost_frequency_run"] is False
    assert rep["predecessor_packages"]["generated"] == []


def test_data_root_unchanged_before_after(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    before = {
        str(p.relative_to(data_root)): p.read_bytes()
        for p in sorted(data_root.rglob("*"))
        if p.is_file()
    }
    _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    after = {
        str(p.relative_to(data_root)): p.read_bytes()
        for p in sorted(data_root.rglob("*"))
        if p.is_file()
    }
    assert after == before  # source packages (incl. data root) untouched; nothing generated into it


# --- CSV distinction -------------------------------------------------------------------


def test_package_csvs_present_both_and_byte_exact(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    csvs = rep["standard_comprehensive_package_csvs"]
    assert rep["standard_comprehensive_package_csvs_generated"] is True
    assert any("actuals_plus_forecast_monthly" in c for c in csvs)
    fp = Path(rep["file_backed_output_package"])
    dp = Path(rep["db_snapshot_backed_output_package"])
    for c in csvs:
        assert (fp / c).is_file() and (dp / c).is_file()
        assert (fp / c).read_bytes() == (dp / c).read_bytes()  # compared byte-exact
    assert rep["safety"]["integrated_csv_generated"] is False  # no SEPARATE cutover CSV


def test_csv_byte_diff_fails_parity(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real_run = p20._run_comprehensive

    def _perturb(*, cfg, data_root, run_stamp, out_root):
        meta = real_run(cfg=cfg, data_root=data_root, run_stamp=run_stamp, out_root=out_root)
        if Path(out_root).name == p20.DB_BACKED_SUBDIR:
            csv = next(
                Path(meta["output_package"]).rglob("actuals_plus_forecast_monthly_by_cost_code.csv")
            )
            csv.write_text(csv.read_text(encoding="utf-8") + "TAMPER\n", encoding="utf-8")
        return meta

    monkeypatch.setattr(p20, "_run_comprehensive", _perturb)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p20.DECISION_NOT_READY
    assert rep["not_ready_reason"] == p20.NOT_READY_REASON_CONFIG_PARITY
    assert any(d["file"].endswith(".csv") for d in rep["comparison"]["differences"])


# --- factual predecessor reporting -----------------------------------------------------


def test_optional_predecessor_reporting_factual(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)  # no probability package
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert (
        rep["safety"]["forecast_probability_package_read"] is False
    )  # absent -> false (not hardcoded)
    assert rep["safety"]["forecast_monthly_package_read"] is True
    assert "probability" not in rep["predecessor_packages"]["read"]
    assert set(rep["predecessor_packages"]["read"]) == {
        "context",
        "intelligence",
        "monthly",
        "cost_frequency",
    }
    assert (
        rep["safety"]["forecast_monthly_run"] is False
        and rep["safety"]["forecast_probability_run"] is False
    )


def test_cfr_config_root_restored(tmp_path, monkeypatch):
    import os

    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert os.environ.get(crootmod.ENV_CONFIG_ROOT) in (None, "")
    assert rep["db_snapshot_backed"]["cfr_config_root_restored"] is True


def test_report_deterministic_under_work_root(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    work = (tmp_path / "work").resolve()
    assert Path(rep["report_path"]).resolve().is_relative_to(work)
    raw = Path(rep["report_path"]).read_text(encoding="utf-8")
    assert raw == json.dumps(json.loads(raw), indent=2, sort_keys=True) + "\n"


# --- gate refusals + missing required predecessor --------------------------------------


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
    with pytest.raises(p20.ForecastComprehensiveDbConfigProofError, match="schema version 59 < 60"):
        p20.run_forecast_comprehensive_db_config_proof(
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
        p20.ForecastComprehensiveDbConfigProofError, match="config_snapshot_id not found"
    ):
        _run(tmp_path, db, "nope", data_root, cfg_root)


def test_refuses_item_count_mismatch(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    with pytest.raises(p20.ForecastComprehensiveDbConfigProofError, match="item_count"):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root, require_item_count=194)


def test_refuses_require_live_snapshot_on_temp_db(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: False)
    with pytest.raises(
        p20.ForecastComprehensiveDbConfigProofError, match="not the live/default DB"
    ):
        p20.run_forecast_comprehensive_db_config_proof(
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
        "forecast_context_package_tropical_20260101_000000",
        "forecast_accuracy_next_package_tropical_20260101_000000",
        "forecast_monthly_package_tropical_20260101_000000",
    ],
)
def test_refuses_missing_required_predecessor(tmp_path, monkeypatch, drop):
    import shutil

    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    shutil.rmtree(data_root / drop)
    with pytest.raises(
        p20.ForecastComprehensiveDbConfigProofError, match="required predecessor package not found"
    ):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)


def test_refuses_work_root_under_data_root(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    with pytest.raises(
        p20.ForecastComprehensiveDbConfigProofError, match="data root / source packages"
    ):
        p20.run_forecast_comprehensive_db_config_proof(
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
        "forecast-comprehensive-db-config-proof",
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
        *extra,
    ]


def test_cli_success_rc0(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rc = cli.main(_cli_args(tmp_path, db, snap["config_snapshot_id"], cfg_root, data_root))
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["decision"] == p20.DECISION_READY


def test_cli_refusal_rc3(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rc = cli.main(_cli_args(tmp_path, db, "missing-snapshot", cfg_root, data_root))
    assert rc == 3
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_cli_mismatch_rc1(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real_run = p20._run_comprehensive

    def _perturb(*, cfg, data_root, run_stamp, out_root):
        meta = real_run(cfg=cfg, data_root=data_root, run_stamp=run_stamp, out_root=out_root)
        if Path(out_root).name == p20.DB_BACKED_SUBDIR:
            f = Path(meta["output_package"]) / "audit" / "db_inventory.json"
            obj = json.loads(f.read_text(encoding="utf-8"))
            obj["__drift__"] = True
            f.write_text(json.dumps(obj), encoding="utf-8")
        return meta

    monkeypatch.setattr(p20, "_run_comprehensive", _perturb)
    rc = cli.main(_cli_args(tmp_path, db, snap["config_snapshot_id"], cfg_root, data_root))
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "not_ready"
    assert any(d["file"] == "audit/db_inventory.json" for d in out["comparison"]["differences"])


def test_parser_has_phase20_command():
    a = cli.build_parser().parse_args(
        [
            "forecast-comprehensive-db-config-proof",
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
    assert a.command == "forecast-comprehensive-db-config-proof"
    assert a.expect_item_count == 194 and a.preflight_stability_seconds == 2.0
