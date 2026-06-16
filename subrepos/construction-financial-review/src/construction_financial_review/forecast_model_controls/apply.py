"""Resolve forecast-model controls into per-code decisions (fail-closed, deterministic).

``resolve`` composes, per accepted+mapped control and in this precedence order (section 5):
  1. canonical mapping; 2. actuals floor; 3. forecast window; 4. value constraint (equal / cap / floor /
  explicit final / explicit remaining against a selected reference); 5. model type / monthly shape;
  6. generate monthly values; 7. apply accepted cap/equality; 8. reconcile.

Hard rules: only accepted controls apply; pending/rejected are documented but never block downstream.
CostEntries actuals are the only floor (target below actuals -> floor conflict, fail closed). A
not_to_exceed constraint may lower the model result only when accepted, and is disclosed as an operator
constraint — never a silent cap. Manual monthly/total values are validated and reconciled. Two accepted
controls that disagree for one key fail closed (no latest-wins).

The per-key decision carries the resolved window, value constraint, controlled final/remaining, model
type, and the concrete ``monthly_allocation`` (OrderedDict month->Decimal) so downstream consumers
(monthly, comprehensive, combined CSV) consume identical numbers.
"""
from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from decimal import Decimal

from ..common.money import D, dec, money_str
from ..forecast_monthly.monthly_reconcile import _allocate
from . import control_schema as cs
from . import mapping as cmap
from . import model_shapes, target_sources, window_resolver

ZERO = Decimal("0")
ONE = Decimal("1")
CENTS = Decimal("0.01")
_MONTH_RE_LEN = 7  # "YYYY-MM"

# application status vocabulary
A_APPLIED = "applied_model_control"
A_FLOOR = "floor_conflicted_not_applied"
A_PENDING = "pending_not_applied"
A_REJECTED = "rejected_not_applied"
A_DUP = "duplicate_conflict_not_applied"
A_MISSING_REF = "missing_reference_not_applied"
A_AMBIGUOUS_REF = "ambiguous_reference_not_applied"
A_CIRCULAR_REF = "circular_reference_not_applied"
A_IMPOSSIBLE_WINDOW = "impossible_window_not_applied"
A_WINDOW_DEGRADED = "window_degraded_not_applied"
A_MANUAL_INVALID = "manual_values_invalid_not_applied"
A_CONSTRAINT_UNRESOLVABLE = "constraint_unresolvable_not_applied"


def even_weights(months: list) -> "OrderedDict":
    if not months:
        return OrderedDict()
    n = Decimal(len(months))
    return OrderedDict((m, ONE / n) for m in months)


# ---------------------------------------------------------------- value constraint

def _resolve_value_constraint(control, actual, model_final, ref_result):
    """Return (controlled_final, changes_final, constraint_applied, fail_reason). Pure."""
    vc = cs.effective_value_constraint(control)
    if vc == cs.VC_NONE:
        return model_final, False, False, None

    if vc == cs.VC_EXPLICIT_FINAL:
        amt = dec(control.get("explicit_value_amount"))
        if amt is None:
            return None, False, False, "explicit_final_value missing explicit_value_amount"
        return amt, True, True, None
    if vc == cs.VC_EXPLICIT_REMAINING:
        amt = dec(control.get("explicit_value_amount"))
        if amt is None:
            return None, False, False, "explicit_remaining_value missing explicit_value_amount"
        if amt < ZERO:
            return None, False, False, "explicit_remaining_value is negative"
        return (actual if actual is not None else ZERO) + amt, True, True, None

    # reference-based constraints
    if ref_result["circular"]:
        return None, False, False, "circular reference"
    if ref_result["ambiguity"]:
        return None, False, False, "ambiguous reference"
    ref_val = (Decimal(ref_result["resolved_reference_value"])
               if ref_result["resolved_reference_value"] is not None else None)
    if ref_val is None:
        return None, False, False, "missing reference value"

    if vc == cs.VC_EQUAL:
        return ref_val, True, True, None
    if vc in (cs.VC_NOT_TO_EXCEED, cs.VC_NOT_LESS_THAN):
        if model_final is None:
            return None, False, False, "constraint needs model final cost which is unavailable"
        if vc == cs.VC_NOT_TO_EXCEED:
            if model_final > ref_val:
                return ref_val, True, True, None      # cap binds (lowers, disclosed)
            return model_final, False, False, None     # no-op
        if model_final < ref_val:
            return ref_val, True, True, None           # floor-up binds
        return model_final, False, False, None         # no-op
    return None, False, False, f"unhandled value_constraint_policy '{vc}'"


