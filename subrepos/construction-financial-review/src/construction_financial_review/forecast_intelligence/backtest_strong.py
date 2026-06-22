"""Stronger backtest: multi as-of-T reconstruction on the near-complete cohort.

Extends the single-point owner>=95% backtest by scoring each method at MULTIPLE as-of points
(40/60/80% owner progress), under the next-gen method names, and adds division/family cohort error
breakdowns plus a before/after comparison against the prior forecast-accuracy package. Realized
"final" is only trusted for near-complete codes (owner >= 95%), so incomplete codes are excluded
(reason recorded) rather than scored against a non-final actual. Fully deterministic.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from decimal import Decimal
from typing import Optional

from ..common.budget_keys import cost_code_family, parse_budget_key
from ..common.dates import normalize_date
from ..common.money import D, dec

GOLD_OWNER_PCT = Decimal("0.95")
MIN_REALIZED = Decimal("1000")
ASOF_TARGETS = (Decimal("0.40"), Decimal("0.60"), Decimal("0.80"))

# Calibration-driving method set (feeds production select_final weights). UNCHANGED — adding a method
# here would shift production calibration. procore_progress is reconstructable as-of (see
# _procore_pct_asof) and is scored in the reconciled backtest, but is intentionally NOT in this set.
METHODS = ("owner_progress_eac", "trend_projection_eac", "commitment_exposure_eac", "cpi_blend_eac")
# semantic map from prior forecast_accuracy method names for before/after
PRIOR_EQUIVALENT = {
    "owner_progress_eac": "owner_percent_complete",
    "trend_projection_eac": "burn_rate",
    "commitment_exposure_eac": "commitment_floor",
    "cpi_blend_eac": "cpi_proxy",
}


def _month_of(date_str) -> Optional[str]:
    ds = normalize_date(date_str)
    return ds[:7] if ds else None


def _procore_pct_asof(procore_rows: list, t_month: str) -> Optional[Decimal]:
    """As-of Procore percent complete: per commitment take the latest pay-app row with period_end
    month <= t_month, then sum completed-to-date / sum scheduled-value (mirrors production's latest
    per-commitment aggregation, period-bounded). Returns a fraction in (0, 1], or None if absent."""
    if not procore_rows:
        return None
    latest: dict = {}  # commitment_id -> (date_str, completed, scheduled)
    for r in procore_rows:
        d = normalize_date(r.get("period_end"))
        if not d or d[:7] > t_month:
            continue
        cid = r.get("commitment_id")
        if cid not in latest or d > latest[cid][0]:
            latest[cid] = (
                d,
                dec(r.get("total_completed_and_stored_to_date")),
                dec(r.get("scheduled_value")),
            )
    if not latest:
        return None
    completed = sum((v[1] for v in latest.values() if v[1] is not None), Decimal("0"))
    scheduled = sum((v[2] for v in latest.values() if v[2] is not None), Decimal("0"))
    if scheduled <= 0 or completed <= 0:
        return None
    return min(completed / scheduled, Decimal("1"))


def _reconstruct(
    ctx: dict, owner_rows: list, target: Decimal, procore_rows: Optional[list] = None
) -> Optional[dict]:
    actuals = ctx.get("actuals") or {}
    realized = D(actuals.get("actual_cost_all_source_to_date"))
    if realized < MIN_REALIZED:
        return None
    owner = ctx.get("owner_pay_app") or {}
    final_pct = dec(owner.get("latest_percent_complete"))
    if final_pct is None or final_pct < GOLD_OWNER_PCT:
        return None
    pts = [
        r
        for r in owner_rows
        if normalize_date(r.get("period_to")) and dec(r.get("percent_complete")) is not None
    ]
    pts.sort(key=lambda r: normalize_date(r["period_to"]))
    if len(pts) < 3:
        return None
    asof = min(pts, key=lambda r: abs(dec(r["percent_complete"]) - target))
    asof_pct = dec(asof["percent_complete"])
    if asof_pct is None or asof_pct <= Decimal("0.05") or asof_pct >= final_pct:
        return None
    t_month = _month_of(asof["period_to"])
    final_month = _month_of(pts[-1]["period_to"])
    if not t_month or not final_month or t_month >= final_month:
        return None
    monthly = sorted(
        (
            m
            for m in (actuals.get("monthly_actuals") or [])
            if m.get("actual_period_bucket") == "through_may_2026"
        ),
        key=lambda m: m.get("month") or "",
    )
    upto = [D(m["amount_decimal_string"]) for m in monthly if (m.get("month") or "") <= t_month]
    if not upto:
        return None
    actual_to_t = sum(upto, Decimal("0"))
    if actual_to_t <= 0:
        return None
    window = upto[-6:]
    burn_to_t = sum(window, Decimal("0")) / Decimal(len(window))
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
        "procore_pct_to_t": _procore_pct_asof(procore_rows or [], t_month),
    }


def _predict(method: str, m: dict) -> Optional[Decimal]:
    actual_t = m["actual_to_t"]
    if method == "owner_progress_eac":
        return actual_t / m["owner_pct_to_t"]
    if method == "procore_progress_eac":
        pct = m.get("procore_pct_to_t")
        return actual_t / pct if pct is not None and pct > 0 else None
    if method == "trend_projection_eac":
        return actual_t + m["burn_to_t"] * m["remaining_months"]
    if method == "commitment_exposure_eac":
        c = m["committed_costs"]
        return max(c, actual_t) if c is not None and c > 0 else None
    if method == "cpi_blend_eac":
        proj = m["erp_projected"]
        pcts = [m["owner_pct_to_t"]]
        if proj is not None and proj > 0:
            pcts.append(min(actual_t / proj, Decimal("1")))
        blended = sum(pcts, Decimal("0")) / Decimal(len(pcts))
        return actual_t / blended if blended > 0 else None
    return None


def _mape(errs: list) -> Optional[Decimal]:
    return (sum(errs, Decimal("0")) / Decimal(len(errs))) if errs else None


def run_strong_backtest(
    context_rows: list, owner_history: dict, project_key: str, prior_summary: Optional[list] = None
) -> dict:
    detail = []
    errs: dict[str, list] = {m: [] for m in METHODS}
    biases: dict[str, list] = {m: [] for m in METHODS}
    div_errs: dict[str, list] = defaultdict(list)
    fam_errs: dict[str, list] = defaultdict(list)
    excluded: dict[str, int] = defaultdict(int)
    cohort_keys = set()

    for ctx in context_rows:
        key = ctx.get("budget_code_key")
        parsed = parse_budget_key(key)
        division = parsed[1].split("-")[0] if parsed else None
        family = cost_code_family(parsed[1]) if parsed else None
        owner_rows = owner_history.get(key, [])
        owner = ctx.get("owner_pay_app") or {}
        final_pct = dec(owner.get("latest_percent_complete"))
        if final_pct is None or final_pct < GOLD_OWNER_PCT:
            excluded["not_near_complete"] += 1
            continue
        if D((ctx.get("actuals") or {}).get("actual_cost_all_source_to_date")) < MIN_REALIZED:
            excluded["trivial_realized"] += 1
            continue
        scored_any = False
        for target in ASOF_TARGETS:
            m = _reconstruct(ctx, owner_rows, target)
            if not m:
                continue
            realized = m["realized_final"]
            preds = []
            for method in METHODS:
                pred = _predict(method, m)
                if pred is None or realized <= 0:
                    continue
                pred_f = pred if pred >= m["actual_to_t"] else m["actual_to_t"]
                ape = (pred_f - realized).copy_abs() / realized
                bias = (pred_f - realized) / realized
                errs[method].append(ape)
                biases[method].append(bias)
                if division:
                    div_errs[division].append(ape)
                if family:
                    fam_errs[family].append(ape)
                preds.append(
                    OrderedDict(
                        [
                            ("method", method),
                            ("absolute_percent_error", str(ape.quantize(Decimal("0.0001")))),
                            ("signed_bias", str(bias.quantize(Decimal("0.0001")))),
                        ]
                    )
                )
            if preds:
                scored_any = True
                detail.append(
                    OrderedDict(
                        [
                            ("project_key", project_key),
                            ("budget_code_key", key),
                            ("asof_target", str(target)),
                            ("asof_month", m["t_month"]),
                            ("asof_owner_percent_complete", str(m["owner_pct_to_t"])),
                            ("predictions", preds),
                        ]
                    )
                )
        if scored_any:
            cohort_keys.add(key)
        else:
            excluded["not_reconstructable"] += 1

    summary, raw_weight = [], {}
    for method in METHODS:
        mape = _mape(errs[method])
        mbias = _mape(biases[method]) if biases[method] else None
        summary.append(
            OrderedDict(
                [
                    ("method", method),
                    ("n", len(errs[method])),
                    ("mape", str(mape.quantize(Decimal("0.0001"))) if mape is not None else None),
                    (
                        "mean_bias",
                        str(
                            (
                                sum(biases[method], Decimal("0")) / Decimal(len(biases[method]))
                            ).quantize(Decimal("0.0001"))
                        )
                        if biases[method]
                        else None,
                    ),
                ]
            )
        )
        if mape is not None:
            raw_weight[method] = Decimal("1") / (Decimal("1") + mape)

    calibration = {}
    if raw_weight:
        mean_w = sum(raw_weight.values(), Decimal("0")) / Decimal(len(raw_weight))
        if mean_w > 0:
            for method, w in raw_weight.items():
                calibration[method] = str((w / mean_w).quantize(Decimal("0.0001")))

    before_after = _before_after(summary, prior_summary)
    div_break = [
        OrderedDict(
            [("division", d), ("n", len(v)), ("mape", str(_mape(v).quantize(Decimal("0.0001"))))]
        )
        for d, v in sorted(div_errs.items())
        if v
    ]
    fam_break = [
        OrderedDict(
            [
                ("cost_code_family", f),
                ("n", len(v)),
                ("mape", str(_mape(v).quantize(Decimal("0.0001")))),
            ]
        )
        for f, v in sorted(fam_errs.items())
        if v
    ]

    detail.sort(key=lambda r: (r["budget_code_key"], r["asof_target"]))
    return {
        "cohort_size": len(cohort_keys),
        "asof_targets": [str(t) for t in ASOF_TARGETS],
        "summary_by_method": summary,
        "calibration_weights": calibration,
        "before_after_by_method": before_after,
        "cohort_breakdown_by_division": div_break,
        "cohort_breakdown_by_family": fam_break,
        "excluded_rows": OrderedDict(sorted(excluded.items())),
        "detail_rows": detail,
        "methodology": (
            "Reconstruct each method's EAC at 40/60/80% owner progress (owner apps + monthly "
            "actuals <= T) on the owner>=95% near-complete cohort; score APE/bias vs realized "
            "actual-to-date; calibration multiplier = (1/(1+MAPE)) normalized to mean 1.0. Schedule "
            "ETC has no history and is excluded from calibration. Incomplete codes are excluded "
            "(realized is not final)."
        ),
    }


def _before_after(summary: list, prior_summary: Optional[list]) -> list:
    prior_by = {}
    for row in prior_summary or []:
        prior_by[row.get("method")] = row.get("mape")
    out = []
    for row in summary:
        method = row["method"]
        prior_mape = prior_by.get(PRIOR_EQUIVALENT.get(method))
        new_mape = row.get("mape")
        delta = None
        if prior_mape is not None and new_mape is not None:
            delta = str((dec(new_mape) - dec(prior_mape)).quantize(Decimal("0.0001")))
        out.append(
            OrderedDict(
                [
                    ("method", method),
                    ("prior_method", PRIOR_EQUIVALENT.get(method)),
                    ("prior_mape", prior_mape),
                    ("new_mape", new_mape),
                    ("mape_delta", delta),
                ]
            )
        )
    return out
