"""Phase 15 — controlled DB-certified final forecast output generation.

Exercises the eligibility gates over Phase 14 certified evidence, the rerun Phase 13 certification gate,
the controlled chain (Phase 12 guarded operator run, monkeypatched for the fast paths and run for real
once end-to-end), the DB-certified analysis package copy under ``work_root/final_output``, the
controlled CSV refusal, and CLI rc 0/1/3. Everything runs under ``tmp_path``; the real live DB is never
touched (the synthetic "live" DB is a migrated temp DB whose path is monkeypatched to be the live DB).

build_fixture mirrors the Phase 11/12/13/14 tests (duplicated, not imported).
"""

from __future__ import annotations

import hashlib
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
from construction_financial_review.workflows import db_certified_final_output as dbcfo  # noqa: E402
from construction_financial_review.workflows import guarded_db_operator_run as gormod  # noqa: E402
from construction_financial_review.workflows import live_db_certification as certmod  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    live_db_source_domain_projection as projmod,
)
from construction_financial_review.workflows.db_certified_final_output import (  # noqa: E402
    DECISION_READY,
    DbCertifiedFinalOutputError,
    run_db_certified_final_output,
)

BCK = "0000.03-01-025.MAT"
PROCORE_DIRNAME = "cost_forecast_agent_db_json_export_tropical_20260614_080344"
STAMP = "20260101_000000"
REQUIRED_TABLES = (
    "forecast_budget_details",
    "forecast_cost_entries",
    "forecast_monthly_actuals_by_budget_code",
)
SYNTH_COUNTS = {
    "forecast_budget_details": 3,
    "forecast_cost_entries": 5,
    "forecast_monthly_actuals_by_budget_code": 7,
}


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for var in (
        "HB_FORECAST_DB_BACKED_READS",
        "HB_FORECAST_DB_PATH",
        "CFR_CONTEXT_DATA_ROOT",
        "CFR_CONTEXT_OUT_DIR",
        "CFR_CONTEXT_STAMP",
        "CFR_RUN_LINEAGE_STATE",
    ):
        monkeypatch.delenv(var, raising=False)


def _same(a, b) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def _flag_live(monkeypatch, live_path: Path) -> None:
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: _same(p, live_path))


def _source_package(root: Path) -> Path:
    return build_fixture(root) / "twn_cost_forecast_json_package"


def _content_sig(p: Path) -> tuple[int, str]:
    b = Path(p).read_bytes()
    return len(b), hashlib.sha256(b).hexdigest()


def _tree_sig(root: Path) -> dict[str, tuple[int, str]]:
    return {
        str(p.relative_to(root)): _content_sig(p) for p in sorted(root.rglob("*")) if p.is_file()
    }


# --- synthetic Phase 14 evidence (fast paths; no chain) --------------------------------


def _synth_evidence(tmp_path: Path, *, live: Path, counts=SYNTH_COUNTS) -> tuple[Path, dict]:
    """Write a valid Phase 14 evidence set (backup + sub-reports) and return (source_package, report)."""
    sp = _source_package(tmp_path / "src")
    evid = tmp_path / "evidence"
    evid.mkdir(parents=True, exist_ok=True)
    backup = evid / "backups" / "hb-personal-assistant.before-phase14.sqlite"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(b"synthetic-live-db-backup-bytes")
    pwc = evid / "post_write_cert.json"
    pwc.write_text(json.dumps({"decision": "certified_match"}), encoding="utf-8")
    gor = evid / "guarded_manifest.json"
    gor.write_text(json.dumps({"status": "ready"}), encoding="utf-8")
    tables = {
        t: {"match": True, "live_rows": counts[t], "temp_rows": counts[t]} for t in REQUIRED_TABLES
    }
    report = {
        "schema_version": 1,
        "project_key": "tropical",
        "status": "ready",
        "decision": "live_db_source_domain_certified",
        "source_package": str(sp),
        "live_db": {"path": str(live)},
        "backup": {
            "path": str(backup),
            "sha256": dbcfo._sha256_file(backup),
            "verified_readable": True,
            "schema_version": 59,
        },
        "post_write_certification": {
            "decision": "certified_match",
            "report_path": str(pwc),
            "tables": tables,
        },
        "guarded_operator_check": {
            "status": "ready",
            "decision": "approved_for_guarded_db_context_analysis_use",
            "live_db": {
                "certified": True,
                "certification_decision": "certified_match",
                "equivalent_to_temp_db": True,
                "used_for_execution": False,
            },
            "report_path": str(gor),
        },
        "safety": {
            "live_db_written": True,
            "live_db_migrated": False,
            "live_db_projected_directly": False,
            "projected_via_temp_db": True,
            "live_root_written": False,
            "production_defaults_changed": False,
            "final_integrated_csv_generated": False,
            "true_live_execution_used": False,
        },
    }
    return sp, report


