"""Score advisory evidence into bounded, de-duplicated weights with accept/downgrade/reject reasons.

History-informed and cost-frequency are advisory: their weight is bounded by config and DOWNGRADED when
actuals contradict (history) or cadence is non-informative (frequency). Independence groups prevent
double-counting a signal that surfaces in several upstream packages. Cost-frequency may shape monthly
TIMING only — it carries zero final-cost weight by construction.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import dec

ZERO, ONE = Decimal("0"), Decimal("1")
ADEQUATE_RELIABILITY = Decimal("0.40")
WEEKDAY_CADENCE = ("weekly_internal_staffing", "weekly_observed")


def _d(x, default=ZERO):
    v = dec(x)
    return v if v is not None else default


def _clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


def _q4(x):
    return str(Decimal(x).quantize(Decimal("0.0001")))


def score_code(entry: dict, cfg_fc: dict) -> dict:
    max_hist_final = _d(cfg_fc.get("max_history_final_cost_weight"), Decimal("0.45"))
    max_hist_month = _d(cfg_fc.get("max_history_monthly_shape_weight"), Decimal("0.30"))
    max_hist_prob = _d(cfg_fc.get("max_history_probability_weight"), Decimal("0.25"))
    max_freq_month = _d(cfg_fc.get("max_frequency_monthly_shape_weight"), Decimal("0.60"))

    hrel, hval, hadj = entry["hist_rel"], entry["hist_val"], entry["hist_adj"]
    reliability = _d(hrel.get("overall_history_reliability_score"))
    vclass = hval.get("validation_class") or ""
    contradiction = _d(hval.get("actual_trend_override_score"))
    contradicted = vclass.startswith("contradicted")
    validated = vclass.startswith("validated")

    reasons = []
    # ---- history final-cost weight (advisory; collapses on contradiction) ----
    if not hadj:
        hist_final_w, hist_status = ZERO, "missing"
        reasons.append("history_final_cost:missing")
    elif contradicted:
        hist_final_w, hist_status = ZERO, "downgraded"
        reasons.append(f"history_final_cost:rejected_contradicted_by_actuals({vclass})")
    else:
        hist_final_w = _clamp(reliability * (ONE - contradiction), ZERO, max_hist_final)
        hist_status = "consumed" if hist_final_w > 0 else "downgraded"
        reasons.append(f"history_final_cost:{'accepted' if hist_final_w > 0 else 'downgraded'}"
                       f"(reliability={_q4(reliability)},weight={_q4(hist_final_w)})")

    # ---- history monthly-shape weight (only when reliability adequate and not contradicted) ----
    if not entry["hist_mon"]:
        hist_month_w = ZERO
    elif contradicted or reliability < ADEQUATE_RELIABILITY:
        hist_month_w = ZERO
        reasons.append("history_monthly_shape:downgraded(inadequate_reliability_or_contradicted)")
    else:
        hist_month_w = _clamp(reliability, ZERO, max_hist_month)
        reasons.append(f"history_monthly_shape:accepted(weight={_q4(hist_month_w)})")

    # ---- history probability weight ----
    hist_prob_w = _clamp(reliability, ZERO, max_hist_prob) if entry["hist_prob"] else ZERO

    # ---- frequency monthly (timing only; never final cost) ----
    freq = entry["freq"]
    eff = (freq or {}).get("effective_frequency_class")
    if not freq:
        freq_month_w, freq_status = ZERO, "missing"
    elif eff in WEEKDAY_CADENCE:
        freq_month_w = _clamp(max_freq_month, ZERO, max_freq_month)
        freq_status = "consumed"
        reasons.append(f"frequency_timing:accepted({eff},weight={_q4(freq_month_w)})")
    else:
        freq_month_w, freq_status = ZERO, "partially_consumed"
        reasons.append(f"frequency_timing:classified_only({eff})")

    sched = entry["sched"]
    schedule_status = ("consumed" if sched.get("influences_code_estimate")
                       else ("context_only" if sched else "missing"))
    pay_present = (entry["owner_pay_app"].get("latest_current_value") is not None
                   or entry["sub_pay_app"].get("latest_total_completed_and_stored_to_date_sum") is not None)
    return {
        "reliability": reliability, "validation_class": vclass or None,
        "contradiction_score": contradiction, "contradicted": contradicted, "validated": validated,
        "history_final_cost_weight": hist_final_w,
        "history_monthly_shape_weight": hist_month_w,
        "history_probability_weight": hist_prob_w,
        "frequency_monthly_weight": freq_month_w,
        "effective_frequency_class": eff,
        "history_consumption_status": hist_status,
        "frequency_consumption_status": freq_status,
        "monthly_consumption_status": "consumed" if entry["monthly_conf"] else "missing",
        "probability_consumption_status": "consumed" if entry["prob_final"] else "missing",
        "schedule_consumption_status": schedule_status,
        "pay_app_consumption_status": "consumed" if pay_present else "missing",
        "reason_codes": reasons,
    }


def weights_row(project_key, key, entry, sc) -> OrderedDict:
    """Per-code evidence-weights output row (bounded, de-duplicated, with reasons)."""
    cost_code = key.split(".")[1] if key and "." in key else None
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key),
        ("cost_code", cost_code),
        ("history_reliability_score", _q4(sc["reliability"])),
        ("validation_class", sc["validation_class"]),
        ("contradiction_score", _q4(sc["contradiction_score"])),
        ("history_final_cost_weight", _q4(sc["history_final_cost_weight"])),
        ("history_monthly_shape_weight", _q4(sc["history_monthly_shape_weight"])),
        ("history_probability_weight", _q4(sc["history_probability_weight"])),
        ("frequency_monthly_weight", _q4(sc["frequency_monthly_weight"])),
        ("frequency_final_cost_weight", "0.0000"),   # cadence never weights final cost (timing only)
        ("independence_groups_deduped", ["actuals_truth", "cost_entry_trend", "base_model",
                                         "history", "frequency", "schedule", "pay_application"]),
        ("reason_codes", sc["reason_codes"]),
        ("requires_human_acceptance", True),
    ])
