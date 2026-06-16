import json
from pathlib import Path

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_actuals import actuals_erp_crosscheck as aec
from construction_financial_review.cli import build_parser


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _context(tmp_path, *, budget_rows=None, cost_rows=None, monthly_rows=None):
    root = tmp_path / "data"
    pkg = root / "forecast_context_package_tropical_test"
    budget_rows = budget_rows if budget_rows is not None else [
        {"budget_code_key": "1000.10-01-100.SUB", "cost_code": "10-01-100", "category": "SUB",
         "budget_code_description": "A", "amounts": {"erp_job_to_date_costs": "100.00"}},
        {"budget_code_key": "1000.10-01-200.MAT", "cost_code": "10-01-200", "category": "MAT",
         "budget_code_description": "B", "amounts": {"erp_job_to_date_costs": "0.00"}},
    ]
    cost_rows = cost_rows if cost_rows is not None else [
        {"budget_code_key": "1000.10-01-100.SUB", "mapped_budget_code_key": "1000.10-01-100.SUB",
         "mapping_status": "mapped", "accounting_date": "2026-05-01", "accounting_month": "2026-05",
         "amount_decimal_string": "60.00", "actual_period_bucket": "through_may_2026"},
        {"budget_code_key": "1000.10-01-100.SUB", "mapped_budget_code_key": "1000.10-01-100.SUB",
         "mapping_status": "mapped", "accounting_date": "2026-06-01", "accounting_month": "2026-06",
         "amount_decimal_string": "40.00", "actual_period_bucket": "june_2026_to_date"},
    ]
    monthly_rows = monthly_rows if monthly_rows is not None else [
        {"budget_code_key": "1000.10-01-100.SUB", "mapped_budget_code_key": "1000.10-01-100.SUB",
         "month": "2026-05", "amount_decimal_string": "60.00", "entry_count": 1, "source": "CostEntries"},
        {"budget_code_key": "1000.10-01-100.SUB", "mapped_budget_code_key": "1000.10-01-100.SUB",
         "month": "2026-06", "amount_decimal_string": "40.00", "entry_count": 1, "source": "CostEntries"},
    ]
    _write_jsonl(pkg / "canonical" / "budget_codes.jsonl", budget_rows)
    _write_jsonl(pkg / "canonical" / "cost_entries.jsonl", cost_rows)
    _write_jsonl(pkg / "canonical" / "monthly_actuals_by_budget_code.jsonl", monthly_rows)
    _write_json(pkg / "manifest.json", {
        "generated_stamp": "test",
        "project": {"project_key": "tropical", "name": "Tropical", "job": "23-435-01",
                    "package_period": "2026-June"},
        "validation_status": {"source_mutation": True},
        "source_files": [],
    })
    _write_json(pkg / "validation_report.json", {"passed": True})
    cfg = {
        "project_key": "tropical",
        "project_name": "Tropical",
        "job_reference": "23-435-01",
        "forecast_period": "2026-June",
        "default_data_root": str(root),
        "forecast_context_package": pkg.name,
        "actuals_erp_crosscheck": dict(aec.DEFAULT_CONFIG),
    }
    return root, pkg, cfg


def _build(tmp_path, **kwargs):
    _root, _pkg, cfg = _context(tmp_path, **kwargs)
    inputs = aec.load_context_inputs(cfg, "tropical")
    return aec.build_crosscheck_collections(inputs, cfg, "tropical", frozen_stamp="20260616_000000")


def test_cli_subcommand_registered():
    args = build_parser().parse_args([
        "actuals-erp-crosscheck", "--project", "tropical", "--frozen-stamp", "x",
        "--out-root", "/tmp/x", "--strict",
    ])
    assert args.command == "actuals-erp-crosscheck"
    assert args.strict is True


def test_exact_match_and_zero_actual_for_no_costentries(tmp_path):
    col = _build(tmp_path)
    rows = {r["budget_code_key"]: r for r in col["actuals_erp_crosscheck_by_budget_code.jsonl"]}
    assert rows["1000.10-01-100.SUB"]["variance_status"] == "matched"
    assert rows["1000.10-01-200.MAT"]["calculated_actual_cost_to_date"] == "0.00"
    assert rows["1000.10-01-200.MAT"]["variance_status"] == "matched"
    assert col["actuals_erp_crosscheck_summary.json"]["matched_count"] == 2