def _write_report(tmp_path: Path, report: dict) -> Path:
    p = tmp_path / "evidence" / "live_db_source_domain_projection_report.json"
    p.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def _mock_cert_ok(monkeypatch, counts=SYNTH_COUNTS) -> None:
    def _cert(**kw):
        return {
            "decision": "certified_match",
            "report_path": str(
                Path(kw["work_root"]) / "live_db_readonly_certification_report.json"
            ),
            "tables": {
                t: {
                    "live_rows": counts[t],
                    "temp_rows": counts[t],
                    "raw_json_match": True,
                    "canonical_match": True,
                    "match": True,
                }
                for t in REQUIRED_TABLES
            },
        }

    monkeypatch.setattr(certmod, "run_live_db_readonly_certification", _cert)


def _fake_analysis_package(root: Path) -> Path:
    """Create a synthetic Phase 7-style analysis package (JSONL + manifest + README)."""
    pkg = root / "forecast_analysis_package_tropical_20260101_000000"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "forecast_recommendations_by_budget_code.jsonl").write_text(
        "".join(json.dumps({"budget_code_key": f"c{i}"}) + "\n" for i in range(3)),
        encoding="utf-8",
    )
    (pkg / "manifest.json").write_text(json.dumps({"package_name": pkg.name}), encoding="utf-8")
    (pkg / "README.md").write_text("# analysis\n", encoding="utf-8")
    return pkg


def _mock_guarded_ok(monkeypatch, tmp_path: Path) -> Path:
    ana = _fake_analysis_package(tmp_path / "ana_src")
    ctx = tmp_path / "ana_src" / "forecast_context_package_tropical_20260101_000000"
    ctx.mkdir(parents=True, exist_ok=True)
    chain = tmp_path / "ana_src" / "forecast_package_chain_manifest.json"
    chain.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    def _guarded(**kw):
        return {
            "status": "ready",
            "decision": "approved_for_guarded_db_context_analysis_use",
            "report_path": str(Path(kw["work_root"]) / "guarded_db_operator_run_manifest.json"),
            "approved_artifacts": {
                "context_package": str(ctx),
                "analysis_package": str(ana),
                "chain_manifest": str(chain),
            },
            "live_db": {"used_for_execution": False, "equivalent_to_temp_db": True},
        }

    monkeypatch.setattr(gormod, "run_guarded_db_operator_run", _guarded)
    return ana


# --- 1-2. Phase 14 report presence / shape --------------------------------------------


