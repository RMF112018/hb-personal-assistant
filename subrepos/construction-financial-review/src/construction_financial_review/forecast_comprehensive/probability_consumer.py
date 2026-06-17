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
from ..forecast_model_controls import probability_assessment as pa
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

    # dormant / closed-code suppression: a suppressed code carries no future cost, so probability is a
    # degenerate point at actual cost to date (probability_status = dormant_suppressed) — NOT a broad risk
    # distribution. Overridden only by a value-asserting operator model control (controlled_remaining > 0).
    dormant = entry.get("dormant")
    mdec = entry.get("model_control")
    op_value_assert = bool(mdec and mdec.get("changes_deterministic_final")
                           and D(mdec.get("controlled_remaining")) > ZERO)
    if dormant and dormant.get("suppression_applied") and not op_value_assert:
        return _dormant_probability(project_key, key, cost_code, entry, dormant)

    # operator forecast-MODEL control that changes the deterministic final value: probability is
    # degraded-not-fatal. Anchor to a prior accepted probability row when one exists, else emit a
    # deterministic provisional plausibility assessment (numeric probabilities null) — never kill the run.
    if mdec and mdec.get("changes_deterministic_final"):
        return _model_controlled_probability(project_key, key, cost_code, entry, sc, cfg_fc, mdec)

    # Operator staffing-plan basis: deterministic accepted-LAB-mapping selected final (NOT a cap). Anchor
    # the accepted distribution to the staffing-selected final, floored at actuals, never capped.
    sb = entry.get("staffing_basis") or {}
    if sb.get("staffing_basis_applied") and entry.get("prob_final"):
        return _basis_anchored_probability(
            project_key, key, cost_code, entry, sc,
            {"cost_basis_status": "operator_staffing_plan_basis",
             "selected_final_cost": sb.get("selected_final_cost")})

    # BudgetDetails projected-cost basis: a deterministic evidence-based selected final (NOT a hidden
    # cap). Anchor the accepted distribution UP to the selected final, floored at actuals, never capped
    # (upper_cap_applied stays False). Disclosed as a deterministic basis, not an operator cap.
    cb = entry.get("cost_basis") or {}
    if cb.get("cost_basis_status") == "budgetdetails_projected_cost_basis" and entry.get("prob_final"):
        return _basis_anchored_probability(project_key, key, cost_code, entry, sc, cb)

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


def _dormant_probability(project_key, key, cost_code, entry, dormant) -> tuple:
    """Degenerate point distribution at actual cost to date for a suppressed dormant/closed code."""
    actual = D(entry["actual_cost_to_date"])
    a = money_str(actual)
    row = OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
        ("probability_method", "dormant_code_suppressed_point"),
        ("probability_status", "dormant_suppressed"),
        ("actual_cost_to_date", a),
        ("integrated_p10", a), ("integrated_p50", a), ("integrated_p80", a),
        ("integrated_p90", a), ("integrated_p95", a),
        ("integrated_uncertainty_direction", "dormant"),
        ("cadence_timing_widening_applied", False), ("upper_cap_applied", False),
        ("operator_final_value_anchor_applied", False),
        ("dormant_status", dormant.get("dormant_status")),
        ("dormant_suppression_reason", dormant.get("suppression_reason")),
        ("history_consumption_status", "not_applicable_dormant"),
        ("frequency_consumption_status", "not_applicable_dormant"),
        ("probability_consumption_status", "dormant_suppressed"),
    ])
    ha.stamp(row)
    return row, {"p50": actual, "p90": actual, "p95": actual, "direction": "dormant"}


def _anchor_row(project_key, key, cost_code, entry, sc, mdec, actual_floor, controlled_final):
    """Anchor the accepted distribution to the controlled final (recenter spread, floor, monotonic)."""
    pfin = entry["prob_final"]
    p50_base = D(pfin.get("simulated_p50"))
    delta = controlled_final - p50_base
    adj, prev = OrderedDict(), None
    for q in QUANTS:
        v = D(pfin.get(q)) + delta
        if v < actual_floor:
            v = actual_floor
        if prev is not None and v < prev:
            v = prev                                         # enforce monotonic p10<=p50<=p80<=p90<=p95
        adj[q] = v
        prev = v
    row = OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
        ("probability_method", "operator_anchored_accepted_distribution"),
        ("probability_status", "accepted_probability_anchor"),
        ("actual_cost_to_date", money_str(actual_floor)),
        ("accepted_simulated_p50", money_str(p50_base)),
        ("integrated_sigma_multiplier", "1.0000"), ("integrated_tail_shift_delta", "0.0000"),
        ("integrated_uncertainty_direction", "operator_anchor"),
        ("cadence_timing_widening_applied", False),
        ("integrated_p10", money_str(adj["simulated_p10"])),
        ("integrated_p50", money_str(adj["simulated_p50"])),
        ("integrated_p80", money_str(adj["simulated_p80"])),
        ("integrated_p90", money_str(adj["simulated_p90"])),
        ("integrated_p95", money_str(adj["simulated_p95"])),
        ("history_probability_weight", "0.0000"), ("upper_cap_applied", False),
        ("operator_final_value_anchor_applied", True),
        ("anchor_control_id", mdec.get("control_id")),
        ("anchor_target_value_source", mdec.get("reference_source")),
        ("anchor_value_constraint_policy", mdec.get("value_constraint_policy")),
        ("anchored_final_cost", money_str(controlled_final)),
        ("history_consumption_status", sc["history_consumption_status"]),
        ("frequency_consumption_status", sc["frequency_consumption_status"]),
        ("probability_consumption_status", "operator_anchored"),
    ])
    ha.stamp(row)
    contrib = {"p50": adj["simulated_p50"], "p90": adj["simulated_p90"], "p95": adj["simulated_p95"],
               "direction": "operator_anchor"}
    return row, contrib


