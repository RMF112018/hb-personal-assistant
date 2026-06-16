"""Select the anticipated final cost and detect overruns for one budget code.

Dual posture (approved): a balanced-central ``recommended_final_cost`` PLUS an evidence-supported
``worst_credible_final_cost`` exposure ceiling. Neither is pulled toward ERP — ERP is not in the
independent set and is never used as a cap or a fallback floor. The only hard floor is actuals.

Overrun is reported against four references independently; ``overrun_projected`` is defined against
CURRENT PROJECTED COST (not revised budget), per Bobby's rule.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.money import D, dec, materiality, money_str
from .estimators_uncapped import INDEPENDENT_METHODS

RELIABILITY_WEIGHT = {"high": Decimal("1.0"), "medium": Decimal("0.6"), "low": Decimal("0.3")}
HIGH_DIVERGENCE = Decimal("0.75")
STABLE_COV = Decimal("0.50")

METHOD_FAMILY = {
    "owner_progress_eac": "owner_progress",
    "procore_progress_eac": "procore_progress",
    "schedule_remaining_work_eac": "schedule_remaining_work",
    "trend_projection_eac": "trend",
    "commitment_exposure_eac": "commitment_exposure",
    "cpi_blend_eac": "calibrated_model",
}


def _median(values: list[Decimal]) -> Decimal:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return Decimal("0")
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / Decimal("2")


def _percentile(values: list[Decimal], p: Decimal) -> Decimal:
    """Linear-interpolation percentile (p in [0,1]) over Decimal values."""
    s = sorted(values)
    n = len(s)
    if n == 0:
        return Decimal("0")
    if n == 1:
        return s[0]
    rank = p * Decimal(n - 1)
    lo = int(rank)
    frac = rank - Decimal(lo)
    if lo + 1 >= n:
        return s[-1]
    return s[lo] + (s[lo + 1] - s[lo]) * frac


def _est_value(method: str, estimates: list[dict]) -> Optional[Decimal]:
    for e in estimates:
        if e["method"] == method and e["applicable"]:
            return dec(e["eac"])
    return None


def select_final(budget_code_key: str, project_key: str, estimates: list[dict], bundle: dict,
                 calibration: Optional[dict] = None) -> OrderedDict:
    calibration = calibration or {}
    actual = D(bundle.get("actual_cost_all_source_to_date"))
    projected = dec(bundle.get("projected_costs"))
    revised = dec(bundle.get("revised_budget"))
    committed = dec(bundle.get("committed_costs"))
    owner_sov = dec(bundle.get("owner_sov_value"))
    trend_signal = bundle.get("trend_signal")

    independent = [e for e in estimates
                   if e["method"] in INDEPENDENT_METHODS and e["applicable"] and dec(e["eac"]) is not None]

    contributions = []
    eac_values = []
    weighted_sum = Decimal("0")
    weight_total = Decimal("0")
    any_exceeds_erp = False
    families_over_projected = set()
    for e in independent:
        eac = dec(e["eac"])
        base = RELIABILITY_WEIGHT.get(e["reliability"], Decimal("0.3"))
        calw = dec(calibration.get(e["method"])) or Decimal("1")
        scale = dec(e.get("association_scale")) or Decimal("1")
        w = base * calw * scale
        weighted_sum += eac * w
        weight_total += w
        eac_values.append(eac)
        if e.get("exceeds_erp_projected"):
            any_exceeds_erp = True
        if projected is not None and eac > projected:
            fam, _, mat = e["method"], None, materiality(eac, projected)[2]
            if mat:
                families_over_projected.add(METHOD_FAMILY.get(e["method"], "calibrated_model"))
        contributions.append(OrderedDict([
            ("method", e["method"]),
            ("eac", e["eac"]),
            ("reliability", e["reliability"]),
            ("calibration_weight", str(calw)),
            ("association_scale", str(scale)),
            ("effective_weight", str(w.quantize(Decimal("0.0001")))),
        ]))

    n_ind = len(eac_values)
    commitment_floor_val = _est_value("commitment_exposure_eac", estimates)

    if n_ind == 0:
        # No independent model evidence. ERP is NEVER a fallback floor or modeled final cost.
        central = max(actual, commitment_floor_val) if commitment_floor_val is not None else actual
        worst = central
        median = low = high = central
        divergence = Decimal("0")
        basis = "no_independent_models"
    else:
        weighted_mean = (weighted_sum / weight_total) if weight_total > 0 else _median(eac_values)
        median = _median(eac_values)
        low, high = min(eac_values), max(eac_values)
        divergence = ((high - low) / median) if median > 0 else Decimal("0")
        p75 = _percentile(eac_values, Decimal("0.75"))
        p90 = _percentile(eac_values, Decimal("0.90"))
        if n_ind == 1:
            central = eac_values[0]
        else:
            central = weighted_mean
            # Don't let a low estimate average away a credible overrun.
            if trend_signal == "supports_overrun" or any_exceeds_erp:
                central = max(weighted_mean, p75)
        candidates = [actual, p90]
        if commitment_floor_val is not None:
            candidates.append(commitment_floor_val)
        worst = max(candidates)
        basis = "+".join(c["method"] for c in contributions)

    recommended = central if central >= actual else actual
    worst = worst if worst >= recommended else recommended  # ceiling never below central

    rec_ctc = recommended - actual
    worst_ctc = worst - actual
    var_projected = (recommended - projected) if projected is not None else None
    var_revised = (recommended - revised) if revised is not None else None

    over_proj = _over(recommended, projected)
    over_rev = _over(recommended, revised)
    over_comm = _over(recommended, committed) if (committed is not None and committed > 0) else False
    over_owner = _over(recommended, owner_sov) if (owner_sov is not None and owner_sov > 0) else False
    overrun_projected = over_proj
    worst_overrun = (not overrun_projected) and _over(worst, projected)

    overrun_basis = _basis(overrun_projected, actual, projected, families_over_projected)
    direction = _direction(n_ind, recommended, projected, divergence, bundle, over_comm)

    primary_evidence = [c["method"] for c in sorted(
        contributions, key=lambda c: Decimal(c["effective_weight"]), reverse=True)]
    gaps = _data_gaps(bundle, n_ind)

    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", budget_code_key),
        ("actual_cost_all_source_to_date", money_str(actual)),
        ("current_projected_cost", money_str(projected) if projected is not None else None),
        ("revised_budget", money_str(revised) if revised is not None else None),
        ("committed_cost", money_str(committed) if committed is not None else None),
        ("owner_scope_value", money_str(owner_sov) if owner_sov is not None else None),
        ("erp_projected_reference", money_str(projected) if projected is not None else None),
        ("n_independent_models", n_ind),
        ("recommended_final_cost", money_str(recommended)),
        ("recommended_cost_to_complete", money_str(rec_ctc)),
        ("worst_credible_final_cost", money_str(worst)),
        ("worst_credible_cost_to_complete", money_str(worst_ctc)),
        ("recommended_variance_to_current_projected_cost",
         money_str(var_projected) if var_projected is not None else None),
        ("recommended_variance_to_revised_budget",
         money_str(var_revised) if var_revised is not None else None),
        ("model_eac_low", money_str(low)),
        ("model_eac_high", money_str(high)),
        ("model_eac_median", money_str(median)),
        ("model_divergence", str(divergence.quantize(Decimal("0.0001")))),
        ("forecast_direction", direction),
        ("overrun_projected", overrun_projected),
        ("overrun_vs_current_projected_cost", over_proj),
        ("overrun_vs_revised_budget", over_rev),
        ("overrun_vs_committed_cost", over_comm),
        ("overrun_vs_owner_scope_value", over_owner),
        ("worst_credible_overrun", worst_overrun),
        ("overrun_basis", overrun_basis),
        ("reconciliation_basis", basis),
        ("primary_evidence", primary_evidence),
        ("contributions", contributions),
        ("limiting_data_gaps", gaps),
        ("requires_human_acceptance", True),
    ])


def _over(value: Decimal, ref: Optional[Decimal]) -> bool:
    if ref is None:
        return False
    if value <= ref:
        return False
    return materiality(value, ref)[2]


def _basis(overrun: bool, actual: Decimal, projected: Optional[Decimal], families: set) -> str:
    if not overrun:
        return "none"
    if projected is not None and actual > projected and materiality(actual, projected)[2]:
        return "actuals"
    if len(families) >= 2:
        return "combined"
    if families:
        return next(iter(families))
    return "calibrated_model"


def _direction(n_ind: int, recommended: Decimal, projected: Optional[Decimal],
               divergence: Decimal, bundle: dict, over_committed: bool) -> str:
    if n_ind == 0:
        return "insufficient_evidence"
    if projected is None:
        return "review"
    gap, _, material = materiality(recommended, projected)
    if material and recommended > projected:
        return "increase"
    if material and recommended < projected:
        return "decrease" if _decrease_defensible(bundle, over_committed) else "hold"
    if divergence >= HIGH_DIVERGENCE:
        return "review"
    return "hold"


def _decrease_defensible(bundle: dict, over_committed: bool) -> bool:
    owner_pct = dec(bundle.get("owner_latest_percent_complete"))
    near_complete = (owner_pct is not None and owner_pct >= Decimal("0.95")) \
        or bundle.get("schedule_remaining_work_status") == "complete"
    cov = dec(bundle.get("cost_volatility_cov"))
    stable = cov is None or cov <= STABLE_COV
    return bool(near_complete and bundle.get("trend_signal") != "supports_overrun"
                and not over_committed and stable)


def _data_gaps(bundle: dict, n_ind: int) -> list:
    gaps = list(bundle.get("data_gap_flags") or [])
    if bundle.get("owner_mapping_status") in (None, "none"):
        gaps.append("no_owner_pay_app_evidence")
    if bundle.get("schedule_association") in (None, "none", "project_level"):
        gaps.append("no_code_level_schedule_association")
    if (bundle.get("months_of_completed_actuals") or 0) < 3:
        gaps.append("sparse_actuals_history")
    if n_ind == 0:
        gaps.append("no_independent_model_evidence")
    # de-dup, stable order
    seen, out = set(), []
    for g in gaps:
        if g not in seen:
            seen.add(g)
            out.append(g)
    return out