# ---------------------------------------------------------------- monthly generation

def _validate_manual_monthly(control, active_months, allow_outside):
    """Return (alloc OrderedDict, total Decimal, errors list)."""
    mmv = control.get("manual_monthly_values") or {}
    errors, alloc = [], OrderedDict()
    active_set = set(active_months)
    for month in sorted(mmv.keys()):
        amt = dec(mmv[month])
        if not (isinstance(month, str) and len(month) == _MONTH_RE_LEN and month[4] == "-"):
            errors.append(f"invalid month key '{month}'")
            continue
        if amt is None:
            errors.append(f"invalid amount for {month}")
            continue
        if amt < ZERO:
            errors.append(f"negative amount for {month}")
            continue
        if month not in active_set and not allow_outside:
            errors.append(f"month {month} outside active forecast window")
            continue
        alloc[month] = amt
    total = sum(alloc.values(), ZERO)
    full = OrderedDict((m, alloc.get(m, ZERO)) for m in active_months)
    for m in alloc:
        if m not in full:  # outside-window month explicitly allowed
            full[m] = alloc[m]
    return full, total, errors


def _build_monthly(decision_kind, months, remaining, control):
    """Return an OrderedDict month->Decimal allocation reconciling to ``remaining``."""
    mt = cs.effective_model_type(control)
    if mt == cs.MT_MANUAL_TOTAL:
        weights = model_shapes.shape_weights(cs.effective_manual_distribution(control), months)
    else:
        weights = model_shapes.shape_weights(mt, months)
    if weights is None:  # existing_model -> even preview (real shape deferred to monthly package)
        weights = even_weights(months)
    return _allocate(remaining, weights, months)


# ---------------------------------------------------------------- resolution

def _conflict_tuple(decision) -> tuple:
    return (
        money_str(decision["controlled_final_cost"]) if decision["controlled_final_cost"] is not None else None,
        decision["value_constraint_policy"], decision["reference_source"], decision["model_type"],
        decision["forecast_start_policy"], decision["forecast_end_policy"],
    )


