"""Phase 10 — controlled DB-cutover-readiness gate (evidence only).

Proves the readiness gate over the Phase 6–9 controlled DB-backed context→analysis chain: preflight
prerequisite checks, read-only temp v59 DB inspection, the ready/not-ready decision, and the
deterministic evidence report. The gate calls the Phase 9 parity workflow (it does not duplicate
orchestration).

Everything runs under ``tmp_path`` with a temp SQLite DB only; never the live Synology root or the
live/default DB. build_fixture / _wj / _wjson / _project_db MIRROR the Phase 9 test (duplicated, not
imported, so the proven earlier phases stay independent).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# hb_assistant is used ONLY to build / monkeypatch around a temp v59 DB (mirrors Phase 9).
from hb_assistant.construction.forecast import source_domain_engine as dbeng
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review.workflows import db_cutover_readiness as rd  # noqa: E402
from construction_financial_review.workflows.db_cutover_readiness import (  # noqa: E402
    DbCutoverReadinessError,
    run_db_cutover_readiness,
)

BCK = "0000.03-01-025.MAT"  # mirrors Phase 5/6/7/8/9
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


# --- 1. readiness succeeds with synthetic fixture + temp v59 DB -------------------------


def test_readiness_succeeds_ready(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    report = run_db_cutover_readiness(
        data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, db_path=db
    )
    assert report["status"] == "ready"
    assert report["decision"] == "ready_for_guarded_operator_use"
    assert report["parity"]["context_match"] is True
    assert report["parity"]["analysis_match"] is True
    assert report["parity"]["chain_match"] is True
    assert Path(report["report_path"]).is_file()
    assert Path(report["workflow"]["parity_report"]).is_file()
    assert Path(report["workflow"]["file_chain_manifest"]).is_file()
    assert Path(report["workflow"]["db_chain_manifest"]).is_file()
    assert report["safety"] == {
        "production_defaults_changed": False,
        "live_root_written": False,
        "live_db_written": False,
    }


# --- 2. deterministic report ------------------------------------------------------------


def test_readiness_report_is_deterministic(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    report = run_db_cutover_readiness(
        data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, db_path=db
    )
    raw = Path(report["report_path"]).read_text(encoding="utf-8")
    loaded = json.loads(raw)
    assert raw == json.dumps(loaded, indent=2, sort_keys=True) + "\n"
    assert loaded["schema_version"] == 1


# --- 3. ready only when parity passes; parity fail -> not_ready -------------------------


def test_parity_fail_yields_not_ready(tmp_path, monkeypatch):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)

    def _fake_parity(*, data_root, work_root, context_stamp, db_path, project_key="tropical"):
        work_root = Path(work_root)
        work_root.mkdir(parents=True, exist_ok=True)
        fr = work_root / "file_report.json"
        dr = work_root / "db_report.json"
        fr.write_text(json.dumps({"chain_manifest": str(work_root / "file" / "m.json")}))
        dr.write_text(json.dumps({"chain_manifest": str(work_root / "db" / "m.json")}))
        pr = work_root / "parity.json"
        pr.write_text("{}")
        return {
            "status": "fail",
            "context_comparison": {"match": False},
            "analysis_comparison": {"match": True},
            "chain_comparison": {"match": True},
            "file_report": str(fr),
            "db_report": str(dr),
            "parity_report_path": str(pr),
        }

    monkeypatch.setattr(rd, "run_controlled_context_analysis_parity", _fake_parity)
    report = run_db_cutover_readiness(
        data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, db_path=db
    )
    assert report["status"] == "not_ready"
    assert report["decision"] == "not_ready"
    assert report["parity"]["context_match"] is False


# --- 4. report includes DB schema version + required table coverage ---------------------


def test_report_includes_db_checks(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    report = run_db_cutover_readiness(
        data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, db_path=db
    )
    checks = report["db_checks"]
    assert checks["db_exists"] is True
    assert checks["live_db_refused"] is True
    assert checks["schema_version"] == LATEST_SCHEMA_VERSION  # synthetic temp DB migrated to latest
    assert checks["required_tables_present"] is True
    assert checks["required_tables_nonempty"] is True


# --- 5-14. fail-closed guards -----------------------------------------------------------


def test_refuses_unsupported_project(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    with pytest.raises(DbCutoverReadinessError, match="not eligible"):
        run_db_cutover_readiness(
            data_root=src,
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            db_path=db,
            project_key="not-tropical",
        )


def test_refuses_missing_data_root(tmp_path):
    db = tmp_path / "v59.db"
    _project_db(build_fixture(tmp_path / "src"), db)
    with pytest.raises(DbCutoverReadinessError, match="data_root not found"):
        run_db_cutover_readiness(
            data_root=tmp_path / "nope",
            work_root=tmp_path / "work",
            context_stamp=STAMP,
            db_path=db,
        )


def test_refuses_missing_db_path(tmp_path):
    src = build_fixture(tmp_path / "src")
    with pytest.raises(DbCutoverReadinessError, match="db_path is required"):
        run_db_cutover_readiness(
            data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, db_path=None
        )


def test_refuses_live_db(tmp_path, monkeypatch):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    # Force the live-DB safety function to treat this temp DB as the live/default DB.
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: True)
    with pytest.raises(DbCutoverReadinessError, match="live/default DB"):
        run_db_cutover_readiness(
            data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, db_path=db
        )


def test_refuses_missing_schema_migrations_table(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "no_migrations.db"
    _make_db(db, migrations=None, create_tables=["_probe"])
    with pytest.raises(DbCutoverReadinessError, match="no schema_migrations"):
        run_db_cutover_readiness(
            data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, db_path=db
        )


def test_refuses_schema_below_required(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v58.db"
    _make_db(db, migrations=[1, 58], create_tables=[])
    with pytest.raises(DbCutoverReadinessError, match="below the required"):
        run_db_cutover_readiness(
            data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, db_path=db
        )


def test_refuses_missing_required_tables(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59_no_tables.db"
    _make_db(db, migrations=[59], create_tables=[])
    with pytest.raises(DbCutoverReadinessError, match="missing required v59 source-domain tables"):
        run_db_cutover_readiness(
            data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, db_path=db
        )


def test_refuses_empty_required_tables(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59_empty.db"
    SQLiteMigrator(db_path=str(db)).apply()  # migrated to v59 but NOT projected -> empty tables
    with pytest.raises(DbCutoverReadinessError, match="empty required v59 source-domain tables"):
        run_db_cutover_readiness(
            data_root=src, work_root=tmp_path / "work", context_stamp=STAMP, db_path=db
        )


def test_refuses_live_root_work_root(tmp_path, monkeypatch):
    fake_live = tmp_path / "fake_live"
    monkeypatch.setattr(rd, "_LIVE_ROOT", fake_live)
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    with pytest.raises(DbCutoverReadinessError, match="live forecast root"):
        run_db_cutover_readiness(
            data_root=src, work_root=fake_live / "work", context_stamp=STAMP, db_path=db
        )


def test_refuses_preexisting_readiness_output(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    work = tmp_path / "work"
    (work / "readiness" / "file").mkdir(parents=True)  # pre-existing conflicting output
    with pytest.raises(DbCutoverReadinessError, match="already contains output"):
        run_db_cutover_readiness(data_root=src, work_root=work, context_stamp=STAMP, db_path=db)


# --- 15 & 16. CLI -----------------------------------------------------------------------


def test_cli_readiness_success(tmp_path, capsys):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    rc = cli.main(
        [
            "db-cutover-readiness",
            "--project",
            "tropical",
            "--data-root",
            str(src),
            "--work-root",
            str(tmp_path / "work"),
            "--context-stamp",
            STAMP,
            "--db-path",
            str(db),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "db-cutover-readiness"
    assert payload["status"] == "ready"
    assert payload["decision"] == "ready_for_guarded_operator_use"


def test_cli_refusal_returns_rc3(tmp_path, capsys):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59_empty.db"
    SQLiteMigrator(db_path=str(db)).apply()  # empty v59 tables -> controlled refusal
    rc = cli.main(
        [
            "db-cutover-readiness",
            "--project",
            "tropical",
            "--data-root",
            str(src),
            "--work-root",
            str(tmp_path / "work"),
            "--context-stamp",
            STAMP,
            "--db-path",
            str(db),
        ]
    )
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "refused"
    assert "empty required v59 source-domain tables" in payload["reason"]


# --- existing defaults preserved --------------------------------------------------------


def test_existing_cli_commands_still_route():
    parser = cli.build_parser()
    for cmd in ("run-context", "run-analysis"):
        assert parser.parse_args([cmd, "--project", "tropical"]).command == cmd
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
    assert cca.command == "controlled-context-analysis"
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
    assert dr.command == "db-cutover-readiness" and dr.db_path == "/z"


# --- hand-crafted DB helper (for schema/table refusal cases) ----------------------------


def _make_db(path: Path, *, migrations, create_tables) -> None:
    """Build a minimal SQLite DB for refusal tests: optional schema_migrations rows + bare tables."""
    conn = sqlite3.connect(str(path))
    try:
        if migrations is not None:
            conn.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT, "
                "applied_at TEXT)"
            )
            conn.executemany(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                [(v, f"v{v}", "2026-01-01T00:00:00") for v in migrations],
            )
        for t in create_tables:
            conn.execute(f"CREATE TABLE {t} (project_key TEXT, raw_json TEXT)")
        conn.commit()
    finally:
        conn.close()


# --- temp v59 DB projection (mirrors Phase 9) -------------------------------------------


def _project_db(root: Path, db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    rec = dbeng.project_source_domain(
        source_package=root / "twn_cost_forecast_json_package",
        project_key="tropical",
        db_path=db,
        apply=True,
    )
    assert rec["ok"] is True


# --- duplicated synthetic source fixture (mirrors Phase 5/6/7/8/9 build_fixture) --------


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
