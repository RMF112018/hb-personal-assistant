"""Backtest the estimators on the near-complete cohort to measure accuracy and calibrate weights.

For each near-complete budget code (owner ~>=95%), pick a mid-progress as-of period T, recompute each
applicable method's EAC using ONLY data <= T, and score it against the realized outcome (current
actual-to-date, since the scope is essentially done). Produces per-method MAPE + bias + a calibration
multiplier centered on 1.0 (low-error methods weighted up). Fully deterministic.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.dates import normalize_date
from ..common.money import D, dec, money_str

GOLD_OWNER_PCT = Decimal("0.95")     # cohort: owner-reported >= 95% complete
MIN_REALIZED = Decimal("1000")       # ignore trivial codes
TARGET_ASOF_PCT = Decimal("0.60")    # reconstruct near mid-progress
BACKTEST_METHODS = ("burn_rate", "owner_percent_complete", "commitment_floor", "cpi_proxy")


def _month_of(date_str) -> Optional[str]:
    ds = normalize_date(date_str)
    return ds[:7] if ds else None


def _asof_metrics(ctx: dict, owner_rows: list) -> Optional[dict]:
    """Reconstruct as-of-T inputs for one near-complete code, or None if not reconstructable."""
    actuals = ctx.get("actuals") or {}
    realized = D(actuals.get("actual_cost_all_source_to_date"))
    if realized < MIN_REALIZED:
        return None
    owner = ctx.get("owner_pay_app") or {}
    final_pct = dec(owner.get("latest_percent_complete"))
    if final_pct is None or final_pct < GOLD_OWNER_PCT:
        return None
    # owner apps with a usable period + cumulative-to-date, ordered by period
    pts = [r for r in owner_rows if normalize_date(r.get("period_to")) and dec(r.get("percent_complete")) is not None]
    pts.sort(key=lambda r: normalize_date(r["period_to"]))
    if len(pts) < 3:
        return None
    # pick the as-of app closest to TARGET_ASOF_PCT (mid progress)
    asof = min(pts, key=lambda r: abs(dec(r["percent_complete"]) - TARGET_ASOF_PCT))
    asof_pct = dec(asof["percent_complete"])
    if asof_pct is None or asof_pct <= Decimal("0.05") or asof_pct >= final_pct:
        return None
    t_month = _month_of(asof["period_to"])
    final_month = _month_of(pts[-1]["period_to"])
    if not t_month or not final_month or t_month >= final_month:
        return None

    monthly = sorted((m for m in (actuals.get("monthly_actuals") or [])
                      if m.get("actual_period_bucket") == "through_may_2026"),
                     key=lambda m: m.get("month") or "")
    upto = [D(m["amount_decimal_string"]) for m in monthly if (m.get("month") or "") <= t_month]
    if not upto:
        return None
    actual_to_t = sum(upto, Decimal("0"))
    if actual_to_t <= 0:
        return None
    window = upto[-6:]
    burn_to_t = sum(window, Decimal("0")) / Decimal(len(window))

    # remaining months from T to final owner period
    ty, tm = int(t_month[:4]), int(t_month[5:7])
    fy, fm = int(final_month[:4]), int(final_month[5:7])
    remaining_months = Decimal((fy - ty) * 12 + (fm - tm))
    if remaining_months <= 0:
        return None

    return {
        "realized_final": realized,
        "actual_to_t": actual_to_t,
        "burn_to_t": burn_to_t,
        "owner_pct_to_t": asof_pct,
        "remaining_months": remaining_months,
        "t_month": t_month,
        "committed_costs": dec(ctx.get("budget_amounts", {}).get("committed_costs")),
        "erp_projected": dec(ctx.get("budget_amounts", {}).get("projected_costs")),
    }


def _predict_asof(method: str, m: dict) -> Optional[Decimal]:
    actual_t = m["actual_to_t"]
    if method == "burn_rate":
        return actual_t + m["burn_to_t"] * m["remaining_months"]
    if method == "owner_percent_complete":
        return actual_t / m["owner_pct_to_t"]
    if method == "commitment_floor":
        c = m["committed_costs"]
        return max(c, actual_t) if c is not None and c > 0 else None
    if method == "cpi_proxy":
        proj = m["erp_projected"]
        pcts = [m["owner_pct_to_t"]]
        if proj is not None and proj > 0:
            pcts.append(min(actual_t / proj, Decimal("1")))
        blended = sum(pcts, Decimal("0")) / Decimal(len(pcts))
        return actual_t / blended if blended > 0 else None
    return None


def run_backtest(context_rows: list[dict], owner_history: dict, project_key: str) -> dict:
    """Return {summary_by_method, detail_rows, calibration_weights}."""
    detail = []
    errs: dict[str, list] = {mth: [] for mth in BACKTEST_METHODS}
    biases: dict[str, list] = {mth: [] for mth in BACKTEST_METHODS}

    for ctx in context_rows:
        key = ctx.get("budget_code_key")
        m = _asof_metrics(ctx, owner_history.get(key, []))
        if not m:
            continue
        realized = m["realized_final"]
        row = OrderedDict([
            ("project_key", project_key),
            ("budget_code_key", key),
            ("asof_month", m["t_month"]),
            ("asof_owner_percent_complete", str(m["owner_pct_to_t"])),
            ("actual_to_asof", money_str(m["actual_to_t"])),
            ("realized_final_actual", money_str(realized)),
            ("predictions", []),
        ])
        for mth in BACKTEST_METHODS:
            pred = _predict_asof(mth, m)
            if pred is None or realized <= 0:
                continue
            pred_floored = pred if pred >= m["actual_to_t"] else m["actual_to_t"]
            ape = ((pred_floored - realized).copy_abs() / realized)
            bias = ((pred_floored - realized) / realized)
            errs[mth].append(ape)
            biases[mth].append(bias)
            row["predictions"].append(OrderedDict([
                ("method", mth),
                ("predicted_eac_asof", money_str(pred_floored)),
                ("absolute_percent_error", str(ape.quantize(Decimal("0.0001")))),
                ("signed_bias", str(bias.quantize(Decimal("0.0001")))),
            ]))
        detail.append(row)

    summary = []
    raw_weight = {}
    for mth in BACKTEST_METHODS:
        n = len(errs[mth])
        if n == 0:
            summary.append(OrderedDict([("method", mth), ("n", 0), ("mape", None), ("mean_bias", None)]))
            continue
        mape = sum(errs[mth], Decimal("0")) / Decimal(n)
        mbias = sum(biases[mth], Decimal("0")) / Decimal(n)
        summary.append(OrderedDict([
            ("method", mth), ("n", n),
            ("mape", str(mape.quantize(Decimal("0.0001")))),
            ("mean_bias", str(mbias.quantize(Decimal("0.0001")))),
        ]))
        raw_weight[mth] = Decimal("1") / (Decimal("1") + mape)

    # Normalize calibration multipliers to mean 1.0 across methods that have data.
    calibration = {}
    if raw_weight:
        mean_w = sum(raw_weight.values(), Decimal("0")) / Decimal(len(raw_weight))
        if mean_w > 0:
            for mth, w in raw_weight.items():
                calibration[mth] = str((w / mean_w).quantize(Decimal("0.0001")))

    detail.sort(key=lambda r: r["budget_code_key"])
    return {
        "summary_by_method": summary,
        "detail_rows": detail,
        "calibration_weights": calibration,
        "cohort_size": len(detail),
    }
