"""CostEntries + subcontractor invoice monthly trends: shaped vectors, unavailable marking."""
from decimal import Decimal

from construction_financial_review.forecast_monthly import (cost_entry_trends as cet,
                                                            subcontractor_invoice_trends as sit)

MONTHS = ["2026-06", "2026-07", "2026-08"]


def _ca(values, start=(2025, 1)):
    out, y, m = [], start[0], start[1]
    for v in values:
        out.append({"month": f"{y:04d}-{m:02d}", "amount_decimal_string": str(v),
                    "actual_period_bucket": "through_may_2026"})
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def test_cost_shape_weights_sum_to_one():
    # exact fractions sum to 1 within Decimal precision (the reconciler ties to the cent separately)
    for kind in (cet.FLAT, cet.FRONT, cet.BACK):
        w = cet.shape_weights(MONTHS, kind)
        assert abs(sum(w.values(), Decimal("0")) - Decimal("1")) < Decimal("1e-40")


def test_accelerating_front_loaded():
    row, w = cet.analyze(_ca([100, 100, 100, 300, 300, 300]), MONTHS, "tropical", "K")
    assert row["cost_entry_trend_shape"] == cet.FRONT
    assert w["2026-06"] > w["2026-08"]      # front-loaded


def test_decelerating_back_loaded():
    row, w = cet.analyze(_ca([300, 300, 300, 50, 50, 50]), MONTHS, "tropical", "K")
    assert row["cost_entry_trend_shape"] == cet.BACK
    assert w["2026-08"] > w["2026-06"]      # back-loaded


def test_flat_recent_burn():
    row, w = cet.analyze(_ca([100, 100, 100, 100, 100, 100]), MONTHS, "tropical", "K")
    assert row["cost_entry_trend_shape"] == cet.FLAT
    assert w["2026-06"] == w["2026-08"]


def test_credit_adjusted():
    row, _ = cet.analyze(_ca([100, 100, 100, 100, 100, -40]), MONTHS, "tropical", "K")
    assert row["cost_entry_trend_shape"] == cet.CREDIT


def test_invoice_unavailable_when_no_rows():
    row, vec = sit.analyze([], MONTHS, "tropical", "K", "2026-05")
    assert row["invoice_evidence"] == "unavailable"
    assert vec is None


def test_invoice_available_builds_vector():
    rows = [{"mapping_status": "mapped", "period_end": f"2026-0{m}-25",
             "work_completed_this_period": "1000", "total_completed_and_stored_to_date": str(1000 * m),
             "scheduled_value": "10000", "retainage_held": "100"} for m in (1, 2, 3)]
    row, vec = sit.analyze(rows, MONTHS, "tropical", "K", "2026-03")
    assert row["invoice_evidence"] == "available"
    assert row["historical_invoice_periods"] == 3
    assert vec is not None


def test_invoice_never_emits_actual_field():
    rows = [{"mapping_status": "mapped", "period_end": "2026-03-25",
             "work_completed_this_period": "1000", "scheduled_value": "10000"}]
    row, _ = sit.analyze(rows, MONTHS, "tropical", "K", "2026-03")
    assert not any("actual_cost" in k for k in row)
