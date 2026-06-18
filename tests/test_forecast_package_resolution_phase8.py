"""Phase 8 — controlled explicit package resolution + deterministic chain manifest.

Proves the CFR-only package-resolution layer: explicit context/analysis package directories resolve
to validated ForecastPackageRefs (no latest-glob), fail closed on every invalid identity, and a
context->analysis chain round-trips through a deterministic sorted-key manifest. One real
file-backed integration test runs the Phase 6 context runner + Phase 7 analysis runner to validate
the resolver's required-member lists against ACTUAL generator output.

Phase 8 adds no hb_assistant dependency, no DB, and no schema; this test imports neither hb_assistant
nor any DB layer. Everything runs under tmp_path.

build_fixture / _wj / _wjson below mirror tests/test_forecast_context_runner_phase6.py (duplicated,
not imported, so the proven Phase 5/6/7 tests stay independent).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review.analysis.final_forecast_runner import (  # noqa: E402
    run_final_forecast_generation,
)
from construction_financial_review.common import package_resolution as pr  # noqa: E402
from construction_financial_review.common.package_resolution import (  # noqa: E402
    ForecastPackageRef,
    PackageResolutionError,
)
from construction_financial_review.context.context_generation_runner import (  # noqa: E402
    run_context_generation,
)

BCK = "0000.03-01-025.MAT"  # mirrors Phase 5/6/7
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


def _wjson(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _fake_context(root: Path, stamp: str = STAMP) -> Path:
    """Structurally-valid (not generated) context package dir for fast resolver tests."""
    ctx = root / f"forecast_context_package_tropical_{stamp}"
    (ctx / "canonical").mkdir(parents=True)
    (ctx / "summaries").mkdir(parents=True)
    _wjson(ctx / "manifest.json", {"package_name": ctx.name})
    _wjson(ctx / "validation_report.json", {"passed": True})
    return ctx


def _fake_analysis(root: Path, stamp: str = STAMP) -> Path:
    """Structurally-valid (not generated) analysis package dir for fast resolver tests."""
    an = root / f"forecast_analysis_package_tropical_{stamp}"
    an.mkdir(parents=True)
    _wjson(an / "manifest.json", {"package_name": an.name})
    _wjson(an / "validation_report.json", {"passed": True})
    (an / "forecast_recommendations_by_budget_code.jsonl").write_text(
        json.dumps({"budget_code_key": BCK}) + "\n", encoding="utf-8"
    )
    return an


# --- 1 & 2. resolve valid explicit packages --------------------------------------------


def test_resolve_valid_context_package(tmp_path):
    ctx = _fake_context(tmp_path)
    ref = pr.resolve_explicit_package(package_kind="context", package_path=ctx)
    assert isinstance(ref, ForecastPackageRef)
    assert ref.project_key == "tropical"
    assert ref.package_kind == "context"
    assert ref.package_path == ctx
    assert ref.stamp == STAMP
    assert ref.source == "explicit"


def test_resolve_valid_analysis_package(tmp_path):
    an = _fake_analysis(tmp_path)
    ref = pr.resolve_explicit_package(package_kind="analysis", package_path=an)
    assert ref.package_kind == "analysis"
    assert ref.stamp == STAMP


# --- 3-8. fail-closed guards ------------------------------------------------------------


def test_refuse_missing_path(tmp_path):
    with pytest.raises(PackageResolutionError, match="not found"):
        pr.resolve_explicit_package(
            package_kind="context",
            package_path=tmp_path / f"forecast_context_package_tropical_{STAMP}",
        )


def test_refuse_file_not_directory(tmp_path):
    f = tmp_path / f"forecast_context_package_tropical_{STAMP}"
    f.write_text("not a dir", encoding="utf-8")
    with pytest.raises(PackageResolutionError, match="not a directory"):
        pr.resolve_explicit_package(package_kind="context", package_path=f)


def test_refuse_wrong_prefix(tmp_path):
    bad = tmp_path / "totally_wrong_name_20260101_000000"
    (bad / "canonical").mkdir(parents=True)
    (bad / "summaries").mkdir(parents=True)
    _wjson(bad / "manifest.json", {})
    _wjson(bad / "validation_report.json", {})
    with pytest.raises(PackageResolutionError, match="prefix"):
        pr.resolve_explicit_package(package_kind="context", package_path=bad)


def test_refuse_wrong_project_key(tmp_path):
    ctx = _fake_context(tmp_path)
    with pytest.raises(PackageResolutionError, match="unsupported project_key"):
        pr.resolve_explicit_package(
            package_kind="context", package_path=ctx, project_key="not-tropical"
        )


def test_refuse_unsupported_package_kind(tmp_path):
    ctx = _fake_context(tmp_path)
    with pytest.raises(PackageResolutionError, match="unsupported package_kind"):
        pr.resolve_explicit_package(package_kind="comprehensive", package_path=ctx)


def test_refuse_missing_required_member(tmp_path):
    ctx = _fake_context(tmp_path)
    # remove a required dir to make it structurally invalid
    (ctx / "summaries").rmdir()
    with pytest.raises(PackageResolutionError, match="structurally invalid"):
        pr.resolve_explicit_package(package_kind="context", package_path=ctx)


def test_refuse_live_root_package(tmp_path, monkeypatch):
    fake_live = tmp_path / "fake_live"
    monkeypatch.setattr(pr, "_LIVE_ROOT", fake_live)
    ctx = _fake_context(fake_live)
    with pytest.raises(PackageResolutionError, match="live forecast root"):
        pr.resolve_explicit_package(package_kind="context", package_path=ctx)


# --- 9. stamp parsing -------------------------------------------------------------------


def test_stamp_parsing_context_and_analysis(tmp_path):
    ctx = tmp_path / f"forecast_context_package_tropical_{STAMP}"
    an = tmp_path / "forecast_analysis_package_tropical_20260203_121314"
    assert pr.package_stamp_from_name(ctx, package_kind="context") == STAMP
    assert pr.package_stamp_from_name(an, package_kind="analysis") == "20260203_121314"
    with pytest.raises(PackageResolutionError, match="empty stamp"):
        pr.package_stamp_from_name(
            tmp_path / "forecast_context_package_tropical_", package_kind="context"
        )


# --- 10 & 11. deterministic chain manifest round-trip -----------------------------------


def test_chain_manifest_round_trip_and_determinism(tmp_path):
    ctx = _fake_context(tmp_path / "root")
    an = _fake_analysis(tmp_path / "root")
    ctx_ref = pr.resolve_explicit_package(package_kind="context", package_path=ctx)
    an_ref = pr.resolve_explicit_package(package_kind="analysis", package_path=an)
    chain = pr.build_package_chain(
        project_key="tropical", data_root=tmp_path / "root", refs=[ctx_ref, an_ref]
    )

    m1 = pr.write_package_chain_manifest(chain=chain, out_path=tmp_path / "a" / "chain.json")
    m2 = pr.write_package_chain_manifest(chain=chain, out_path=tmp_path / "b" / "chain.json")
    # Deterministic: identical bytes, sorted keys, trailing newline.
    assert m1.read_bytes() == m2.read_bytes()
    assert m1.read_text(encoding="utf-8").endswith("}\n")
    payload = json.loads(m1.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert list(payload["packages"]) == sorted(payload["packages"])  # sorted keys

    loaded = pr.read_package_chain_manifest(m1)
    assert loaded == chain
    assert loaded.packages["context"] == ctx_ref
    assert loaded.packages["analysis"] == an_ref


def test_read_manifest_rejects_bad_schema_version(tmp_path):
    bad = tmp_path / "chain.json"
    _wjson(bad, {"schema_version": 99, "project_key": "tropical", "data_root": ".", "packages": {}})
    with pytest.raises(PackageResolutionError, match="schema_version"):
        pr.read_package_chain_manifest(bad)


# --- real Phase 6 + Phase 7 output integration (file-backed only) -----------------------


def test_resolves_real_phase6_phase7_outputs(tmp_path):
    src = build_fixture(tmp_path / "src")
    ctx_dir = tmp_path / "root" / f"forecast_context_package_tropical_{STAMP}"
    cmeta = run_context_generation(data_root=src, out_dir=ctx_dir, stamp=STAMP)  # file-backed
    ameta = run_final_forecast_generation(context_package=Path(cmeta["output_package"]))

    ctx_ref = pr.resolve_explicit_package(
        package_kind="context", package_path=Path(cmeta["output_package"])
    )
    an_ref = pr.resolve_explicit_package(
        package_kind="analysis", package_path=Path(ameta["output_package"])
    )
    chain = pr.build_package_chain(
        project_key="tropical", data_root=ctx_ref.package_path.parent, refs=[ctx_ref, an_ref]
    )
    manifest = pr.write_package_chain_manifest(chain=chain, out_path=tmp_path / "chain.json")
    loaded = pr.read_package_chain_manifest(manifest)
    assert loaded == chain
    assert set(loaded.packages) == {"context", "analysis"}
    assert str(manifest).startswith(str(tmp_path))


# --- 13. CLI command --------------------------------------------------------------------


def test_cli_writes_manifest_from_explicit_paths(tmp_path, capsys):
    ctx = _fake_context(tmp_path / "root")
    an = _fake_analysis(tmp_path / "root")
    out = tmp_path / "chain.json"
    rc = cli.main(
        [
            "package-chain-manifest",
            "--project",
            "tropical",
            "--context-package",
            str(ctx),
            "--analysis-package",
            str(an),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["packages"]["context"]["stamp"] == STAMP
    assert out.is_file()
    reloaded = pr.read_package_chain_manifest(out)
    assert set(reloaded.packages) == {"context", "analysis"}


def test_cli_refuses_invalid_package(tmp_path, capsys):
    an = _fake_analysis(tmp_path / "root")
    rc = cli.main(
        [
            "package-chain-manifest",
            "--project",
            "tropical",
            "--context-package",
            str(tmp_path / "forecast_context_package_tropical_x"),
            "--analysis-package",
            str(an),
            "--out",
            str(tmp_path / "chain.json"),
        ]
    )
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "refused"
    assert not (tmp_path / "chain.json").exists()


def test_cli_refuses_live_root(tmp_path, capsys, monkeypatch):
    fake_live = tmp_path / "fake_live"
    monkeypatch.setattr(pr, "_LIVE_ROOT", fake_live)
    ctx = _fake_context(fake_live)
    an = _fake_analysis(fake_live)
    rc = cli.main(
        [
            "package-chain-manifest",
            "--project",
            "tropical",
            "--context-package",
            str(ctx),
            "--analysis-package",
            str(an),
            "--out",
            str(tmp_path / "chain.json"),
        ]
    )
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "refused" and "live forecast root" in payload["reason"]


# --- existing defaults preserved --------------------------------------------------------


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
    ff = parser.parse_args(
        ["final-forecast-generate", "--project", "tropical", "--context-package", "/x"]
    )
    assert ff.command == "final-forecast-generate"


# --- duplicated synthetic source fixture (mirrors Phase 5/6/7 build_fixture) ------------


def _wj(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


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