def test_one_cent_rounding_and_material_variance(tmp_path):
    budget = [
        {"budget_code_key": "1000.10-01-100.SUB", "cost_code": "10-01-100", "category": "SUB",
         "amounts": {"erp_job_to_date_costs": "100.01"}},
        {"budget_code_key": "1000.10-01-200.MAT", "cost_code": "10-01-200", "category": "MAT",
         "amounts": {"erp_job_to_date_costs": "10.00"}},
    ]
    cost = [
        {"budget_code_key": "1000.10-01-100.SUB", "mapped_budget_code_key": "1000.10-01-100.SUB",
         "mapping_status": "mapped", "accounting_date": "2026-05-01", "accounting_month": "2026-05",
         "amount_decimal_string": "100.00", "actual_period_bucket": "through_may_2026"},
        {"budget_code_key": "1000.10-01-200.MAT", "mapped_budget_code_key": "1000.10-01-200.MAT",
         "mapping_status": "mapped", "accounting_date": "2026-05-01", "accounting_month": "2026-05",
         "amount_decimal_string": "25.00", "actual_period_bucket": "through_may_2026"},
    ]
    monthly = [
        {"budget_code_key": r["mapped_budget_code_key"], "mapped_budget_code_key": r["mapped_budget_code_key"],
         "month": "2026-05", "amount_decimal_string": r["amount_decimal_string"], "entry_count": 1,
         "source": "CostEntries"} for r in cost
    ]
    col = _build(tmp_path, budget_rows=budget, cost_rows=cost, monthly_rows=monthly)
    rows = {r["budget_code_key"]: r for r in col["actuals_erp_crosscheck_by_budget_code.jsonl"]}
    assert rows["1000.10-01-100.SUB"]["variance_status"] == "rounding_only"
    assert rows["1000.10-01-200.MAT"]["variance_status"] == "material_variance"


def test_missing_erp_and_noncomparable_field_semantics(tmp_path):
    budget = [{"budget_code_key": "1000.10-01-100.SUB", "cost_code": "10-01-100", "category": "SUB",
               "amounts": {"projected_costs": "100.00"}}]
    _root, _pkg, cfg = _context(tmp_path, budget_rows=budget)
    cfg["actuals_erp_crosscheck"]["erp_cost_to_date_field"] = "amounts.projected_costs"
    inputs = aec.load_context_inputs(cfg, "tropical")
    col = aec.build_crosscheck_collections(inputs, cfg, "tropical")
    row = col["actuals_erp_crosscheck_by_budget_code.jsonl"][0]
    assert row["variance_status"] == "not_comparable_field_semantics"
    assert col["audit/actuals_erp_cost_to_date_field_audit.json"]["semantic_status"] == "not_comparable"


def test_duplicate_validation_after_canonical_normalization(tmp_path):
    budget = [
        {"budget_code_key": "1000.10-01-100.SUB", "cost_code": "10-01-100", "category": "SUB",
         "amounts": {"erp_job_to_date_costs": "100.00"}},
        {"budget_code_key": "1000.10-01-100.SUB", "cost_code": "10-01-100", "category": "SUB",
         "amounts": {"erp_job_to_date_costs": "100.00"}},
    ]
    col = _build(tmp_path, budget_rows=budget)
    assert col["validation_report.json"]["checks"]["no_duplicate_canonical_erp_rows"] is False


def test_unknown_costentry_mapping_and_malformed_actual(tmp_path):
    cost = [
        {"budget_code_key": "9999.99-99-999.SUB", "mapped_budget_code_key": None,
         "mapping_status": "invalid_budget_code_key", "accounting_date": "2026-05-01",
         "amount_decimal_string": "10.00"},
        {"budget_code_key": "1000.10-01-100.SUB", "mapped_budget_code_key": "1000.10-01-100.SUB",
         "mapping_status": "mapped", "accounting_date": "2026-05-01", "accounting_month": "2026-05",
         "amount_decimal_string": "not-money"},
    ]
    col = _build(tmp_path, cost_rows=cost, monthly_rows=[])
    assert col["validation_report.json"]["checks"]["calculated_actuals_input_reliable"] is False
    assert col["actuals_erp_crosscheck_by_budget_code.jsonl"][0]["variance_status"] == "missing_calculated_actual"


