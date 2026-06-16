"""Combined actuals+forecast monthly-by-cost-code CSV (comprehensive package): boundary, rollup, audit.

Unit tests use synthetic actuals + integrated-forecast rows (no data root). The e2e test runs
forecast-comprehensive with the (unrelated) operator-controls layer disabled in a config copy so it
exercises the export without the inherited ambiguous-control blocker; skipped if the data root is absent.
"""
import copy
from decimal import Decimal
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json
from construction_financial_review.forecast_actuals import actuals_export as ax

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]

# two cost codes: 15-16-110 has actuals + forecast (two budget keys); 99-99-999 has forecast only;
# 88-88-888 has actuals only. Boundary (min forecast month) = 2026-06.
ACTUALS_CC = []
for cc, desc, vals in [
    ("15-16-110", "ELECTRICAL", {"2026-04": "100.00", "2026-05": "200.00", "2026-06": "999.00"}),
    ("88-88-888", "SITEWORK", {"2026-04": "10.00", "2026-05": "20.00"}),
]:
    for m in ("2026-04", "2026-05", "2026-06"):
        ACTUALS_CC.append({"cost_code": cc, "cost_code_description": desc, "month": m,
                           "actual_cost": vals.get(m, "0.00"), "entry_count": 1})
ACTUALS_BC = [
    {"budget_code_key": "1000.15-16-110.SUB", "cost_code": "15-16-110", "cost_type": "SUB",
     "budget_code_description": "ELECTRICAL.Sub", "month": "2026-05", "actual_cost": "150.00"},
    {"budget_code_key": "1000.15-16-110.MAT", "cost_code": "15-16-110", "cost_type": "MAT",
     "budget_code_description": "ELECTRICAL.Mat", "month": "2026-05", "actual_cost": "50.00"},
    {"budget_code_key": "1000.88-88-888.SUB", "cost_code": "88-88-888", "cost_type": "SUB",
     "budget_code_description": "SITEWORK", "month": "2026-05", "actual_cost": "20.00"},
]
INTEGRATED = [
    {"budget_code_key": "1000.15-16-110.SUB", "cost_code": "15-16-110",
     "monthly_costs": [{"forecast_month": "2026-06", "integrated_month_cost": "300.00"},
                       {"forecast_month": "2026-07", "integrated_month_cost": "400.00"}]},
    {"budget_code_key": "1000.15-16-110.MAT", "cost_code": "15-16-110",
     "monthly_costs": [{"forecast_month": "2026-06", "integrated_month_cost": "30.00"},
                       {"forecast_month": "2026-07", "integrated_month_cost": "20.00"}]},
    {"budget_code_key": "1000.99-99-999.SUB", "cost_code": "99-99-999",
     "monthly_costs": [{"forecast_month": "2026-06", "integrated_month_cost": "500.00"}]},
]


def _build():
    return ax.build_actuals_plus_forecast("tropical", [], ACTUALS_CC, ACTUALS_BC, INTEGRATED)


def test_csv_shape_first_column_and_sorted_months():
    col = _build()["actuals_plus_forecast_monthly_by_cost_code.csv"]
    assert col["fieldnames"][0] == "cost_code"
    months = col["fieldnames"][1:]
    assert months == sorted(months)
    assert months[0] == "2026-04" and months[-1] == "2026-07"   # union actual(04-06)+forecast(06-07)
    assert [r["cost_code"] for r in col["rows"]] == ["15-16-110", "88-88-888", "99-99-999"]  # union, sorted


def test_boundary_actuals_before_forecast_from_current_month():
    rows = {r["cost_code"]: r for r in _build()["actuals_plus_forecast_monthly_by_cost_code.csv"]["rows"]}
    e = rows["15-16-110"]
    assert e["2026-04"] == "100.00" and e["2026-05"] == "200.00"   # actuals (< boundary)
    assert e["2026-06"] == "330.00"                                 # forecast rollup 300+30 (>= boundary)
    assert e["2026-07"] == "420.00"                                 # forecast 400+20


def test_june_2026_actual_does_not_leak():
    # 15-16-110 has a 2026-06 actual of 999.00, but the combined file must show the forecast (330.00)
    e = {r["cost_code"]: r for r in _build()["actuals_plus_forecast_monthly_by_cost_code.csv"]["rows"]}["15-16-110"]
    assert e["2026-06"] == "330.00" and e["2026-06"] != "999.00"