def resolve(load_result, mapping_results, cfg_fmc, actuals_by_key, ref_ctx_by_key, schedule_by_key,
            project_schedule, calendar_months, model_final_by_key, model_ctc_by_key, project_key):
    """Resolve model controls into applied decisions + auditable rows. Pure + deterministic."""
    require_accepted = bool(cfg_fmc.get("require_accepted_status_for_value_change", True))
    preserve_floor = bool(cfg_fmc.get("preserve_actuals_floor", True))
    allow_horizon_fallback = bool(cfg_fmc.get("allow_existing_horizon_fallback_when_schedule_missing", False))
    allow_manual_outside = bool(cfg_fmc.get("allow_manual_month_outside_window", False))
    materiality = dec(cfg_fmc.get("manual_monthly_total_materiality")) or CENTS

    mapping_by_id = {m["control_id"]: m for m in mapping_results}

    records = []
    for c in load_result["controls"]:
        records.append(_resolve_one(
            c, mapping_by_id.get(c["control_id"], {}), actuals_by_key, ref_ctx_by_key, schedule_by_key,
            project_schedule, calendar_months, model_final_by_key, model_ctc_by_key,
            require_accepted, preserve_floor, allow_horizon_fallback, allow_manual_outside, materiality))

    # duplicate-conflict among eligible (accepted, otherwise-applicable) controls per key
    groups = defaultdict(list)
    for r in records:
        if r["eligible"]:
            groups[r["key"]].append(r)
    conflicted_keys, winners = {}, {}
    for key, members in groups.items():
        distinct = {_conflict_tuple(r["decision"]) for r in members}
        if len(distinct) > 1:
            conflicted_keys[key] = sorted(r["control_id"] for r in members)
        else:
            winners[key] = sorted(members, key=lambda r: r["control_id"])[-1]["control_id"]

    by_key, applications, resolved_targets = OrderedDict(), [], []
    review_queue, conflicts, warnings, floor_conflicts = [], [], [], []
    counts = Counter()

    for r in records:
        app_status = r["app_status"]
        if r["eligible"]:
            app_status = A_DUP if (r["key"] in conflicted_keys or winners.get(r["key"]) != r["control_id"]) else A_APPLIED
        applied = app_status == A_APPLIED
        counts[r["status"] or "other"] += 1

        resolved_targets.append(_resolved_target_row(project_key, r, app_status))
        applications.append(_application_row(project_key, r, app_status, applied))
        if applied:
            d = r["decision"]
            d["disposition"] = A_APPLIED
            by_key[r["key"]] = d
        q = _queue_row(project_key, r, app_status)
        if q:
            review_queue.append(q)
        conflicts.extend(_conflict_rows(project_key, r, app_status, conflicted_keys.get(r["key"])))
        if app_status == A_FLOOR:
            floor_conflicts.append(_floor_row(project_key, r))
        warnings.extend(_warnings_for(project_key, r, app_status))

    resolved_targets.sort(key=lambda x: (x["budget_code_key"] or "", x["control_id"] or ""))
    applications.sort(key=lambda x: (x["budget_code_key"] or "", x["control_id"] or ""))
    review_queue.sort(key=lambda x: (x.get("review_priority") or "", x.get("budget_code_key") or "",
                                     x.get("control_id") or ""))
    conflicts.sort(key=lambda x: (x.get("budget_code_key") or "", x.get("control_id") or ""))
    warnings.sort(key=lambda x: (x.get("warning_type") or "", x.get("budget_code_key") or ""))

    return OrderedDict([
        ("by_key", by_key), ("applications", applications), ("resolved_targets", resolved_targets),
        ("review_queue", review_queue), ("conflicts", conflicts), ("warnings", warnings),
        ("floor_conflicts", floor_conflicts), ("controlled_budget_codes", sorted(by_key.keys())),
        ("counts", OrderedDict(sorted(counts.items()))),
        ("any_ambiguous_mapping", _acc_any(records, lambda r: r["mapping_status"] == cmap.M_AMBIGUOUS)),
        ("any_invented", _acc_any(records, lambda r: r["mapping_status"] == cmap.M_INVENTED)),
        # reference flags apply only to controls whose value-constraint policy actually uses a reference
        ("any_unknown_source", _acc_any(records, lambda r: _uses_reference(r) and "unknown reference_source" in (r["reference"].get("missing_reason") or ""))),
        ("any_missing_reference", _acc_any(records, lambda r: r["app_status"] == A_MISSING_REF)),
        ("any_ambiguous_reference", _acc_any(records, lambda r: r["app_status"] == A_AMBIGUOUS_REF)),
        ("any_circular_reference", _acc_any(records, lambda r: r["app_status"] == A_CIRCULAR_REF)),
        ("any_floor_conflict", _acc_any(records, lambda r: r["app_status"] == A_FLOOR)),
        ("any_impossible_window", _acc_any(records, lambda r: r["app_status"] == A_IMPOSSIBLE_WINDOW)),
        ("any_window_degraded_blocked", _acc_any(records, lambda r: r["app_status"] == A_WINDOW_DEGRADED)),
        ("any_manual_invalid", _acc_any(records, lambda r: r["app_status"] == A_MANUAL_INVALID)),
        ("any_constraint_unresolvable", _acc_any(records, lambda r: r["app_status"] == A_CONSTRAINT_UNRESOLVABLE)),
        ("any_duplicate_conflict", bool(conflicted_keys)),
        ("duplicate_conflicted_keys", OrderedDict(sorted(conflicted_keys.items()))),
    ])


def _acc_any(records, pred) -> bool:
    return any(r["is_accepted"] and pred(r) for r in records)


