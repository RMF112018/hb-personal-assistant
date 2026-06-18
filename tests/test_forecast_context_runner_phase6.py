"""Phase 6 — controlled, default-off DB-backed context-generation runner.

Proves the runner (and its optional CLI command) can intentionally drive the Phase 5 context
generator in file-backed (default) or DB-backed mode from EXPLICIT inputs, with:
  - controlled file-backed and DB-backed runs that write only under tmp_path;
  - file-backed vs DB-backed package parity through the runner (Phase 5 normalization);
  - explicit environment isolation (DB toggles set only for the DB-backed run, restored on
    success AND failure; a file-backed run is unaffected by ambient DB env);
  - fail-closed behavior (no db_path / live DB / missing v59 rows / live-root out_dir / unknown
    project / existing out_dir);
  - preservation of existing defaults (default_config, generator main wrapper, run-context CLI).

Nothing here touches the live DB or writes under the live data root.

The fixture/normalization/projection helpers below intentionally MIRROR
tests/test_forecast_context_generator_phase5.py. They are duplicated (not imported) so the
proven Phase 5 parity test stays independent and untouched.
"""

from __future__ import annotations

import json
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
from construction_financial_review import cli  # noqa: E402
from construction_financial_review.context.context_generation_runner import (  # noqa: E402
    ContextRunnerError,
    run_context_generation,
)
from construction_financial_review.context.db_source_adapter import ForecastDbReadError  # noqa: E402

BCK = "0000.03-01-025.MAT"  # one budget code threaded through every source (mirrors Phase 5)
PROCORE_DIRNAME = "cost_forecast_agent_db_json_export_tropical_20260614_080344"
STAMP = "20260618_000000"

# Env toggles the Phase 4 adapter / Phase 6 runner manage.
_ENV_DB_BACKED = "HB_FORECAST_DB_BACKED_READS"
_ENV_DB_PATH = "HB_FORECAST_DB_PATH"


@pytest.fixture(autouse=True)
def _clear_db_toggles(monkeypatch):
    """No ambient DB env leaks into a controlled run unless a test sets it explicitly."""
    monkeypatch.delenv(_ENV_DB_BACKED, raising=False)
    monkeypatch.delenv(_ENV_DB_PATH, raising=False)
    # Also clear the Phase 5 CFR_CONTEXT_* overrides so the runner's direct config is authoritative.
    monkeypatch.delenv("CFR_CONTEXT_DATA_ROOT", raising=False)
    monkeypatch.delenv("CFR_CONTEXT_OUT_DIR", raising=False)
    monkeypatch.delenv("CFR_CONTEXT_STAMP", raising=False)


