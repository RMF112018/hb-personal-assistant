"""Phase 7 — controlled final-forecast (analysis) DB parity.

Proves the downstream analysis generator (the immediate layer consuming ONLY the context package)
produces a parity-equivalent analysis package whether its context package was built file-backed or
DB-backed by the Phase 6 runner. Also proves the controlled runner fails closed (missing/invalid
context, non-tropical project, live-root data root, pre-existing analysis package, deterministic=
False, and a hard-pin miss that must NOT fall back to latest-glob), and that the CLI command is
additive and JSON-clean.

Everything runs under tmp_path; nothing touches the live DB or the live Synology root.

The fixture / DB-projection / normalization helpers below intentionally MIRROR
tests/test_forecast_context_runner_phase6.py (duplicated, not imported, so the proven Phase 5/6
tests stay independent and untouched).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from hb_assistant.construction.forecast import source_domain_engine as dbeng
from hb_assistant.store.migrator import SQLiteMigrator

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review.analysis import final_forecast_runner as ffr  # noqa: E402
from construction_financial_review.analysis.final_forecast_runner import (  # noqa: E402
    FinalForecastRunnerError,
    run_final_forecast_generation,
)
from construction_financial_review.context.context_generation_runner import (  # noqa: E402
    run_context_generation,
)

BCK = "0000.03-01-025.MAT"  # one budget code threaded through every source (mirrors Phase 5/6)
PROCORE_DIRNAME = "cost_forecast_agent_db_json_export_tropical_20260614_080344"
CTX_STAMP = "20260101_000000"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """No ambient DB/context env leaks into a controlled run unless a test sets it explicitly."""
    for var in (
        "HB_FORECAST_DB_BACKED_READS",
        "HB_FORECAST_DB_PATH",
        "CFR_CONTEXT_DATA_ROOT",
        "CFR_CONTEXT_OUT_DIR",
        "CFR_CONTEXT_STAMP",
        "CFR_RUN_LINEAGE_STATE",
    ):
        monkeypatch.delenv(var, raising=False)


def _wj(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _wjson(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def build_fixture(root: Path) -> Path:
    """Minimal-valid synthetic source packages: one budget code through every dependency.

    Mirrors tests/test_forecast_context_runner_phase6.py::build_fixture."""
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


def _project_db(root: Path, db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    rec = dbeng.project_source_domain(
        source_package=root / "twn_cost_forecast_json_package",
        project_key="tropical",
        db_path=db,
        apply=True,
    )
    assert rec["ok"] is True


# Approved volatile metadata — mirrors Phase 5/6 (only fields allowed to differ between runs).
_VOLATILE_KEYS = {"generated_stamp", "generated_timestamp_local", "package_name", "input_root"}


def _normalize(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in _VOLATILE_KEYS:
                out[k] = "<volatile>"
            elif k == "sha256":
                out[k] = "<sha>"
            elif k == "size_bytes":
                out[k] = "<size>"
            else:
                out[k] = _normalize(v)
        return out
    if isinstance(obj, list):
        return [_normalize(x) for x in obj]
    return obj


def _load_analysis_outputs(out: Path, data_root: Path) -> dict:
    """Parse + normalize an analysis package; neutralize run-location paths/stamps/name only.

    Replaces the whole (temp) data-root path — which contains both the consumed context package
    path and the analysis output path — and the analysis package name, then normalizes the
    approved volatile keys. Financial/domain values are never normalized.
    """
    data = {}
    for p in sorted(out.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(out))
        raw = (
            p.read_text(encoding="utf-8")
            .replace(str(data_root), "<ROOT>")
            .replace(out.name, "<OUT_NAME>")
        )
        if rel.endswith(".jsonl"):
            data[rel] = [_normalize(json.loads(line)) for line in raw.splitlines() if line.strip()]
        elif rel.endswith(".json"):
            data[rel] = _normalize(json.loads(raw))
        else:
            data[rel] = raw
    return data


def _fake_context(root: Path, stamp: str = CTX_STAMP) -> Path:
    """A structurally-valid (but not generated) context package dir for fast guard tests.

    The runner's context validation is structural (prefix + manifest + validation_report +
    canonical/ + summaries/); guard tests that never reach the subprocess can use this stub.
    """
    ctx = root / f"forecast_context_package_tropical_{stamp}"
    (ctx / "canonical").mkdir(parents=True)
    (ctx / "summaries").mkdir(parents=True)
    _wjson(ctx / "manifest.json", {"package_name": ctx.name})
    _wjson(ctx / "validation_report.json", {"passed": True})
    return ctx


def _real_context(src_root: Path, ctx_dir: Path, *, db_path: Path | None = None) -> Path:
    meta = run_context_generation(
        data_root=src_root,
        out_dir=ctx_dir,
        stamp=CTX_STAMP,
        db_backed=db_path is not None,
        db_path=db_path,
    )
    return Path(meta["output_package"])


# --- 1 & 2. controlled file-backed-context and DB-backed-context runs -------------------


def test_controlled_run_from_file_backed_context(tmp_path):
    src = build_fixture(tmp_path / "src")
    ctx = _real_context(src, tmp_path / "A" / f"forecast_context_package_tropical_{CTX_STAMP}")
    meta = run_final_forecast_generation(context_package=ctx)
    assert meta["ok"] is True and meta["mode"] == "analysis"
    assert meta["context_stamp"] == CTX_STAMP
    assert meta["lineage_source"] == "explicit_override"
    out = Path(meta["output_package"])
    assert str(out).startswith(str(tmp_path))
    assert out.name.startswith("forecast_analysis_package_tropical_")
    assert (out / "forecast_recommendations_by_budget_code.jsonl").is_file()
    assert (out / "validation_report.json").is_file()


def test_controlled_run_from_db_backed_context(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    ctx = _real_context(
        src, tmp_path / "B" / f"forecast_context_package_tropical_{CTX_STAMP}", db_path=db
    )
    meta = run_final_forecast_generation(context_package=ctx)
    assert meta["ok"] is True and meta["mode"] == "analysis"
    out = Path(meta["output_package"])
    assert str(out).startswith(str(tmp_path))
    assert (out / "forecast_recommendations_by_budget_code.jsonl").is_file()


# --- 3. file-backed-context vs DB-backed-context final-output parity --------------------


def test_final_output_parity_file_vs_db_backed_context(tmp_path):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    ctx_a = _real_context(src, tmp_path / "A" / f"forecast_context_package_tropical_{CTX_STAMP}")
    ctx_b = _real_context(
        src, tmp_path / "B" / f"forecast_context_package_tropical_{CTX_STAMP}", db_path=db
    )
    meta_a = run_final_forecast_generation(context_package=ctx_a)
    meta_b = run_final_forecast_generation(context_package=ctx_b)

    a = _load_analysis_outputs(Path(meta_a["output_package"]), Path(meta_a["data_root"]))
    b = _load_analysis_outputs(Path(meta_b["output_package"]), Path(meta_b["data_root"]))
    assert set(a) == set(b)
    mismatches = [f for f in a if a[f] != b[f]]
    assert not mismatches, (
        f"DB-context analysis differs from file-context analysis at: {mismatches}"
    )
    assert str(meta_a["output_package"]).startswith(str(tmp_path))
    assert str(meta_b["output_package"]).startswith(str(tmp_path))


# --- 4 & 5. fail-closed guards ----------------------------------------------------------


def test_refuses_missing_context_package(tmp_path):
    with pytest.raises(FinalForecastRunnerError, match="not found"):
        run_final_forecast_generation(
            context_package=tmp_path / f"forecast_context_package_tropical_{CTX_STAMP}"
        )


def test_refuses_structurally_invalid_context_package(tmp_path):
    bad = tmp_path / f"forecast_context_package_tropical_{CTX_STAMP}"
    (bad / "canonical").mkdir(parents=True)  # missing manifest/validation_report/summaries
    with pytest.raises(FinalForecastRunnerError, match="structurally invalid"):
        run_final_forecast_generation(context_package=bad)


def test_refuses_non_tropical_project(tmp_path):
    ctx = _fake_context(tmp_path)
    with pytest.raises(FinalForecastRunnerError, match="not eligible"):
        run_final_forecast_generation(context_package=ctx, project_key="not-tropical")


def test_refuses_non_deterministic(tmp_path):
    ctx = _fake_context(tmp_path)
    with pytest.raises(FinalForecastRunnerError, match="deterministic"):
        run_final_forecast_generation(context_package=ctx, deterministic=False)


def test_refuses_live_root_data_root(tmp_path, monkeypatch):
    fake_live = tmp_path / "fake_live"
    monkeypatch.setattr(ffr, "_LIVE_ROOT", fake_live)
    ctx = _fake_context(fake_live)
    with pytest.raises(FinalForecastRunnerError, match="live forecast root"):
        run_final_forecast_generation(context_package=ctx)
    assert not list(fake_live.glob("forecast_analysis_package_tropical_*"))


def test_refuses_pre_existing_analysis_package(tmp_path):
    root = tmp_path / "A"
    ctx = _fake_context(root)
    (root / "forecast_analysis_package_tropical_20259999_000000").mkdir()
    with pytest.raises(FinalForecastRunnerError, match="already exists"):
        run_final_forecast_generation(context_package=ctx)


def test_hard_pin_no_latest_glob_fallback(tmp_path):
    """A present decoy context must NOT be discovered when a different stamp is requested."""
    root = tmp_path / "A"
    _fake_context(root, stamp="20260101_000000")  # decoy present in the data root
    requested = root / "forecast_context_package_tropical_19990101_000000"  # absent
    with pytest.raises(FinalForecastRunnerError, match="not found"):
        run_final_forecast_generation(context_package=requested)
    assert not list(root.glob("forecast_analysis_package_tropical_*"))


# --- 6. existing defaults preserved -----------------------------------------------------


def test_run_analysis_and_context_cli_still_route():
    parser = cli.build_parser()
    a = parser.parse_args(["run-analysis", "--project", "tropical"])
    assert a.command == "run-analysis"
    c = parser.parse_args(["run-context", "--project", "tropical"])
    assert c.command == "run-context"


# --- 7. CLI command ---------------------------------------------------------------------


def test_cli_file_backed_context_succeeds(tmp_path, capsys):
    src = build_fixture(tmp_path / "src")
    ctx = _real_context(src, tmp_path / "A" / f"forecast_context_package_tropical_{CTX_STAMP}")
    capsys.readouterr()  # drain context-generation chatter so stdout holds only the CLI JSON
    rc = cli.main(
        ["final-forecast-generate", "--project", "tropical", "--context-package", str(ctx)]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok" and payload["mode"] == "analysis"
    assert Path(payload["output_package"]).is_dir()


def test_cli_db_backed_context_succeeds(tmp_path, capsys):
    src = build_fixture(tmp_path / "src")
    db = tmp_path / "v59.db"
    _project_db(src, db)
    ctx = _real_context(
        src, tmp_path / "B" / f"forecast_context_package_tropical_{CTX_STAMP}", db_path=db
    )
    capsys.readouterr()  # drain context-generation chatter so stdout holds only the CLI JSON
    rc = cli.main(
        ["final-forecast-generate", "--project", "tropical", "--context-package", str(ctx)]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok" and payload["mode"] == "analysis"


def test_cli_refuses_missing_context(tmp_path, capsys):
    rc = cli.main(
        [
            "final-forecast-generate",
            "--project",
            "tropical",
            "--context-package",
            str(tmp_path / "forecast_context_package_tropical_x"),
        ]
    )
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "refused"


def test_cli_refuses_live_root(tmp_path, capsys, monkeypatch):
    fake_live = tmp_path / "fake_live"
    monkeypatch.setattr(ffr, "_LIVE_ROOT", fake_live)
    ctx = _fake_context(fake_live)
    rc = cli.main(
        ["final-forecast-generate", "--project", "tropical", "--context-package", str(ctx)]
    )
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "refused" and "live forecast root" in payload["reason"]
