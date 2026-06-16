"""Advisory probability-spread suggestion (never edits the accepted probability package).

History validated by actuals justifies tightening the spread (lower sigma, slight tail pull-in); history
contradicted by actuals or volatile history justifies widening it. These are suggested multipliers/deltas
only — the deterministic probability package is never mutated.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

ZERO = Decimal("0")


def _d(x, default=ZERO):
    try:
        return Decimal(str(x))
    except Exception:
        return default


def _q4(x):
    return str(Decimal(x).quantize(Decimal("0.0001")))


def build_probability_adjustment(signal: dict, validation: dict, reliability: dict,
                                 sim_input_row: dict, overrun_row: dict, project_key: str) -> OrderedDict:
    key = signal.get("budget_code_key")
    current_sigma = _d((sim_input_row or {}).get("sigma"))
    current_overrun = _d((overrun_row or {}).get("prob_exceeds_current_projected_cost"))
    reliability_score = _d(reliability.get("overall_history_reliability_score"))
    vclass = validation.get("validation_class") or ""
    validated = vclass.startswith("validated")
    contradicted = vclass.startswith("contradicted")
    volatile = signal.get("historical_pattern_class") == "volatile_review"

    if validated and reliability_score >= Decimal("0.6"):
        # tighten in proportion to reliability, bounded to [0.85, 1.0]
        sigma_mult = Decimal("1") - (Decimal("0.15") * reliability_score)
        tail_shift = Decimal("-0.02") * reliability_score
        direction = "decrease_uncertainty"
        reason = "history validated by actuals supports a tighter spread"
    elif contradicted or volatile:
        sigma_mult = Decimal("1") + (Decimal("0.15") * (Decimal("1") - reliability_score))
        tail_shift = Decimal("0.03")
        direction = "increase_uncertainty"
        reason = ("history contradicted by recent actuals" if contradicted
                  else "volatile historical forecast")
    else:
        sigma_mult = Decimal("1")
        tail_shift = ZERO
        direction = "hold"
        reason = "insufficient reliability signal to adjust spread"

    sigma_mult = sigma_mult.max(Decimal("0.85")).min(Decimal("1.25"))
    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", key),
        ("cost_code", signal.get("cost_code")),
        ("current_sigma", _q4(current_sigma)),
        ("current_overrun_probability", _q4(current_overrun)),
        ("history_reliability_score", _q4(reliability_score)),
        ("history_validated_by_actuals", validated),
        ("history_contradicted_by_actuals", contradicted),
        ("suggested_sigma_multiplier", _q4(sigma_mult)),
        ("suggested_tail_shift_delta", _q4(tail_shift)),
        ("suggested_probability_direction", direction),
        ("adjustment_reason", reason),
        ("do_not_auto_apply", True),
        ("requires_human_acceptance", True),
    ])