def _uses_reference(r) -> bool:
    """True when the control's value-constraint policy actually consumes a reference_source."""
    return cs.effective_value_constraint(r["control"]) in cs.REFERENCE_REQUIRED_POLICIES


def _resolve_one(c, m, actuals_by_key, ref_ctx_by_key, schedule_by_key, project_schedule,
                 calendar_months, model_final_by_key, model_ctc_by_key, require_accepted,
                 preserve_floor, allow_horizon_fallback, allow_manual_outside, materiality):
    cid = c["control_id"]
    key = m.get("mapped_budget_code_key")
    mapping_status = m.get("mapping_status")
    status = c.get("acceptance_status")
    is_accepted = status == "accepted"
    actual = actuals_by_key.get(key)
    model_final = model_final_by_key.get(key)
    model_ctc = model_ctc_by_key.get(key)
    ref_result = target_sources.resolve_reference(c, ref_ctx_by_key.get(key))
    window = window_resolver.resolve_window(c, schedule_by_key.get(key), project_schedule, calendar_months)

    # acceptance / mapping gate first (so pending/rejected never trip value gates)
    base = {"control": c, "control_id": cid, "key": key, "mapping_status": mapping_status,
            "status": status, "is_accepted": is_accepted, "actual": actual, "reference": ref_result,
            "window": window, "model_final": model_final, "eligible": False, "decision": None}
    if mapping_status not in cmap.MAPPED_STATUSES:
        base["app_status"] = "not_applied_" + (mapping_status or "unmapped")
        return base
    if status == "rejected":
        base["app_status"] = A_REJECTED
        return base
    if not is_accepted and require_accepted:
        base["app_status"] = A_PENDING
        return base

    # accepted + mapped: window
    if window["impossible_window"]:
        base["app_status"] = A_IMPOSSIBLE_WINDOW
        return base
    if window["window_degraded"] and not allow_horizon_fallback:
        base["app_status"] = A_WINDOW_DEGRADED
        return base
    active_months = window["active_months"]

    # value constraint
    controlled_final, changes_final, constraint_applied, fail = _resolve_value_constraint(
        c, actual, model_final, ref_result)
    if fail:
        if ref_result["circular"]:
            base["app_status"] = A_CIRCULAR_REF
        elif ref_result["ambiguity"]:
            base["app_status"] = A_AMBIGUOUS_REF
        elif ref_result["missing"] or "reference" in fail:
            base["app_status"] = A_MISSING_REF
        else:
            base["app_status"] = A_CONSTRAINT_UNRESOLVABLE
        return base

    # model / manual monthly
    mt = cs.effective_model_type(c)
    manual_alloc = None
    if mt == cs.MT_MANUAL_MONTHLY:
        manual_alloc, manual_sum, errs = _validate_manual_monthly(c, active_months, allow_manual_outside)
        if errs:
            base["app_status"] = A_MANUAL_INVALID
            base["manual_errors"] = errs
            return base
        # manual sets the totals; reconcile against any value constraint
        manual_final = (actual if actual is not None else ZERO) + manual_sum
        if changes_final and controlled_final is not None:
            if abs(manual_final - controlled_final) > materiality:
                base["app_status"] = A_MANUAL_INVALID
                base["manual_errors"] = [
                    f"manual monthly sum implies final {money_str(manual_final)} but value constraint "
                    f"requires {money_str(controlled_final)}"]
                return base
        controlled_final = manual_final
        changes_final = True
    elif mt == cs.MT_MANUAL_TOTAL:
        mf = dec(c.get("manual_final_cost"))
        mr = dec(c.get("manual_remaining_cost"))
        manual_total_final = mf if mf is not None else ((actual if actual is not None else ZERO) + mr)
        if changes_final and controlled_final is not None and abs(manual_total_final - controlled_final) > materiality:
            base["app_status"] = A_MANUAL_INVALID
            base["manual_errors"] = [
                f"manual_total final {money_str(manual_total_final)} conflicts with value constraint "
                f"{money_str(controlled_final)}"]
            return base
        controlled_final = manual_total_final
        changes_final = True

    # floor
    if controlled_final is None:
        controlled_final = model_final if model_final is not None else actual
    if actual is not None and controlled_final is not None and controlled_final < actual and preserve_floor:
        base["app_status"] = A_FLOOR
        base["controlled_final"] = controlled_final
        return base

    # remaining + monthly allocation
    remaining = (controlled_final - actual) if (controlled_final is not None and actual is not None) else (
        model_ctc if model_ctc is not None else ZERO)
    if remaining < ZERO:
        remaining = ZERO
    if manual_alloc is not None:
        monthly_alloc = manual_alloc
        # ensure reconciliation: manual months define remaining exactly
        remaining = sum(manual_alloc.values(), ZERO)
        controlled_final = (actual if actual is not None else ZERO) + remaining
        vector_source = "manual_monthly"
    else:
        monthly_alloc = _build_monthly(mt, active_months, remaining, c)
        vector_source = (f"manual_total_{cs.effective_manual_distribution(c)}" if mt == cs.MT_MANUAL_TOTAL
                         else ("existing_model" if mt == cs.MT_EXISTING else f"model_shape_{mt}"))

    base["eligible"] = True
    base["app_status"] = A_APPLIED
    base["decision"] = _decision(c, key, actual, model_final, controlled_final, remaining, changes_final,
                                 constraint_applied, window, vector_source, monthly_alloc, ref_result)
    return base