def test_monthly_reconciliation_statuses_and_negative_credit(tmp_path):
    cost = [
        {"budget_code_key": "1000.10-01-100.SUB", "mapped_budget_code_key": "1000.10-01-100.SUB",
         "mapping_status": "mapped", "accounting_date": "2026-05-01", "accounting_month": "2026-05",
         "amount_decimal_string": "110.00", "actual_period_bucket": "through_may_2026"},
        {"budget_code_key": "1000.10-01-100.SUB", "mapped_budget_code_key": "1000.10-01-100.SUB",
         "mapping_status": "mapped", "accounting_date": "2026-05-02", "accounting_month": "2026-05",
         "amount_decimal_string": "-10.00", "actual_period_bucket": "through_may_2026"},
    ]
    monthly = [{"budget_code_key": "1000.10-01-100.SUB", "mapped_budget_code_key": "1000.10-01-100.SUB",
                "month": "2026-05", "amount_decimal_string": "99.99", "entry_count": 2,
                "source": "CostEntries"}]
    col = _build(tmp_path, cost_rows=cost, monthly_rows=monthly)
    recon = {r["budget_code_key"]: r for r in col["actuals_monthly_reconciliation_by_budget_code.jsonl"]}
    assert recon["1000.10-01-100.SUB"]["calculated_actual_cost_to_date"] == "100.00"
    assert recon["1000.10-01-100.SUB"]["monthly_reconciliation_status"] == "rounding_only_variance"
    assert col["audit/actuals_month_assignment_audit.json"]["negative_corrections_credits_included"] is True


def test_strict_fails_material_variance_and_generate_manifest(tmp_path):
    budget = [{"budget_code_key": "1000.10-01-100.SUB", "cost_code": "10-01-100", "category": "SUB",
               "amounts": {"erp_job_to_date_costs": "1.00"}}]
    _root, _pkg, cfg = _context(tmp_path, budget_rows=budget)
    out_root = tmp_path / "out"
    res = aec.generate("tropical", cfg, frozen_stamp="20260616_000000", out_root=out_root, strict=True)
    out = Path(res["output_package"])
    assert res["validation_passed"] is False
    man = read_json(out / "manifest.json")
    listed = {f["path"] for f in man["output_files"]}
    for fname in aec.DATA_FILES + aec.AUDIT_FILES + ("validation_report.json", "README.md"):
        assert fname in listed
    assert man["generation"]["mode"] == "strict"
    assert man["source_hashes_unchanged"] is True


def test_frozen_stamp_determinism(tmp_path):
    _root, _pkg, cfg = _context(tmp_path)
    a = Path(aec.generate("tropical", cfg, frozen_stamp="20260616_000000",
                          out_root=tmp_path / "a")["output_package"])
    b = Path(aec.generate("tropical", cfg, frozen_stamp="20260616_000000",
                          out_root=tmp_path / "b")["output_package"])
    for rel in (
        "actuals_erp_crosscheck_by_budget_code.jsonl",
        "actuals_erp_crosscheck_summary.json",
        "actuals_monthly_reconciliation_by_budget_code.jsonl",
        "audit/actuals_erp_variance_audit.json",
    ):
        assert (a / rel).read_bytes() == (b / rel).read_bytes()


def test_category_split_preserved(tmp_path):
    col = _build(tmp_path)
    rows = list(read_jsonl(Path(aec.generate(
        "tropical", _context(tmp_path / "gen")[2], frozen_stamp="20260616_000000",
        out_root=tmp_path / "out")["output_package"]) / "actuals_erp_crosscheck_by_budget_code.jsonl"))
    assert {(r["cost_code"], r["category"]) for r in rows} == {("10-01-100", "SUB"), ("10-01-200", "MAT")}
    assert col["audit/actuals_mapping_audit.json"]["mapping_basis"].startswith("canonical budget_code_key")