def test_refuses_missing_phase14_report(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, _ = _synth_evidence(tmp_path, live=live)
    with pytest.raises(DbCertifiedFinalOutputError, match="Phase 14 report not found"):
        run_db_certified_final_output(
            phase14_report=tmp_path / "nope.json",
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
        )


def test_refuses_malformed_phase14_report(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, _ = _synth_evidence(tmp_path, live=live)
    bad = tmp_path / "evidence" / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(DbCertifiedFinalOutputError, match="not readable JSON"):
        run_db_certified_final_output(
            phase14_report=bad,
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
        )


# --- 3-7. Phase 14 decision / certification / guarded gates ---------------------------


def _run_with(tmp_path, monkeypatch, mutate, *, live=None):
    live = live or (tmp_path / "live" / "hb.sqlite")
    _flag_live(monkeypatch, live)
    sp, report = _synth_evidence(tmp_path, live=live)
    mutate(report)
    rp = _write_report(tmp_path, report)
    return run_db_certified_final_output(
        phase14_report=rp,
        source_package=sp,
        work_root=tmp_path / "work",
        context_stamp=STAMP,
        live_db_path=live,
    )


def test_refuses_wrong_phase14_decision(tmp_path, monkeypatch):
    with pytest.raises(DbCertifiedFinalOutputError, match="decision is not"):
        _run_with(tmp_path, monkeypatch, lambda r: r.update(decision="something_else"))


def test_refuses_post_write_cert_not_match(tmp_path, monkeypatch):
    def _m(r):
        r["post_write_certification"]["decision"] = "stale_or_mismatch"

    with pytest.raises(DbCertifiedFinalOutputError, match="post-write certification is not"):
        _run_with(tmp_path, monkeypatch, _m)


def test_refuses_table_match_false(tmp_path, monkeypatch):
    def _m(r):
        r["post_write_certification"]["tables"]["forecast_cost_entries"]["match"] = False

    with pytest.raises(DbCertifiedFinalOutputError, match="is not a confirmed match"):
        _run_with(tmp_path, monkeypatch, _m)


def test_refuses_guarded_used_for_execution(tmp_path, monkeypatch):
    def _m(r):
        r["guarded_operator_check"]["live_db"]["used_for_execution"] = True

    with pytest.raises(DbCertifiedFinalOutputError, match="used_for_execution is not False"):
        _run_with(tmp_path, monkeypatch, _m)


def test_refuses_guarded_not_equivalent(tmp_path, monkeypatch):
    def _m(r):
        r["guarded_operator_check"]["live_db"]["equivalent_to_temp_db"] = False

    with pytest.raises(DbCertifiedFinalOutputError, match="not equivalent_to_temp_db"):
        _run_with(tmp_path, monkeypatch, _m)


# --- 8-9. backup gates ----------------------------------------------------------------


def test_refuses_missing_backup(tmp_path, monkeypatch):
    def _m(r):
        Path(r["backup"]["path"]).unlink()

    with pytest.raises(DbCertifiedFinalOutputError, match="backup not found"):
        _run_with(tmp_path, monkeypatch, _m)


def test_refuses_backup_sha_mismatch(tmp_path, monkeypatch):
    def _m(r):
        Path(r["backup"]["path"]).write_bytes(b"corrupted-different-bytes")

    with pytest.raises(DbCertifiedFinalOutputError, match="backup sha256 mismatch"):
        _run_with(tmp_path, monkeypatch, _m)


# --- 10-11. source / work-root gates --------------------------------------------------


def test_refuses_mismatched_source_package(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, report = _synth_evidence(tmp_path, live=live)
    other = _source_package(tmp_path / "other_src")  # valid name, different path
    rp = _write_report(tmp_path, report)
    with pytest.raises(DbCertifiedFinalOutputError, match="does not match the Phase 14 report"):
        run_db_certified_final_output(
            phase14_report=rp,
            source_package=other,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
        )


def test_refuses_unsafe_work_root(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, report = _synth_evidence(tmp_path, live=live)
    rp = _write_report(tmp_path, report)
    fake_live_root = tmp_path / "fake_live_root"
    monkeypatch.setattr(dbcfo, "_LIVE_ROOT", fake_live_root)
    with pytest.raises(DbCertifiedFinalOutputError, match="live forecast root"):
        run_db_certified_final_output(
            phase14_report=rp,
            source_package=sp,
            work_root=fake_live_root / "work",
            context_stamp=STAMP,
            live_db_path=live,
        )


def test_refuses_mismatched_live_db_path(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    other_live = tmp_path / "live2" / "hb.sqlite"
    # Both treated as live so the mismatch (not the live-check) is what fails.
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: True)
    sp, report = _synth_evidence(tmp_path, live=live)
    rp = _write_report(tmp_path, report)
    with pytest.raises(DbCertifiedFinalOutputError, match="does not match the Phase 14 report"):
        run_db_certified_final_output(
            phase14_report=rp,
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=other_live,
        )


# --- 12-13. rerun certification gate --------------------------------------------------


def test_rerun_cert_mismatch_refused(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, report = _synth_evidence(tmp_path, live=live)
    rp = _write_report(tmp_path, report)
    monkeypatch.setattr(
        certmod,
        "run_live_db_readonly_certification",
        lambda **kw: {"decision": "stale_or_mismatch", "report_path": "x", "tables": {}},
    )
    with pytest.raises(DbCertifiedFinalOutputError, match="rerun live-DB certification is not"):
        run_db_certified_final_output(
            phase14_report=rp,
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
        )


def test_rerun_cert_count_drift_refused(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, report = _synth_evidence(tmp_path, live=live)
    rp = _write_report(tmp_path, report)
    drift = {**SYNTH_COUNTS, "forecast_cost_entries": 99}
    _mock_cert_ok(monkeypatch, counts=drift)
    with pytest.raises(DbCertifiedFinalOutputError, match="count drift"):
        run_db_certified_final_output(
            phase14_report=rp,
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            live_db_path=live,
        )


# --- 14-20. controlled generation (monkeypatched generator) ---------------------------


def _happy(tmp_path, monkeypatch, **kwargs) -> dict:
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, report = _synth_evidence(tmp_path, live=live)
    rp = _write_report(tmp_path, report)
    _mock_cert_ok(monkeypatch)
    _mock_guarded_ok(monkeypatch, tmp_path)
    return run_db_certified_final_output(
        phase14_report=rp,
        source_package=sp,
        work_root=tmp_path / "work",
        context_stamp=STAMP,
        live_db_path=live,
        **kwargs,
    )


def test_controlled_generation_ready(tmp_path, monkeypatch):
    report = _happy(tmp_path, monkeypatch)
    assert report["status"] == "ready"
    assert report["decision"] == DECISION_READY
    assert report["live_db_verification"]["certification_decision"] == "certified_match"


def test_records_final_csv_path_hash_rowcount(tmp_path, monkeypatch):
    report = _happy(tmp_path, monkeypatch)
    fo = report["final_outputs"]
    assert len(fo["package_paths"]) == 1
    assert fo["csv_paths"] == []
    # the synthetic analysis package has one 3-row JSONL
    assert fo["row_counts"]["forecast_recommendations_by_budget_code.jsonl"] == 3
    assert len(fo["sha256"]["manifest.json"]) == 64
    assert "README.md" in fo["sha256"]


def test_all_outputs_under_work_root(tmp_path, monkeypatch):
    report = _happy(tmp_path, monkeypatch)
    work = (tmp_path / "work").resolve()
    for p in (
        report["report_path"],
        *report["final_outputs"]["package_paths"],
        str(tmp_path / "work" / "db_certified_final_output_summary.md"),
    ):
        assert Path(p).resolve().is_relative_to(work)
    assert (tmp_path / "work" / "db_certified_final_output_summary.md").is_file()


def test_live_db_not_opened_for_write(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    live.parent.mkdir(parents=True)
    SQLiteMigrator(db_path=str(live)).apply()
    before = _content_sig(live)
    _flag_live(monkeypatch, live)
    sp, report = _synth_evidence(tmp_path, live=live)
    rp = _write_report(tmp_path, report)
    _mock_cert_ok(monkeypatch)
    _mock_guarded_ok(monkeypatch, tmp_path)
    out = run_db_certified_final_output(
        phase14_report=rp,
        source_package=sp,
        work_root=tmp_path / "work",
        context_stamp=STAMP,
        live_db_path=live,
    )
    assert _content_sig(live) == before
    assert out["safety"]["live_db_written"] is False
    assert out["safety"]["live_db_read_only_verification"] is True


def test_source_package_not_mutated(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, report = _synth_evidence(tmp_path, live=live)
    before = _tree_sig(sp)
    rp = _write_report(tmp_path, report)
    _mock_cert_ok(monkeypatch)
    _mock_guarded_ok(monkeypatch, tmp_path)
    run_db_certified_final_output(
        phase14_report=rp,
        source_package=sp,
        work_root=tmp_path / "work",
        context_stamp=STAMP,
        live_db_path=live,
    )
    assert _tree_sig(sp) == before


def test_no_production_default_flags_changed(tmp_path, monkeypatch):
    report = _happy(tmp_path, monkeypatch)
    s = report["safety"]
    assert s["production_defaults_changed"] is False
    assert s["db_backed_reads_default_changed"] is False
    assert s["db_backed_package_resolution_default_changed"] is False
    assert s["source_files_mutated"] is False
    assert s["source_package_mutated"] is False
    assert s["true_live_execution_used"] is False
    assert s["output_root_only"] is True


def test_report_deterministic(tmp_path, monkeypatch):
    report = _happy(tmp_path, monkeypatch)
    raw = Path(report["report_path"]).read_text(encoding="utf-8")
    loaded = json.loads(raw)
    assert raw == json.dumps(loaded, indent=2, sort_keys=True) + "\n"
    for block in (
        "live_db_verification",
        "phase14_evidence",
        "controlled_chain",
        "final_outputs",
        "comparison",
        "csv_generation",
        "safety",
    ):
        assert block in loaded


# --- CSV controlled refusal -----------------------------------------------------------


def test_generate_final_csv_refused_not_ready(tmp_path, monkeypatch):
    report = _happy(tmp_path, monkeypatch, generate_final_csv=True)
    assert report["status"] == "not_ready"
    assert report["decision"] == "not_ready"
    assert report["csv_generation"]["requested"] is True
    assert report["csv_generation"]["decision"] == "out_of_scope"
    assert "forecast_comprehensive" in report["csv_generation"]["blocker"]
    assert report["safety"]["final_integrated_csv_generated"] is False
    assert report["final_outputs"]["package_paths"] == []


# --- guarded not-ready outcome (rc 1, not a refusal) ----------------------------------


def test_guarded_not_ready_is_not_ready(tmp_path, monkeypatch):
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, report = _synth_evidence(tmp_path, live=live)
    rp = _write_report(tmp_path, report)
    _mock_cert_ok(monkeypatch)
    monkeypatch.setattr(
        gormod,
        "run_guarded_db_operator_run",
        lambda **kw: {"status": "not_ready", "decision": "not_ready", "report_path": "x"},
    )
    out = run_db_certified_final_output(
        phase14_report=rp,
        source_package=sp,
        work_root=tmp_path / "work",
        context_stamp=STAMP,
        live_db_path=live,
    )
    assert out["decision"] == "not_ready"
    assert out["final_outputs"]["package_paths"] == []


# --- 21-23. CLI -----------------------------------------------------------------------


def _cli_args(tmp_path, live, sp, rp, *extra):
    return [
        "db-certified-final-output",
        "--project",
        "tropical",
        "--phase14-report",
        str(rp),
        "--source-package",
        str(sp),
        "--work-root",
        str(tmp_path / "work"),
        "--context-stamp",
        STAMP,
        "--live-db-path",
        str(live),
        *extra,
    ]


def test_cli_success_rc0(tmp_path, monkeypatch, capsys):
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, report = _synth_evidence(tmp_path, live=live)
    rp = _write_report(tmp_path, report)
    _mock_cert_ok(monkeypatch)
    _mock_guarded_ok(monkeypatch, tmp_path)
    rc = cli.main(_cli_args(tmp_path, live, sp, rp))
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["decision"] == DECISION_READY


def test_cli_not_ready_rc1_csv(tmp_path, monkeypatch, capsys):
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, report = _synth_evidence(tmp_path, live=live)
    rp = _write_report(tmp_path, report)
    _mock_cert_ok(monkeypatch)
    rc = cli.main(_cli_args(tmp_path, live, sp, rp, "--generate-final-csv"))
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["decision"] == "not_ready"


def test_cli_refusal_rc3(tmp_path, monkeypatch, capsys):
    live = tmp_path / "live" / "hb.sqlite"
    _flag_live(monkeypatch, live)
    sp, _ = _synth_evidence(tmp_path, live=live)
    rc = cli.main(_cli_args(tmp_path, live, sp, tmp_path / "missing.json"))
    assert rc == 3
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_existing_cli_commands_still_route():
    parser = cli.build_parser()
    for cmd in ("run-context", "run-analysis"):
        assert parser.parse_args([cmd, "--project", "tropical"]).command == cmd
    dfo = parser.parse_args(
        [
            "db-certified-final-output",
            "--project",
            "tropical",
            "--phase14-report",
            "/r.json",
            "--source-package",
            "/x",
            "--work-root",
            "/y",
            "--context-stamp",
            "s",
            "--generate-final-csv",
        ]
    )
    assert dfo.command == "db-certified-final-output"
    assert dfo.generate_final_csv is True
    # Phase 14 command unchanged.
    assert (
        parser.parse_args(
            [
                "live-db-source-domain-project",
                "--project",
                "tropical",
                "--source-package",
                "/x",
                "--work-root",
                "/y",
                "--context-stamp",
                "s",
                "--allow-live-db-write",
            ]
        ).command
        == "live-db-source-domain-project"
    )


# --- real end-to-end integration (real Phase 14 evidence + real chain) ----------------


def _checkpoint(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def test_real_chain_end_to_end(tmp_path, monkeypatch):
    """Build real Phase 14 evidence against a synthetic live DB, then run Phase 15 for real."""
    sp = _source_package(tmp_path / "src")
    live = tmp_path / "live" / "hb.sqlite"
    live.parent.mkdir(parents=True)
    SQLiteMigrator(db_path=str(live)).apply()
    _checkpoint(live)
    _flag_live(monkeypatch, live)

    p14 = projmod.run_controlled_live_db_source_domain_projection(
        source_package=sp,
        work_root=tmp_path / "phase14",
        context_stamp=STAMP,
        live_db_path=live,
        allow_live_db_write=True,
        run_guarded_operator_check=True,
    )
    assert p14["decision"] == "live_db_source_domain_certified"
    p14_report = Path(p14["report_path"])

    out = run_db_certified_final_output(
        phase14_report=p14_report,
        source_package=sp,
        work_root=tmp_path / "phase15",
        context_stamp=STAMP,
        live_db_path=live,
    )
    assert out["status"] == "ready"
    assert out["decision"] == DECISION_READY
    assert out["live_db_verification"]["table_counts"] == {
        "forecast_budget_details": 1,
        "forecast_cost_entries": 2,
        "forecast_monthly_actuals_by_budget_code": 2,
    }
    pkg = Path(out["final_outputs"]["package_paths"][0])
    assert pkg.is_dir()
    assert pkg.resolve().is_relative_to((tmp_path / "phase15").resolve())
    assert out["final_outputs"]["sha256"]  # at least one hashed file
    assert out["controlled_chain"]["guarded_decision"] == (
        "approved_for_guarded_db_context_analysis_use"
    )


# --- duplicated synthetic source fixture (mirrors Phase 11/12/13/14 build_fixture) -----


def _wj(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _wjson(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def build_fixture(root: Path) -> Path:
    """Minimal-valid synthetic source packages: one budget code through every dependency."""
    twn = root / "twn_cost_forecast_json_package"
    owner = root / "owner_pay_app_json_package"
    proc = root / PROCORE_DIRNAME
    _wj(
        twn / "data" / "budget_details.jsonl",
        [
            {
                "source_sheet": "BudgetDetails",
                "source_row": 2,
                "budget_code_key": BCK,
                "extra": "0000",
                "sub_job": {"raw": "0000 - X", "code": "0000", "description": "X"},
                "cost_code": "03-01-025",
                "cost_code_tiers": {
                    "tier_1": {"raw": "03 - EST", "code": "03", "description": "EST"},
                    "tier_2": {"raw": "03-01 - GC", "code": "03-01", "description": "GC"},
                    "tier_3": {"raw": "03-01-025 - PCE", "code": "03-01-025", "description": "PCE"},
                },
                "category": "MAT",
                "cost_type": {"raw": "MAT - Materials", "code": "MAT", "description": "Materials"},
                "budget_code_description": "X.PCE.Materials",
                "amounts": {
                    "original_budget_amount": 0.0,
                    "budget_modifications": 1000.0,
                    "approved_cos": 0.0,
                    "revised_budget": 1000.0,
                    "pending_budget_changes": 0.0,
                    "projected_budget": 1000.0,
                    "committed_costs": 0.0,
                    "commitment_invoiced": 0.0,
                    "erp_direct_costs": 500.0,
                    "erp_job_to_date_costs": 500.0,
                    "pending_cost_changes": 0.0,
                    "projected_costs": 500.0,
                    "estimated_cost_at_completion": 500.0,
                    "forecast_to_complete": 0.0,
                    "projected_over_under": 500.0,
                    "costentries_total_amount": 500.0,
                    "costentries_entry_count": 2,
                },
                "notes": None,
                "costentries_match_status": "Matched",
            }
        ],
    )
    _wj(
        twn / "data" / "cost_entries.jsonl",
        [
            {
                "source_sheet": "CostEntries",
                "source_row": 2,
                "job": "23-435-01",
                "job_description": "TWN",
                "job2": "23-435-01",
                "extra": "0000",
                "cost_code": "03-01-025",
                "category": "MAT",
                "tran_type": "AP cost",
                "accounting_date": "2024-06-30",
                "accounting_month": "2024-06",
                "amount": 300.0,
                "description": None,
                "application_of_origin": "AP",
                "budget_code_key": BCK,
            },
            {
                "source_sheet": "CostEntries",
                "source_row": 3,
                "job": "23-435-01",
                "job_description": "TWN",
                "job2": "23-435-01",
                "extra": "0000",
                "cost_code": "03-01-025",
                "category": "MAT",
                "tran_type": "AP cost",
                "accounting_date": "2026-06-05",
                "accounting_month": "2026-06",
                "amount": 200.0,
                "description": None,
                "application_of_origin": "AP",
                "budget_code_key": BCK,
            },
        ],
    )
    _wj(
        twn / "data" / "monthly_actuals_by_budget_code.jsonl",
        [
            {
                "budget_code_key": BCK,
                "month": "2024-06",
                "type": "actual",
                "amount": 300.0,
                "entry_count": 1,
                "job": "23-435-01",
                "extra": "0000",
                "cost_code": "03-01-025",
                "category": "MAT",
                "first_accounting_date": "2024-06-30",
                "last_accounting_date": "2024-06-30",
                "source": "CostEntries",
            },
            {
                "budget_code_key": BCK,
                "month": "2026-06",
                "type": "actual",
                "amount": 200.0,
                "entry_count": 1,
                "job": "23-435-01",
                "extra": "0000",
                "cost_code": "03-01-025",
                "category": "MAT",
                "first_accounting_date": "2026-06-05",
                "last_accounting_date": "2026-06-05",
                "source": "CostEntries",
            },
        ],
    )
    _wjson(twn / "validation_report.json", {"status": "ok", "checks": []})
    _wjson(twn / "manifest.json", {"package_name": "twn_cost_forecast_json_package"})
    _wj(
        owner / "owner_pay_app_line_items.jsonl",
        [
            {
                "source_workbook": "TWN-Owner-Pay-Apps.xlsx",
                "source_sheet": "App 1",
                "source_row": 5,
                "sheet_index": 0,
                "application_no": 1,
                "application_date": "2026-05-31",
                "period_to": "2026-05-31",
                "contractor_project_no": "23-435-01",
                "row_type": "line_item",
                "item": "1",
                "owner_sov_code": "03-01-025",
                "cost_code": "03-01-025",
                "description_of_work": "GC",
                "candidate_budget_code_keys": [BCK],
                "validation_flags": [],
                "scheduled_value": 1000.0,
                "current_value": 1000.0,
                "work_completed": {
                    "from_previous_application": 0.0,
                    "this_period": 500.0,
                    "materials_presently_stored": 0.0,
                    "total_completed_and_stored_to_date": 500.0,
                    "percent_complete": 50.0,
                    "balance_to_finish": 500.0,
                },
                "retainage": {"retainage_current_or_reduced": 50.0},
            }
        ],
    )
    _wj(
        owner / "owner_pay_app_totals.jsonl",
        [
            {
                "source_workbook": "TWN-Owner-Pay-Apps.xlsx",
                "source_sheet": "App 1",
                "source_row": 20,
                "sheet_index": 0,
                "application_no": 1,
                "period_to": "2026-05-31",
                "row_type": "grand_total",
                "description_of_work": "GRAND TOTAL",
                "cost_code": None,
                "scheduled_value": 1000.0,
                "current_value": 1000.0,
                "work_completed": {
                    "this_period": 500.0,
                    "total_completed_and_stored_to_date": 500.0,
                },
                "retainage": {"retainage_current_or_reduced": 50.0},
            }
        ],
    )
    _wjson(owner / "owner_pay_app_validation_report.json", {"status": "ok"})
    _wjson(owner / "owner_pay_app_sheet_manifest.json", {"sheets": []})
    _wj(
        proc / "procore_subcontractor_payment_app_headers.jsonl",
        [
            {
                "record_key": "h1",
                "period_end": "2026-05-31",
                "billing_date": "2026-05-31",
                "submitted_at": "2026-05-31",
                "updated_at_utc": "2026-05-31T00:00:00Z",
            }
        ],
    )
    _wj(
        proc / "procore_subcontractor_payment_app_line_items.jsonl",
        [
            {
                "invoice_item_key": "li1",
                "wbs_flat_code": BCK,
                "period_end": "2026-05-31",
                "vendor_entity_key": "v1",
                "commitment_id": "c1",
                "scheduled_value": 1000.0,
                "work_completed_this_period": 500.0,
                "materials_presently_stored": 0.0,
                "total_completed_and_stored_to_date": 500.0,
                "retainage_held": 50.0,
                "subcontractor_claimed_amount": 500.0,
                "invoice_record_key": "h1",
            }
        ],
    )
    _wj(
        proc / "procore_latest_subcontractor_invoice_by_vendor_cost_code.jsonl",
        [
            {
                "source_invoice_item_key": "li1",
                "wbs_flat_code": BCK,
                "vendor_entity_key": "v1",
                "commitment_id": "c1",
                "latest_period_end": "2026-05-31",
                "latest_scheduled_value": 1000.0,
                "latest_work_completed_this_period": 500.0,
                "latest_materials_presently_stored": 0.0,
                "latest_total_completed_and_stored_to_date": 500.0,
                "latest_retainage_held": 50.0,
            }
        ],
    )
    _wj(
        proc / "procore_commitments.jsonl",
        [
            {
                "contract_id": "c1",
                "record_key": "c1",
                "number": "SC-001",
                "status": "Approved",
                "contract_family": "03-01",
                "contract_type": "Subcontract",
                "executed": True,
                "vendor_entity_key": "v1",
                "company_entity_key": "co1",
                "grand_total": 1000.0,
                "original_contract_sum": 1000.0,
                "revised_contract_sum": 1000.0,
                "approved_change_orders_amount": 0.0,
                "pending_change_orders_amount": 0.0,
                "retainage_percent": 5.0,
                "contract_date": "2026-01-01",
                "start_date": "2026-01-01",
                "completion_date": "2026-12-31",
                "updated_at_utc": "2026-05-31T00:00:00Z",
            }
        ],
    )
    _wj(
        proc / "procore_payapp_amount_facts_through_may_2026.jsonl",
        [{"period_end": "2026-05-31", "period_start": "2026-05-01"}],
    )
    _wjson(
        proc / "forecast_mapping_template.json",
        [
            {
                "procore_wbs_flat_code": BCK,
                "procore_commitment_id": "c1",
                "procore_vendor_entity_key": "v1",
            }
        ],
    )
    _wjson(proc / "procore_db_export_validation_report.json", {"status": "ok"})
    return root
