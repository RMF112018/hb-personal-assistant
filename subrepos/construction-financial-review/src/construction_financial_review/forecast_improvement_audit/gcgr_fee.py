"""Priority 6 — GC/GR behavior classification + fee projected-budget cap diagnostics.

GC/GR behavior is advisory classification only (it does not change any final cost). The fee cap is the
governance carve-out: fee codes (currently ``20-18-110 CONTRACTORS FEE``) ARE capped by the projected
budget value, subject to the actuals floor. This module proves whether that cap is satisfied for the
audit package's own logic; it never writes the cap into an accepted package.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, dec, money_str
from ..forecast_comprehensive import human_acceptance as ha

ZERO = Decimal("0")

DEFAULT_FEE_COST_CODES = ("20-18-110",)
DEFAULT_FEE_CAP_FIELD = "projected_budget"
DEFAULT_GCGR_KEYWORDS = ("GENERAL CONDITION", "GENERAL REQUIREMENT", "FEE", "INSURANCE", "BOND",
                         "PERMIT", "UTILITY", "ADMIN", "SUPERVISION", "OVERHEAD", "GENERAL LIABILITY")


def _cfg(cfg):
    return (cfg or {}).get("forecast_improvement_audit") or {}


def _is_fee(cost_code, fee_codes):
    return any(fc and fc in (cost_code or "") for fc in fee_codes)


def _amounts(entry):
    return (entry or {}).get("amounts") or {}


def behavior_class(key, entry, trend, zero_threshold: Decimal):
    """Deterministic GC/GR behavior class from amounts + trend evidence."""
    amt = _amounts(entry)
    actual = D(amt.get("costentries_total_amount"))
    ftc = D(amt.get("forecast_to_complete"))
    cov = D((trend or {}).get("cost_volatility_cov"))
    accel = dec((trend or {}).get("burn_acceleration_ratio"))
    months = int((trend or {}).get("months_of_completed_actuals") or 0)
    recent = D((trend or {}).get("recent_avg_monthly_burn"))
    prior = D((trend or {}).get("prior_avg_monthly_burn"))
    recency_gap = int((trend or {}).get("recency_gap_months") or 0)

    if actual.copy_abs() <= zero_threshold and ftc.copy_abs() <= zero_threshold:
        return "stable_zero_inactive"
    if cov >= Decimal("0.75"):
        return "volatile_review_required"
    if recent <= zero_threshold and prior > zero_threshold and recency_gap >= 2:
        return "closeout_taper"
    if accel is not None and accel < Decimal("0.6") and prior > recent and months >= 3:
        return "front_loaded"
    if accel is not None and Decimal("0.8") <= accel <= Decimal("1.2") and recent > zero_threshold:
        return "fixed_monthly_burn"
    return "volatile_review_required" if months < 2 else "fixed_monthly_burn"


def build_gcgr_behavior(inputs: dict, cfg: dict):
    fia = _cfg(cfg)
    keywords = tuple(k.upper() for k in (fia.get("gcgr_description_keywords") or DEFAULT_GCGR_KEYWORDS))
    zero_threshold = D(fia.get("gcgr_zero_threshold", "1.0"))
    project_key = inputs["project_key"]

    # duplicate bare-cost-code description detection (distinct keys, same description)
    desc_to_codes = {}
    for r in inputs["budget_codes"]:
        d = (r.get("budget_code_description") or "").strip().upper()
        if d:
            desc_to_codes.setdefault(d, set()).add(r.get("cost_code"))
    dup_descriptions = {d for d, codes in desc_to_codes.items() if len(codes) > 1}

    rows = []
    for key in sorted(inputs["budget_by_key"]):
        entry = inputs["budget_by_key"][key]
        desc = (entry.get("budget_code_description") or "").upper()
        cost_code = entry.get("cost_code")
        is_gcgr = any(kw in desc for kw in keywords)
        if not is_gcgr:
            continue
        trend = inputs["trend_by_key"].get(key)
        cls = behavior_class(key, entry, trend, zero_threshold)
        dup = (entry.get("budget_code_description") or "").strip().upper() in dup_descriptions
        row = OrderedDict([
            ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
            ("budget_code_description", entry.get("budget_code_description")),
            ("gcgr_behavior_class", "duplicate_description_review_required" if dup else cls),
            ("secondary_behavior_class", cls if dup else None),
            ("gcgr_class_basis", "amounts+trend_evidence; keyword-matched GC/GR/fee description"),
            ("actual_cost_to_date", money_str(_amounts(entry).get("costentries_total_amount")) or "0.00"),
            ("forecast_to_complete_reference", money_str(_amounts(entry).get("forecast_to_complete"))),
            ("cost_volatility_cov", (trend or {}).get("cost_volatility_cov")),
            ("months_of_completed_actuals", int((trend or {}).get("months_of_completed_actuals") or 0)),
            ("is_fee_code", _is_fee(cost_code, fia.get("fee_cost_codes") or DEFAULT_FEE_COST_CODES)),
            ("note", "advisory classification only; does not change any final cost"),
        ])
        rows.append(ha.stamp(row))
    rows.sort(key=lambda r: (r["budget_code_key"], r["cost_code"] or ""))
    return rows


def build_fee_cap(inputs: dict, cfg: dict):
    """Return (fee_rows, fee_gaps). Enforces the projected-budget fee cap in this audit's own logic."""
    fia = _cfg(cfg)
    fee_codes = tuple(fia.get("fee_cost_codes") or DEFAULT_FEE_COST_CODES)
    cap_field = fia.get("fee_cap_source_field") or DEFAULT_FEE_CAP_FIELD
    project_key = inputs["project_key"]

    rows, gaps = [], []
    fee_keys = [k for k, e in inputs["budget_by_key"].items() if _is_fee(e.get("cost_code"), fee_codes)]
    for key in sorted(fee_keys):
        entry = inputs["budget_by_key"][key]
        amt = _amounts(entry)
        acc = inputs["accuracy_by_key"].get(key) or {}

        actual = D(acc.get("actual_cost_all_source_to_date") or amt.get("costentries_total_amount"))
        evidence = D(acc.get("recommended_final_cost"))
        worst = dec(acc.get("worst_credible_final_cost"))
        cap_raw = dec(amt.get(cap_field))

        cap_present = cap_raw is not None and cap_raw > ZERO
        if not cap_present:
            # missing/zero cap value -> data gap, never invent a cap
            after = max(actual, evidence)  # uncapped (floored at actuals) since no cap value
            row = OrderedDict([
                ("project_key", project_key), ("budget_code_key", key), ("cost_code", entry.get("cost_code")),
                ("budget_code_description", entry.get("budget_code_description")),
                ("fee_cap_basis", "none"),
                ("fee_cap_basis_field", cap_field),
                ("fee_projected_budget_cap_value", None),
                ("evidence_supported_fee_before_cap", money_str(evidence)),
                ("fee_forecast_after_cap", money_str(after)),
                ("fee_projected_budget_cap_applied", False),
                ("actuals_exceed_fee_cap_exception", False),
                ("actual_fee_cost_to_date", money_str(actual)),
                ("projected_budget_reference", money_str(amt.get("projected_budget"))),
                ("current_projected_cost_reference", money_str(amt.get("projected_costs"))),
                ("revised_budget_reference", money_str(amt.get("revised_budget"))),
                ("worst_credible_fee_reference", money_str(worst) if worst is not None else None),
                ("note", "no projected-budget cap value present (>0) for this fee code; cap NOT invented"),
            ])
            rows.append(ha.stamp(row))
            gaps.append(OrderedDict([
                ("project_key", project_key), ("improvement", "priority_6_fee_cap"),
                ("budget_code_key", key), ("gap_type", "fee_cap_value_missing"),
                ("detail", f"fee cap source field '{cap_field}' is missing/zero for {key}; "
                           "emitted data-gap, no cap applied"),
                ("requires_human_acceptance", True)]))
            continue

        cap = cap_raw
        actuals_exception = actual > cap
        if actuals_exception:
            after = actual                 # actuals floor wins; never below actuals
            applied = False                # the cap was superseded by actuals, not the binding constraint
        else:
            capped = min(evidence, cap)
            after = max(actual, capped)
            applied = evidence > cap       # the cap actually lowered the evidence-supported fee
        row = OrderedDict([
            ("project_key", project_key), ("budget_code_key", key), ("cost_code", entry.get("cost_code")),
            ("budget_code_description", entry.get("budget_code_description")),
            ("fee_cap_basis", "projected_budget_value"),
            ("fee_cap_basis_field", cap_field),
            ("fee_projected_budget_cap_value", money_str(cap)),
            ("evidence_supported_fee_before_cap", money_str(evidence)),
            ("fee_forecast_after_cap", money_str(after)),
            ("fee_projected_budget_cap_applied", bool(applied)),
            ("actuals_exceed_fee_cap_exception", bool(actuals_exception)),
            ("actual_fee_cost_to_date", money_str(actual)),
            ("projected_budget_reference", money_str(amt.get("projected_budget"))),
            ("current_projected_cost_reference", money_str(amt.get("projected_costs"))),
            ("revised_budget_reference", money_str(amt.get("revised_budget"))),
            ("worst_credible_fee_reference", money_str(worst) if worst is not None else None),
            ("cap_binding", bool(applied)),
            ("note", "fee forecast capped at projected budget value; actuals are the only floor"),
        ])
        rows.append(ha.stamp(row))
    rows.sort(key=lambda r: r["budget_code_key"])
    return rows, gaps


