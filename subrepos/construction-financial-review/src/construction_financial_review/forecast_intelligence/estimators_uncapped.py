"""Uncapped EAC/ETC estimators. The ONLY clamp is the actuals floor.

Every estimator returns a normalized dict with ETC (future cost only) and EAC (= actual + ETC) as
DISTINCT fields. No estimator reads ERP projected cost, revised budget, committed cost, owner SOV
value, Procore pay-app value, or any prior output as a CEILING. ``exceeds_erp`` / ``exceeds_revised``
are reported for transparency only. ERP figures appear solely as labeled references, never weighted.

Near-complete codes are handled WITHOUT suppressing genuine overruns: burn-based ETC shrinks
organically as the remaining horizon goes to zero, while the owner-progress and commitment-exposure
estimators stay live — so a "done" code whose committed cost or actuals already exceed ERP/budget
still produces an overrun-capable EAC.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.money import D, dec, money_str
from . import timeseries_engine

WORKDAYS_PER_MONTH = Decimal("21.67")
PCT_FLOOR = Decimal("0.05")
COMPLETE_PCT = Decimal("0.999")
ACCEL_MIN = Decimal("0.5")
ACCEL_MAX = Decimal("2.0")

INDEPENDENT_METHODS = ("owner_progress_eac", "procore_progress_eac", "schedule_remaining_work_eac",
                       "trend_projection_eac", "commitment_exposure_eac", "cpi_blend_eac")
REFERENCE_METHODS = ("erp_projected_reference", "erp_eac_reference")


def _norm(method: str, applicable: bool, eac: Optional[Decimal], actual: Decimal, reliability: str,
          b: dict, inputs: dict, note: str, association_scale: str = "1.0",
          source: str = "independent") -> OrderedDict:
    """Build a normalized estimate. Floors EAC to actual only; never caps upward."""
    eac_f = etc = None
    floored = False
    exceeds_erp = exceeds_rev = False
    if applicable and eac is not None:
        eac_f = eac if eac >= actual else actual
        floored = eac < actual
        etc = eac_f - actual
        erp = dec(b.get("projected_costs"))
        revised = dec(b.get("revised_budget"))
        exceeds_erp = erp is not None and eac_f > erp
        exceeds_rev = revised is not None and eac_f > revised
    return OrderedDict([
        ("method", method),
        ("source", source),
        ("applicable", bool(applicable and eac is not None)),
        ("etc", money_str(etc) if etc is not None else None),
        ("eac", money_str(eac_f) if eac_f is not None else None),
        ("floored_to_actuals", floored),
        ("exceeds_erp_projected", exceeds_erp),
        ("exceeds_revised_budget", exceeds_rev),
        ("reliability", reliability),
        ("association_scale", association_scale),
        ("inputs", inputs),
        ("note", note),
    ])


def _reference(method: str, value, label: str) -> OrderedDict:
    return OrderedDict([
        ("method", method),
        ("source", "erp_reference"),
        ("applicable", False),
        ("etc", None),
        ("eac", money_str(value) if dec(value) is not None else None),
        ("floored_to_actuals", False),
        ("exceeds_erp_projected", False),
        ("exceeds_revised_budget", False),
        ("reliability", "reference"),
        ("association_scale", "0.0"),
        ("inputs", {"value": money_str(value)}),
        ("note", label + " — REFERENCE ONLY; never weighted, never a cap or fallback floor."),
    ])


def owner_progress_eac(b: dict) -> OrderedDict:
    actual = D(b.get("actual_cost_all_source_to_date"))
    pct = dec(b.get("owner_latest_percent_complete"))
    mapped = b.get("owner_mapping_status") not in (None, "none")
    applicable = mapped and pct is not None and pct >= PCT_FLOOR and actual > 0
    eac = None
    rel = "low"
    if applicable:
        eac = actual if pct >= COMPLETE_PCT else (actual / pct)
        rel = "medium" if pct >= Decimal("0.50") else "low"
    return _norm("owner_progress_eac", applicable, eac, actual, rel, b,
                 {"owner_latest_percent_complete": b.get("owner_latest_percent_complete"),
                  "owner_mapping_status": b.get("owner_mapping_status")},
                 "actual / owner-reported %-complete (uncapped; cost assumed proportional to owner progress).")


def procore_progress_eac(b: dict) -> OrderedDict:
    actual = D(b.get("actual_cost_all_source_to_date"))
    completed = dec(b.get("procore_latest_total_completed_to_date"))
    scheduled = dec(b.get("procore_scheduled_value"))
    mapped = b.get("procore_mapping_status") not in (None, "none")
    pct = None
    if mapped and completed is not None and scheduled is not None and scheduled > 0 and completed > 0:
        pct = completed / scheduled
    applicable = pct is not None and pct >= PCT_FLOOR and actual > 0
    eac = None
    rel = "low"
    if applicable:
        eac = actual if pct >= COMPLETE_PCT else (actual / pct)
        rel = "medium" if pct >= Decimal("0.50") else "low"
    return _norm("procore_progress_eac", applicable, eac, actual, rel, b,
                 {"procore_completed_to_date": b.get("procore_latest_total_completed_to_date"),
                  "procore_scheduled_value": b.get("procore_scheduled_value"),
                  "procore_percent_complete": str(pct.quantize(Decimal("0.0001"))) if pct is not None else None},
                 "actual / Procore subcontractor %-complete (uncapped).")


def schedule_remaining_work_eac(b: dict) -> OrderedDict:
    """ETC = avg burn x remaining schedule months; EAC = actual + ETC. NOT gated off near-complete."""
    actual = D(b.get("actual_cost_all_source_to_date"))
    burn = dec(b.get("avg_monthly_burn"))
    rem_days = dec(b.get("assoc_remaining_duration_days"))
    influences = bool(b.get("schedule_influences_estimate"))
    scale = b.get("schedule_confidence") or "0.0"
    applicable = (influences and burn is not None and burn > 0
                  and rem_days is not None and rem_days > 0 and actual > 0)
    eac = None
    if applicable:
        rem_months = rem_days / WORKDAYS_PER_MONTH
        eac = actual + burn * rem_months
    return _norm("schedule_remaining_work_eac", applicable, eac, actual, "low", b,
                 {"avg_monthly_burn": b.get("avg_monthly_burn"),
                  "schedule_association": b.get("schedule_association"),
                  "assoc_remaining_duration_days": b.get("assoc_remaining_duration_days"),
                  "schedule_confidence": scale},
                 "actual + burn over remaining mapped/associated schedule duration (uncapped; "
                 "weight scaled by schedule association confidence).", association_scale=scale)


def trend_projection_eac(b: dict) -> OrderedDict:
    """Acceleration-adjusted recent burn projected over the remaining horizon. Uncapped."""
    actual = D(b.get("actual_cost_all_source_to_date"))
    recent = dec(b.get("recent_avg_monthly_burn"))
    months_actual = b.get("months_of_completed_actuals") or 0
    # Prefer schedule horizon when a code-level schedule association exists, else project horizon.
    rem_months = None
    if b.get("schedule_influences_estimate"):
        rem_months = dec(b.get("remaining_months_schedule"))
    if rem_months is None or rem_months <= 0:
        rem_months = dec(b.get("remaining_months_project"))
    accel = dec(b.get("burn_acceleration_ratio"))
    if accel is None:
        accel = Decimal("1")
    accel = max(ACCEL_MIN, min(ACCEL_MAX, accel))
    applicable = (recent is not None and recent > 0 and rem_months is not None and rem_months > 0
                  and months_actual >= 3 and actual > 0)
    eac = None
    rel = "low"
    if applicable:
        eac = actual + recent * accel * rem_months
        cov = dec(b.get("cost_volatility_cov"))
        rel = "medium" if (months_actual >= 6 and (cov is None or cov <= Decimal("0.75"))) else "low"
    return _norm("trend_projection_eac", applicable, eac, actual, rel, b,
                 {"recent_avg_monthly_burn": b.get("recent_avg_monthly_burn"),
                  "burn_acceleration_ratio": b.get("burn_acceleration_ratio"),
                  "applied_acceleration": str(accel.quantize(Decimal("0.0001"))),
                  "remaining_months": str(rem_months) if rem_months is not None else None},
                 "actual + acceleration-adjusted recent burn over remaining horizon (uncapped).")


def commitment_exposure_eac(b: dict) -> OrderedDict:
    """max(actual, committed + net pending change orders). Contractual lower bound; uncapped above."""
    actual = D(b.get("actual_cost_all_source_to_date"))
    committed = dec(b.get("committed_costs"))
    pending = dec(b.get("pending_cost_changes")) or Decimal("0")
    applicable = committed is not None and committed > 0
    eac = None
    if applicable:
        exposure = committed + pending
        eac = max(exposure, actual)
    ratio = dec(b.get("commitment_pipeline_ratio"))
    rel = "medium" if (ratio is not None and ratio >= Decimal("0.50")) else "low"
    return _norm("commitment_exposure_eac", applicable, eac, actual, rel, b,
                 {"committed_costs": b.get("committed_costs"),
                  "pending_cost_changes": b.get("pending_cost_changes"),
                  "commitment_invoiced": b.get("commitment_invoiced"),
                  "commitment_pipeline_ratio": b.get("commitment_pipeline_ratio")},
                 "Committed cost + net pending change orders (uncapped; may exceed ERP when approved "
                 "scope is not yet in ERP projected_costs).")


def cpi_blend_eac(b: dict) -> OrderedDict:
    """actual / blended %-complete over available NON-ERP proxies. Uncapped (no budget ceiling).

    Deliberately excludes any ERP-derived proxy (e.g. actual/projected): anchoring on ERP would make
    this estimator echo ERP projected for evidence-poor codes, which would reintroduce ERP as a
    modeled answer. ERP stays a labeled reference only.
    """
    actual = D(b.get("actual_cost_all_source_to_date"))
    pcts = []
    owner_pct = dec(b.get("owner_latest_percent_complete"))
    if owner_pct is not None and owner_pct > 0:
        pcts.append(min(owner_pct, Decimal("1")))
    completed = dec(b.get("procore_latest_total_completed_to_date"))
    scheduled = dec(b.get("procore_scheduled_value"))
    if completed is not None and scheduled is not None and scheduled > 0 and completed > 0:
        pcts.append(min(completed / scheduled, Decimal("1")))
    if b.get("schedule_remaining_work_status") == "complete":
        pcts.append(Decimal("1"))
    blended = (sum(pcts, Decimal("0")) / Decimal(len(pcts))) if pcts else None
    applicable = blended is not None and blended >= PCT_FLOOR and actual > 0
    eac = None
    if applicable:
        eac = actual if blended >= COMPLETE_PCT else (actual / blended)
    return _norm("cpi_blend_eac", applicable, eac, actual, "low", b,
                 {"blended_percent_complete":
                  str(blended.quantize(Decimal("0.0001"))) if blended is not None else None,
                  "proxy_count": len(pcts)},
                 "Earned-value blend of available completion proxies (uncapped).")


def erp_projected_reference(b: dict) -> OrderedDict:
    return _reference("erp_projected_reference", b.get("projected_costs"), "ERP current projected cost")


def erp_eac_reference(b: dict) -> OrderedDict:
    return _reference("erp_eac_reference", b.get("estimated_cost_at_completion"),
                      "ERP estimated cost at completion")


def timeseries_eac(b: dict) -> OrderedDict:
    """SHADOW classical time-series ensemble EAC. Uncapped (actuals floor only).

    Computed and emitted for comparison/backtest, but NOT in ``INDEPENDENT_METHODS`` — so it never
    enters the weighted central forecast (mirrors the ERP references). Fits the completed monthly
    actuals (CostEntries truth) with a median ensemble (naive/drift/holt/theta-like) and projects the
    remaining horizon. Output quantized to cents for determinism. A statsforecast backend can later
    replace ``timeseries_engine`` behind this same estimator.
    """
    actual = D(b.get("actual_cost_all_source_to_date"))
    series = b.get("monthly_actuals_completed") or []
    vals = [float(D(p.get("amount"))) for p in series]
    n = len(vals)
    # Remaining horizon: prefer schedule when a code-level association exists, else project horizon.
    rem = None
    if b.get("schedule_influences_estimate"):
        rem = dec(b.get("remaining_months_schedule"))
    if rem is None or rem <= 0:
        rem = dec(b.get("remaining_months_project"))
    horizon = int(rem) if rem is not None and rem > 0 else 0
    applicable = n >= 3 and horizon > 0 and actual > 0
    eac = None
    rel = "low"
    fc: dict = {}
    if applicable:
        fc = timeseries_engine.forecast_etc(vals, horizon)
        eac = actual + Decimal(str(round(fc["etc"], 2)))
        rel = "medium" if n >= timeseries_engine.MIN_OBS_FULL_ENSEMBLE else "low"
    inputs = OrderedDict([
        ("backend", timeseries_engine.BACKEND_LABEL),
        ("n_completed_months", n),
        ("horizon_months", horizon),
        ("model_set", fc.get("model_set", [])),
        ("fallback_used", fc.get("fallback_used", False)),
        ("etc_raw", str(round(fc["etc"], 2)) if fc else None),
    ])
    return _norm("timeseries_eac", applicable, eac, actual, rel, b, inputs,
                 "SHADOW classical time-series ensemble (median of naive/drift/holt/theta-like) over "
                 "the remaining horizon; uncapped, never weighted in the central forecast.",
                 association_scale="0.0", source="shadow_timeseries")


ALL_ESTIMATORS = (owner_progress_eac, procore_progress_eac, schedule_remaining_work_eac,
                  trend_projection_eac, commitment_exposure_eac, cpi_blend_eac,
                  erp_projected_reference, erp_eac_reference, timeseries_eac)


def estimate_all(b: dict) -> list[OrderedDict]:
    """Run every estimator on one evidence bundle; deterministic order."""
    return [fn(b) for fn in ALL_ESTIMATORS]
