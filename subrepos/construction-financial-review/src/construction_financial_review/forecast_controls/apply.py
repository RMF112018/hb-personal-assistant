"""Resolve operator controls into per-code decisions and reshape monthly forecasts.

Two responsibilities:
1. ``resolve`` — parse + map + precedence (accepted > pending) -> per-key applied decisions, plus
   application rows, review-queue rows, warnings, floor violations, and superseded records. A
   posture-changing control (stop-date zeroing or dollar change) applies ONLY when human-accepted
   (config-gated) and never sets final cost below actual cost to date.
2. ``reshape_reconcile`` / weight + ctc helpers — apply a resolved decision to a monthly reconcile
   result (zero post-stop months, redistribute the allowed remaining cost, reconcile to CTC). Reused
   by forecast_monthly and forecast_comprehensive so both consume identical control semantics.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from decimal import Decimal

from ..common.money import D, dec, money_str
from ..forecast_monthly.monthly_reconcile import _allocate
from . import control_schema as cs
from . import mapping as cmap

ZERO, ONE = Decimal("0"), Decimal("1")
CENTS = Decimal("0.01")


# --------------------------------------------------------------------------- resolution

def _winners(groups, allow_pending_timing) -> dict:
    """Pick the winning control_id per budget_code_key (accepted posture-changing > pending timing)."""
    winners = {}
    for key, members in groups.items():
        accepted_posture = [c for c in members
                            if c.get("acceptance_status") == "accepted"
                            and cs.is_posture_changing(c.get("control_type"))]
        if accepted_posture:
            winners[key] = sorted(accepted_posture, key=lambda c: c.get("control_id") or "")[-1]["control_id"]
        elif allow_pending_timing:
            pend_stop = [c for c in members
                         if c.get("acceptance_status") == "pending"
                         and cs.is_stop_date_type(c.get("control_type"))]
            if pend_stop:
                winners[key] = sorted(pend_stop, key=lambda c: c.get("control_id") or "")[-1]["control_id"]
    return winners


def resolve(load_result: dict, mapping_results: list, cfg_fctl: dict, actuals_by_key: dict,
            project_key: str) -> "OrderedDict":
    """Resolve controls into applied decisions + auditable rows. Pure + deterministic."""
    require_acc_final = bool(cfg_fctl.get("require_accepted_status_for_final_cost_change", True))
    require_acc_stop = bool(cfg_fctl.get("require_accepted_status_for_post_stop_zero", True))
    allow_pending_timing = bool(cfg_fctl.get("allow_pending_timing_controls", False))
    preserve_floor = bool(cfg_fctl.get("preserve_actuals_floor", True))
    allow_pending_queue = bool(cfg_fctl.get("allow_pending_controls_in_review_queue", True))

    mapping_by_id = {m["control_id"]: m for m in mapping_results}
    controls = load_result["controls"]

    groups = defaultdict(list)
    for c in controls:
        key = mapping_by_id.get(c["control_id"], {}).get("mapped_budget_code_key")
        if key:
            groups[key].append(c)
    winners = _winners(groups, allow_pending_timing)

    applications, review_queue, warnings = [], [], []
    floor_violations, superseded_rows = [], []
    by_key = OrderedDict()
    counts = Counter_like()

    for c in controls:
        cid = c["control_id"]
        m = mapping_by_id.get(cid, {})
        key = m.get("mapped_budget_code_key")
        mapping_status = m.get("mapping_status")
        status = c.get("acceptance_status")
        ctype = c.get("control_type")
        actual = actuals_by_key.get(key)
        acc_rem = dec(c.get("accepted_remaining_cost"))
        acc_fin = dec(c.get("accepted_final_cost"))
        stop_month = cs.stop_month_for(c)

        applied = timing_applied = dollar_applied = dollars_model_derived = False
        floor_ok = True
        superseded_by = None

        if mapping_status not in cmap.MAPPED_STATUSES:
            disposition = "not_applied_" + (mapping_status or "unmapped")
        elif ctype == cs.CT_WATCH_ONLY:
            disposition = "watch_only_no_change"
        elif winners.get(key) == cid:
            applied, timing_applied, dollar_applied, dollars_model_derived, floor_ok, disposition = \
                _apply_winner(ctype, status, acc_rem, acc_fin, stop_month, actual,
                              require_acc_final, require_acc_stop, allow_pending_timing, preserve_floor)
        elif key in winners:
            superseded_by = winners[key]
            disposition = "superseded_by_accepted_control"
            superseded_rows.append(OrderedDict([
                ("control_id", cid), ("budget_code_key", key), ("superseded_by", superseded_by)]))
        elif cs.is_posture_changing(ctype):
            disposition = "pending_not_applied"
        else:
            disposition = "no_action"

        if not floor_ok:
            floor_violations.append(OrderedDict([
                ("control_id", cid), ("budget_code_key", key),
                ("accepted_final_cost", money_str(acc_fin) if acc_fin is not None else None),
                ("actual_cost_to_date", money_str(actual) if actual is not None else None),
                ("violation", "accepted final/remaining below actual cost to date")]))

        if applied:
            by_key[key] = OrderedDict([
                ("control_id", cid), ("budget_code_key", key), ("cost_code", c.get("cost_code")),
                ("control_type", ctype), ("acceptance_status", status),
                ("stop_month", stop_month if timing_applied else None),
                ("accepted_remaining_cost", acc_rem if dollar_applied else None),
                ("accepted_final_cost", acc_fin if dollar_applied else None),
                ("timing_applied", timing_applied), ("dollar_applied", dollar_applied),
                ("dollars_model_derived", dollars_model_derived), ("disposition", disposition)])

        applications.append(OrderedDict([
            ("project_key", c.get("project_key") or project_key), ("control_id", cid),
            ("budget_code_key", key), ("cost_code", c.get("cost_code")), ("control_type", ctype),
            ("acceptance_status", status), ("mapping_status", mapping_status),
            ("applied", applied), ("timing_applied", timing_applied), ("dollar_applied", dollar_applied),
            ("dollars_remain_model_derived", dollars_model_derived),
            ("stop_month", stop_month if timing_applied else None),
            ("accepted_remaining_cost", money_str(acc_rem) if (dollar_applied and acc_rem is not None) else None),
            ("accepted_final_cost", money_str(acc_fin) if (dollar_applied and acc_fin is not None) else None),
            ("actual_cost_to_date", money_str(actual) if actual is not None else None),
            ("actuals_floor_respected", floor_ok), ("disposition", disposition),
            ("superseded_by", superseded_by), ("source", c.get("source")), ("reason", c.get("reason")),
            ("requires_human_acceptance", c.get("requires_human_acceptance"))]))

        counts.tally(status)
        # review queue + warnings
        q = _queue_row(project_key, c, key, mapping_status, status, ctype, disposition, superseded_by,
                       floor_ok)
        if q and allow_pending_queue:
            review_queue.append(q)
        warnings.extend(_warnings_for(project_key, c, key, mapping_status, applied, dollars_model_derived,
                                      floor_ok))

    applications.sort(key=lambda r: (r["budget_code_key"] or "", r["control_id"] or ""))
    review_queue.sort(key=lambda r: (r.get("review_priority") or "", r.get("budget_code_key") or "",
                                     r.get("control_id") or ""))
    warnings.sort(key=lambda r: (r.get("warning_type") or "", r.get("budget_code_key") or ""))

    return OrderedDict([
        ("by_key", by_key),
        ("applications", applications),
        ("review_queue", review_queue),
        ("warnings", warnings),
        ("floor_violations", floor_violations),
        ("superseded", superseded_rows),
        ("controlled_budget_codes", sorted(by_key.keys())),
        ("counts", counts.as_dict()),
        ("any_ambiguous", any(a["mapping_status"] == cmap.M_AMBIGUOUS for a in applications)),
        ("any_invented", any(a["mapping_status"] == cmap.M_INVENTED for a in applications)),
        ("any_floor_violation", bool(floor_violations)),
    ])


def _apply_winner(ctype, status, acc_rem, acc_fin, stop_month, actual,
                  require_acc_final, require_acc_stop, allow_pending_timing, preserve_floor):
    applied = timing_applied = dollar_applied = dollars_model_derived = False
    floor_ok = True
    if ctype == cs.CT_FINAL_OVERRIDE:
        if status != "accepted" and require_acc_final:
            disposition = "pending_not_applied"
        elif acc_fin is None:
            disposition = "accepted_final_override_missing_amount"
        elif actual is not None and acc_fin < actual and preserve_floor:
            floor_ok, disposition = False, "rejected_final_below_actuals"
        else:
            applied = dollar_applied = True
            disposition = "applied_final_override"
    elif ctype == cs.CT_REMAINING_ALLOWANCE:
        if status != "accepted" and require_acc_final:
            disposition = "pending_not_applied"
        elif acc_rem is None:
            disposition = "accepted_remaining_allowance_missing_amount"
        elif acc_rem < ZERO:
            floor_ok, disposition = False, "rejected_remaining_below_zero"
        else:
            applied = dollar_applied = True
            disposition = "applied_remaining_allowance"
    elif cs.is_stop_date_type(ctype):
        accepted_ok = (status == "accepted") or (allow_pending_timing and status == "pending")
        if not accepted_ok and require_acc_stop:
            disposition = "pending_not_applied"
        elif stop_month is None:
            disposition = "stop_date_missing_or_invalid"
        elif acc_fin is not None and actual is not None and acc_fin < actual and preserve_floor:
            floor_ok, disposition = False, "rejected_final_below_actuals"
        else:
            applied = timing_applied = True
            if acc_rem is not None or acc_fin is not None:
                dollar_applied = True
                disposition = "applied_stop_date_with_accepted_amount"
            else:
                dollars_model_derived = True
                disposition = "applied_stop_date_timing_only"
    elif ctype == cs.CT_MONTHLY_DIST:
        if status != "accepted":
            disposition = "pending_not_applied"
        else:
            applied = timing_applied = True
            disposition = "applied_monthly_distribution"
    else:
        disposition = "no_action"
    return applied, timing_applied, dollar_applied, dollars_model_derived, floor_ok, disposition


def _queue_row(project_key, c, key, mapping_status, status, ctype, disposition, superseded_by, floor_ok):
    if not floor_ok:
        reason, priority = "accepted dollar control below actuals floor — rejected", "high"
    elif mapping_status == cmap.M_AMBIGUOUS:
        reason, priority = "ambiguous cost_code mapping — budget_code_key required", "high"
    elif mapping_status in (cmap.M_INVENTED, cmap.M_UNMAPPED, cmap.M_MISSING):
        reason, priority = "control could not be mapped to a canonical budget code", "high"
    elif disposition in ("accepted_final_override_missing_amount",
                         "accepted_remaining_allowance_missing_amount", "stop_date_missing_or_invalid"):
        reason, priority = f"accepted control incomplete ({disposition})", "high"
    elif disposition == "superseded_by_accepted_control":
        reason, priority = f"superseded by accepted control {superseded_by}", "low"
    elif status == "pending" and cs.is_posture_changing(ctype):
        reason, priority = "pending operator control — not applied until accepted", "medium"
    elif ctype == cs.CT_WATCH_ONLY:
        reason, priority = "watch-only control — monitor; no forecast change", "low"
    else:
        return None
    return OrderedDict([
        ("project_key", project_key), ("control_id", c.get("control_id")), ("budget_code_key", key),
        ("cost_code", c.get("cost_code")), ("control_type", ctype), ("acceptance_status", status),
        ("review_priority", priority), ("review_reason", reason),
        ("disposition", disposition), ("requires_human_acceptance", c.get("requires_human_acceptance")),
        ("operator_reason", c.get("reason")), ("source", c.get("source"))])


def _warnings_for(project_key, c, key, mapping_status, applied, dollars_model_derived, floor_ok):
    out = []

    def w(wtype, severity, message):
        out.append(OrderedDict([("project_key", project_key), ("budget_code_key", key),
                                ("control_id", c.get("control_id")), ("warning_type", wtype),
                                ("severity", severity), ("message", message)]))
    if not floor_ok:
        w("accepted_amount_below_actuals_floor", "high",
          "accepted final/remaining cost is below actual cost to date; control rejected (floor preserved)")
    if mapping_status == cmap.M_AMBIGUOUS:
        w("ambiguous_cost_code_mapping", "high",
          "cost_code maps to multiple canonical keys; provide budget_code_key")
    if mapping_status in (cmap.M_INVENTED, cmap.M_UNMAPPED, cmap.M_MISSING):
        w("control_mapping_failed", "high", f"control not mapped to canonical budget code ({mapping_status})")
    if applied and dollars_model_derived:
        w("dollar_total_model_derived", "medium",
          "stop-date timing applied but no accepted remaining/final amount; total remaining cost is "
          "still model-derived (redistributed through the stop window)")
    return out


class Counter_like:
    """Tiny deterministic acceptance-status tally (avoids importing Counter for one use)."""

    def __init__(self):
        self.accepted = self.pending = self.rejected = self.other = 0

    def tally(self, status):
        if status == "accepted":
            self.accepted += 1
        elif status == "pending":
            self.pending += 1
        elif status == "rejected":
            self.rejected += 1
        else:
            self.other += 1

    def as_dict(self):
        return OrderedDict([("accepted", self.accepted), ("pending", self.pending),
                            ("rejected", self.rejected), ("other", self.other)])


# --------------------------------------------------------------------------- monthly reshaping

def effective_ctc(rec_ctc: Decimal, worst_ctc: Decimal, actual: Decimal, decision: dict):
    """Resolve the target recommended/worst CTC for a decision (floored at actuals). Returns (rec, worst, dollar)."""
    if decision.get("accepted_final_cost") is not None:
        final_t = decision["accepted_final_cost"]
        if final_t < actual:
            final_t = actual
        rec = final_t - actual
        return rec, (worst_ctc if worst_ctc > rec else rec), True
    if decision.get("accepted_remaining_cost") is not None:
        rec = decision["accepted_remaining_cost"]
        if rec < ZERO:
            rec = ZERO
        return rec, (worst_ctc if worst_ctc > rec else rec), True
    return rec_ctc, worst_ctc, False


def restrict_weights(blended: "OrderedDict[str, Decimal]", months: list, stop_month) -> "OrderedDict[str, Decimal]":
    """Zero months after the stop month and renormalize over the allowed months (flat fallback)."""
    def allowed(m):
        return stop_month is None or m <= stop_month
    vec = OrderedDict((m, (blended.get(m, ZERO) if allowed(m) else ZERO)) for m in months)
    total = sum(vec.values(), ZERO)
    if total > 0:
        return OrderedDict((m, vec[m] / total) for m in months)
    allow_ms = [m for m in months if allowed(m)] or list(months)
    n = Decimal(len(allow_ms))
    return OrderedDict((m, (ONE / n) if m in set(allow_ms) else ZERO) for m in months)


def reshape_reconcile(reconcile: dict, decision: dict) -> dict:
    """Return a control-adjusted copy of a monthly reconcile result."""
    months = [mc["forecast_month"] for mc in reconcile["month_costs"]]
    actual = reconcile["actual"]
    rec_ctc, worst_ctc, _ = effective_ctc(reconcile["recommended_cost_to_complete"],
                                          reconcile["worst_credible_cost_to_complete"], actual, decision)
    new_blended = restrict_weights(reconcile["blended"], months, decision.get("stop_month"))
    rec_month = _allocate(rec_ctc, new_blended, months)
    worst_month = _allocate(worst_ctc, new_blended, months)
    rec_final, worst_final = actual + rec_ctc, actual + worst_ctc
    projected, revised = reconcile["current_projected_cost"], reconcile["revised_budget"]

    cum_rec = cum_worst = actual
    peak = ZERO
    first_exceed_proj = first_exceed_rev = None
    new_rows = []
    for mc in reconcile["month_costs"]:
        m = mc["forecast_month"]
        cum_rec += rec_month[m]
        cum_worst += worst_month[m]
        if first_exceed_proj is None and projected is not None and cum_rec > projected:
            first_exceed_proj = m
        if first_exceed_rev is None and revised is not None and cum_rec > revised:
            first_exceed_rev = m
        if rec_month[m] > peak:
            peak = rec_month[m]
        row = OrderedDict(mc)
        row["recommended_month_cost"] = money_str(rec_month[m])
        row["worst_credible_month_cost"] = money_str(worst_month[m])
        row["cumulative_recommended_cost_through_month"] = money_str(cum_rec)
        row["cumulative_worst_credible_cost_through_month"] = money_str(cum_worst)
        row["remaining_recommended_cost_after_month"] = money_str(rec_final - cum_rec)
        row["remaining_worst_credible_cost_after_month"] = money_str(worst_final - cum_worst)
        row["blended_month_weight"] = str(new_blended[m].quantize(Decimal("0.000001")))
        new_rows.append(row)

    rec_sum = sum((D(r["recommended_month_cost"]) for r in new_rows), ZERO)
    worst_sum = sum((D(r["worst_credible_month_cost"]) for r in new_rows), ZERO)
    rec_ok = abs(rec_sum - rec_ctc) <= CENTS and abs((actual + rec_sum) - rec_final) <= CENTS
    worst_ok = abs(worst_sum - worst_ctc) <= CENTS and abs((actual + worst_sum) - worst_final) <= CENTS

    out = dict(reconcile)
    out["month_costs"] = new_rows
    out["blended"] = new_blended
    out["recommended_cost_to_complete"] = rec_ctc
    out["worst_credible_cost_to_complete"] = worst_ctc
    out["recommended_final_cost"] = rec_final
    out["worst_credible_final_cost"] = worst_final
    out["variance_to_current_projected_cost"] = (rec_final - projected) if projected is not None else None
    out["variance_to_revised_budget"] = (rec_final - revised) if revised is not None else None
    out["peak_month_cost"] = money_str(peak)
    out["first_month_exceed_current_projected"] = first_exceed_proj
    out["first_month_exceed_revised_budget"] = first_exceed_rev
    out["monthly_forecast_basis"] = "operator_controlled_" + reconcile["monthly_forecast_basis"]
    out["reconciliation_ok"] = bool(rec_ok and worst_ok)
    out["operator_controlled"] = True
    out["operator_control_id"] = decision.get("control_id")
    out["operator_stop_month"] = decision.get("stop_month")
    return out