def _basis_anchored_probability(project_key, key, cost_code, entry, sc, cb) -> tuple:
    """Anchor the accepted distribution to a deterministic selected final (BudgetDetails or staffing)."""
    actual_floor = D(entry["actual_cost_to_date"])
    selected_final = D(cb["selected_final_cost"])
    status = cb.get("cost_basis_status") or "budgetdetails_projected_cost_basis"
    method = ("operator_staffing_plan_deterministic_basis"
              if status == "operator_staffing_plan_basis"
              else "budgetdetails_projected_cost_deterministic_basis")
    pfin = entry["prob_final"]
    p50_base = D(pfin.get("simulated_p50"))
    delta = selected_final - p50_base
    adj, prev = OrderedDict(), None
    for q in QUANTS:
        v = D(pfin.get(q)) + delta
        if v < actual_floor:
            v = actual_floor                                 # floor; never cap
        if prev is not None and v < prev:
            v = prev                                         # monotonic
        adj[q] = v
        prev = v
    row = OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
        ("probability_method", method),
        ("probability_status", status),
        ("actual_cost_to_date", money_str(actual_floor)),
        ("accepted_simulated_p50", money_str(p50_base)),
        ("integrated_sigma_multiplier", "1.0000"), ("integrated_tail_shift_delta", "0.0000"),
        ("integrated_uncertainty_direction", "budgetdetails_basis"),
        ("cadence_timing_widening_applied", False),
        ("integrated_p10", money_str(adj["simulated_p10"])),
        ("integrated_p50", money_str(adj["simulated_p50"])),
        ("integrated_p80", money_str(adj["simulated_p80"])),
        ("integrated_p90", money_str(adj["simulated_p90"])),
        ("integrated_p95", money_str(adj["simulated_p95"])),
        ("history_probability_weight", "0.0000"), ("upper_cap_applied", False),
        ("operator_final_value_anchor_applied", False),
        ("cost_basis_status", cb.get("cost_basis_status")),
        ("cost_basis_selected_final_cost", money_str(selected_final)),
        ("cost_basis_treatment", "deterministic_evidence_based_basis_not_a_cap"),
        ("history_consumption_status", sc["history_consumption_status"]),
        ("frequency_consumption_status", sc["frequency_consumption_status"]),
        ("probability_consumption_status", "consumed"),
    ])
    ha.stamp(row)
    contrib = {"p50": adj["simulated_p50"], "p90": adj["simulated_p90"], "p95": adj["simulated_p95"],
               "direction": "budgetdetails_basis"}
    return row, contrib


def _model_controlled_probability(project_key, key, cost_code, entry, sc, cfg_fc, mdec) -> tuple:
    actual_floor = D(entry["actual_cost_to_date"])
    controlled_final = D(mdec["controlled_final_cost"])
    if entry.get("prob_final"):
        return _anchor_row(project_key, key, cost_code, entry, sc, mdec, actual_floor, controlled_final)

    # no prior accepted probability row -> deterministic provisional plausibility assessment (degraded)
    amounts = OrderedDict([
        ("projected_costs", entry.get("projected_costs")), ("revised_budget", entry.get("revised_budget")),
        ("committed_costs", entry.get("committed_costs")),
        ("original_budget_amount", entry.get("original_budget_amount"))])
    a = pa.assess(project_key, mdec, amounts, prior_prob_present=False, historical_burn=None,
                  within_pct=Decimal("0.10"))
    row = OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
        ("probability_method", "operator_provisional_manual_value_assessment"),
        ("probability_status", a["probability_status"]),
        ("actual_cost_to_date", money_str(actual_floor)),
        ("integrated_p10", None), ("integrated_p50", money_str(controlled_final)),
        ("integrated_p80", None), ("integrated_p90", None), ("integrated_p95", None),
        ("integrated_uncertainty_direction", "provisional"),
        ("upper_cap_applied", False),
        ("operator_final_value_anchor_applied", False),
        ("anchor_control_id", mdec.get("control_id")),
        ("controlled_final_cost", money_str(controlled_final)),
        ("uncontrolled_model_final_cost", a["uncontrolled_model_final_cost"]),
        ("delta_from_uncontrolled_model", a["delta_from_uncontrolled_model"]),
        ("manual_value_assessment", a["manual_value_assessment"]),
        ("evidence_support_score", a["evidence_support_score"]),
        ("probability_final_cost_at_or_below_controlled_value",
         a["probability_final_cost_at_or_below_controlled_value"]),
        ("probability_final_cost_exceeds_controlled_value",
         a["probability_final_cost_exceeds_controlled_value"]),
        ("confidence", a["confidence"]), ("data_gaps", a["data_gaps"]),
        ("history_consumption_status", sc["history_consumption_status"]),
        ("frequency_consumption_status", sc["frequency_consumption_status"]),
        ("probability_consumption_status", "provisional_manual_value_assessment"),
    ])
    ha.stamp(row)
    contrib = {"p50": controlled_final, "p90": controlled_final, "p95": controlled_final,
               "direction": "provisional"}
    return row, contrib
