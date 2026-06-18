"""Phase 5 — CFR context-generator parameterization + full-package DB parity.

Proves: the context generator is import-safe (no I/O at import) and re-runnable via
build_context_package(config); file-backed and DB-backed runs produce parity-equivalent
context packages under temp roots (only approved volatile metadata normalized); and the
DB-backed path fails closed (missing rows / missing DB path / live DB path). The generator
is driven to completion against a synthetic, self-contained fixture so the test needs no
Synology access.

Adapter-boundary parity was proven in Phase 4; this is full generated-package parity.
Nothing here touches the live DB or writes under the live data root.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.forecast import source_domain_engine as dbeng
from hb_assistant.store.migrator import SQLiteMigrator

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

import construction_financial_review.context.generate_forecast_context_package as gen  # noqa: E402, I001
from construction_financial_review.context.db_source_adapter import ForecastDbReadError  # noqa: E402

BCK = "0000.03-01-025.MAT"  # one budget code threaded through every source
PROCORE_DIRNAME = "cost_forecast_agent_db_json_export_tropical_20260614_080344"


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


# Approved volatile metadata (the only fields allowed to differ between runs).
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


def _load_outputs(out: Path) -> dict:
    """Parse + normalize all package outputs; neutralize run-location paths/stamps only."""
    data = {}
    for p in sorted(out.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(out))
        if rel == "generate_forecast_context_package.py":
            continue  # verbatim script copy (identical across runs)
        raw = (
            p.read_text(encoding="utf-8").replace(str(out), "<OUT>").replace(out.name, "<OUT_NAME>")
        )
        if rel.endswith(".jsonl"):
            data[rel] = [_normalize(json.loads(line)) for line in raw.splitlines() if line.strip()]
        elif rel.endswith(".json"):
            data[rel] = _normalize(json.loads(raw))
        else:
            data[rel] = raw
    return data


def _project_db(root: Path, db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    rec = dbeng.project_source_domain(
        source_package=root / "twn_cost_forecast_json_package",
        project_key="tropical",
        db_path=db,
        apply=True,
    )
    assert rec["ok"] is True


def _run(monkeypatch, *, data_root: Path, out_dir: Path, db_path: Path | None) -> Path:
    monkeypatch.setenv("CFR_CONTEXT_DATA_ROOT", str(data_root))
    monkeypatch.setenv("CFR_CONTEXT_OUT_DIR", str(out_dir))
    monkeypatch.setenv("CFR_CONTEXT_STAMP", "20260618_000000")
    if db_path is not None:
        monkeypatch.setenv("HB_FORECAST_DB_BACKED_READS", "1")
        monkeypatch.setenv("HB_FORECAST_DB_PATH", str(db_path))
    else:
        monkeypatch.delenv("HB_FORECAST_DB_BACKED_READS", raising=False)
        monkeypatch.delenv("HB_FORECAST_DB_PATH", raising=False)
    return gen.build_context_package(gen.default_config())


# --- 1. build with explicit temp config -------------------------------------------------


def test_build_with_temp_config_writes_under_temp(tmp_path, monkeypatch):
    root = build_fixture(tmp_path / "data_root")
    out = tmp_path / "out"
    result = _run(monkeypatch, data_root=root, out_dir=out, db_path=None)
    assert result == out
    assert str(result).startswith(str(tmp_path))
    assert (out / "manifest.json").is_file()
    # No package was written under the data root.
    assert not list(root.glob("forecast_context_package_*"))


# --- 2. importing the generator performs no I/O (subprocess, clean interpreter) ----------


def test_import_is_side_effect_free():
    code = (
        "import sys, builtins\n"
        f"sys.path.insert(0, {str(CFR_SRC)!r})\n"
        "opened=[]\n"
        "_o=builtins.open\n"
        "builtins.open=lambda f,*a,**k: (opened.append(str(f)), _o(f,*a,**k))[1]\n"
        "import construction_financial_review.context.generate_forecast_context_package as g\n"
        "builtins.open=_o\n"
        "assert opened==[], opened\n"
        "assert not hasattr(g,'ROOT') and not hasattr(g,'SRC_FILES')\n"
        "assert hasattr(g,'build_context_package') and hasattr(g,'default_config')\n"
        "print('OK')\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert "OK" in proc.stdout


# --- 3 & 4 & 5. file-backed and DB-backed full-package parity ----------------------------


def test_file_backed_and_db_backed_full_package_parity(tmp_path, monkeypatch):
    root = build_fixture(tmp_path / "data_root")
    db = tmp_path / "v59.db"
    _project_db(root, db)

    out_a = tmp_path / "outA"
    out_b = tmp_path / "outB"
    res_a = _run(monkeypatch, data_root=root, out_dir=out_a, db_path=None)
    res_b = _run(monkeypatch, data_root=root, out_dir=out_b, db_path=db)
    assert str(res_a).startswith(str(tmp_path)) and str(res_b).startswith(str(tmp_path))

    a, b = _load_outputs(out_a), _load_outputs(out_b)
    assert set(a) == set(b)
    mismatches = [f for f in a if a[f] != b[f]]
    assert not mismatches, f"DB-backed package differs from file-backed at: {mismatches}"
    assert len(a) >= 30  # full package generated, not a stub


def test_global_reset_proven_in_both_orders(tmp_path, monkeypatch):
    """DB-first then file (reverse of the parity test) must still match — proves _reset_state."""
    root = build_fixture(tmp_path / "data_root")
    db = tmp_path / "v59.db"
    _project_db(root, db)
    out_b = tmp_path / "outB"
    out_a = tmp_path / "outA"
    _run(monkeypatch, data_root=root, out_dir=out_b, db_path=db)  # DB first
    _run(monkeypatch, data_root=root, out_dir=out_a, db_path=None)  # then file
    a, b = _load_outputs(out_a), _load_outputs(out_b)
    assert set(a) == set(b)
    assert [f for f in a if a[f] != b[f]] == []


# --- 6, 7, 8. DB-backed fail-closed ------------------------------------------------------


def test_db_backed_fails_closed_when_rows_missing(tmp_path, monkeypatch):
    root = build_fixture(tmp_path / "data_root")
    db = tmp_path / "v59.db"
    SQLiteMigrator(db_path=str(db)).apply()  # migrated but NOT projected -> no rows
    with pytest.raises(ForecastDbReadError, match="no DB rows"):
        _run(monkeypatch, data_root=root, out_dir=tmp_path / "out", db_path=db)
    assert not (tmp_path / "out").exists()  # failed before any output dir was created


def test_db_backed_fails_closed_without_db_path(tmp_path, monkeypatch):
    root = build_fixture(tmp_path / "data_root")
    monkeypatch.setenv("CFR_CONTEXT_DATA_ROOT", str(root))
    monkeypatch.setenv("CFR_CONTEXT_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("HB_FORECAST_DB_BACKED_READS", "1")
    monkeypatch.delenv("HB_FORECAST_DB_PATH", raising=False)
    with pytest.raises(ForecastDbReadError, match="HB_FORECAST_DB_PATH"):
        gen.build_context_package(gen.default_config())


def test_db_backed_refuses_live_db_path(tmp_path, monkeypatch):
    root = build_fixture(tmp_path / "data_root")
    monkeypatch.setenv("CFR_CONTEXT_DATA_ROOT", str(root))
    monkeypatch.setenv("CFR_CONTEXT_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("HB_FORECAST_DB_BACKED_READS", "1")
    monkeypatch.setenv("HB_FORECAST_DB_PATH", str(PathPolicy().get_db_path()))
    with pytest.raises(ForecastDbReadError, match="live/default DB"):
        gen.build_context_package(gen.default_config())


# --- 9. default/toggle-off stays file-backed --------------------------------------------


def test_toggle_off_default_is_file_backed(tmp_path, monkeypatch):
    root = build_fixture(tmp_path / "data_root")
    # No DB env at all; build must complete purely file-backed.
    res = _run(monkeypatch, data_root=root, out_dir=tmp_path / "out", db_path=None)
    assert (res / "canonical" / "budget_codes.jsonl").is_file()


# --- optional: read-only live-source smoke (skipped without Synology) --------------------

_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


@pytest.mark.skipif(not _LIVE_ROOT.exists(), reason="live Synology source root not available")
def test_live_source_copy_smoke(tmp_path, monkeypatch):
    """Read-only: copy live packages into temp and run the same parity harness. Never CI."""
    import shutil

    root = tmp_path / "data_root"
    root.mkdir()
    for name in ("twn_cost_forecast_json_package", "owner_pay_app_json_package", PROCORE_DIRNAME):
        src = _LIVE_ROOT / name
        if src.exists():
            shutil.copytree(src, root / name)
    db = tmp_path / "v59.db"
    _project_db(root, db)
    out_a, out_b = tmp_path / "outA", tmp_path / "outB"
    _run(monkeypatch, data_root=root, out_dir=out_a, db_path=None)
    _run(monkeypatch, data_root=root, out_dir=out_b, db_path=db)
    a, b = _load_outputs(out_a), _load_outputs(out_b)
    assert [f for f in a if a[f] != b[f]] == []
