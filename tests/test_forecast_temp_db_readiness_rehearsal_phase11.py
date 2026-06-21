"""Phase 11 — controlled temp-DB preparation + readiness rehearsal (operator-safe).

Proves the rehearsal workflow: explicit Tropical source package → non-live temp v59 DB (migrate +
project) → Phase 10 readiness gate → deterministic rehearsal report. Covers the success paths
(derived + explicit temp DB), determinism, the fail-closed guard matrix, the not_ready/failed path,
and the additive CLI — without writing the live DB or live root.

Everything runs under ``tmp_path`` with a temp SQLite DB only. build_fixture / _wj / _wjson MIRROR
the Phase 9/10 tests (duplicated, not imported, so the proven earlier phases stay independent).
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
from construction_financial_review.workflows import (  # noqa: E402
    temp_db_readiness_rehearsal as rehearsal,
)
from construction_financial_review.workflows.temp_db_readiness_rehearsal import (  # noqa: E402
    TempDbRehearsalError,
    run_temp_db_readiness_rehearsal,
)

BCK = "0000.03-01-025.MAT"  # mirrors Phase 5/6/7/8/9/10
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


def _source_package(tmp_path: Path) -> Path:
    return build_fixture(tmp_path / "src") / "twn_cost_forecast_json_package"


# --- 1 & 2. success: derived + explicit temp DB path -----------------------------------


def test_rehearsal_succeeds_derived_db(tmp_path):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    report = run_temp_db_readiness_rehearsal(source_package=sp, work_root=work, context_stamp=STAMP)
    assert report["status"] == "passed"
    assert report["decision"] == "ready_for_guarded_operator_use"
    assert report["data_root"] == str(sp.parent)
    # derived DB path under <work>/temp_dbs/
    assert report["db"]["path"] == str(work / "temp_dbs" / "forecast_source_domain_tropical.sqlite")
    assert Path(report["db"]["path"]).is_file()
    assert report["db"]["schema_version"] == 61  # Phase 4: migrator now at v61 (synthetic temp DB)
    for t in (
        "forecast_budget_details",
        "forecast_cost_entries",
        "forecast_monthly_actuals_by_budget_code",
    ):
        assert report["projection"]["required_tables"][t]["rows"] > 0
    assert Path(report["readiness"]["report_path"]).is_file()
    assert Path(report["report_path"]).is_file()


def test_rehearsal_succeeds_explicit_db_under_work_root(tmp_path):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    db = work / "temp_dbs" / "explicit.sqlite"
    report = run_temp_db_readiness_rehearsal(
        source_package=sp, work_root=work, context_stamp=STAMP, db_path=db
    )
    assert report["status"] == "passed"
    assert report["db"]["path"] == str(db)
    assert Path(db).is_file()


# --- 3 & 4. deterministic report + content coverage ------------------------------------


def test_rehearsal_report_is_deterministic(tmp_path):
    sp = _source_package(tmp_path)
    report = run_temp_db_readiness_rehearsal(
        source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP
    )
    raw = Path(report["report_path"]).read_text(encoding="utf-8")
    loaded = json.loads(raw)
    assert raw == json.dumps(loaded, indent=2, sort_keys=True) + "\n"
    assert loaded["schema_version"] == 1


def test_rehearsal_report_includes_required_sections(tmp_path):
    sp = _source_package(tmp_path)
    report = run_temp_db_readiness_rehearsal(
        source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP
    )
    assert report["db"]["schema_version"] == 61  # Phase 4: migrator now at v61 (synthetic temp DB)  # migration status
    assert report["db"]["live_db_refused"] is True
    assert report["projection"]["applied"] is True  # projection status
    assert set(report["projection"]["required_tables"]) == {
        "forecast_budget_details",
        "forecast_cost_entries",
        "forecast_monthly_actuals_by_budget_code",
    }
    assert report["readiness"]["decision"] == "ready_for_guarded_operator_use"
    assert "report_path" in report["readiness"]
    assert report["safety"] == {
        "production_defaults_changed": False,
        "live_db_written": False,
        "live_root_written": False,
    }


# --- 5-12. fail-closed guards ----------------------------------------------------------


def test_refuses_unsupported_project(tmp_path):
    sp = _source_package(tmp_path)
    with pytest.raises(TempDbRehearsalError, match="unsupported project_key"):
        run_temp_db_readiness_rehearsal(
            source_package=sp,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            project_key="not-tropical",
        )


def test_refuses_missing_source_package(tmp_path):
    sp = tmp_path / "src" / "twn_cost_forecast_json_package"  # never built
    with pytest.raises(TempDbRehearsalError, match="source_package not found"):
        run_temp_db_readiness_rehearsal(
            source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP
        )


def test_refuses_invalid_source_structure(tmp_path):
    sp = _source_package(tmp_path)
    (sp / "data" / "cost_entries.jsonl").unlink()  # break structural validity
    with pytest.raises(TempDbRehearsalError, match="structurally invalid"):
        run_temp_db_readiness_rehearsal(
            source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP
        )


def test_refuses_live_root_work_root(tmp_path, monkeypatch):
    fake_live = tmp_path / "fake_live"
    monkeypatch.setattr(rehearsal, "_LIVE_ROOT", fake_live)
    sp = _source_package(tmp_path)
    with pytest.raises(TempDbRehearsalError, match="live forecast root"):
        run_temp_db_readiness_rehearsal(
            source_package=sp, work_root=fake_live / "work", context_stamp=STAMP
        )


def test_refuses_db_path_outside_work_root(tmp_path):
    sp = _source_package(tmp_path)
    outside = tmp_path / "outside.sqlite"
    with pytest.raises(TempDbRehearsalError, match="must be under work_root"):
        run_temp_db_readiness_rehearsal(
            source_package=sp, work_root=tmp_path / "work", context_stamp=STAMP, db_path=outside
        )


def test_refuses_live_db_path(tmp_path, monkeypatch):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    db = work / "temp_dbs" / "x.sqlite"
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: True)
    with pytest.raises(TempDbRehearsalError, match="live/default DB"):
        run_temp_db_readiness_rehearsal(
            source_package=sp, work_root=work, context_stamp=STAMP, db_path=db
        )


def test_refuses_preexisting_db_path(tmp_path):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    db = work / "temp_dbs" / "x.sqlite"
    db.parent.mkdir(parents=True)
    db.write_text("not really a db", encoding="utf-8")
    with pytest.raises(TempDbRehearsalError, match="db_path already exists"):
        run_temp_db_readiness_rehearsal(
            source_package=sp, work_root=work, context_stamp=STAMP, db_path=db
        )


def test_refuses_preexisting_work_root_output(tmp_path):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    (work / "junk.txt").write_text("prior output", encoding="utf-8")
    with pytest.raises(TempDbRehearsalError, match="already contains output"):
        run_temp_db_readiness_rehearsal(source_package=sp, work_root=work, context_stamp=STAMP)


# --- 13. readiness not_ready -> rehearsal failed ----------------------------------------


def test_not_ready_yields_failed(tmp_path, monkeypatch):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"

    def _fake_readiness(*, data_root, work_root, context_stamp, db_path, project_key="tropical"):
        return {
            "decision": "not_ready",
            "report_path": str(Path(work_root) / "readiness" / "db_cutover_readiness_report.json"),
        }

    monkeypatch.setattr(rehearsal, "run_db_cutover_readiness", _fake_readiness)
    report = run_temp_db_readiness_rehearsal(source_package=sp, work_root=work, context_stamp=STAMP)
    assert report["status"] == "failed"
    assert report["decision"] == "not_ready"
    # DB prep still really happened.
    assert Path(report["db"]["path"]).is_file()
    assert report["projection"]["applied"] is True


# --- 14-17. CLI -------------------------------------------------------------------------


def test_cli_success_derived_db(tmp_path, capsys):
    sp = _source_package(tmp_path)
    rc = cli.main(
        [
            "temp-db-readiness-rehearsal",
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
    assert payload["command"] == "temp-db-readiness-rehearsal"
    assert payload["status"] == "passed"


def test_cli_success_explicit_db(tmp_path, capsys):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"
    db = work / "temp_dbs" / "explicit.sqlite"
    rc = cli.main(
        [
            "temp-db-readiness-rehearsal",
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
    assert payload["status"] == "passed" and payload["db"]["path"] == str(db)


def test_cli_refusal_returns_rc3(tmp_path, capsys):
    sp = _source_package(tmp_path)
    outside = tmp_path / "outside.sqlite"
    rc = cli.main(
        [
            "temp-db-readiness-rehearsal",
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


def test_cli_not_ready_returns_rc1(tmp_path, capsys, monkeypatch):
    sp = _source_package(tmp_path)
    work = tmp_path / "work"

    def _fake_readiness(*, data_root, work_root, context_stamp, db_path, project_key="tropical"):
        return {
            "decision": "not_ready",
            "report_path": str(Path(work_root) / "readiness" / "db_cutover_readiness_report.json"),
        }

    monkeypatch.setattr(rehearsal, "run_db_cutover_readiness", _fake_readiness)
    rc = cli.main(
        [
            "temp-db-readiness-rehearsal",
            "--project",
            "tropical",
            "--source-package",
            str(sp),
            "--work-root",
            str(work),
            "--context-stamp",
            STAMP,
        ]
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed" and payload["decision"] == "not_ready"


# --- existing defaults preserved --------------------------------------------------------


def test_existing_cli_commands_still_route():
    parser = cli.build_parser()
    for cmd in ("run-context", "run-analysis"):
        assert parser.parse_args([cmd, "--project", "tropical"]).command == cmd
    dr = parser.parse_args(
        [
            "db-cutover-readiness",
            "--project",
            "tropical",
            "--data-root",
            "/x",
            "--work-root",
            "/y",
            "--context-stamp",
            "s",
            "--db-path",
            "/z",
        ]
    )
    assert dr.command == "db-cutover-readiness"
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
    assert tdr.command == "temp-db-readiness-rehearsal" and tdr.db_path is None


# --- duplicated synthetic source fixture (mirrors Phase 5/6/7/8/9/10 build_fixture) -----


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