def fee_followups(inputs: dict, cfg: dict, fee_rows: list):
    """Report if any existing generator emits an UNCAPPED fee forecast for a fee code (follow-up work)."""
    project_key = inputs["project_key"]
    gaps = []
    for r in fee_rows:
        key = r["budget_code_key"]
        # the upstream accepted recommended_final_cost is produced with NO fee cap (confirmed by cap scan);
        # flag it as required follow-up so a future consumer slice enforces the cap into accepted outputs.
        evidence = D(r.get("evidence_supported_fee_before_cap"))
        cap_val = dec(r.get("fee_projected_budget_cap_value"))
        binding_now = bool(r.get("fee_projected_budget_cap_applied"))
        gaps.append(OrderedDict([
            ("project_key", project_key), ("improvement", "priority_6_fee_cap"),
            ("budget_code_key", key), ("gap_type", "required_follow_up_implementation"),
            ("detail", "no upstream forecast generator enforces the projected-budget fee cap; the audit "
                       "package validates the rule but does not apply it into accepted outputs. A future "
                       "consumer/final-forecast slice must apply the fee cap, with Bobby's authorization."),
            ("upstream_fee_forecast_currently_exceeds_cap",
             bool(cap_val is not None and evidence > cap_val)),
            ("cap_binding_in_audit", binding_now),
            ("requires_human_acceptance", True), ("do_not_auto_apply", True)]))
    return gaps