def test_zero_fill_and_union_membership():
    rows = {r["cost_code"]: r for r in _build()["actuals_plus_forecast_monthly_by_cost_code.csv"]["rows"]}
    assert rows["99-99-999"]["2026-04"] == "0.00"   # forecast-only code: zero in actual months
    assert rows["99-99-999"]["2026-06"] == "500.00"
    assert rows["88-88-888"]["2026-06"] == "0.00"   # actuals-only code: zero in forecast months
    assert rows["88-88-888"]["2026-05"] == "20.00"


def test_budget_code_csv_present_and_boundary():
    col = _build()["actuals_plus_forecast_monthly_by_budget_code.csv"]
    assert col["fieldnames"][:4] == ["budget_code_key", "cost_code", "cost_type", "budget_code_description"]
    r = {x["budget_code_key"]: x for x in col["rows"]}["1000.15-16-110.SUB"]
    assert r["2026-05"] == "150.00" and r["2026-06"] == "300.00"


def test_audit_boundaries_totals_and_reconciliation():
    aud = _build()[ax.ACTUALS_PLUS_FORECAST_AUDIT_FILE]
    assert aud["current_forecast_month"] == "2026-06"
    assert aud["actual_month_start"] == "2026-04" and aud["actual_month_end"] == "2026-05"
    assert aud["forecast_month_start"] == "2026-06" and aud["forecast_month_end"] == "2026-07"
    assert aud["cost_code_count"] == 3
    # actual side: 100+200 (elec 04,05) + 10+20 (site 04,05) = 330.00 ; June actuals excluded
    assert aud["actual_total"] == "330.00"
    # forecast side: 330+420 (elec) + 500 (99) = 1250.00
    assert aud["forecast_total"] == "1250.00"
    assert aud["combined_total"] == "1580.00"
    assert aud["actual_months_reconciled"] is True
    assert aud["forecast_months_reconciled"] is True
    assert aud["validation_passed"] is True


def test_combined_validation_gates_pass():
    col = _build()
    gates = ax.combined_validation_gates(col)
    assert all(gates.values()), [k for k, v in gates.items() if not v]


def test_determinism_identical():
    a, b = _build(), _build()
    assert a["actuals_plus_forecast_monthly_by_cost_code.csv"] == b["actuals_plus_forecast_monthly_by_cost_code.csv"]
    assert a[ax.ACTUALS_PLUS_FORECAST_AUDIT_FILE] == b[ax.ACTUALS_PLUS_FORECAST_AUDIT_FILE]


def test_money_two_decimals_no_float():
    rows = _build()["actuals_plus_forecast_monthly_by_cost_code.csv"]["rows"]
    for r in rows:
        for k, v in r.items():
            if k != "cost_code":
                assert isinstance(v, str) and v.count(".") == 1 and len(v.split(".")[1]) == 2


# --------------------------------------------------------------------------- e2e (controls disabled)

CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
_e2e = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_monthly_package_tropical_*"))),
    reason="local data root / required packages not present")


@_e2e
def test_comprehensive_emits_combined_csv(tmp_path):
    from construction_financial_review.forecast_comprehensive import \
        generate_comprehensive_forecast_package as gen
    cfg = copy.deepcopy(CFG)
    cfg.setdefault("forecast_controls", {})["enabled"] = False   # isolate from the inherited control gate
    out = Path(gen.generate("tropical", cfg, data_root=DATA_ROOT, frozen_stamp="20260101_000000",
                            out_root=tmp_path)["output_package"])
    for f in ax.ACTUALS_PLUS_FORECAST_FILES:
        assert (out / f).exists(), f
    aud = read_json(out / ax.ACTUALS_PLUS_FORECAST_AUDIT_FILE)
    assert aud["current_forecast_month"] == "2026-06"
    assert aud["actual_month_end"] == "2026-05" and aud["forecast_month_start"] == "2026-06"
    assert aud["validation_passed"] is True
    man = read_json(out / "manifest.json")
    listed = {f["path"] for f in man["output_files"]}
    assert all(f in listed for f in ax.ACTUALS_PLUS_FORECAST_FILES)
    rep = read_json(out / "validation_report.json")
    assert all(v for k, v in rep["checks"].items() if k.startswith("actuals_plus_forecast"))
