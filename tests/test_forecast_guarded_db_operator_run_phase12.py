"""Phase 12 — controlled guarded DB operator-run package (operator handoff).

Proves the operator handoff: explicit Tropical source package → Phase 11 rehearsal → nested Phase 10
readiness + Phase 9 DB-mode report → validated DB-backed artifacts → deterministic guarded operator-run
manifest. Success / determinism / evidence / approved-artifact / counts tests run the REAL Phase 11
chain end-to-end (as Phase 11 tests run real Phase 10); refusal / corruption / not-ready tests
monkeypatch the rehearsal to return crafted evidence so Phase 12's own validation is exercised in
isolation. Nothing writes the live DB or live root; everything runs under ``tmp_path``.

build_fixture / _wj / _wjson MIRROR the Phase 9/10/11 tests (duplicated, not imported, so the proven
earlier phases stay independent).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# hb_assistant is imported by the rehearsal's lazy DB-prep path; the live-DB test monkeypatches it.
from hb_assistant.construction.forecast import source_domain_engine as dbeng

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review.common.package_resolution import (  # noqa: E402
    ForecastPackageRef,
    build_package_chain,
    write_package_chain_manifest,
)
from construction_financial_review.workflows import (  # noqa: E402
    guarded_db_operator_run as guarded,
)
from construction_financial_review.workflows.guarded_db_operator_run import (  # noqa: E402
    GuardedDbOperatorRunError,
    run_guarded_db_operator_run,
)

BCK = "0000.03-01-025.MAT"  # mirrors Phase 5/6/7/8/9/10/11
PROCORE_DIRNAME = "cost_forecast_agent_db_json_export_tropical_20260614_080344"
STAMP = "20260101_000000"
REQUIRED_TABLES = (
    "forecast_budget_details",
    "forecast_cost_entries",
    "forecast_monthly_actuals_by_budget_code",
)


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


def _source_package(tmp_path: Path) -> Path:
    return build_fixture(tmp_path / "src") / "twn_cost_forecast_json_package"


# --- 1 & 2. success: derived + explicit temp DB path (REAL chain) ----------------------


def test_operator_run_succeeds_derived_db(tmp_path):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    report = run_guarded_db_operator_run(source_package=sp, work_root=work, context_stamp=STAMP)
    assert report["status"] == "ready"
    assert report["decision"] == "approved_for_guarded_db_context_analysis_use"
    assert report["data_root"] == str(sp.parent)
    assert report["temp_db"]["path"] == str(
        work / "temp_dbs" / "forecast_source_domain_tropical.sqlite"
    )
    assert report["temp_db"]["schema_version"] == 61  # Phase 4: migrator now at v61 (synthetic temp DB)
    assert Path(report["report_path"]).is_file()


def test_operator_run_succeeds_explicit_db_under_work_root(tmp_path):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    db = work / "temp_dbs" / "explicit.sqlite"
    report = run_guarded_db_operator_run(
        source_package=sp, work_root=work, context_stamp=STAMP, db_path=db
    )
    assert report["status"] == "ready"
    assert report["temp_db"]["path"] == str(db)
    assert Path(db).is_file()


# --- 3-6. deterministic manifest + evidence + approved artifacts + counts ---------------


def test_manifest_is_deterministic(tmp_path):
    sp = _source_package(tmp_path)
    report = run_guarded_db_operator_run(
        source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP
    )
    raw = Path(report["report_path"]).read_text(encoding="utf-8")
    loaded = json.loads(raw)
    assert raw == json.dumps(loaded, indent=2, sort_keys=True) + "\n"
    assert loaded["schema_version"] == 1


def test_manifest_includes_evidence_chain(tmp_path):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    report = run_guarded_db_operator_run(source_package=sp, work_root=work, context_stamp=STAMP)
    ev = report["evidence"]
    for key in (
        "phase11_rehearsal_report",
        "phase10_readiness_report",
        "phase9_db_report",
        "db_chain_manifest",
    ):
        assert Path(ev[key]).is_file(), key


def test_manifest_includes_approved_artifacts(tmp_path):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    report = run_guarded_db_operator_run(source_package=sp, work_root=work, context_stamp=STAMP)
    art = report["approved_artifacts"]
    assert Path(art["context_package"]).is_dir()
    assert Path(art["analysis_package"]).is_dir()
    assert Path(art["chain_manifest"]).is_file()
    # every approved artifact resolves under the explicit work root
    for p in art.values():
        assert guarded._is_under(Path(p), work)


def test_manifest_includes_source_domain_counts(tmp_path):
    sp = _source_package(tmp_path)
    report = run_guarded_db_operator_run(
        source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP
    )
    counts = report["source_domain_counts"]
    assert set(counts) == set(REQUIRED_TABLES)
    assert all(counts[t] > 0 for t in REQUIRED_TABLES)
    assert report["safety"] == {
        "production_defaults_changed": False,
        "live_db_written": False,
        "live_root_written": False,
        "final_integrated_csv_generated": False,
    }


# --- 7-13. lightweight preflight fail-closed guards ------------------------------------


def test_refuses_unsupported_project(tmp_path):
    sp = _source_package(tmp_path)
    with pytest.raises(GuardedDbOperatorRunError, match="unsupported project_key"):
        run_guarded_db_operator_run(
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            project_key="not-tropical",
        )


def test_refuses_missing_source_package(tmp_path):
    sp = tmp_path / "src" / "twn_cost_forecast_json_package"  # never built
    with pytest.raises(GuardedDbOperatorRunError, match="source_package not found"):
        run_guarded_db_operator_run(
            source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP
        )


def test_refuses_empty_context_stamp(tmp_path):
    sp = _source_package(tmp_path)
    with pytest.raises(GuardedDbOperatorRunError, match="context_stamp is required"):
        run_guarded_db_operator_run(
            source_package=sp, work_root=tmp_path / "work", context_stamp=""
        )


def test_refuses_live_root_work_root(tmp_path, monkeypatch):
    fake_live = tmp_path / "fake_live"
    monkeypatch.setattr(guarded, "_LIVE_ROOT", fake_live)
    sp = _source_package(tmp_path)
    with pytest.raises(GuardedDbOperatorRunError, match="live forecast root"):
        run_guarded_db_operator_run(
            source_package=sp, work_root=fake_live / "work", context_stamp=STAMP
        )


def test_refuses_db_path_outside_work_root(tmp_path):
    sp = _source_package(tmp_path)
    outside = tmp_path / "outside.sqlite"
    with pytest.raises(GuardedDbOperatorRunError, match="must be under work_root"):
        run_guarded_db_operator_run(
            source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP, db_path=outside
        )


def test_refuses_live_db_path(tmp_path, monkeypatch):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    db = work / "temp_dbs" / "x.sqlite"
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: True)
    with pytest.raises(GuardedDbOperatorRunError, match="live/default DB"):
        run_guarded_db_operator_run(
            source_package=sp, work_root=work, context_stamp=STAMP, db_path=db
        )


def test_refuses_preexisting_db_path_via_phase11(tmp_path):
    # Pre-existing-DB enforcement is delegated to Phase 11; its error is mapped to a Phase 12 refusal.
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    db = work / "temp_dbs" / "x.sqlite"
    db.parent.mkdir(parents=True)
    db.write_text("not really a db", encoding="utf-8")
    with pytest.raises(GuardedDbOperatorRunError, match="rehearsal refused"):
        run_guarded_db_operator_run(
            source_package=sp, work_root=work, context_stamp=STAMP, db_path=db
        )


# --- 14 & 15. not-ready outcome + rehearsal-raises mapping -----------------------------


def test_not_ready_yields_rc_evidence(tmp_path, monkeypatch):
    work = tmp_path / "work"

    def _fake(**kwargs):
        return {
            "status": "failed",
            "decision": "not_ready",
            "data_root": str(tmp_path / "src"),
            "report_path": str(work / "temp_db_readiness_rehearsal_report.json"),
        }

    monkeypatch.setattr(guarded, "run_temp_db_readiness_rehearsal", _fake)
    report = run_guarded_db_operator_run(
        source_package=_source_package(tmp_path), work_root=work, context_stamp=STAMP
    )
    assert report["status"] == "not_ready"
    assert report["decision"] == "not_ready"
    assert "approved_artifacts" not in report
    assert report["evidence"]["phase11_rehearsal_report"].endswith(
        "temp_db_readiness_rehearsal_report.json"
    )


def test_rehearsal_error_is_controlled_refusal(tmp_path, monkeypatch):
    from construction_financial_review.workflows.temp_db_readiness_rehearsal import (
        TempDbRehearsalError,
    )

    def _raise(**kwargs):
        raise TempDbRehearsalError("boom from phase 11")

    monkeypatch.setattr(guarded, "run_temp_db_readiness_rehearsal", _raise)
    with pytest.raises(GuardedDbOperatorRunError, match="rehearsal refused"):
        run_guarded_db_operator_run(
            source_package=_source_package(tmp_path),
            work_root=tmp_path / "work",
            context_stamp=STAMP,
        )


# --- 16-19. post-pass structural/provenance inconsistency -> controlled refusal --------


def _passed_rehearsal_dict(work: Path) -> dict:
    """A synthetic *passed* rehearsal return with a real on-disk evidence tree under ``work``."""
    work.mkdir(parents=True, exist_ok=True)
    readiness_dir = work / "readiness"
    dbdir = readiness_dir / "db"
    ctx = _make_pkg(dbdir, "context", STAMP)
    ana = _make_pkg(dbdir, "analysis", STAMP)
    chain = build_package_chain(
        project_key="tropical",
        data_root=work,
        refs=[
            ForecastPackageRef("tropical", "context", ctx, STAMP),
            ForecastPackageRef("tropical", "analysis", ana, STAMP),
        ],
    )
    chain_path = write_package_chain_manifest(
        chain=chain, out_path=dbdir / "forecast_package_chain_manifest.json"
    )
    phase9_path = dbdir / "controlled_workflow_report.json"
    phase9_path.write_text(
        json.dumps(
            {
                "mode": "db",
                "db_backed": True,
                "context_package": str(ctx),
                "analysis_package": str(ana),
                "chain_manifest": str(chain_path),
                "status": "ok",
                "report_path": str(phase9_path),
            }
        ),
        encoding="utf-8",
    )
    phase10_path = readiness_dir / "db_cutover_readiness_report.json"
    phase10_path.write_text(
        json.dumps(
            {
                "decision": "ready_for_guarded_operator_use",
                "status": "ready",
                "workflow": {"db_report": str(phase9_path)},
            }
        ),
        encoding="utf-8",
    )
    rehearsal_path = work / "temp_db_readiness_rehearsal_report.json"
    rehearsal_path.write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    return {
        "status": "passed",
        "decision": "ready_for_guarded_operator_use",
        "data_root": str(work.parent / "src"),
        "work_root": str(work),
        "context_stamp": STAMP,
        "db": {"path": str(work / "temp_dbs" / "x.sqlite"), "schema_version": 59},
        "projection": {"required_tables": {t: {"rows": 1} for t in REQUIRED_TABLES}},
        "readiness": {"report_path": str(phase10_path)},
        "report_path": str(rehearsal_path),
        "_phase9_path": str(phase9_path),  # test-only handle for mutation
        "_phase10_path": str(phase10_path),
    }


def test_synthetic_passed_evidence_is_approved(tmp_path, monkeypatch):
    # Sanity: the synthetic evidence tree itself produces an approved manifest.
    work = tmp_path / "work"
    rd = _passed_rehearsal_dict(work)
    monkeypatch.setattr(guarded, "run_temp_db_readiness_rehearsal", lambda **k: rd)
    report = run_guarded_db_operator_run(
        source_package=_source_package(tmp_path), work_root=work, context_stamp=STAMP
    )
    assert report["decision"] == "approved_for_guarded_db_context_analysis_use"


def test_refuses_when_phase10_report_missing(tmp_path, monkeypatch):
    work = tmp_path / "work"
    rd = _passed_rehearsal_dict(work)
    Path(rd["_phase10_path"]).unlink()
    monkeypatch.setattr(guarded, "run_temp_db_readiness_rehearsal", lambda **k: rd)
    with pytest.raises(GuardedDbOperatorRunError, match="Phase 10 readiness report not found"):
        run_guarded_db_operator_run(
            source_package=_source_package(tmp_path), work_root=work, context_stamp=STAMP
        )


def test_refuses_when_phase9_db_report_missing(tmp_path, monkeypatch):
    work = tmp_path / "work"
    rd = _passed_rehearsal_dict(work)
    Path(rd["_phase9_path"]).unlink()
    monkeypatch.setattr(guarded, "run_temp_db_readiness_rehearsal", lambda **k: rd)
    with pytest.raises(GuardedDbOperatorRunError, match="Phase 9 DB-mode report not found"):
        run_guarded_db_operator_run(
            source_package=_source_package(tmp_path), work_root=work, context_stamp=STAMP
        )


def test_refuses_when_not_db_mode(tmp_path, monkeypatch):
    work = tmp_path / "work"
    rd = _passed_rehearsal_dict(work)
    p9 = Path(rd["_phase9_path"])
    data = json.loads(p9.read_text())
    data["mode"] = "file"
    data["db_backed"] = False
    p9.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(guarded, "run_temp_db_readiness_rehearsal", lambda **k: rd)
    with pytest.raises(GuardedDbOperatorRunError, match="not a DB-mode report"):
        run_guarded_db_operator_run(
            source_package=_source_package(tmp_path), work_root=work, context_stamp=STAMP
        )


def test_refuses_when_artifact_path_escapes_work_root(tmp_path, monkeypatch):
    work = tmp_path / "work"
    rd = _passed_rehearsal_dict(work)
    p9 = Path(rd["_phase9_path"])
    data = json.loads(p9.read_text())
    escaped = tmp_path / "escaped_context"
    escaped.mkdir()
    data["context_package"] = str(escaped)
    p9.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(guarded, "run_temp_db_readiness_rehearsal", lambda **k: rd)
    with pytest.raises(GuardedDbOperatorRunError, match="outside the work root"):
        run_guarded_db_operator_run(
            source_package=_source_package(tmp_path), work_root=work, context_stamp=STAMP
        )


def test_refuses_when_chain_manifest_mismatches(tmp_path, monkeypatch):
    work = tmp_path / "work"
    rd = _passed_rehearsal_dict(work)
    # Point the DB report's context_package at a DIFFERENT (valid) package than the chain manifest.
    other = _make_pkg(work / "readiness" / "db", "context", "29991231_235959")
    p9 = Path(rd["_phase9_path"])
    data = json.loads(p9.read_text())
    data["context_package"] = str(other)
    p9.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(guarded, "run_temp_db_readiness_rehearsal", lambda **k: rd)
    with pytest.raises(GuardedDbOperatorRunError, match="does not match"):
        run_guarded_db_operator_run(
            source_package=_source_package(tmp_path), work_root=work, context_stamp=STAMP
        )


# --- 20-23. CLI ------------------------------------------------------------------------


def test_cli_success_derived_db(tmp_path, capsys):
    sp = _source_package(tmp_path)
    rc = cli.main(
        [
            "guarded-db-operator-run",
            "--project",
            "tropical",
            "--source-package",
            str(sp),
            "--work-root",
            str(tmp_path / "work"),
            "--context-stamp",
            STAMP,
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "guarded-db-operator-run"
    assert payload["decision"] == "approved_for_guarded_db_context_analysis_use"


def test_cli_success_explicit_db(tmp_path, capsys):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    db = work / "temp_dbs" / "explicit.sqlite"
    rc = cli.main(
        [
            "guarded-db-operator-run",
            "--project",
            "tropical",
            "--source-package",
            str(sp),
            "--work-root",
            str(work),
            "--context-stamp",
            STAMP,
            "--db-path",
            str(db),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ready" and payload["temp_db"]["path"] == str(db)


def test_cli_not_ready_returns_rc1(tmp_path, capsys, monkeypatch):
    work = tmp_path / "work"

    def _fake(**kwargs):
        return {
            "status": "failed",
            "decision": "not_ready",
            "data_root": str(tmp_path / "src"),
            "report_path": str(work / "temp_db_readiness_rehearsal_report.json"),
        }

    monkeypatch.setattr(guarded, "run_temp_db_readiness_rehearsal", _fake)
    rc = cli.main(
        [
            "guarded-db-operator-run",
            "--project",
            "tropical",
            "--source-package",
            str(_source_package(tmp_path)),
            "--work-root",
            str(work),
            "--context-stamp",
            STAMP,
        ]
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "not_ready" and payload["decision"] == "not_ready"


def test_cli_refusal_returns_rc3(tmp_path, capsys):
    sp = _source_package(tmp_path)
    outside = tmp_path / "outside.sqlite"
    rc = cli.main(
        [
            "guarded-db-operator-run",
            "--project",
            "tropical",
            "--source-package",
            str(sp),
            "--work-root",
            str(tmp_path / "work"),
            "--context-stamp",
            STAMP,
            "--db-path",
            str(outside),
        ]
    )
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "refused" and "must be under work_root" in payload["reason"]


# --- existing defaults preserved -------------------------------------------------------


def test_existing_cli_commands_still_route():
    parser = cli.build_parser()
    for cmd in ("run-context", "run-analysis"):
        assert parser.parse_args([cmd, "--project", "tropical"]).command == cmd
    tdr = parser.parse_args(
        [
            "temp-db-readiness-rehearsal",
            "--project",
            "tropical",
            "--source-package",
            "/x",
            "--work-root",
            "/y",
            "--context-stamp",
            "s",
        ]
    )
    assert tdr.command == "temp-db-readiness-rehearsal"
    gor = parser.parse_args(
        [
            "guarded-db-operator-run",
            "--project",
            "tropical",
            "--source-package",
            "/x",
            "--work-root",
            "/y",
            "--context-stamp",
            "s",
        ]
    )
    assert gor.command == "guarded-db-operator-run" and gor.db_path is None


# --- duplicated synthetic helpers (mirror Phase 5/6/7/8/9/10/11 build_fixture) ---------


def _make_pkg(parent: Path, kind: str, stamp: str) -> Path:
    """Build a structurally-valid synthetic context/analysis package directory."""
    prefix = {
        "context": "forecast_context_package_tropical_",
        "analysis": "forecast_analysis_package_tropical_",
    }[kind]
    d = parent / f"{prefix}{stamp}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text("{}", encoding="utf-8")
    (d / "validation_report.json").write_text("{}", encoding="utf-8")
    if kind == "context":
        (d / "canonical").mkdir()
        (d / "summaries").mkdir()
    else:
        (d / "forecast_recommendations_by_budget_code.jsonl").write_text("", encoding="utf-8")
    return d


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
