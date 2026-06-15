"""History signals: remaining-forecast series, pattern class (stable-zero/nonzero/increasing/tapering)."""
from decimal import Decimal

from construction_financial_review.forecast_history_informed import history_signals as hs

MAP = {"budget_code_key": "1000.20-18-110.OVH", "mapping_status": "cost_code_unique_budget_match",
       "mapping_confidence": 1.0, "source_row_count": 5, "source_packages": ["cash_flow"],
       "duplicate_cost_code_warning": False, "description_sensitive_review": False,
       "distinct_descriptions": ["FEE"]}


def _fr(snap, pm, amt, cc="20-18-110"):
    return {"history_source_package": "cash_flow", "source_workbook": "W", "source_sheet": snap,
            "source_row": 1, "source_ref": "C", "snapshot_month": snap, "cost_code": cc,
            "description": "FEE", "raw_code_description": None, "period_month": pm,
            "classification": "forecast", "row_label_key": None, "amount": Decimal(str(amt))}


def _series_rows(pairs, cc="20-18-110"):
    """pairs = [(snapshot_month, remaining_total)] -> one forecast row each into a far-future month."""
    return [_fr(snap, "2099-01", amt, cc) for snap, amt in pairs]


def test_decreasing_tapering_pattern():
    rows = _series_rows([("2025-11", 854000), ("2025-12", 716000), ("2026-01", 573000),
                         ("2026-02", 550000), ("2026-04", 315000)])
    sig = hs.build_signal("20-18-110", rows, MAP, "tropical")
    assert sig["historical_pattern_class"] == "decreasing_tapering_exposure"
    assert Decimal(sig["historical_remaining_forecast_latest"]) == Decimal("315000.00")


def test_increasing_exposure_pattern():
    rows = _series_rows([("2025-11", 100000), ("2025-12", 150000), ("2026-01", 220000),
                         ("2026-02", 300000)])
    sig = hs.build_signal("X", rows, MAP, "tropical")
    assert sig["historical_pattern_class"] == "increasing_exposure"


def test_stable_zero_pattern():
    rows = _series_rows([("2025-11", 50000), ("2025-12", 0), ("2026-01", 0), ("2026-02", 0)])
    sig = hs.build_signal("X", rows, MAP, "tropical")
    assert sig["historical_pattern_class"] == "stable_zero"
    assert Decimal(sig["zero_remaining_persistence_score"]) > Decimal("0")


def test_inactive_all_zero():
    rows = _series_rows([("2025-11", 0), ("2025-12", 0), ("2026-01", 0)])
    sig = hs.build_signal("X", rows, MAP, "tropical")
    assert sig["historical_pattern_class"] == "inactive"


def test_stable_nonzero_pattern():
    rows = _series_rows([("2025-11", 200000), ("2025-12", 201000), ("2026-01", 199500),
                         ("2026-02", 200500)])
    sig = hs.build_signal("X", rows, MAP, "tropical")
    assert sig["historical_pattern_class"] == "stable_nonzero"


def test_volatile_pattern():
    rows = _series_rows([("2025-11", 10000), ("2025-12", 400000), ("2026-01", 5000),
                         ("2026-02", 350000)])
    sig = hs.build_signal("X", rows, MAP, "tropical")
    assert sig["historical_pattern_class"] == "volatile_review"
