"""Monthly actuals export contract: dense matrix, reconciliation, contamination guard, determinism.

Unit tests use a synthetic CostEntries dataset (no data root). E2e tests run forecast-intelligence
(the forecast_accuracy_next producer, not gated by the controls layer) and skip when the data root /
required packages are absent.
"""
from decimal import Decimal
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_actuals import actuals_export as ax

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]

# ---- synthetic canonical universe: two cost codes, one with two categories, one zero-activity code ----
BUDGET_CODES = [
    {"budget_code_key": "1000.15-07-590.SUB", "cost_code": "15-07-590", "category": "SUB",
     "budget_code_description": "ROOFING"},
    {"budget_code_key": "1000.15-07-590.MAT", "cost_code": "15-07-590", "category": "MAT",
     "budget_code_description": "ROOFING MATERIALS"},
    {"budget_code_key": "1000.10-01-318.LAB", "cost_code": "10-01-318", "category": "LAB",
     "budget_code_description": "PROJECT MANAGER"},  # zero-activity code
]
MONTHLY = {
    "1000.15-07-590.SUB": {
        "2026-03": {"amount": Decimal("100.00"), "count": 2, "first": "2026-03-05", "last": "2026-03-20"},
        "2026-05": {"amount": Decimal("250.50"), "count": 3, "first": "2026-05-01", "last": "2026-05-31"}},
    "1000.15-07-590.MAT": {
        "2026-04": {"amount": Decimal("40.00"), "count": 1, "first": "2026-04-10", "last": "2026-04-10"}},
}
TO_DATE = {"1000.15-07-590.SUB": "350.50", "1000.15-07-590.MAT": "40.00", "1000.10-01-318.LAB": "0.00"}
CANON = {b["budget_code_key"] for b in BUDGET_CODES}


def _build():
    return ax.build_collections("tropical", BUDGET_CODES, MONTHLY, TO_DATE)


def test_dense_every_canonical_key_every_month_no_sentinel():
    col = _build()
    rows = col["actuals_monthly_by_budget_code.jsonl"]
    months = ["2026-03", "2026-04", "2026-05"]   # contiguous axis from min..max activity
    assert all(r["month"] is not None for r in rows), "no month:null sentinel allowed"
    assert all(r["is_actual"] is True for r in rows)
    # every canonical key has exactly one row per month
    for key in CANON:
        kr = {r["month"]: r for r in rows if r["budget_code_key"] == key}
        assert set(kr) == set(months), key
    # zero-activity months: 0.00 / 0 / null dates, still is_actual true
    z = next(r for r in rows if r["budget_code_key"] == "1000.10-01-318.LAB" and r["month"] == "2026-03")
    assert z["actual_cost"] == "0.00" and z["entry_count"] == 0
    assert z["first_cost_entry_date"] is None and z["last_cost_entry_date"] is None
    assert z["is_actual"] is True and z["actual_source"] == "CostEntries"


def test_money_is_two_decimal_strings():
    rows = _build()["actuals_monthly_by_budget_code.jsonl"]
    r = next(r for r in rows if r["budget_code_key"] == "1000.15-07-590.SUB" and r["month"] == "2026-05")
    assert r["actual_cost"] == "250.50" and isinstance(r["actual_cost"], str)


def test_csv_matrix_dimensions_and_ordering_and_zero_fill():
    col = _build()
    csv = col["actuals_monthly_by_budget_code.csv"]
    assert csv["fieldnames"][:4] == ["budget_code_key", "cost_code", "cost_type", "budget_code_description"]
    assert csv["fieldnames"][4:] == ["2026-03", "2026-04", "2026-05"]  # months ascending
    assert len(csv["rows"]) == len(BUDGET_CODES)                       # one row per canonical code
    assert [r["budget_code_key"] for r in csv["rows"]] == sorted(CANON)  # sorted by budget_code_key
    pm = next(r for r in csv["rows"] if r["budget_code_key"] == "1000.10-01-318.LAB")
    assert pm["2026-03"] == "0.00" and pm["2026-05"] == "0.00"          # zero-fill
    cc_csv = col["actuals_monthly_by_cost_code.csv"]
    assert cc_csv["fieldnames"][:2] == ["cost_code", "cost_code_description"]
    assert [r["cost_code"] for r in cc_csv["rows"]] == ["10-01-318", "15-07-590"]  # sorted by cost_code