def _decision(c, key, actual, model_final, controlled_final, remaining, changes_final, constraint_applied,
              window, vector_source, monthly_alloc, ref_result) -> "OrderedDict":
    return OrderedDict([
        ("control_id", c["control_id"]), ("budget_code_key", key), ("cost_code", c.get("cost_code")),
        ("control_type", c.get("control_type")), ("acceptance_status", c.get("acceptance_status")),
        ("forecast_start_policy", window["forecast_start_policy"]),
        ("forecast_end_policy", window["forecast_end_policy"]),
        ("resolved_start_date", window["resolved_start_date"]),
        ("resolved_end_date", window["resolved_end_date"]),
        ("schedule_start_basis", window["schedule_start_basis"]),
        ("schedule_end_basis", window["schedule_end_basis"]),
        ("active_months", list(window["active_months"])),
        ("value_constraint_policy", cs.effective_value_constraint(c)),
        ("reference_source", c.get("reference_source")),
        ("reference_field", ref_result.get("reference_field")),
        ("resolved_reference_value", ref_result.get("resolved_reference_value")),
        ("model_type", cs.effective_model_type(c)),
        ("monthly_vector_source", vector_source),
        # Decimal fields for downstream consumers:
        ("actual_cost_to_date", actual),
        ("uncontrolled_model_final_cost", model_final),
        ("controlled_final_cost", controlled_final),
        ("controlled_remaining", remaining),
        ("monthly_allocation", monthly_alloc),
        ("changes_deterministic_final", bool(changes_final)),
        ("constraint_applied", bool(constraint_applied)),
        ("operator_model_controlled", True),
        ("disposition", A_APPLIED),
    ])


# ---------------------------------------------------------------- audit rows

def _resolved_target_row(project_key, r, app_status) -> "OrderedDict":
    d, ref, w = r["decision"], r["reference"], r["window"]
    return OrderedDict([
        ("project_key", project_key), ("control_id", r["control_id"]), ("budget_code_key", r["key"]),
        ("value_constraint_policy", cs.effective_value_constraint(r["control"])),
        ("reference_source", ref.get("reference_source")),
        ("reference_field", ref.get("reference_field")),
        ("resolved_reference_value", ref.get("resolved_reference_value")),
        ("model_type", cs.effective_model_type(r["control"])),
        ("forecast_start_basis", w["schedule_start_basis"]), ("forecast_end_basis", w["schedule_end_basis"]),
        ("active_month_count", w["active_month_count"]),
        ("controlled_final_cost", money_str(d["controlled_final_cost"]) if d else None),
        ("actual_cost_to_date", money_str(r["actual"]) if r["actual"] is not None else None),
        ("controlled_remaining", money_str(d["controlled_remaining"]) if d else None),
        ("changes_deterministic_final", d["changes_deterministic_final"] if d else None),
        ("floor_status", "ok" if app_status != A_FLOOR else "target_below_actuals_floor"),
        ("application_status", app_status),
        ("source_package_type", ref.get("source_package_type")),
        ("source_package_path", ref.get("source_package_path")),
        ("source_file", ref.get("source_file")), ("source_row_id", ref.get("source_row_id")),
        ("reference_is_total_or_remaining", ref.get("reference_is_total_or_remaining")),
        ("alias_used", ref.get("alias_used")), ("resolved_at_package_stamp", None),
    ])


