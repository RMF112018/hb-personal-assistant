"""Integrated probability — DETERMINISTIC adjustment of the accepted probability distribution.

This is NOT a fresh Monte Carlo. It reshapes the accepted per-code percentile band around P50 by a bounded
sigma multiplier (history suggested multiplier × bounded weight, plus cadence-change timing widening) and
shifts the upper tail by the history tail-shift delta. Every adjusted quantile is floored at actual cost
to date and never capped. `probability_method = accepted_distribution_deterministic_adjustment`.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, dec, money_str
from . import human_acceptance as ha

ZERO, ONE = Decimal("0"), Decimal("1")
PROBABILITY_METHOD = "accepted_distribution_deterministic_adjustment"
CADENCE_WIDEN = Decimal("0.05")
QUANTS = ("simulated_p10", "simulated_p50", "simulated_p80", "simulated_p90", "simulated_p95")
UPPER = ("simulated_p80", "simulated_p90", "simulated_p95")


def _d(x, default=ZERO):
    v = dec(x)
    return v if v is not None else default


def build(project_key, key, entry, sc, cfg_fc) -> tuple:
    cost_code = key.split(".")[1] if "." in key else None
    pfin = entry["prob_final"]
    if not pfin:
        return None, None
    actual_floor = D(entry["actual_cost_to_date"])
    p50 = D(pfin.get("simulated_p50"))

    # bounded sigma multiplier from history (advisory) + cadence-change timing widening
    hist_prob = entry["hist_prob"]
    w = sc["history_probability_weight"]
    hmult = _d(hist_prob.get("suggested_sigma_multiplier"), ONE) if hist_prob else ONE
    tail_shift = _d(hist_prob.get("suggested_tail_shift_delta")) if (hist_prob and w > 0) else ZERO
    mult = ONE + (hmult - ONE) * w                       # dampened by bounded weight
    cadence_changed = bool((entry["freq"] or {}).get("cadence_change_detected"))
    if cadence_changed:
        mult = mult * (ONE + CADENCE_WIDEN)              # cadence volatility widens timing risk
    direction = ("tighten" if mult < ONE else ("widen" if mult > ONE else "hold"))

    adj = OrderedDict()
    for q in QUANTS:
        base = D(pfin.get(q))
        m = mult + (tail_shift if q in UPPER else ZERO)
        val = p50 + (base - p50) * m
        if val < actual_floor:
            val = actual_floor                            # floor; never cap
        adj[q] = val

    row = OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
        ("probability_method", PROBABILITY_METHOD),
        ("actual_cost_to_date", money_str(actual_floor)),
        ("accepted_simulated_p50", money_str(p50)),
        ("integrated_sigma_multiplier", str(mult.quantize(Decimal("0.0001")))),
        ("integrated_tail_shift_delta", str(tail_shift.quantize(Decimal("0.0001")))),
        ("integrated_uncertainty_direction", direction),
        ("cadence_timing_widening_applied", cadence_changed),
        ("integrated_p10", money_str(adj["simulated_p10"])),
        ("integrated_p50", money_str(adj["simulated_p50"])),
        ("integrated_p80", money_str(adj["simulated_p80"])),
        ("integrated_p90", money_str(adj["simulated_p90"])),
        ("integrated_p95", money_str(adj["simulated_p95"])),
        ("accepted_prob_exceeds_recommended_final_cost", pfin.get("prob_exceeds_recommended_final_cost")),
        ("history_probability_weight", str(w.quantize(Decimal("0.0001")))),
        ("upper_cap_applied", False),
        ("history_consumption_status", "consumed" if (hist_prob and w > 0) else sc["history_consumption_status"]),
        ("frequency_consumption_status", sc["frequency_consumption_status"]),
        ("probability_consumption_status", "consumed"),
    ])
    ha.stamp(row)
    contrib = {"p50": adj["simulated_p50"], "p90": adj["simulated_p90"], "p95": adj["simulated_p95"],
               "direction": direction}
    return row, contrib
