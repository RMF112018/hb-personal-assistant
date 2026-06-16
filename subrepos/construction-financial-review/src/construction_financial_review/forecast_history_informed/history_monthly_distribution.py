"""Advisory monthly-distribution suggestion from the historical curve shape (never auto-applied).

The historical forecast curve is a SHAPE hint only. It is blended with the current monthly package's
source weights (schedule / cost-entries / invoice) in proportion to history reliability, and only when
schedule evidence is not already strong. Output is advisory; it never edits the accepted monthly package.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

ZERO = Decimal("0")
ONE = Decimal("1")


def _d(x, default=ZERO):
    try:
        return Decimal(str(x))
    except Exception:
        return default


def _q4(x):
    return str(Decimal(x).quantize(Decimal("0.0001")))


def build_distribution(signal: dict, validation: dict, reliability: dict, monthly_row: dict,
                       cfg_fhi: dict, project_key: str) -> OrderedDict:
    key = signal.get("budget_code_key")
    mr = monthly_row or {}
    shares = mr.get("source_shares") or {}
    sched_w = _d(shares.get("schedule_weight"))
    ce_w = _d(shares.get("cost_entries_weight"))
    inv_w = _d(shares.get("subcontractor_invoice_weight"))
    # explicit: did we have real accepted monthly source-share evidence, or did we fall back to equal?
    source_shares_available = (sched_w + ce_w + inv_w) > ZERO

    reliability_score = _d(reliability.get("overall_history_reliability_score"))
    curve_shape = signal.get("latest_curve_shape_class")
    informative = curve_shape not in (None, "inactive", "stable_zero", "volatile_review")
    w_val = _d(cfg_fhi.get("history_max_weight_when_validated"), Decimal("0.45"))
    # history curve earns weight only when informative AND schedule is not already dominant
    history_curve_weight = (w_val * reliability_score) if (informative and sched_w < Decimal("0.6")) else ZERO

    # advisory re-blend: keep current source weights, carve out history_curve_weight, renormalize
    remaining = max(ZERO, ONE - history_curve_weight)
    base_total = sched_w + ce_w + inv_w
    if base_total > 0:
        sched_s = sched_w / base_total * remaining
        ce_s = ce_w / base_total * remaining
        inv_s = inv_w / base_total * remaining
    else:
        sched_s = ce_s = inv_s = remaining / Decimal("3")
    final = OrderedDict([
        ("schedule_weight", _q4(sched_s)),
        ("actual_trend_weight", _q4(ce_s)),
        ("invoice_weight", _q4(inv_s)),
        ("history_curve_weight", _q4(history_curve_weight)),
    ])
    conf_delta = Decimal("0.03") if (informative and reliability_score >= Decimal("0.6")) else ZERO

    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", key),
        ("cost_code", signal.get("cost_code")),
        ("current_monthly_distribution_basis", mr.get("monthly_forecast_basis")),
        ("source_shares_available", source_shares_available),
        ("distribution_source_basis",
         "accepted_monthly_source_shares" if source_shares_available else "equal_weight_fallback"),
        ("historical_curve_shape_class", curve_shape),
        ("history_curve_weight_suggestion", _q4(history_curve_weight)),
        ("schedule_weight_suggestion", _q4(sched_s)),
        ("actual_trend_weight_suggestion", _q4(ce_s)),
        ("invoice_weight_suggestion", _q4(inv_s)),
        ("final_suggested_distribution_weights", final),
        ("distribution_confidence_delta", _q4(conf_delta)),
        ("do_not_auto_apply", True),
        ("requires_human_acceptance", True),
    ])
