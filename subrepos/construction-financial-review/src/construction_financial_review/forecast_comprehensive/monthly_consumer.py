"""Integrated monthly phasing: accepted monthly base + bounded frequency + history curve-shape tilt.

Reshapes months only and reconciles EXACTLY to the integrated cost-to-complete (reusing the monthly
reconciler's allocator). Frequency cadence (weekday-normalized) and the history curve-shape tilt are
bounded timing sources; cost-to-complete and final cost are unchanged by timing. Emits six source shares
(cost_entry / invoice / schedule / history_shape / frequency / fallback).
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, money_str
from ..forecast_monthly.monthly_reconcile import _allocate
from . import human_acceptance as ha

ZERO, ONE = Decimal("0"), Decimal("1")
CENTS = Decimal("0.01")


def _norm(vec: "OrderedDict[str, Decimal]") -> "OrderedDict[str, Decimal]":
    total = sum(vec.values(), ZERO)
    if total <= 0:
        n = Decimal(len(vec) or 1)
        return OrderedDict((m, ONE / n) for m in vec)
    return OrderedDict((m, v / total) for m, v in vec.items())


def _curve_tilt(shape_class: str, months: list) -> "OrderedDict[str, Decimal]":
    """A simple monthly tilt vector from the historical curve-shape class (bounded influence)."""
    n = len(months)
    if n == 0:
        return OrderedDict()
    if shape_class in ("front_loaded", "spike", "tapering_closeout"):
        raw = [Decimal(n - i) for i in range(n)]            # heavier near-term
    elif shape_class == "back_loaded":
        raw = [Decimal(i + 1) for i in range(n)]            # heavier later
    elif shape_class == "s_curve":
        raw = [Decimal(min(i + 1, n - i)) for i in range(n)]  # middle-heavy
    else:
        raw = [ONE for _ in range(n)]                        # flat / linear / volatile / unknown
    return _norm(OrderedDict(zip(months, raw, strict=False)))


def build(project_key, key, entry, sc, integrated_ctc: Decimal) -> tuple:
    cost_code = key.split(".")[1] if "." in key else None
    mdist = entry["monthly_dist"]
    base_weights = mdist.get("monthly_distribution_weights") or []
    months = [w["month"] for w in base_weights]

    # operator forecast-MODEL control: the controlled code's monthly forecast IS the operator's reconciled
    # allocation (window + shape + value), not the blended model timing. It reconciles exactly to the
    # integrated cost-to-complete (which the intelligence consumer already set to the controlled remaining).
    mdec = entry.get("model_control")
    if mdec:
        alloc = mdec.get("monthly_allocation") or {}
        all_months = sorted(set(months) | set(alloc.keys()))
        if not all_months:
            return None, None, None
        month_costs = OrderedDict((m, D(alloc.get(m, ZERO))) for m in all_months)
        total = sum(month_costs.values(), ZERO)
        reconciled = abs(total - integrated_ctc) <= CENTS
        shares = OrderedDict([("cost_entry_share", "0.0000"), ("invoice_share", "0.0000"),
                              ("schedule_share", "0.0000"), ("history_shape_share", "0.0000"),
                              ("frequency_share", "0.0000"), ("fallback_share", "0.0000"),
                              ("operator_model_share", "1.0000")])
        row = OrderedDict([
            ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
            ("integrated_cost_to_complete", money_str(integrated_ctc)),
            ("monthly_costs", [OrderedDict([("forecast_month", m),
                                            ("integrated_month_cost", money_str(month_costs[m]))])
                               for m in all_months]),
            ("source_shares", shares),
            ("reconciles_to_integrated_ctc", bool(reconciled)),
            ("history_consumption_status", sc["history_consumption_status"]),
            ("frequency_consumption_status", sc["frequency_consumption_status"]),
            ("schedule_consumption_status", sc["schedule_consumption_status"]),
            ("operator_controlled", False), ("operator_stop_month", None),
            ("operator_model_controlled", True),
            ("operator_model_control_id", mdec.get("control_id")),
            ("operator_model_type", mdec.get("model_type")),
            ("operator_model_value_constraint_policy", mdec.get("value_constraint_policy")),
            ("operator_forecast_start_date", mdec.get("resolved_start_date")),
            ("operator_forecast_end_date", mdec.get("resolved_end_date")),
            ("operator_schedule_end_basis", mdec.get("schedule_end_basis")),
            ("operator_controlled_final_cost", money_str(mdec["controlled_final_cost"])),
        ])
        ha.stamp(row)
        audit = OrderedDict([("budget_code_key", key),
                             ("integrated_cost_to_complete", money_str(integrated_ctc)),
                             ("monthly_sum", money_str(total)), ("reconciled", bool(reconciled)),
                             ("operator_model_controlled", True)])
        return row, {m: month_costs[m] for m in all_months}, audit

    if not months:
        return None, None, None   # no monthly base for this code (skip; required monthly package covers all)

    base_vec = _norm(OrderedDict((w["month"], D(w["weight"])) for w in base_weights))

    # frequency weekday vector (timing only)
    freq_share = sc["frequency_monthly_weight"]
    fphase = entry["freq_phasing"]
    freq_vec = None
    if freq_share > 0 and fphase.get("monthly_phasing_weights"):
        fw = {w["forecast_month"]: D(w["weight"]) for w in fphase["monthly_phasing_weights"]}
        freq_vec = _norm(OrderedDict((m, fw.get(m, ZERO)) for m in months))
    else:
        freq_share = ZERO

    # history curve-shape tilt (bounded; only when reliability adequate + not contradicted)
    hist_share = sc["history_monthly_shape_weight"]
    hist_vec = None
    if hist_share > 0 and entry["hist_mon"]:
        hist_vec = _curve_tilt(entry["hist_mon"].get("historical_curve_shape_class"), months)
    else:
        hist_share = ZERO

    base_share = ONE - freq_share - hist_share
    if base_share < ZERO:
        base_share = ZERO

    blended = OrderedDict()
    for m in months:
        v = base_vec[m] * base_share
        if freq_vec:
            v += freq_vec[m] * freq_share
        if hist_vec:
            v += hist_vec[m] * hist_share
        blended[m] = v
    blended = _norm(blended)

    # operator forecast control: zero months after an applied stop date and renormalize over the allowed
    # window (timing only; integrated_ctc is unchanged and still reconciles exactly).
    decision = entry.get("operator_control")
    operator_stop_month = None
    if decision and decision.get("timing_applied") and decision.get("stop_month"):
        from ..forecast_controls.apply import restrict_weights
        operator_stop_month = decision["stop_month"]
        blended = restrict_weights(blended, months, operator_stop_month)

    month_costs = _allocate(integrated_ctc, blended, months)
    total = sum(month_costs.values(), ZERO)
    reconciled = abs(total - integrated_ctc) <= CENTS

    # source shares from the accepted monthly package, scaled into the base share
    acc = mdist
    cost_e = D(acc.get("cost_entries_weight")) * base_share
    inv = D(acc.get("subcontractor_invoice_weight")) * base_share
    schd = D(acc.get("schedule_weight")) * base_share
    flat = D(acc.get("flat_weight")) * base_share
    shares = OrderedDict([
        ("cost_entry_share", _q4(cost_e)), ("invoice_share", _q4(inv)),
        ("schedule_share", _q4(schd)), ("history_shape_share", _q4(hist_share)),
        ("frequency_share", _q4(freq_share)), ("fallback_share", _q4(flat)),
    ])

    row = OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
        ("integrated_cost_to_complete", money_str(integrated_ctc)),
        ("monthly_costs", [OrderedDict([("forecast_month", m), ("integrated_month_cost", money_str(month_costs[m]))])
                           for m in months]),
        ("source_shares", shares),
        ("reconciles_to_integrated_ctc", bool(reconciled)),
        ("history_consumption_status", "consumed" if hist_share > 0 else sc["history_consumption_status"]),
        ("frequency_consumption_status", sc["frequency_consumption_status"]),
        ("schedule_consumption_status", sc["schedule_consumption_status"]),
        ("operator_controlled", bool(operator_stop_month)),
        ("operator_stop_month", operator_stop_month),
        ("dormant_status", (entry.get("dormant") or {}).get("dormant_status")),
        ("dormant_suppression_applied",
         bool((entry.get("dormant") or {}).get("suppression_applied") and integrated_ctc == ZERO)),
    ])
    ha.stamp(row)
    audit = OrderedDict([("budget_code_key", key),
                         ("integrated_cost_to_complete", money_str(integrated_ctc)),
                         ("monthly_sum", money_str(total)), ("reconciled", bool(reconciled))])
    return row, {m: month_costs[m] for m in months}, audit


def _q4(x):
    return str(Decimal(x).quantize(Decimal("0.0001")))
