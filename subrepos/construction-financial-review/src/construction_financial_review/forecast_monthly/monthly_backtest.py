"""Monthly-distribution backtest: how well do the timing shapes phase realized monthly cost?

As-of hold-out on codes with enough monthly history: hold out the last K completed months, derive each
method's forward SHAPE from the pre-holdout data, distribute the realized hold-out TOTAL by that shape,
and score the per-month distribution error. This isolates TIMING accuracy (magnitude is the final-cost
backtest of the prior slice). WAPE = Σ|pred−actual| / Σ|actual| is the primary metric (robust to
zero/near-zero months); MAE and MAPE are reported alongside. Schedule phasing has no historical
snapshots, so the comparison is CostEntries-only vs CostEntries+invoice; that limitation is stated.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.money import D, dec, money_str
from .cost_entry_trends import ACCEL_HIGH, ACCEL_LOW, BACK, FLAT, FRONT, shape_weights
from .subcontractor_invoice_trends import _monthly_movement

HOLDOUT = 3
MIN_HISTORY = HOLDOUT + 5          # need enough pre-holdout months
MIN_REALIZED = Decimal("1000")
MIN_COHORT = 8


def _classify(vals: list[Decimal]) -> str:
    n = len(vals)
    if n < 3:
        return FLAT
    burn3 = sum(vals[-3:], Decimal("0")) / Decimal(min(3, n))
    prior3 = (sum(vals[-6:-3], Decimal("0")) / Decimal(3)) if n >= 6 else None
    if prior3 and prior3 > 0:
        accel = burn3 / prior3
        if accel >= ACCEL_HIGH:
            return FRONT
        if accel <= ACCEL_LOW:
            return BACK
    return FLAT


def _wape_mae_mape(errs_abs: list[Decimal], actuals_abs: list[Decimal],
                   biases: list[Decimal]) -> dict:
    n = len(errs_abs)
    if n == 0:
        return {"n_months": 0, "wape": None, "mae": None, "mape": None, "bias": None}
    sum_err = sum(errs_abs, Decimal("0"))
    sum_act = sum(actuals_abs, Decimal("0"))
    wape = (sum_err / sum_act) if sum_act > 0 else None
    mae = sum_err / Decimal(n)
    mape_terms = [e / a for e, a in zip(errs_abs, actuals_abs) if a > 0]
    mape = (sum(mape_terms, Decimal("0")) / Decimal(len(mape_terms))) if mape_terms else None
    bias = sum(biases, Decimal("0")) / Decimal(n)
    return {
        "n_months": n,
        "wape": str(wape.quantize(Decimal("0.0001"))) if wape is not None else None,
        "mae": money_str(mae),
        "mape": str(mape.quantize(Decimal("0.0001"))) if mape is not None else None,
        "bias": str(bias.quantize(Decimal("0.0001"))),
    }


def run_monthly_backtest(context_rows: list, invoice_by_key: dict, project_key: str) -> dict:
    methods = {"cost_entries_only": {"err": [], "act": [], "bias": []},
               "cost_plus_invoice": {"err": [], "act": [], "bias": []}}
    cohort = 0
    excluded = {"insufficient_history": 0, "trivial_realized": 0}

    for ctx in context_rows:
        key = ctx.get("budget_code_key")
        monthly = sorted((m for m in ((ctx.get("actuals") or {}).get("monthly_actuals") or [])
                          if m.get("actual_period_bucket") == "through_may_2026"),
                         key=lambda m: m.get("month") or "")
        if len(monthly) < MIN_HISTORY:
            excluded["insufficient_history"] += 1
            continue
        vals = [D(m["amount_decimal_string"]) for m in monthly]
        if sum((v.copy_abs() for v in vals), Decimal("0")) < MIN_REALIZED:
            excluded["trivial_realized"] += 1
            continue
        train_vals = vals[:-HOLDOUT]
        hold_months = [m["month"] for m in monthly[-HOLDOUT:]]
        hold_actual = vals[-HOLDOUT:]
        realized_total = sum(hold_actual, Decimal("0"))
        if realized_total <= 0:
            excluded["trivial_realized"] += 1
            continue
        cohort += 1

        kind = _classify(train_vals)
        cost_w = shape_weights(hold_months, kind)
        inv_move = _monthly_movement([r for r in invoice_by_key.get(key, [])
                                      if r.get("mapping_status") == "mapped"])
        inv_w = None
        inv_hold = [inv_move.get(m, Decimal("0")) for m in hold_months]
        if sum((x.copy_abs() for x in inv_hold), Decimal("0")) > 0:
            tot = sum((x if x > 0 else Decimal("0")) for x in inv_hold)
            if tot > 0:
                inv_w = OrderedDict((m, (inv_hold[i] if inv_hold[i] > 0 else Decimal("0")) / tot)
                                    for i, m in enumerate(hold_months))

        for method, weights in (("cost_entries_only", cost_w),
                                ("cost_plus_invoice",
                                 _blend(cost_w, inv_w, hold_months) if inv_w else cost_w)):
            for i, m in enumerate(hold_months):
                pred = realized_total * weights[m]
                act = hold_actual[i]
                methods[method]["err"].append((pred - act).copy_abs())
                methods[method]["act"].append(act.copy_abs())
                methods[method]["bias"].append(
                    ((pred - act) / realized_total) if realized_total > 0 else Decimal("0"))

    summary = OrderedDict()
    for method, d in methods.items():
        summary[method] = _wape_mae_mape(d["err"], d["act"], d["bias"])

    co = summary["cost_entries_only"]
    cpi = summary["cost_plus_invoice"]
    before_after = OrderedDict([
        ("primary_metric", "WAPE"),
        ("cost_entries_only_wape", co["wape"]),
        ("cost_plus_invoice_wape", cpi["wape"]),
        ("wape_delta", str((dec(cpi["wape"]) - dec(co["wape"])).quantize(Decimal("0.0001")))
         if (co["wape"] and cpi["wape"]) else None),
        ("invoice_improved_phasing", bool(co["wape"] and cpi["wape"] and dec(cpi["wape"]) < dec(co["wape"]))),
    ])
    warning = None
    if cohort < MIN_COHORT:
        warning = (f"Monthly backtest cohort is small ({cohort} codes < {MIN_COHORT}); monthly "
                   "distribution accuracy is indicative only.")

    return {
        "cohort_size": cohort,
        "holdout_months": HOLDOUT,
        "summary_by_method": summary,
        "before_after": before_after,
        "excluded_rows": OrderedDict(sorted(excluded.items())),
        "schedule_limitation": ("Schedule phasing has no historical monthly snapshots; only "
                                "CostEntries-only vs CostEntries+invoice are backtested."),
        "cohort_warning": warning,
    }


def _blend(cost_w, inv_w, months):
    out = OrderedDict()
    for m in months:
        out[m] = (cost_w[m] + inv_w[m]) / Decimal("2")
    total = sum(out.values(), Decimal("0"))
    if total > 0:
        for m in months:
            out[m] = out[m] / total
    return out