def _application_row(project_key, r, app_status, applied) -> "OrderedDict":
    c, d, w = r["control"], r["decision"], r["window"]
    return OrderedDict([
        ("project_key", c.get("project_key") or project_key), ("control_id", r["control_id"]),
        ("budget_code_key", r["key"]), ("cost_code", c.get("cost_code")),
        ("control_type", c.get("control_type")), ("acceptance_status", c.get("acceptance_status")),
        ("mapping_status", r["mapping_status"]),
        ("value_constraint_policy", cs.effective_value_constraint(c)),
        ("model_type", cs.effective_model_type(c)),
        ("forecast_start_policy", cs.effective_start_policy(c)),
        ("forecast_end_policy", cs.effective_end_policy(c)),
        ("schedule_end_basis", w["schedule_end_basis"]),
        ("controlled_final_cost", money_str(d["controlled_final_cost"]) if d else None),
        ("controlled_remaining", money_str(d["controlled_remaining"]) if d else None),
        ("actual_cost_to_date", money_str(r["actual"]) if r["actual"] is not None else None),
        ("changes_deterministic_final", d["changes_deterministic_final"] if d else None),
        ("constraint_applied", d["constraint_applied"] if d else None),
        ("applied", applied), ("operator_model_controlled", applied),
        ("actuals_floor_respected", app_status != A_FLOOR),
        ("application_status", app_status), ("disposition", app_status),
        ("requires_human_acceptance", c.get("requires_human_acceptance")),
        ("accepted_by", c.get("accepted_by")), ("accepted_at", c.get("accepted_at")),
        ("reason", c.get("reason")),
    ])


def _queue_row(project_key, r, app_status):
    c, key = r["control"], r["key"]
    mp = {
        A_FLOOR: ("selected/controlled final below actual cost to date — rejected (floor preserved)", "high"),
        A_DUP: ("duplicate conflicting accepted model controls for this key", "high"),
        A_MISSING_REF: ("selected reference value missing for this code", "high"),
        A_AMBIGUOUS_REF: ("projected_budget vs projected_costs ambiguity", "high"),
        A_CIRCULAR_REF: ("prior_comprehensive reference is circular (current run)", "high"),
        A_IMPOSSIBLE_WINDOW: ("resolved forecast window has no active months", "high"),
        A_WINDOW_DEGRADED: ("schedule dataset missing and horizon fallback disabled", "high"),
        A_MANUAL_INVALID: ("manual values invalid / do not reconcile", "high"),
        A_CONSTRAINT_UNRESOLVABLE: ("value constraint could not be resolved", "high"),
        A_PENDING: ("pending operator model control — not applied until accepted", "medium"),
        A_REJECTED: ("rejected operator model control — audit only", "low"),
    }
    if r["mapping_status"] not in cmap.MAPPED_STATUSES:
        reason, priority = "control could not be mapped to a canonical budget code", "high"
    elif app_status in mp:
        reason, priority = mp[app_status]
    else:
        return None
    return OrderedDict([
        ("project_key", project_key), ("control_id", c.get("control_id")), ("budget_code_key", key),
        ("cost_code", c.get("cost_code")), ("value_constraint_policy", cs.effective_value_constraint(c)),
        ("model_type", cs.effective_model_type(c)), ("acceptance_status", c.get("acceptance_status")),
        ("application_status", app_status), ("review_priority", priority), ("review_reason", reason),
        ("requires_human_acceptance", c.get("requires_human_acceptance")), ("operator_reason", c.get("reason")),
    ])