def test_cost_code_rollup_and_project_total_reconcile():
    col = _build()
    audit = col[ax.ACTUALS_AUDIT_FILE]
    assert audit["budget_code_equals_cost_code_total"] is True
    assert audit["budget_code_equals_project_total"] is True
    assert audit["project_monthly_total"] == "390.50"   # 350.50 + 40.00
    # cost-code 15-07-590 May == its SUB row (MAT has no May)
    cc = {(r["cost_code"], r["month"]): r["actual_cost"]
          for r in col["actuals_monthly_by_cost_code.jsonl"]}
    assert cc[("15-07-590", "2026-05")] == "250.50"


def test_bridge_reconciles_to_actual_cost_to_date():
    col = _build()
    bridge = {r["budget_code_key"]: r for r in col["actuals_to_forecast_bridge_by_budget_code.jsonl"]}
    sub = bridge["1000.15-07-590.SUB"]
    assert sub["exported_monthly_actuals_total"] == "350.50"
    assert sub["actual_cost_to_date"] == "350.50"
    assert sub["reconciliation_difference"] == "0.00" and sub["reconciles"] is True
    assert sub["last_nonzero_actual_month"] == "2026-05"
    assert col[ax.ACTUALS_AUDIT_FILE]["all_codes_reconcile_to_actual_cost_to_date"] is True


def test_validation_gates_all_pass_for_clean_build():
    col = _build()
    gates = ax.validation_gates(col, CANON, contamination_ok=True)
    assert all(gates.values()), [k for k, v in gates.items() if not v]


def test_rec_row_fields():
    f = ax.rec_row_fields(MONTHLY["1000.15-07-590.SUB"])
    assert f["actuals_monthly_total_to_date"] == "350.50"
    assert f["actuals_latest_month"] == "2026-05"
    assert f["actuals_latest_month_amount"] == "250.50"
    assert f["actuals_month_count_nonzero"] == 2
    assert f["actuals_last_nonzero_month"] == "2026-05"


def test_no_contamination_costentries_only(tmp_path):
    """The loader accepts only source == CostEntries; any other source flips contamination_ok."""
    ctx = tmp_path / "ctx" / "canonical"
    ctx.mkdir(parents=True)
    import json
    with open(ctx.parent / "canonical" / "monthly_actuals_by_budget_code.jsonl", "w") as fh:
        fh.write(json.dumps({"budget_code_key": "1000.15-07-590.SUB", "month": "2026-05",
                             "amount_decimal_string": "10.00", "entry_count": 1,
                             "source": "owner_pay_application"}) + "\n")
    load = ax.load_costentries_monthly(tmp_path / "ctx")
    assert load["contamination_ok"] is False
    assert load["by_key"] == {}              # the non-CostEntries row is excluded, never an actual
    assert load["non_costentries_rows"]


def test_determinism_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    (a / "audit").mkdir(parents=True); (b / "audit").mkdir(parents=True)
    ax.write_collections(a, _build())
    ax.write_collections(b, _build())
    from construction_financial_review.common.hashing import sha256_file
    for f in ax.ACTUALS_FILES:
        assert sha256_file(a / f) == sha256_file(b / f), f


# --------------------------------------------------------------------------- e2e (controls-independent)

CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
_e2e = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_analysis_package_tropical_crosswalk_v2_*"))),
    reason="local data root / required packages not present")


@_e2e
def test_forecast_intelligence_emits_actuals(tmp_path):
    from construction_financial_review.forecast_intelligence import \
        generate_forecast_intelligence_package as gen
    out = Path(gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp="20260101_000000",
                            out_root=tmp_path)["output_package"])
    rep = read_json(out / "validation_report.json")
    assert rep["passed"] is True, [k for k, v in rep["checks"].items() if not v]
    for f in ax.ACTUALS_FILES:
        assert (out / f).exists(), f
    # all canonical keys covered in the dense export
    canon = {b["budget_code_key"] for b in read_jsonl(out / "forecast_recommendations_by_budget_code.jsonl")}
    keys = {r["budget_code_key"] for r in read_jsonl(out / "actuals_monthly_by_budget_code.jsonl")}
    assert canon <= keys
    # manifest lists the actuals files with hashes
    man = read_json(out / "manifest.json")
    listed = {f["path"] for f in man["output_files"]}
    assert all(f in listed for f in ax.ACTUALS_FILES)
    # recommendation rows carry the 5 additive actuals fields
    r = next(iter(read_jsonl(out / "forecast_recommendations_by_budget_code.jsonl")))
    for fld in ("actuals_monthly_total_to_date", "actuals_latest_month", "actuals_latest_month_amount",
                "actuals_month_count_nonzero", "actuals_last_nonzero_month"):
        assert fld in r
