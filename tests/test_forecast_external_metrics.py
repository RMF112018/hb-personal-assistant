"""Phase 4 — external-forecast accuracy metric primitives (pure Decimal math)."""

from __future__ import annotations

from decimal import Decimal

from hb_assistant.construction.analytics.forecast_external_metrics import (
    Pair,
    aligned_pairs,
    compute_metrics,
    gap,
    to_decimal,
)


def test_to_decimal_parses_money_forms() -> None:
    assert to_decimal("1,234.50") == Decimal("1234.50")
    assert to_decimal("$2000") == Decimal("2000")
    assert to_decimal("(500)") == Decimal("-500")
    assert to_decimal(42) == Decimal("42")
    assert to_decimal("") is None
    assert to_decimal("n/a") is None
    assert to_decimal(None) is None
    assert to_decimal(True) is None


def test_aligned_pairs_intersects_numeric_keys_in_sorted_order() -> None:
    ext = {"b": "200", "a": "110", "x": "n/a"}
    base = {"a": "100", "b": "250", "c": "5"}
    pairs = aligned_pairs(ext, base)
    assert [(str(p.external), str(p.baseline)) for p in pairs] == [("110", "100"), ("200", "250")]


def test_compute_metrics_known_values() -> None:
    pairs = [Pair(Decimal("110"), Decimal("100")), Pair(Decimal("200"), Decimal("250"))]
    m = compute_metrics(pairs)
    assert m["variance"] == "-40.00"  # (10) + (-50)
    assert m["mae"] == "30.00"  # (10+50)/2
    assert m["bias"] == "-20.00"  # -40/2
    assert m["mape"] == "0.1500"  # mean(0.1, 0.2)
    assert m["wape"] == "0.1714"  # 60/350
    assert m["rmse"] == "36.06"  # sqrt((100+2500)/2)


def test_compute_metrics_zero_guard_excludes_zero_baseline_from_ratios() -> None:
    pairs = [Pair(Decimal("10"), Decimal("0")), Pair(Decimal("120"), Decimal("100"))]
    m = compute_metrics(pairs)
    # variance/mae still include the zero-baseline row; mape/wape exclude it.
    assert m["variance"] == "30.00"
    assert m["mape"] == "0.2000"  # only the 120 vs 100 row
    assert m["wape"] == "0.2000"  # 20 / 100


def test_compute_metrics_empty_is_no_sample() -> None:
    assert compute_metrics([]) == {}


def test_gap_zero_guards_percent() -> None:
    assert gap("110", "100") == ("10.00", "0.1000")
    assert gap("110", "0") == ("110.00", None)
    assert gap("x", "100") == (None, None)
