"""Phase 18a — live-DB stability hardening for the forecast_monthly DB-config proof.

The first REAL Phase 18 live operator proof failed not_ready: an external writer (HB morning automation /
Procore live sync) mutated the live app DB mid-run (procore_* row counts grew; the file hash changed), so
forecast_monthly's mode=ro ``audit/db_inventory.json`` differed between the file-backed and DB-backed runs.

This suite proves the hardened proof: a fail-closed quiescence PREFLIGHT (physical main/-wal/-shm fingerprints
+ logical schema/data_version/db_inventory counts, sampled twice), a measured before/after ``live_db_integrity``
block driving the safety claim (not a hardcoded literal), a pinned mode=ro connection that prevents the reused
materialize from inducing a checkpoint, and ``audit/db_inventory.json`` kept byte-exact (a real parity signal).
"""

from __future__ import annotations

import copy
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from hb_assistant.store.migrator import SQLiteMigrator

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review import config_registry as cr  # noqa: E402
from construction_financial_review.common import config_root as crootmod  # noqa: E402
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


def _build_config_root(root: Path) -> Path:
    proj = {
        "project_key": "tropical",
        "project_name": "T",
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
        "forecast_intelligence": {"db_path": str(root / "no_inv.sqlite")},
        "owner_sov_scope_crosswalk": "config/owner_sov_scope_crosswalk.jsonl",
    }
    (root / "config" / "projects").mkdir(parents=True, exist_ok=True)
    (root / "config" / "projects" / "tropical.json").write_text(
        json.dumps(proj, indent=2), encoding="utf-8"
    )
    rows = {
        "config/forecast_controls/tropical/code_forecast_controls.jsonl": {
            "project_key": "tropical",
            "control_id": "c1",
            "budget_code_key": CODE,
            "cost_code": None,
            "control_type": "forecast_stop_date",
            "stop_month": "2026-08",
            "acceptance_status": "pending",
            "requires_human_acceptance": True,
            "accepted_by": None,
            "accepted_at": None,
            "reason": "x",
            "notes": "x",
        },
        "config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl": {
            "project_key": "tropical",
            "control_id": "m1",
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
            "reason": "x",
            "notes": "x",
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
            "reason": "x",
            "notes": "x",
        },
    }
    for rel, row in rows.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(row) + "\n", encoding="utf-8")
    (root / "config" / "owner_sov_scope_crosswalk.jsonl").write_text(
        json.dumps({"owner_sov_code": "01-000", "scope": "G"}) + "\n", encoding="utf-8"
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
                "budget_code_description": "T",
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
    an = root / "forecast_analysis_package_tropical_crosswalk_v2_20260101_000000"
    an.mkdir(parents=True, exist_ok=True)
    (an / "forecast_recommendations_by_budget_code.jsonl").write_text(
        json.dumps({"budget_code_key": CODE, "assigned_owner_sov_code": "01-000"}) + "\n",
        encoding="utf-8",
    )
    ac = root / "forecast_accuracy_next_package_tropical_20260101_000000"
    ac.mkdir(parents=True, exist_ok=True)
    (ac / "forecast_recommendations_by_budget_code.jsonl").write_text(
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
    (ac / "schedule_forecast_evidence_by_budget_code.jsonl").write_text(
        json.dumps({"budget_code_key": CODE, "schedule_association": "none"}) + "\n",
        encoding="utf-8",
    )
    return root


def _setup(tmp_path: Path, monkeypatch):
    cfg_root = _build_config_root(tmp_path / "config_root")
    (tmp_path / "db").mkdir()
    db = tmp_path / "db" / "reg.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    cr.import_forecast_config_to_db(
        config_root=cfg_root, db_path=db, project_key="tropical", import_run_id="p18a"
    )
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="p18a", snapshot_reason="proof"
    )
    _c = sqlite3.connect(str(db))
    _c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    _c.close()
    data_root = _build_data_root(tmp_path / "data")
    monkeypatch.setattr(cli, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(mgen, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(db_inventory, "resolve_db_path", lambda cfg: tmp_path / "no_inv.sqlite")
    return db, snap, data_root, cfg_root


def _run(tmp_path, db, snap_id, data_root, cfg_root, **kw):
    kw.setdefault("require_item_count", None)
    kw.setdefault("preflight_stability_seconds", 0.0)
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


# --- stable preflight + measured integrity ---------------------------------------------


def test_stable_db_preflight_passes(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p18.DECISION_READY
    assert rep["not_ready_reason"] is None
    integ = rep["live_db_integrity"]
    assert integ["preflight_stable"] is True
    assert integ["unchanged"] is True and integ["drift"] == []


def test_wal_shm_fingerprints_included(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    before = rep["live_db_integrity"]["before"]["physical"]
    for f in ("main", "wal", "shm"):
        assert set(before[f]) == {"exists", "path", "size_bytes", "mtime_ns", "sha256"}
    assert before["main"]["exists"] is True and before["main"]["sha256"]
    # an absent sibling is recorded with explicit nulls, not omitted
    for f in ("wal", "shm"):
        if not before[f]["exists"]:
            assert before[f]["size_bytes"] is None and before[f]["sha256"] is None


def test_pragma_data_version_included(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    integ = rep["live_db_integrity"]
    for snap_state in (*integ["preflight_samples"], integ["before"], integ["after"]):
        assert isinstance(snap_state["logical"]["data_version"], int)
        assert isinstance(snap_state["logical"]["schema_version"], int)
        assert snap_state["logical"]["db_inventory_digest"]


def test_pin_prevents_proof_induced_change(tmp_path, monkeypatch):
    # materialization + the two runs must NOT change a quiescent WAL-mode DB's measured state
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    assert sqlite3.connect(str(db)).execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    integ = rep["live_db_integrity"]
    assert (
        integ["before"]["physical"]["main"]["sha256"]
        == integ["after"]["physical"]["main"]["sha256"]
    )
    assert integ["unchanged"] is True


# --- unstable preflight -> refusal (rc 3) ----------------------------------------------


def test_unstable_preflight_refuses(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real = p18._live_db_state
    n = {"i": 0}

    def drifting(path, conn, *, db_inventory_tables):
        s = copy.deepcopy(real(path, conn, db_inventory_tables=db_inventory_tables))
        n["i"] += 1
        s["logical"]["data_version"] = n["i"]  # every sample differs -> preflight drift
        return s

    monkeypatch.setattr(p18, "_live_db_state", drifting)
    with pytest.raises(p18.ForecastMonthlyDbConfigProofError, match="live_db_not_quiescent"):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)


# --- during-run drift -> not_ready (rc 1) ----------------------------------------------


def test_during_run_drift_not_ready(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real = p18._live_db_state
    n = {"i": 0}

    def drift_after(path, conn, *, db_inventory_tables):
        s = copy.deepcopy(real(path, conn, db_inventory_tables=db_inventory_tables))
        n["i"] += 1
        if n["i"] >= 3:  # preflight_a, preflight_b stable; the after-capture drifts
            s["logical"]["data_version"] += 1000
        return s

    monkeypatch.setattr(p18, "_live_db_state", drift_after)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p18.DECISION_NOT_READY
    assert rep["not_ready_reason"] == p18.NOT_READY_REASON_LIVE_DB_MUTATED
    assert rep["live_db_integrity"]["unchanged"] is False
    assert "logical.data_version" in rep["live_db_integrity"]["drift"]


def test_safety_block_from_measured_evidence(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    s = rep["safety"]
    # measured, not declared: mirrors the integrity block exactly
    assert s["live_db_unchanged_during_run"] == rep["live_db_integrity"]["unchanged"] is True
    assert s["live_db_preflight_stable"] is True
    # structural read-only claims still asserted
    assert (
        s["live_db_written"] is False
        and s["live_db_migrated"] is False
        and s["live_db_imported"] is False
    )


# --- audit/db_inventory.json stays a real parity signal --------------------------------


def test_db_inventory_drift_is_real_parity_failure(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real_run = p18._run_monthly

    def _perturb(*, project_key, cfg, data_root, run_stamp, out_root):
        meta = real_run(
            project_key=project_key,
            cfg=cfg,
            data_root=data_root,
            run_stamp=run_stamp,
            out_root=out_root,
        )
        if (
            Path(out_root).name == p18.DB_BACKED_SUBDIR
        ):  # simulate the live-DB inventory drifting db-side
            f = Path(meta["output_package"]) / "audit" / "db_inventory.json"
            obj = json.loads(f.read_text(encoding="utf-8"))
            obj["__simulated_inventory_drift__"] = True
            f.write_text(json.dumps(obj), encoding="utf-8")
        return meta

    monkeypatch.setattr(p18, "_run_monthly", _perturb)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p18.DECISION_NOT_READY
    assert rep["not_ready_reason"] == p18.NOT_READY_REASON_CONFIG_PARITY
    assert any(d["file"] == "audit/db_inventory.json" for d in rep["comparison"]["differences"])


def test_db_inventory_not_path_normalized():
    # the inventory file must be compared byte-exact; never normalized away
    assert "audit/db_inventory.json" not in p18._PATH_EMBEDDING_FILES


# --- no live DB write/migrate/import ---------------------------------------------------


def test_no_live_db_write(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    before = db.read_bytes()
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert db.read_bytes() == before  # pinned mode=ro -> the proof induces no write/checkpoint
    s = rep["safety"]
    assert not (s["live_db_written"] or s["live_db_migrated"] or s["live_db_imported"])


# --- CLI -------------------------------------------------------------------------------


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
        "--preflight-stability-seconds",
        "0",
        *extra,
    ]


def test_cli_success_rc0(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rc = cli.main(_cli_args(tmp_path, db, snap["config_snapshot_id"], cfg_root, data_root))
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["decision"] == p18.DECISION_READY


def test_cli_preflight_refusal_rc3(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real = p18._live_db_state
    n = {"i": 0}

    def drifting(path, conn, *, db_inventory_tables):
        s = copy.deepcopy(real(path, conn, db_inventory_tables=db_inventory_tables))
        n["i"] += 1
        s["logical"]["data_version"] = n["i"]
        return s

    monkeypatch.setattr(p18, "_live_db_state", drifting)
    rc = cli.main(_cli_args(tmp_path, db, snap["config_snapshot_id"], cfg_root, data_root))
    assert rc == 3
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "refused" and "live_db_not_quiescent" in out["reason"]


def test_parser_has_preflight_flag():
    a = cli.build_parser().parse_args(
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
    assert a.preflight_stability_seconds == 2.0
