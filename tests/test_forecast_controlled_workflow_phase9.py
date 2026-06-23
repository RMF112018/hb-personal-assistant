"""Phase 9 — controlled DB-backed context->analysis workflow (orchestration only).

Proves the single explicit operation that chains the proven Phase 6 context runner, Phase 7 analysis
runner, and Phase 8 package resolution into one auditable run under an explicit work root: file mode,
DB mode (temp v59 DB), and parity mode (run both + compare). Also proves the additive
``controlled-context-analysis`` CLI and that Phase 9 changes no existing command/default.

Everything runs under ``tmp_path`` with a temp SQLite DB only; never the live Synology root or the
live/default DB. build_fixture / _wj / _wjson / _project_db MIRROR the Phase 6/8 tests (duplicated,
not imported, so the proven earlier phases stay independent).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# hb_assistant is used ONLY to build a temp v59 DB for the DB/parity-mode tests (mirrors Phase 6).
from hb_assistant.construction.forecast import source_domain_engine as dbeng
from hb_assistant.store.migrator import SQLiteMigrator

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review.common import package_resolution as pr  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    controlled_db_context_analysis as wf,
)
from construction_financial_review.workflows.controlled_db_context_analysis import (  # noqa: E402
    ControlledWorkflowError,
    run_controlled_context_analysis_parity,
    run_controlled_context_analysis_workflow,
)

BCK = "0000.03-01-025.MAT"  # mirrors Phase 5/6/7/8
PROCORE_DIRNAME = "cost_forecast_agent_db_json_export_tropical_20260614_080344"
STAMP = "20260101_000000"


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


# --- 1. file-backed controlled workflow -------------------------------------------------


def test_file_backed_workflow_succeeds(tmp_path):
    src = build_fixture(tmp_path / "src")
    work = tmp_path / "work"
    report = run_controlled_context_analysis_workflow(
        data_root=src, work_root=work, context_stamp=STAMP, mode="file"
    )
    assert report["status"] == "ok"
    assert report["mode"] == "file" and report["db_backed"] is False
    assert report["db_path"] is None
    ctx = Path(report["context_package"])
    an = Path(report["analysis_package"])
    assert ctx.is_dir() and an.is_dir()
    assert str(ctx).startswith(str(work / "file"))
    assert str(an).startswith(str(work / "file"))
    assert (an / "forecast_recommendations_by_budget_code.jsonl").is_file()
    assert Path(report["chain_manifest"]).is_file()
    assert Path(report["report_path"]).is_file()
    # the produced chain manifest round-trips through the Phase 8 reader
    chain = pr.read_package_chain_manifest(Path(report["chain_manifest"]))
    assert set(chain.packages) == {"context", "analysis"}


# --- 2. DB-backed controlled workflow (temp v59 DB) -------------------------------------


def test_db_backed_workflow_succeeds(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    work = tmp_path / "work"
    report = run_controlled_context_analysis_workflow(
        data_root=src, work_root=work, context_stamp=STAMP, mode="db", db_path=db
    )
    assert report["status"] == "ok"
    assert report["mode"] == "db" and report["db_backed"] is True
    assert report["db_path"] == str(db)
    assert str(Path(report["context_package"])).startswith(str(work / "db"))
    assert Path(report["analysis_package"], "validation_report.json").is_file()
    assert Path(report["chain_manifest"]).is_file()


# --- 3. deterministic chain manifest ----------------------------------------------------


def test_chain_manifest_is_deterministic(tmp_path):
    src = build_fixture(tmp_path / "src")
    report = run_controlled_context_analysis_workflow(
        data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, mode="file"
    )
    produced = Path(report["chain_manifest"])
    # Deterministic: re-resolving the same packages + re-writing yields byte-identical output.
    ctx_ref = pr.resolve_explicit_package(
        package_kind="context", package_path=Path(report["context_package"])
    )
    an_ref = pr.resolve_explicit_package(
        package_kind="analysis", package_path=Path(report["analysis_package"])
    )
    chain = pr.build_package_chain(
        project_key="tropical",
        data_root=Path(report["context_package"]).parent,
        refs=[ctx_ref, an_ref],
    )
    rewritten = pr.write_package_chain_manifest(chain=chain, out_path=tmp_path / "again.json")
    assert produced.read_bytes() == rewritten.read_bytes()
    assert produced.read_text(encoding="utf-8").endswith("}\n")


# --- 4. deterministic operator report ---------------------------------------------------


def test_report_is_deterministic_sorted_key_no_wallclock(tmp_path):
    src = build_fixture(tmp_path / "src")
    report = run_controlled_context_analysis_workflow(
        data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, mode="file"
    )
    raw = Path(report["report_path"]).read_text(encoding="utf-8")
    loaded = json.loads(raw)
    # The on-disk report is sorted-key, indented, trailing-newline (deterministic format).
    assert raw == json.dumps(loaded, indent=2, sort_keys=True) + "\n"
    # Phase 9 adds no wall-clock field of its own. The only volatile value is the generator-assigned
    # analysis stamp embedded in analysis_package (a known downstream volatile, normalized in parity).
    astamp = Path(loaded["analysis_package"]).name[len("forecast_analysis_package_tropical_") :]
    assert astamp, "analysis package should carry a generator-assigned stamp"


# --- 5. report key coverage -------------------------------------------------------------


def test_report_includes_required_keys(tmp_path):
    src = build_fixture(tmp_path / "src")
    report = run_controlled_context_analysis_workflow(
        data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, mode="file"
    )
    for key in (
        "schema_version",
        "project_key",
        "mode",
        "data_root",
        "work_root",
        "context_stamp",
        "db_backed",
        "db_path",
        "context_package",
        "analysis_package",
        "chain_manifest",
        "safety_checks",
        "status",
    ):
        assert key in report, f"missing report key: {key}"
    assert report["project_key"] == "tropical"
    assert report["schema_version"] == 1


# --- 6-11. fail-closed guards -----------------------------------------------------------


def test_refuses_unsupported_project(tmp_path):
    src = build_fixture(tmp_path / "src")
    with pytest.raises(ControlledWorkflowError, match="not eligible"):
        run_controlled_context_analysis_workflow(
            data_root=src,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            mode="file",
            project_key="not-tropical",
        )


def test_refuses_missing_data_root(tmp_path):
    with pytest.raises(ControlledWorkflowError, match="data_root not found"):
        run_controlled_context_analysis_workflow(
            data_root=tmp_path / "nope",
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            mode="file",
        )


def test_refuses_live_root_work_root(tmp_path, monkeypatch):
    fake_live = tmp_path / "fake_live"
    monkeypatch.setattr(wf, "_LIVE_ROOT", fake_live)
    src = build_fixture(tmp_path / "src")
    with pytest.raises(ControlledWorkflowError, match="live forecast root"):
        run_controlled_context_analysis_workflow(
            data_root=src, work_root=fake_live / "work", context_stamp=STAMP, mode="file"
        )


def test_refuses_invalid_mode(tmp_path):
    src = build_fixture(tmp_path / "src")
    with pytest.raises(ControlledWorkflowError, match="unsupported mode"):
        run_controlled_context_analysis_workflow(
            data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, mode="comprehensive"
        )


def test_db_mode_without_db_path_fails_closed(tmp_path):
    src = build_fixture(tmp_path / "src")
    with pytest.raises(ControlledWorkflowError, match="requires an explicit db_path"):
        run_controlled_context_analysis_workflow(
            data_root=src,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            mode="db",
            db_path=None,
        )


def test_file_mode_rejects_db_path(tmp_path):
    # Approved explicit contract: file mode with a db_path is ambiguous and fails closed.
    src = build_fixture(tmp_path / "src")
    with pytest.raises(ControlledWorkflowError, match="must not be given a db_path"):
        run_controlled_context_analysis_workflow(
            data_root=src,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            mode="file",
            db_path=tmp_path / "x.sqlite",
        )


def test_empty_context_stamp_fails_closed(tmp_path):
    src = build_fixture(tmp_path / "src")
    with pytest.raises(ControlledWorkflowError, match="context_stamp is required"):
        run_controlled_context_analysis_workflow(
            data_root=src, work_root=tmp_path / "work", context_stamp="", mode="file"
        )


# --- 12 & 13. parity mode ---------------------------------------------------------------


def test_parity_mode_file_vs_db_match(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    parity = run_controlled_context_analysis_parity(
        data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, db_path=db
    )
    assert parity["status"] == "pass"
    assert parity["context_comparison"]["match"] is True
    assert parity["analysis_comparison"]["match"] is True
    assert parity["chain_comparison"]["match"] is True
    assert parity["context_comparison"]["files_compared"] > 0
    # both per-mode reports were written
    assert Path(parity["file_report"]).is_file()
    assert Path(parity["db_report"]).is_file()
    # parity report written deterministically
    assert Path(parity["parity_report_path"]).is_file()
    raw = Path(parity["parity_report_path"]).read_text(encoding="utf-8")
    assert raw == json.dumps(json.loads(raw), indent=2, sort_keys=True) + "\n"


def test_parity_normalizes_bare_analysis_generated_stamp(tmp_path):
    """Regression (found in Phase 11): the analysis README.md / forecast_review_summary.md embed the
    generator's wall-clock stamp as PLAIN TEXT (``generated <stamp>``), not only inside the package
    dir name. When the file-mode and db-mode analysis subprocesses straddle a 1-second boundary those
    bare stamps differ; the parity normalizer must neutralize them so parity does not flake on a
    timestamp-only difference. Two analysis-like packages identical except their bare stamp must
    compare equal."""

    def _make(mode: str, stamp: str) -> Path:
        pkg = tmp_path / mode / f"forecast_analysis_package_tropical_{stamp}"
        pkg.mkdir(parents=True)
        (pkg / "manifest.json").write_text(
            json.dumps({"package_name": pkg.name, "generated_stamp": stamp}), encoding="utf-8"
        )
        (pkg / "validation_report.json").write_text(json.dumps({"passed": True}), encoding="utf-8")
        (pkg / "forecast_recommendations_by_budget_code.jsonl").write_text(
            json.dumps({"budget_code_key": BCK}) + "\n", encoding="utf-8"
        )
        # Bare wall-clock stamp + output-path line, exactly like the real analysis markdown.
        (pkg / "README.md").write_text(
            f"- Output analysis package: `{pkg}`\n- generated `{stamp}`\n", encoding="utf-8"
        )
        return pkg

    a = _make("file", "20260618_074103")
    b = _make("db", "20260618_074104")  # one second later
    cmp = wf._compare_packages(a, b)
    assert cmp["match"] is True, cmp


# --- 14-17. CLI -------------------------------------------------------------------------


def test_cli_file_mode_succeeds(tmp_path, capsys):
    src = build_fixture(tmp_path / "src")
    rc = cli.main(
        [
            "controlled-context-analysis",
            "--project",
            "tropical",
            "--data-root",
            str(src),
            "--work-root",
            str(tmp_path / "work"),
            "--context-stamp",
            STAMP,
            "--mode",
            "file",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "controlled-context-analysis"
    assert payload["status"] == "ok" and payload["mode"] == "file"
    assert Path(payload["chain_manifest"]).is_file()


def test_cli_db_mode_succeeds(tmp_path, capsys):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    rc = cli.main(
        [
            "controlled-context-analysis",
            "--project",
            "tropical",
            "--data-root",
            str(src),
            "--work-root",
            str(tmp_path / "work"),
            "--context-stamp",
            STAMP,
            "--mode",
            "db",
            "--db-path",
            str(db),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok" and payload["mode"] == "db" and payload["db_backed"] is True


def test_cli_parity_mode_succeeds(tmp_path, capsys):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    rc = cli.main(
        [
            "controlled-context-analysis",
            "--project",
            "tropical",
            "--data-root",
            str(src),
            "--work-root",
            str(tmp_path / "work"),
            "--context-stamp",
            STAMP,
            "--mode",
            "parity",
            "--db-path",
            str(db),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "controlled-context-analysis"
    assert payload["status"] == "pass"
    assert payload["context_comparison"]["match"] is True


def test_cli_db_mode_without_db_path_refused(tmp_path, capsys):
    src = build_fixture(tmp_path / "src")
    rc = cli.main(
        [
            "controlled-context-analysis",
            "--project",
            "tropical",
            "--data-root",
            str(src),
            "--work-root",
            str(tmp_path / "work"),
            "--context-stamp",
            STAMP,
            "--mode",
            "db",
        ]
    )
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "refused" and "db_path" in payload["reason"]


# --- 18. existing defaults preserved ----------------------------------------------------


def test_existing_cli_commands_still_route():
    parser = cli.build_parser()
    for cmd in ("run-context", "run-analysis"):
        assert parser.parse_args([cmd, "--project", "tropical"]).command == cmd
    cg = parser.parse_args(
        [
            "context-generate",
            "--project",
            "tropical",
            "--data-root",
            "/x",
            "--out-dir",
            "/y",
            "--stamp",
            "s",
        ]
    )
    assert cg.command == "context-generate"
    pcm = parser.parse_args(
        [
            "package-chain-manifest",
            "--project",
            "tropical",
            "--context-package",
            "/x",
            "--analysis-package",
            "/y",
            "--out",
            "/z",
        ]
    )
    assert pcm.command == "package-chain-manifest"
    cca = parser.parse_args(
        [
            "controlled-context-analysis",
            "--project",
            "tropical",
            "--data-root",
            "/x",
            "--work-root",
            "/y",
            "--context-stamp",
            "s",
            "--mode",
            "file",
        ]
    )
    assert cca.command == "controlled-context-analysis" and cca.mode == "file"


# --- temp v59 DB projection (mirrors Phase 6) -------------------------------------------


def _project_db(root: Path, db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    rec = dbeng.project_source_domain(
        source_package=root / "twn_cost_forecast_json_package",
        project_key="tropical",
        db_path=db,
        apply=True,
    )
    assert rec["ok"] is True


# --- duplicated synthetic source fixture (mirrors Phase 5/6/7/8 build_fixture) ----------


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