def _conflict_rows(project_key, r, app_status, conflicting_ids):
    out = []
    c, key = r["control"], r["key"]

    def row(cclass, severity, detail):
        out.append(OrderedDict([
            ("project_key", project_key), ("control_id", c.get("control_id")), ("budget_code_key", key),
            ("conflict_class", cclass), ("severity", severity), ("detail", detail),
            ("value_constraint_policy", cs.effective_value_constraint(c)),
            ("model_type", cs.effective_model_type(c)), ("requires_human_acceptance", True)]))
    mapping = {
        A_FLOOR: ("operator_model_value_below_actuals", "high"),
        A_DUP: ("operator_model_duplicate_conflict", "high"),
        A_MISSING_REF: ("operator_model_missing_reference", "high"),
        A_AMBIGUOUS_REF: ("operator_model_ambiguous_reference", "high"),
        A_CIRCULAR_REF: ("operator_model_circular_reference", "high"),
        A_IMPOSSIBLE_WINDOW: ("operator_model_impossible_window", "high"),
        A_WINDOW_DEGRADED: ("operator_window_degraded", "high"),
        A_MANUAL_INVALID: ("manual_values_invalid", "high"),
        A_CONSTRAINT_UNRESOLVABLE: ("operator_model_constraint_unresolvable", "high"),
    }
    if app_status in mapping:
        cclass, sev = mapping[app_status]
        detail = (f"conflicting accepted controls {conflicting_ids}" if app_status == A_DUP
                  else "; ".join(r.get("manual_errors") or []) if app_status == A_MANUAL_INVALID
                  else r["reference"].get("missing_reason") or r["reference"].get("ambiguity_reason")
                  or r["window"].get("window_degraded_reason") or app_status)
        row(cclass, sev, detail)
    elif app_status == A_APPLIED and r["decision"] and r["decision"]["constraint_applied"] \
            and cs.effective_value_constraint(c) == cs.VC_NOT_TO_EXCEED:
        row("operator_not_to_exceed_constraint_applied", "medium",
            "operator not_to_exceed constraint lowered the model result (disclosed as operator-controlled)")
    return out


def _floor_row(project_key, r) -> "OrderedDict":
    cf = r.get("controlled_final") if r.get("decision") is None else r["decision"]["controlled_final_cost"]
    return OrderedDict([
        ("project_key", project_key), ("control_id", r["control_id"]), ("budget_code_key", r["key"]),
        ("value_constraint_policy", cs.effective_value_constraint(r["control"])),
        ("controlled_final_cost", money_str(cf) if cf is not None else None),
        ("actual_cost_to_date", money_str(r["actual"]) if r["actual"] is not None else None),
        ("violation", "controlled final cost is below actual cost to date"),
    ])


def _warnings_for(project_key, r, app_status):
    out = []
    c, key = r["control"], r["key"]

    def w(wtype, severity, message):
        out.append(OrderedDict([("project_key", project_key), ("budget_code_key", key),
                                ("control_id", c.get("control_id")), ("warning_type", wtype),
                                ("severity", severity), ("message", message)]))
    if r["mapping_status"] == cmap.M_AMBIGUOUS:
        w("ambiguous_cost_code_mapping", "high",
          "cost_code maps to multiple canonical keys; provide budget_code_key")
    if r["mapping_status"] in (cmap.M_INVENTED, cmap.M_UNMAPPED, cmap.M_MISSING):
        w("control_mapping_failed", "high", f"control not mapped to canonical budget code ({r['mapping_status']})")
    if app_status == A_FLOOR:
        w("controlled_value_below_actuals_floor", "high",
          "controlled final is below actual cost to date; control rejected (actuals floor preserved)")
    if app_status == A_DUP:
        w("duplicate_conflicting_model_controls", "high",
          "two accepted model controls disagree for this budget code")
    if r["window"].get("window_degraded"):
        w("forecast_window_degraded", "medium",
          r["window"].get("window_degraded_reason") or "schedule dataset missing")
    if r["reference"].get("alias_used"):
        w("projected_budget_alias_used", "low", f"projected_budget resolved via {r['reference']['alias_used']}")
    return out
