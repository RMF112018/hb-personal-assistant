"""Resolve the staffing plan into per-.LAB decisions, dual monthly forecasts, and the bridge.

Core rule (operator-directed): the package never lets "timing-only reconciliation" hide a stale or
excessive accepted cost-to-complete. For every mapped ``.LAB`` code it emits BOTH:
  - ``staffing_plan_implied_monthly_forecast`` — the operator plan dollars by month (used directly), and
  - ``current_ctc_reconciled_monthly_forecast`` — the accepted CTC distributed over the SAME plan
    month-shape (so it still reconciles to the currently accepted CTC if the downstream model requires
    that),
plus the implied remaining / implied final cost, the deltas vs the accepted CTC and final cost, and a
``requires_operator_acceptance`` flag when the difference is material. Final-cost changes stay advisory.

Actuals are the only floor (implied_final >= actual). No reference is ever a cap. Deterministic.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, dec, materiality, money_str
from ..forecast_monthly.monthly_reconcile import _allocate
from . import mapping as smap
from . import staffing_schema as ss

ZERO = Decimal("0")
CENTS = Decimal("0.01")


def _weights(plan_monthly: "OrderedDict[str, Decimal]") -> "OrderedDict[str, Decimal]":
    total = sum(plan_monthly.values(), ZERO)
    months = list(plan_monthly.keys())
    if total > 0:
        return OrderedDict((m, plan_monthly[m] / total) for m in months)
    n = Decimal(len(months)) if months else Decimal("1")
    return OrderedDict((m, (Decimal("1") / n)) for m in months)


def _monthly_pairs(d: "OrderedDict[str, Decimal]") -> list:
    return [OrderedDict([("forecast_month", m), ("amount", money_str(v))]) for m, v in d.items()]


def resolve(discovery: dict, mapping_results: list, actuals_by_key: dict, rec_by_key: dict,
            cfg_sp: dict, project_key: str, *, monthly_actuals_by_key: dict | None = None,
            forecast_horizon_end: str | None = None, freq_basis_by_key: dict | None = None) -> "OrderedDict":
    """Resolve the staffing plan into applied decisions + auditable rows. Pure + deterministic."""
    parsed = discovery.get("parsed") or {}
    monthly_cc = parsed.get("monthly_by_cost_code") or []
    abs_thresh = D(cfg_sp.get("materiality_threshold") or "25000.00")
    zero_after = bool(cfg_sp.get("zero_after_staffing_plan_end", True))
    monthly_actuals_by_key = monthly_actuals_by_key or {}
    freq_basis_by_key = freq_basis_by_key or {}

    plan_by_cc = {r.get("cost_code"): r for r in monthly_cc}
    map_by_cc = {m["source_cost_code"]: m for m in mapping_results}

    by_key = OrderedDict()
    monthly_rows, summary_rows, conflicts, warnings, review_queue = [], [], [], [], []
    floor_violations, reconciliation_failures = [], []
    applied_codes = []

    for cc in sorted(plan_by_cc.keys()):
        mres = map_by_cc.get(cc)
        plan_row = plan_by_cc[cc]
        plan_monthly = OrderedDict(
            (m, D(v)) for m, v in sorted((plan_row.get("monthly_forecast") or {}).items()))
        plan_total = sum(plan_monthly.values(), ZERO)
        plan_months = list(plan_monthly.keys())
        plan_end = plan_months[-1] if plan_months else None

        if not mres or not mres.get("applied_numeric"):
            _queue_and_conflict_unapplied(project_key, cc, mres, plan_total, review_queue, conflicts)
            continue

        key = mres["numeric_target_budget_code_key"]
        applied_codes.append(key)
        actual = D(actuals_by_key.get(key))
        rec = rec_by_key.get(key) or {}
        accepted_final = dec(rec.get("recommended_final_cost"))
        accepted_ctc = dec(rec.get("recommended_cost_to_complete"))

        implied_remaining = plan_total
        implied_final = actual + implied_remaining            # floored at actuals (remaining >= 0)
        floored = bool(implied_final == actual and implied_remaining <= ZERO)
        if implied_final < actual:                            # impossible by construction; guard anyway
            floor_violations.append(OrderedDict([("budget_code_key", key),
                                                  ("implied_final_cost", money_str(implied_final)),
                                                  ("actual_cost_to_date", money_str(actual))]))

        # dual monthly vectors
        weights = _weights(plan_monthly)
        implied_monthly = OrderedDict((m, plan_monthly[m]) for m in plan_months)
        ctc_reconciled = (_allocate(accepted_ctc, weights, plan_months)
                          if accepted_ctc is not None else None)

        # reconciliation (cent tolerance)
        implied_ok = abs(sum(implied_monthly.values(), ZERO) - plan_total) <= CENTS
        ctc_ok = True
        if ctc_reconciled is not None:
            ctc_ok = abs(sum(ctc_reconciled.values(), ZERO) - accepted_ctc) <= CENTS
        if not (implied_ok and ctc_ok):
            reconciliation_failures.append(key)

        # deltas + materiality
        delta_ctc = (implied_remaining - accepted_ctc) if accepted_ctc is not None else None
        delta_final = (implied_final - accepted_final) if accepted_final is not None else None
        ctc_material = (materiality(implied_remaining, accepted_ctc, abs_thresh)[2]
                        if accepted_ctc is not None else True)
        final_material = (materiality(implied_final, accepted_final, abs_thresh)[2]
                          if accepted_final is not None else True)
        requires_acceptance = bool(ctc_material or final_material)

        decision = OrderedDict([
            ("budget_code_key", key), ("source_cost_code", cc),
            ("resolved_role_family", mres.get("resolved_role_family")),
            ("allocation_share", mres.get("allocation_share")),
            ("plan_months", plan_months), ("plan_end_month", plan_end),
            ("zero_after_staffing_plan_end", zero_after),
            ("plan_implied_remaining_cost", implied_remaining),
            ("plan_implied_final_cost", implied_final),
            ("accepted_cost_to_complete", accepted_ctc),
            ("accepted_final_cost", accepted_final),
            ("actual_cost_to_date", actual),
            ("implied_monthly", implied_monthly),
            ("ctc_reconciled_monthly", ctc_reconciled),
            ("weights", weights),
            ("requires_operator_acceptance", requires_acceptance),
            ("floored_at_actuals", floored),
        ])
        by_key[key] = decision

        monthly_rows.append(_monthly_row(project_key, key, cc, mres, implied_monthly, ctc_reconciled,
                                          requires_acceptance, accepted_ctc))
        summary_rows.append(_summary_row(project_key, key, cc, mres, actual, accepted_final, accepted_ctc,
                                         implied_remaining, implied_final, delta_ctc, delta_final,
                                         requires_acceptance, implied_monthly, ctc_reconciled, plan_end))

        # ---- conflicts (applied codes) ----
        _applied_conflicts(project_key, key, cc, abs_thresh, accepted_ctc, accepted_final,
                           implied_remaining, implied_final, delta_ctc, delta_final, ctc_material,
                           final_material, plan_monthly, plan_end, forecast_horizon_end,
                           monthly_actuals_by_key.get(key), freq_basis_by_key.get(key), conflicts)
        if key in reconciliation_failures:
            conflicts.append(_conflict(project_key, key, cc,
                                       "staffing_plan_monthly_total_reconciliation_failure", "high",
                                       "staffing-plan monthly values do not reconcile to the source total "
                                       "or the accepted cost-to-complete",
                                       ["operator_staffing_plan", "forecast_monthly"]))

        # zero-after disclosure: never fold a stale CTC into earlier months silently
        if zero_after and forecast_horizon_end and plan_end and plan_end < forecast_horizon_end:
            warnings.append(_warn(project_key, key, "medium",
                                  f"staffing plan ends {plan_end} but the forecast horizon runs to "
                                  f"{forecast_horizon_end}; plan-implied months after {plan_end} are zero. "
                                  "Any accepted-CTC reconciliation difference is reported here, not folded "
                                  "into earlier months."))
        if requires_acceptance:
            review_queue.append(_review(project_key, key, cc, "high",
                                        "staffing plan implies a materially different remaining/final cost "
                                        "than the currently accepted forecast; operator acceptance required",
                                        mres.get("mapping_status")))

    counts = OrderedDict([
        ("plan_cost_codes", len(plan_by_cc)),
        ("applied_numeric_codes", len(applied_codes)),
        ("mapped_operator_approved", sum(1 for m in mapping_results if m["mapping_status"] == ss.M_OP_APPROVED)),
        ("resolved_pending_acceptance", sum(1 for m in mapping_results
                                            if m["mapping_status"] == ss.M_RESOLVED_PENDING)),
        ("ambiguous", sum(1 for m in mapping_results if m["mapping_status"] == ss.M_AMBIGUOUS)),
        ("invented", sum(1 for m in mapping_results if m["mapping_status"] == ss.M_INVENTED)),
        ("mismatch", sum(1 for m in mapping_results if m["mapping_status"] == ss.M_MISMATCH)),
        ("unmapped", sum(1 for m in mapping_results if m["mapping_status"] == ss.M_UNMAPPED)),
    ])

    monthly_rows.sort(key=lambda r: r["budget_code_key"])
    summary_rows.sort(key=lambda r: r["budget_code_key"])
    conflicts.sort(key=lambda c: (c["budget_code_key"] or "", c["conflict_class"]))
    warnings.sort(key=lambda w: (w.get("warning_type") or "", w.get("budget_code_key") or ""))
    review_queue.sort(key=lambda r: (r.get("review_priority") or "", r.get("budget_code_key") or ""))

    return OrderedDict([
        ("by_key", by_key),
        ("applied_budget_codes", sorted(applied_codes)),
        ("monthly_by_budget_code", monthly_rows),
        ("summary_by_budget_code", summary_rows),
        ("conflicts", conflicts),
        ("warnings", warnings),
        ("review_queue", review_queue),
        ("floor_violations", floor_violations),
        ("reconciliation_failures", sorted(set(reconciliation_failures))),
        ("counts", counts),
        ("any_ambiguous_applied", any(m["mapping_status"] in (ss.M_AMBIGUOUS, ss.M_INVENTED, ss.M_MISMATCH)
                                      and m.get("applied_numeric") for m in mapping_results)),
        ("any_unmapped_applied", any(m["mapping_status"] == ss.M_UNMAPPED and m.get("applied_numeric")
                                     for m in mapping_results)),
        ("any_invented", any(m["mapping_status"] == ss.M_INVENTED for m in mapping_results)),
        ("any_floor_violation", bool(floor_violations)),
        ("any_reconciliation_failure", bool(reconciliation_failures)),
        ("plan_total", money_str(sum((D((r.get("monthly_forecast") or {}).get(m))
                                      for r in monthly_cc for m in (r.get("monthly_forecast") or {})), ZERO))),
        ("applied_total", money_str(sum((d["plan_implied_remaining_cost"] for d in by_key.values()), ZERO))),
    ])


# --------------------------------------------------------------------------- row builders

def _monthly_row(project_key, key, cc, mres, implied_monthly, ctc_reconciled, requires_acceptance,
                 accepted_ctc) -> "OrderedDict":
    ctc_pairs = _monthly_pairs(ctc_reconciled) if ctc_reconciled is not None else None
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cc),
        ("numeric_target_category", "LAB"),
        ("allocation_share", mres.get("allocation_share")),
        ("staffing_plan_implied_monthly_forecast", _monthly_pairs(implied_monthly)),
        ("current_ctc_reconciled_monthly_forecast", ctc_pairs),
        ("ctc_reconciliation_available", ctc_reconciled is not None),
        ("accepted_cost_to_complete", money_str(accepted_ctc) if accepted_ctc is not None else None),
        ("requires_operator_acceptance", requires_acceptance),
        ("date_context_target_budget_code_keys", mres.get("date_context_target_budget_code_keys")),
        ("note", "implied = operator plan dollars (LAB only); ctc_reconciled = accepted CTC distributed "
                 "over the same plan month-shape. They differ when the accepted CTC disagrees with the plan."),
        ("requires_human_acceptance", True),
    ])


def _summary_row(project_key, key, cc, mres, actual, accepted_final, accepted_ctc, implied_remaining,
                 implied_final, delta_ctc, delta_final, requires_acceptance, implied_monthly,
                 ctc_reconciled, plan_end) -> "OrderedDict":
    """The per-code BRIDGE: actuals, accepted vs plan-implied final/CTC, deltas, recommendation status."""
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cc),
        ("resolved_role_family", mres.get("resolved_role_family")),
        ("actual_cost_to_date", money_str(actual)),
        ("current_accepted_final_cost", money_str(accepted_final) if accepted_final is not None else None),
        ("current_accepted_cost_to_complete", money_str(accepted_ctc) if accepted_ctc is not None else None),
        ("staffing_plan_implied_remaining_cost", money_str(implied_remaining)),
        ("staffing_plan_implied_final_cost", money_str(implied_final)),
        ("delta_vs_current_accepted_ctc", money_str(delta_ctc) if delta_ctc is not None else None),
        ("delta_vs_current_accepted_final_cost", money_str(delta_final) if delta_final is not None else None),
        ("plan_end_month", plan_end),
        ("recommendation_status", "advisory_operator_planned_staffing"),
        ("requires_operator_acceptance", requires_acceptance),
        ("acceptance_status", "pending"),
        ("staffing_plan_implied_monthly_forecast", _monthly_pairs(implied_monthly)),
        ("current_ctc_reconciled_monthly_forecast",
         _monthly_pairs(ctc_reconciled) if ctc_reconciled is not None else None),
        ("actuals_floor_preserved", implied_final >= actual),
        ("requires_human_acceptance", True),
    ])


# --------------------------------------------------------------------------- conflicts / queue / warnings

def _conflict(project_key, key, cc, cls, severity, detail, families) -> "OrderedDict":
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cc),
        ("conflict_class", cls), ("severity", severity), ("detail", detail),
        ("families_involved", families), ("requires_human_acceptance", True),
    ])


def _applied_conflicts(project_key, key, cc, abs_thresh, accepted_ctc, accepted_final, implied_remaining,
                       implied_final, delta_ctc, delta_final, ctc_material, final_material, plan_monthly,
                       plan_end, horizon_end, monthly_actuals, freq_basis, out) -> None:
    if accepted_ctc is not None and ctc_material:
        direction = "exceeds" if accepted_ctc > implied_remaining else "is below"
        out.append(_conflict(project_key, key, cc, "staffing_plan_conflicts_with_current_accepted_ctc",
                             "high", f"accepted remaining CTC {money_str(accepted_ctc)} {direction} the "
                             f"staffing-plan implied remaining {money_str(implied_remaining)} "
                             f"(delta {money_str(delta_ctc)})",
                             ["operator_staffing_plan", "forecast_intelligence"]))
    if accepted_final is not None and final_material:
        out.append(_conflict(project_key, key, cc, "staffing_plan_changes_final_cost_materially", "high",
                             f"staffing-plan implied final {money_str(implied_final)} differs materially "
                             f"from accepted final {money_str(accepted_final)} (delta {money_str(delta_final)}); "
                             "advisory only until operator acceptance",
                             ["operator_staffing_plan", "forecast_intelligence"]))
    if horizon_end and plan_end and plan_end < horizon_end:
        out.append(_conflict(project_key, key, cc, "staffing_plan_ends_before_forecast_horizon", "medium",
                             f"staffing plan ends {plan_end} but the forecast horizon runs to {horizon_end}",
                             ["operator_staffing_plan", "forecast_monthly"]))
    # recent actual burn vs plan first month
    if monthly_actuals:
        recent = _recent_burn(monthly_actuals)
        first = next(iter(plan_monthly.values()), ZERO)
        if recent is not None and materiality(first, recent, abs_thresh)[2]:
            out.append(_conflict(project_key, key, cc, "staffing_plan_conflicts_with_recent_actual_burn",
                                 "medium", f"plan first-month {money_str(first)} differs materially from "
                                 f"recent actual monthly burn {money_str(recent)}",
                                 ["operator_staffing_plan", "cost_entry_trend"]))
    # cost-frequency cadence supersession (diagnostic; plan is the stronger forward-looking timing source)
    if freq_basis:
        out.append(_conflict(project_key, key, cc, "staffing_plan_conflicts_with_cost_frequency", "low",
                             f"operator staffing plan supersedes cost-frequency cadence "
                             f"(basis={freq_basis}) as the forward-looking timing source; cadence retained "
                             "as diagnostic",
                             ["operator_staffing_plan", "cost_frequency_cadence"]))


def _queue_and_conflict_unapplied(project_key, cc, mres, plan_total, review_queue, conflicts) -> None:
    status = (mres or {}).get("mapping_status")
    key = (mres or {}).get("numeric_target_budget_code_key")
    if status == ss.M_UNMAPPED or mres is None:
        conflicts.append(_conflict(project_key, key, cc, "staffing_plan_unmapped_cost_code", "high",
                                   f"staffing cost_code '{cc}' (plan total {money_str(plan_total)}) maps to "
                                   "no canonical budget-code key; excluded from applied forecast",
                                   ["operator_staffing_plan"]))
        review_queue.append(_review(project_key, key, cc, "high",
                                    "unmapped staffing cost code — review and add a canonical mapping", status))
    elif status in (ss.M_AMBIGUOUS, ss.M_INVENTED, ss.M_MISMATCH):
        conflicts.append(_conflict(project_key, key, cc, "staffing_plan_ambiguous_mapping", "high",
                                   f"staffing cost_code '{cc}' mapping is {status}: {(mres or {}).get('detail')}; "
                                   "excluded from applied forecast",
                                   ["operator_staffing_plan"]))
        review_queue.append(_review(project_key, key, cc, "high",
                                    f"ambiguous/invalid staffing mapping ({status}) — operator review required",
                                    status))
    else:  # resolved_unique_lab_pending_acceptance
        review_queue.append(_review(project_key, key, cc, "medium",
                                    "unique .LAB resolution awaiting operator acceptance — not applied", status))


def _review(project_key, key, cc, priority, reason, status) -> "OrderedDict":
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cc),
        ("review_priority", priority), ("review_reason", reason), ("mapping_status", status),
        ("requires_human_acceptance", True),
    ])


def _warn(project_key, key, severity, message) -> "OrderedDict":
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key),
        ("warning_type", "staffing_plan_reconciliation_disclosure"),
        ("severity", severity), ("message", message)])


def _recent_burn(monthly_actuals) -> Decimal | None:
    """Mean of the last up-to-3 nonzero monthly actuals (Decimal), or None."""
    vals = []
    for r in monthly_actuals[-3:]:
        v = dec(r.get("actual_cost") if isinstance(r, dict) else r)
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    return sum(vals, ZERO) / Decimal(len(vals))
