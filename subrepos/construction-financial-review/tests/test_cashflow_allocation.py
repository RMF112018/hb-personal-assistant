"""Cash-flow timing allocation: ties to exposure, medium-capped confidence, not_allocated cases."""
from decimal import Decimal

from construction_financial_review.common.money import D
from construction_financial_review.schedule_analysis import cashflow


def _feat(rem_start, rem_finish):
    return {"remaining_start": rem_start, "remaining_finish": rem_finish}


def test_allocation_ties_to_exposure_across_months():
    feats = [
        _feat("2026-06-01T08:00:00", "2026-06-30T16:00:00"),
        _feat("2026-07-01T08:00:00", "2026-08-15T16:00:00"),
    ]
    rows = cashflow.allocate_budget_code("1000.15-02-010.SUB", "tropical", Decimal("1000.00"), feats)
    alloc = [r for r in rows if r["allocation_method"] != cashflow.ALLOC_NOT_ALLOCATED]
    assert len(alloc) >= 2
    total = sum((D(r["scheduled_allocation_amount"]) for r in alloc), Decimal("0"))
    assert total == Decimal("1000.00")                      # ties exactly (last month absorbs rounding)
    assert cashflow.allocation_ties(rows, Decimal("1000.00")) is True


def test_confidence_capped_at_medium():
    feats = [_feat("2026-06-01T08:00:00", "2026-06-30T16:00:00")]
    rows = cashflow.allocate_budget_code("k", "tropical", Decimal("500.00"), feats)
    assert all(r["allocation_confidence"] == "medium" for r in rows
               if r["allocation_method"] != cashflow.ALLOC_NOT_ALLOCATED)


def test_missing_dates_not_allocated():
    rows = cashflow.allocate_budget_code("k", "tropical", Decimal("500.00"),
                                         [_feat(None, None)])
    assert len(rows) == 1
    assert rows[0]["allocation_method"] == cashflow.ALLOC_NOT_ALLOCATED


def test_zero_exposure_not_allocated():
    feats = [_feat("2026-06-01T08:00:00", "2026-06-30T16:00:00")]
    rows = cashflow.allocate_budget_code("k", "tropical", Decimal("0"), feats)
    assert rows[0]["allocation_method"] == cashflow.ALLOC_NOT_ALLOCATED
    assert cashflow.allocation_ties(rows, Decimal("0")) is True


def test_remaining_forecast_exposure_floor_and_higher_recommended():
    # projected - actual
    assert cashflow.remaining_forecast_exposure("100.00", "30.00") == Decimal("70.00")
    # actual exceeds projected -> zero floor
    assert cashflow.remaining_forecast_exposure("100.00", "150.00") == Decimal("0")
    # schedule-integrated recommended higher than projected (floor-to-actuals) is used as basis
    assert cashflow.remaining_forecast_exposure("100.00", "120.00", "120.00") == Decimal("0")
    assert cashflow.remaining_forecast_exposure("100.00", "90.00", "130.00") == Decimal("40.00")


def test_single_month_allocation_full_exposure():
    feats = [_feat("2026-06-05T08:00:00", "2026-06-20T16:00:00")]
    rows = cashflow.allocate_budget_code("k", "tropical", Decimal("250.00"), feats)
    alloc = [r for r in rows if r["allocation_method"] != cashflow.ALLOC_NOT_ALLOCATED]
    assert len(alloc) == 1
    assert alloc[0]["month"] == "2026-06"
    assert alloc[0]["scheduled_allocation_amount"] == "250.00"
