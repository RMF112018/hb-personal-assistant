"""Phase 17 — DB-backed config consumer proof for forecast_model_controls.

Runs the REAL deterministic ``forecast_model_controls`` generator twice — file-backed (CFR_CONFIG_ROOT
unset) and DB-snapshot-backed (CFR_CONFIG_ROOT = materialized snapshot) — and proves path-normalized
parity. Uses the real repo config imported into a temp v60 DB (so both sides share identical config) and a
minimal synthetic context package; the real live DB is never touched. Covers gates, scoped env restore,
parity pass + mismatch, safety, no-mutation, and CLI rc 0/1/3.
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
from construction_financial_review.forecast_model_controls import load_controls  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    forecast_model_controls_db_config_proof as p17,
)

SUBPROJ = CFR_SRC.parent  # construction-financial-review subproject root (holds config/)
STAMP = "20260101_000000"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(crootmod.ENV_CONFIG_ROOT, raising=False)


def _build_ctx(data_root: Path) -> Path:
    pkg = data_root / "forecast_context_package_tropical_20260101_000000"
    (pkg / "canonical").mkdir(parents=True, exist_ok=True)
    (pkg / "summaries").mkdir(parents=True, exist_ok=True)
    (pkg / "canonical" / "budget_codes.jsonl").write_text(
        json.dumps(
            {"budget_code_key": "0000.03-01-025.MAT", "cost_code": "03-01-025", "category": "MAT"}
        )
        + "\n",
        encoding="utf-8",
    )
    (pkg / "summaries" / "budget_code_forecast_context.jsonl").write_text(
        json.dumps(
            {
                "budget_code_key": "0000.03-01-025.MAT",
                "actuals": {"actual_cost_all_source_to_date": "500.00"},
                "budget_amounts": {"projected_budget": "1000.00"},
                "burn": {"avg_monthly_burn": "100.00"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return data_root


def _setup(tmp_path: Path):
    """Temp v60 DB with the REAL repo config imported + a snapshot; minimal context data root."""
    db = tmp_path / "reg.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    cr.import_forecast_config_to_db(
        config_root=SUBPROJ, db_path=db, project_key="tropical", import_run_id="p17"
    )
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="p17", snapshot_reason="proof"
    )
    data_root = _build_ctx(tmp_path / "data")
    return db, snap, data_root


def _run(tmp_path, db, snap_id, data_root, **kw):
    return p17.run_forecast_model_controls_db_config_proof(
        live_db_path=db,
        config_snapshot_id=snap_id,
        work_root=tmp_path / "work",
        run_stamp=STAMP,
        require_live_snapshot=False,
        data_root=data_root,
        source_config_root=SUBPROJ,
        **kw,
    )


# --- 1-5. gates ------------------------------------------------------------------------


def test_refuses_missing_live_db(tmp_path):
    data_root = _build_ctx(tmp_path / "data")
    with pytest.raises(p17.ForecastModelControlsDbConfigProofError, match="live DB not found"):
        p17.run_forecast_model_controls_db_config_proof(
            live_db_path=tmp_path / "nope.sqlite",
            config_snapshot_id="x",
            work_root=tmp_path / "w",
            require_live_snapshot=False,
            data_root=data_root,
            source_config_root=SUBPROJ,
        )


def test_refuses_schema_below_v60(tmp_path):
    bad = tmp_path / "old.sqlite"
    c = sqlite3.connect(str(bad))
    c.execute("CREATE TABLE schema_migrations(version INTEGER, name TEXT, applied_at TEXT)")
    c.execute("INSERT INTO schema_migrations VALUES(59, 'v59', 'x')")
    c.commit()
    c.close()
    with pytest.raises(p17.ForecastModelControlsDbConfigProofError, match="schema version 59 < 60"):
        p17.run_forecast_model_controls_db_config_proof(
            live_db_path=bad,
            config_snapshot_id="x",
            work_root=tmp_path / "w",
            require_live_snapshot=False,
            data_root=_build_ctx(tmp_path / "d"),
            source_config_root=SUBPROJ,
        )


def test_refuses_missing_config_tables(tmp_path):
    bad = tmp_path / "v60_no_tables.sqlite"
    c = sqlite3.connect(str(bad))
    c.execute("CREATE TABLE schema_migrations(version INTEGER, name TEXT, applied_at TEXT)")
    c.execute("INSERT INTO schema_migrations VALUES(60, 'v60', 'x')")
    c.commit()
    c.close()
    with pytest.raises(
        p17.ForecastModelControlsDbConfigProofError, match="missing config registry table"
    ):
        p17.run_forecast_model_controls_db_config_proof(
            live_db_path=bad,
            config_snapshot_id="x",
            work_root=tmp_path / "w",
            require_live_snapshot=False,
            data_root=_build_ctx(tmp_path / "d"),
            source_config_root=SUBPROJ,
        )


def test_refuses_missing_snapshot(tmp_path):
    db, _snap, data_root = _setup(tmp_path)
    with pytest.raises(
        p17.ForecastModelControlsDbConfigProofError, match="config_snapshot_id not found"
    ):
        _run(tmp_path, db, "does-not-exist", data_root)


def test_refuses_wrong_project_snapshot(tmp_path):
    db, snap, data_root = _setup(tmp_path)
    # rewrite the snapshot row's project_key to a different project
    c = sqlite3.connect(str(db))
    c.execute(
        "UPDATE forecast_config_snapshots SET project_key='other' WHERE config_snapshot_id=?",
        (snap["config_snapshot_id"],),
    )
    c.commit()
    c.close()
    with pytest.raises(p17.ForecastModelControlsDbConfigProofError, match="snapshot project_key"):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root)


def test_refuses_item_count_mismatch(tmp_path):
    db, snap, data_root = _setup(tmp_path)
    with pytest.raises(p17.ForecastModelControlsDbConfigProofError, match="item_count"):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, require_item_count=999)


def test_refuses_require_live_snapshot_on_temp_db(tmp_path, monkeypatch):
    db, snap, data_root = _setup(tmp_path)
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: False)  # temp DB is not live
    with pytest.raises(
        p17.ForecastModelControlsDbConfigProofError, match="not the live/default DB"
    ):
        p17.run_forecast_model_controls_db_config_proof(
            live_db_path=db,
            config_snapshot_id=snap["config_snapshot_id"],
            work_root=tmp_path / "w",
            require_live_snapshot=True,
            data_root=data_root,
            source_config_root=SUBPROJ,
        )


# --- 6-10. happy path: parity + materialize + scoped env + consumption ------------------


def test_parity_ready_and_materialized(tmp_path):
    db, snap, data_root = _setup(tmp_path)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, require_item_count=194)
    assert rep["decision"] == p17.DECISION_READY
    assert rep["comparison"]["result"] == "pass"
    assert rep["comparison"]["differences"] == []
    # snapshot materialized under work_root/db_snapshot_config
    assert (tmp_path / "work" / p17.MATERIALIZE_SUBDIR / "materialized_config").is_dir()
    assert rep["snapshot_item_count"] == 194
    assert rep["consumed_snapshot_item_count"] == 5
    assert rep["db_snapshot_consumed_files"] == [p17.CONSUMED_CONFIG_FILE]
    assert rep["consumed_config_domains"] == ["forecast_model_controls"]


def test_cfr_config_root_scoped_and_restored(tmp_path):
    db, snap, data_root = _setup(tmp_path)
    assert crootmod.ENV_CONFIG_ROOT not in __import__("os").environ
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root)
    import os

    assert os.environ.get(crootmod.ENV_CONFIG_ROOT) in (None, "")  # restored
    assert rep["db_snapshot_backed"]["cfr_config_root_restored"] is True
    assert rep["file_backed"]["cfr_config_root"] is None


def test_file_backed_default_reader_unchanged_when_unset(tmp_path):
    # with CFR_CONFIG_ROOT unset the reader resolves under SUBPROJ (repo default), unchanged
    p = load_controls.control_file_path({}, SUBPROJ)
    assert str(p).startswith(str(SUBPROJ))
    assert p.is_file()


def test_db_backed_consumes_materialized_config(tmp_path):
    db, snap, data_root = _setup(tmp_path)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root)
    db_block = rep["db_snapshot_backed"]
    assert db_block["config_snapshot_consumed"] is True
    assert db_block["config_snapshot_id"] == snap["config_snapshot_id"]
    assert Path(rep["materialized_config_root"]).is_dir()
    # both output packages exist under work_root
    work = (tmp_path / "work").resolve()
    assert Path(rep["file_backed"]["output_package"]).resolve().is_relative_to(work)
    assert Path(db_block["output_package"]).resolve().is_relative_to(work)


def test_outputs_and_report_under_work_root(tmp_path):
    db, snap, data_root = _setup(tmp_path)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root)
    work = (tmp_path / "work").resolve()
    assert Path(rep["report_path"]).resolve().is_relative_to(work)
    assert (tmp_path / "work" / p17.SUMMARY_NAME).is_file()
    # deterministic report (sorted-key + trailing newline)
    raw = Path(rep["report_path"]).read_text(encoding="utf-8")
    loaded = json.loads(raw)
    assert raw == json.dumps(loaded, indent=2, sort_keys=True) + "\n"


# --- 11. mismatch -> rc1 with exact differences ----------------------------------------


def test_parity_mismatch_reports_differences(tmp_path, monkeypatch):
    db, snap, data_root = _setup(tmp_path)
    real_mat = cr.materialize_forecast_config_snapshot

    def _tamper(**kw):
        out = real_mat(**kw)
        f = Path(out["materialized_config_root"]) / p17.CONSUMED_CONFIG_FILE
        f.write_text(
            f.read_text(encoding="utf-8")
            + json.dumps(
                {
                    "project_key": "tropical",
                    "control_id": "TAMPER",
                    "control_type": "forecast_model_control",
                    "effective_month": "2026-06",
                    "cost_code": "03-01-025",
                    "acceptance_status": "pending",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return out

    monkeypatch.setattr(cr, "materialize_forecast_config_snapshot", _tamper)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root)
    assert rep["decision"] == "not_ready"
    assert rep["comparison"]["result"] == "fail"
    assert rep["comparison"]["differences"]
    d = rep["comparison"]["differences"][0]
    assert {
        "file",
        "key_or_path",
        "file_backed_value",
        "db_backed_value",
        "normalized_rules",
    } <= set(d)


# --- 12-16. safety / no mutation / no out-of-scope -------------------------------------


def test_safety_block_no_live_write(tmp_path):
    db, snap, data_root = _setup(tmp_path)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root)
    s = rep["safety"]
    assert s["live_db_written"] is False and s["live_db_migrated"] is False
    assert s["db_snapshot_config_consumed"] is True
    assert s["file_backed_default_preserved"] is True
    assert s["cfr_config_root_default_changed"] is False
    assert s["downstream_monthly_comprehensive_probability_run"] is False
    assert s["integrated_csv_generated"] is False
    assert s["model_backed_llm_or_ollama_run"] is False
    assert s["source_config_mutated"] is False and s["source_package_mutated"] is False


def test_live_db_and_source_config_not_mutated(tmp_path):
    db, snap, data_root = _setup(tmp_path)
    db_before = db.read_bytes()
    cfg_dir = SUBPROJ / "config"
    cfg_before = {
        str(p.relative_to(cfg_dir)): p.read_bytes()
        for p in sorted(cfg_dir.rglob("*"))
        if p.is_file()
    }
    ctx_before = {
        str(p.relative_to(data_root)): p.read_bytes()
        for p in sorted(data_root.rglob("*"))
        if p.is_file()
    }
    _run(tmp_path, db, snap["config_snapshot_id"], data_root)
    assert db.read_bytes() == db_before  # live/registry DB read-only -> unchanged
    cfg_after = {
        str(p.relative_to(cfg_dir)): p.read_bytes()
        for p in sorted(cfg_dir.rglob("*"))
        if p.is_file()
    }
    ctx_after = {
        str(p.relative_to(data_root)): p.read_bytes()
        for p in sorted(data_root.rglob("*"))
        if p.is_file()
    }
    assert cfg_after == cfg_before  # repo config untouched
    assert ctx_after == ctx_before  # source/context package untouched


def test_no_ollama_or_llm_import_in_generator():
    from construction_financial_review.forecast_model_controls import (
        generate_forecast_model_controls_package as gen,
    )

    src = Path(gen.__file__).read_text(encoding="utf-8")
    assert "ollama" not in src.lower()
    assert "import llm" not in src.lower()


# --- 17-19. CLI ------------------------------------------------------------------------


def _cli_args(tmp_path, db, snap_id, *extra):
    return [
        "forecast-model-controls-db-config-proof",
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
        str(_ctx_for(tmp_path)),
        "--source-config-root",
        str(SUBPROJ),
        "--no-require-live-snapshot",
        *extra,
    ]


def _ctx_for(tmp_path):
    return _build_ctx(tmp_path / "data")


def test_cli_success_rc0(tmp_path, capsys):
    db, snap, _dr = _setup(tmp_path)
    rc = cli.main(_cli_args(tmp_path, db, snap["config_snapshot_id"], "--expect-item-count", "194"))
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["decision"] == p17.DECISION_READY


def test_cli_refusal_rc3(tmp_path, capsys):
    db, snap, _dr = _setup(tmp_path)
    rc = cli.main(_cli_args(tmp_path, db, "missing-snapshot"))
    assert rc == 3
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_cli_mismatch_rc1(tmp_path, capsys, monkeypatch):
    db, snap, _dr = _setup(tmp_path)
    real_mat = cr.materialize_forecast_config_snapshot

    def _tamper(**kw):
        out = real_mat(**kw)
        f = Path(out["materialized_config_root"]) / p17.CONSUMED_CONFIG_FILE
        f.write_text(
            f.read_text(encoding="utf-8")
            + json.dumps(
                {
                    "project_key": "tropical",
                    "control_id": "TAMP",
                    "control_type": "forecast_model_control",
                    "effective_month": "2026-06",
                    "cost_code": "03-01-025",
                    "acceptance_status": "pending",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return out

    monkeypatch.setattr(cr, "materialize_forecast_config_snapshot", _tamper)
    rc = cli.main(_cli_args(tmp_path, db, snap["config_snapshot_id"]))
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["decision"] == "not_ready"


def test_existing_commands_still_route():
    parser = cli.build_parser()
    a = parser.parse_args(
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
    )
    assert a.command == "forecast-model-controls-db-config-proof"
    assert a.expect_item_count == 194 and a.no_require_live_snapshot is False
    assert (
        parser.parse_args(
            [
                "forecast-config-db-parity",
                "--project",
                "tropical",
                "--config-root",
                "/c",
                "--work-root",
                "/w",
            ]
        ).command
        == "forecast-config-db-parity"
    )
