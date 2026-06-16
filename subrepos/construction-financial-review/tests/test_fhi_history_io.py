"""History IO: normalize cash-flow + GC/GR rows; null/zero/numeric/formula/"-" handling; ordering."""
from decimal import Decimal

from construction_financial_review.forecast_history_informed import history_io


def test_normalize_cashflow_numeric_and_classification():
    r = {"source_workbook": "CashFlow-Forecast-History.xlsx", "source_sheet": "04-February-2025",
         "source_row": 7, "source_column": "C", "forecast_month": "2025-02", "cost_code": "02-21-00",
         "description": "Survey", "raw_code_description": "02 21 00 - Survey", "period_month": "2025-05",
         "period_type": "forecast", "amount": 20000.0, "formula": None}
    n = history_io.normalize_cashflow_row(r)
    assert n["history_source_package"] == "cash_flow"
    assert n["classification"] == "forecast"
    assert n["amount"] == Decimal("20000.0")
    assert n["source_ref"] == "C"


def test_normalize_cashflow_null_and_dash_amounts():
    base = {"source_sheet": "s", "source_row": 1, "cost_code": "00-73-00", "period_month": "2025-01",
            "period_type": "actual"}
    assert history_io.normalize_cashflow_row({**base, "amount": None})["amount"] is None
    assert history_io.normalize_cashflow_row({**base, "amount": "-"})["amount"] is None
    assert history_io.normalize_cashflow_row({**base, "amount": 0})["amount"] == Decimal("0")


def test_normalize_gcgr_amount_type_and_zero():
    r = {"source_sheet": "01-November-2024", "shape": "shape_1", "source_row": 13,
         "row_label_raw": "Proj/Actual", "row_label_key": "proj_actual", "forecast_month": "2024-11",
         "cost_code": "10-01-025", "description": "Plans/Printing", "budget": 8500.0,
         "cost_code_unresolved": False, "source_cell": "F13", "period_month": "2024-11",
         "amount_type": "actual", "amount": 0.0, "formula": None}
    n = history_io.normalize_gcgr_row(r)
    assert n["history_source_package"] == "gcgr"
    assert n["classification"] == "actual"
    assert n["amount"] == Decimal("0.0")
    assert n["source_ref"] == "F13"
    assert n["row_label_key"] == "proj_actual"


def test_reconcile_counts_flags_mismatch(tmp_path, monkeypatch):
    rows = [{"history_source_package": "cash_flow"} for _ in range(3)]
    # documented (5) != observed (3) -> not reconciled
    monkeypatch.setattr(history_io, "_documented_counts",
                        lambda c, g: {"cash_flow": {"monthly_values_including_zero": 5}})
    rec = history_io.reconcile_counts(object(), None, rows)
    assert rec["reconciled"] is False
    assert rec["observed_monthly_values"]["cash_flow"] == 3