def _wj(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _wjson(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def build_fixture(root: Path) -> Path:
    """Minimal-valid synthetic source packages: one budget code through every dependency.

    Mirrors tests/test_forecast_context_generator_phase5.py::build_fixture."""
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


# Approved volatile metadata — mirrors Phase 5 (the only fields allowed to differ between runs).
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


# --- 1. controlled file-backed run ------------------------------------------------------


def test_controlled_file_backed_run_writes_under_tmp(tmp_path):
    root = build_fixture(tmp_path / "data_root")
    out = tmp_path / "out"
    meta = run_context_generation(data_root=root, out_dir=out, stamp=STAMP)
    assert meta["ok"] is True and meta["mode"] == "file_backed"
    assert meta["db_path"] is None
    assert Path(meta["output_package"]) == out
    assert str(out).startswith(str(tmp_path))
    assert (out / "manifest.json").is_file()
    assert (out / "canonical" / "budget_codes.jsonl").is_file()
    assert not list(root.glob("forecast_context_package_*"))


# --- 2. controlled DB-backed run --------------------------------------------------------


def test_controlled_db_backed_run_writes_under_tmp(tmp_path):
    root = build_fixture(tmp_path / "data_root")
    db = tmp_path / "v59.db"
    _project_db(root, db)
    out = tmp_path / "out"
    meta = run_context_generation(
        data_root=root, out_dir=out, stamp=STAMP, db_backed=True, db_path=db
    )
    assert meta["ok"] is True and meta["mode"] == "db_backed"
    assert meta["db_path"] == str(db)
    assert Path(meta["output_package"]) == out
    assert str(out).startswith(str(tmp_path))
    assert (out / "canonical" / "budget_codes.jsonl").is_file()


# --- 3. file-backed vs DB-backed parity through the runner ------------------------------


def test_runner_file_vs_db_backed_parity(tmp_path):
    root = build_fixture(tmp_path / "data_root")
    db = tmp_path / "v59.db"
    _project_db(root, db)
    out_a = tmp_path / "outA"
    out_b = tmp_path / "outB"
    run_context_generation(data_root=root, out_dir=out_a, stamp=STAMP)
    run_context_generation(data_root=root, out_dir=out_b, stamp=STAMP, db_backed=True, db_path=db)
    a, b = _load_outputs(out_a), _load_outputs(out_b)
    assert set(a) == set(b)
    mismatches = [f for f in a if a[f] != b[f]]
    assert not mismatches, f"DB-backed package differs from file-backed at: {mismatches}"
    assert len(a) >= 30  # full package generated, not a stub


# --- 4. environment isolation -----------------------------------------------------------


def test_env_restored_after_success(tmp_path, monkeypatch):
    monkeypatch.setenv(_ENV_DB_BACKED, "ambient-backed")
    monkeypatch.setenv(_ENV_DB_PATH, "ambient-path")
    root = build_fixture(tmp_path / "data_root")
    db = tmp_path / "v59.db"
    _project_db(root, db)
    run_context_generation(
        data_root=root, out_dir=tmp_path / "out", stamp=STAMP, db_backed=True, db_path=db
    )
    import os

    assert os.environ[_ENV_DB_BACKED] == "ambient-backed"
    assert os.environ[_ENV_DB_PATH] == "ambient-path"


def test_env_restored_after_failure(tmp_path, monkeypatch):
    monkeypatch.setenv(_ENV_DB_BACKED, "ambient-backed")
    monkeypatch.setenv(_ENV_DB_PATH, "ambient-path")
    root = build_fixture(tmp_path / "data_root")
    db = tmp_path / "v59.db"
    SQLiteMigrator(db_path=str(db)).apply()  # migrated but NOT projected -> no rows -> fail closed
    with pytest.raises(ForecastDbReadError, match="no DB rows"):
        run_context_generation(
            data_root=root, out_dir=tmp_path / "out", stamp=STAMP, db_backed=True, db_path=db
        )
    import os

    assert os.environ[_ENV_DB_BACKED] == "ambient-backed"
    assert os.environ[_ENV_DB_PATH] == "ambient-path"
    assert not (tmp_path / "out").exists()  # failed before any output dir was created


def test_file_backed_unaffected_by_ambient_db_env(tmp_path, monkeypatch):
    # Ambient shell claims DB-backed reads are on, with a bogus path — a file-backed controlled
    # run must ignore it (the runner clears the toggles for the duration) and still succeed.
    monkeypatch.setenv(_ENV_DB_BACKED, "1")
    monkeypatch.setenv(_ENV_DB_PATH, "/nonexistent/should-not-be-used.sqlite")
    root = build_fixture(tmp_path / "data_root")
    out = tmp_path / "out"
    meta = run_context_generation(data_root=root, out_dir=out, stamp=STAMP)
    assert meta["mode"] == "file_backed"
    assert (out / "canonical" / "budget_codes.jsonl").is_file()
    import os

    assert os.environ[_ENV_DB_BACKED] == "1"  # ambient value restored


# --- 5. fail-closed behavior ------------------------------------------------------------


def test_db_backed_without_db_path_fails(tmp_path):
    root = build_fixture(tmp_path / "data_root")
    with pytest.raises(ContextRunnerError, match="requires an explicit db_path"):
        run_context_generation(
            data_root=root, out_dir=tmp_path / "out", stamp=STAMP, db_backed=True, db_path=None
        )
    assert not (tmp_path / "out").exists()


def test_db_backed_refuses_live_db_path(tmp_path):
    root = build_fixture(tmp_path / "data_root")
    with pytest.raises(ContextRunnerError, match="live/default DB"):
        run_context_generation(
            data_root=root,
            out_dir=tmp_path / "out",
            stamp=STAMP,
            db_backed=True,
            db_path=PathPolicy().get_db_path(),
        )
    assert not (tmp_path / "out").exists()


def test_db_backed_missing_rows_fails(tmp_path):
    root = build_fixture(tmp_path / "data_root")
    db = tmp_path / "v59.db"
    SQLiteMigrator(db_path=str(db)).apply()  # migrated but not projected
    with pytest.raises(ForecastDbReadError, match="no DB rows"):
        run_context_generation(
            data_root=root, out_dir=tmp_path / "out", stamp=STAMP, db_backed=True, db_path=db
        )
    assert not (tmp_path / "out").exists()


def test_out_dir_under_live_root_refused(tmp_path):
    root = build_fixture(tmp_path / "data_root")
    bad_out = gen._DEFAULT_DATA_ROOT / "forecast_context_package_tropical_phase6test"
    with pytest.raises(ContextRunnerError, match="live forecast data root"):
        run_context_generation(data_root=root, out_dir=bad_out, stamp=STAMP)


def test_existing_out_dir_refused(tmp_path):
    root = build_fixture(tmp_path / "data_root")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ContextRunnerError, match="already exists"):
        run_context_generation(data_root=root, out_dir=out, stamp=STAMP)


def test_unsupported_project_refused(tmp_path):
    root = build_fixture(tmp_path / "data_root")
    with pytest.raises(ContextRunnerError, match="unsupported project_key"):
        run_context_generation(
            data_root=root, out_dir=tmp_path / "out", stamp=STAMP, project_key="not-tropical"
        )


# --- 6. existing defaults preserved -----------------------------------------------------


def test_default_config_unchanged_without_env():
    cfg = gen.default_config()
    assert cfg.data_root == gen._DEFAULT_DATA_ROOT
    assert cfg.out_dir == gen._DEFAULT_DATA_ROOT / f"forecast_context_package_tropical_{cfg.stamp}"


def test_generator_main_is_thin_default_wrapper():
    # main() must remain the default-config wrapper Phase 5 established (no Phase 6 change).
    assert callable(gen.main)
    assert callable(gen.build_context_package)
    assert callable(gen.default_config)


def test_run_context_cli_still_routes():
    args = cli.build_parser().parse_args(["run-context", "--project", "tropical"])
    assert args.command == "run-context"
    assert args.project == "tropical"


# --- 7. CLI command ---------------------------------------------------------------------


def test_cli_file_backed_succeeds(tmp_path, capsys):
    root = build_fixture(tmp_path / "data_root")
    out = tmp_path / "out"
    rc = cli.main(
        [
            "context-generate",
            "--project",
            "tropical",
            "--data-root",
            str(root),
            "--out-dir",
            str(out),
            "--stamp",
            STAMP,
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok" and payload["mode"] == "file_backed"
    assert (out / "manifest.json").is_file()


def test_cli_db_backed_succeeds(tmp_path, capsys):
    root = build_fixture(tmp_path / "data_root")
    db = tmp_path / "v59.db"
    _project_db(root, db)
    out = tmp_path / "out"
    rc = cli.main(
        [
            "context-generate",
            "--project",
            "tropical",
            "--data-root",
            str(root),
            "--out-dir",
            str(out),
            "--stamp",
            STAMP,
            "--db-backed",
            "--db-path",
            str(db),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok" and payload["mode"] == "db_backed"
    assert (out / "canonical" / "budget_codes.jsonl").is_file()


def test_cli_db_backed_without_db_path_fails(tmp_path, capsys):
    root = build_fixture(tmp_path / "data_root")
    rc = cli.main(
        [
            "context-generate",
            "--project",
            "tropical",
            "--data-root",
            str(root),
            "--out-dir",
            str(tmp_path / "out"),
            "--stamp",
            STAMP,
            "--db-backed",
        ]
    )
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "refused" and "db_path" in payload["reason"]
    assert not (tmp_path / "out").exists()


def test_cli_refuses_live_db_path(tmp_path, capsys):
    root = build_fixture(tmp_path / "data_root")
    rc = cli.main(
        [
            "context-generate",
            "--project",
            "tropical",
            "--data-root",
            str(root),
            "--out-dir",
            str(tmp_path / "out"),
            "--stamp",
            STAMP,
            "--db-backed",
            "--db-path",
            str(PathPolicy().get_db_path()),
        ]
    )
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "refused" and "live/default DB" in payload["reason"]


def test_cli_refuses_live_root_output(tmp_path, capsys):
    root = build_fixture(tmp_path / "data_root")
    bad_out = gen._DEFAULT_DATA_ROOT / "forecast_context_package_tropical_phase6cli"
    rc = cli.main(
        [
            "context-generate",
            "--project",
            "tropical",
            "--data-root",
            str(root),
            "--out-dir",
            str(bad_out),
            "--stamp",
            STAMP,
        ]
    )
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "refused" and "live forecast data root" in payload["reason"]
