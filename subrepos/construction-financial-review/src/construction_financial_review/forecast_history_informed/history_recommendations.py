"""Advisory history-informed forecast adjustment (never auto-applied, never a cap, floored at actuals).

The historical remaining forecast implies a prior EAC (actual-to-date + remaining). We nudge the current
recommended final cost toward that prior ONLY in proportion to how reliable the history is — so
contradicted/stale history (low reliability) produces ~zero pull, and actuals always dominate. The
adjusted figure is advisory, floored at actual cost to date, and never capped above any reference.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, money_str

ZERO = Decimal("0")
LOW_RELIABILITY = Decimal("0.20")


def _d(x, default=ZERO):
    try:
        return Decimal(str(x))
    except Exception:
        return default


def _q4(x):
    return str(Decimal(x).quantize(Decimal("0.0001")))


def build_adjustment(signal: dict, validation: dict, reliability: dict, intel_rec: dict,
                     context_row: dict, cfg_fhi: dict, project_key: str) -> OrderedDict:
    key = signal.get("budget_code_key")
    rec = intel_rec or {}
    actual = D(rec.get("actual_cost_all_source_to_date"))
    current_rec = D(rec.get("recommended_final_cost"))
    current_worst = D(rec.get("worst_credible_final_cost"))
    current_proj = D(rec.get("current_projected_cost"))
    revised_budget = D(rec.get("revised_budget"))

    remaining_latest = signal.get("historical_remaining_forecast_latest")
    history_implied_final = actual + (D(remaining_latest) if remaining_latest is not None else ZERO)

    reliability_score = _d(reliability.get("overall_history_reliability_score"))
    vclass = validation.get("validation_class") or ""
    validated = vclass.startswith("validated")
    contradicted = vclass.startswith("contradicted")

    w_val = _d(cfg_fhi.get("history_max_weight_when_validated"), Decimal("0.45"))
    w_unval = _d(cfg_fhi.get("history_max_weight_when_unvalidated"), Decimal("0.20"))
    base_weight = w_val if validated else w_unval
    effective_weight = base_weight * reliability_score

    raw_adjustment = effective_weight * (history_implied_final - current_rec)
    adjusted = current_rec + raw_adjustment
    if adjusted < actual:                       # actuals are the only hard floor; never below
        adjusted = actual
    applied_adjustment = adjusted - current_rec

    direction, conf_delta, unc_delta = _direction(reliability_score, validated, contradicted,
                                                   history_implied_final, current_rec)

    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", key),
        ("cost_code", signal.get("cost_code")),
        ("current_recommended_final_cost", money_str(current_rec)),
        ("current_worst_credible_final_cost", money_str(current_worst)),
        ("actual_cost_to_date", money_str(actual)),
        ("current_projected_cost", money_str(current_proj)),
        ("revised_budget", money_str(revised_budget)),
        ("historical_implied_final_cost", money_str(history_implied_final)),
        ("history_reliability_score", _q4(reliability_score)),
        ("history_informed_direction", direction),
        ("history_informed_adjustment_amount", money_str(applied_adjustment)),
        ("history_informed_adjusted_final_cost", money_str(adjusted)),
        ("floored_at_actuals", bool(adjusted == actual and applied_adjustment != ZERO)),
        ("upper_cap_applied", False),
        ("do_not_auto_apply", True),
        ("adjustment_basis", f"effective_weight={_q4(effective_weight)} (base {_q4(base_weight)} x "
                             f"reliability {_q4(reliability_score)}); validation={vclass}"),
        ("competing_evidence_summary", _competing(validation, signal)),
        ("confidence_delta", _q4(conf_delta)),
        ("uncertainty_delta", _q4(unc_delta)),
        ("requires_human_acceptance", True),
    ])


def _direction(reliability, validated, contradicted, implied, current):
    if contradicted or reliability < LOW_RELIABILITY:
        return "defer_to_actuals_review", ZERO, Decimal("0.05")
    if validated and (implied - current).copy_abs() <= current * Decimal("0.03"):
        return "hold_reduce_uncertainty", Decimal("0.05"), Decimal("-0.05")
    if validated and implied < current:
        return "suggest_decrease", Decimal("0.03"), Decimal("-0.03")
    if implied > current:
        return "suggest_increase_review", ZERO, Decimal("0.03")
    return "hold", ZERO, ZERO


def _competing(validation, signal):
    bits = [f"validation={validation.get('validation_class')}",
            f"burn={validation.get('burn_acceleration_class')}",
            f"pattern={signal.get('historical_pattern_class')}",
            f"curve={signal.get('latest_curve_shape_class')}"]
    if validation.get("credits_deductive_pattern"):
        bits.append("credits_present")
    if validation.get("late_cost_emergence"):
        bits.append("late_cost_emergence")
    return "; ".join(bits)
