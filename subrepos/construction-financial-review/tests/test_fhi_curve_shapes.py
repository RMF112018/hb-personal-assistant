"""Curve-shape classifier on the latest-snapshot monthly forecast curve."""
from decimal import Decimal

from construction_financial_review.forecast_history_informed import history_signals as hs


def _curve(amounts, start=(2026, 5)):
    out, y, m = [], start[0], start[1]
    for a in amounts:
        out.append((f"{y:04d}-{m:02d}", Decimal(str(a))))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def test_stable_zero_curve():
    assert hs.classify_curve_shape(_curve([0, 0, 0, 0])) == "stable_zero"


def test_inactive_empty_curve():
    assert hs.classify_curve_shape([]) == "inactive"


def test_flat_curve():
    assert hs.classify_curve_shape(_curve([100, 102, 99, 101])) == "flat"


def test_spike_curve():
    assert hs.classify_curve_shape(_curve([5, 500, 5, 5])) == "spike"


def test_tapering_curve():
    assert hs.classify_curve_shape(_curve([300, 200, 100, 0])) == "tapering_closeout"


def test_back_loaded_curve():
    assert hs.classify_curve_shape(_curve([10, 40, 90, 160])) == "back_loaded"


def test_front_loaded_curve():
    assert hs.classify_curve_shape(_curve([160, 90, 40, 12])) == "front_loaded"
