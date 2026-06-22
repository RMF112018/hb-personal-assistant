"""As-of backtest of the PRODUCTION reconciled forecast (the trust gate's core scoring).

`backtest_strong` scores individual estimator methods at 40/60/80% owner progress on the
near-complete cohort. This module reuses that exact as-of reconstruction, but instead of scoring
methods in isolation it feeds the as-of per-method EACs through the REAL
``reconcile_final.select_final`` (with the same calibration weights production uses) and scores the
resulting ``recommended_final_cost`` — the value operators actually consume — against the realized
actual. It reports accuracy (MAPE), signed bias (systematic over/under-forecast), worst-case ceiling
coverage, whether blending beats the best single method, and whether it beats a naive "trust ERP"
baseline.

Evidence-only and deterministic: it calls ``select_final`` purely to score history and never alters
any production row. Reconstruction fidelity is APPROXIMATE and disclosed: it rebuilds only the fields
``select_final`` reads, assigns a uniform "medium" reliability (calibration weights — from the same
backtest — carry the per-method differentiation), and uses a neutral trend signal (no reconstructed
``supports_overrun`` bump beyond the ERP-exceedance path). The schedule method has no history and is
absent, exactly as in ``backtest_strong``.
"""

from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.money import D, dec, money_str
from . import backtest_strong as bts
from . import reconcile_final
from . import trend as trend_mod

# Real per-method reliability thresholds (mirror estimators_uncapped) for faithful as-of weighting.
_OWNER_MEDIUM_PCT = Decimal("0.50")
_TREND_MIN_MONTHS = 6
_TREND_MAX_COV = Decimal("0.75")


def _asof_reliabilities(owner_pct: Optional[Decimal], trend_block: dict) -> dict:
    """Each method's REAL reliability at the as-of point (estimators_uncapped rules). The commitment
    pipeline ratio isn't reconstructable at as-of -> 'low' (conservative, under-weights the most
    accurate method); cpi_blend is always 'low'."""
    months = int(trend_block.get("months_of_completed_actuals") or 0)
    cov = dec(trend_block.get("cost_volatility_cov"))
    owner_rel = "medium" if (owner_pct is not None and owner_pct >= _OWNER_MEDIUM_PCT) else "low"
    trend_rel = (
        "medium"
        if (months >= _TREND_MIN_MONTHS and (cov is None or cov <= _TREND_MAX_COV))
        else "low"
    )
    return {
        "owner_progress_eac": owner_rel,
        "trend_projection_eac": trend_rel,
        "commitment_exposure_eac": "low",
        "cpi_blend_eac": "low",
    }


def _q4(x: Decimal) -> str:
    return str(x.quantize(Decimal("0.0001")))


def _mean(xs: list) -> Optional[Decimal]:
    return (sum(xs, Decimal("0")) / Decimal(len(xs))) if xs else None


def _asof_estimates(m: dict, reliabilities: dict) -> list[dict]:
    """select_final-shaped estimate dicts from the as-of per-method EACs (floored to as-of actual),
    each carrying its REAL as-of reliability."""
    actual_t = m["actual_to_t"]
    erp = m.get("erp_projected")
    out = []
    for method in bts.METHODS:
        pred = bts._predict(method, m)
        if pred is None:
            continue
        eac = pred if pred >= actual_t else actual_t
        out.append(
            {
                "method": method,
                "applicable": True,
                "eac": money_str(eac),
                "reliability": reliabilities.get(method, "low"),
                "association_scale": "1.0",
                "exceeds_erp_projected": bool(erp is not None and eac > erp),
            }
        )
    return out


def _asof_bundle(m: dict, budget_amounts: dict, trend_signal) -> dict:
    """Minimal as-of bundle exposing the fields select_final reads (reconstructed trend; owner_sov
    absent)."""
    return {
        "actual_cost_all_source_to_date": money_str(m["actual_to_t"]),
        "projected_costs": money_str(m["erp_projected"])
        if m.get("erp_projected") is not None
        else None,
        "revised_budget": money_str(dec(budget_amounts.get("revised_budget")))
        if dec(budget_amounts.get("revised_budget")) is not None
        else None,
        "committed_costs": money_str(m["committed_costs"])
        if m.get("committed_costs") is not None
        else None,
        "owner_sov_value": None,
        "trend_signal": trend_signal,
        # As-of completion fraction, so the (opt-in) p75 stage-gate is exercised in the backtest.
        # Does not affect the baseline (stage-gate off) recommended value.
        "owner_latest_percent_complete": str(m["owner_pct_to_t"]),
    }


def run_reconciled_backtest(
    context_rows: list,
    owner_history: dict,
    project_key: str,
    calibration: Optional[dict],
    method_summary: Optional[list],
) -> dict:
    """Score the reconciled production forecast as-of vs realized on the near-complete cohort.

    Reuses ``backtest_strong``'s cohort gate + as-of reconstruction; blends the as-of per-method EACs
    via the real ``select_final`` (same ``calibration``); returns a deterministic evidence dict.
    """
    calibration = calibration or {}
    detail = []
    rec_apes: list[Decimal] = []
    rec_biases: list[Decimal] = []
    within_ceiling = 0
    naive_apes: list[Decimal] = []
    per_target: dict[str, list] = {str(t): [] for t in bts.ASOF_TARGETS}
    cohort_keys = set()
    # Recalibrated variant (p75 stage-gate ON) — the before/after the gate reports.
    recal_apes: list[Decimal] = []
    recal_biases: list[Decimal] = []
    recal_within_ceiling = 0
    recal_per_target: dict[str, list] = {str(t): [] for t in bts.ASOF_TARGETS}

    for ctx in context_rows:
        key = ctx.get("budget_code_key")
        owner_rows = owner_history.get(key, [])
        for target in bts.ASOF_TARGETS:
            m = bts._reconstruct(ctx, owner_rows, target)
            if not m:
                continue
            # Reconstruct the as-of trend block via the real production trend.analyze on the monthly
            # series truncated to <= t_month -> faithful trend_signal + reliability inputs.
            monthly_upto = [
                r
                for r in ((ctx.get("actuals") or {}).get("monthly_actuals") or [])
                if r.get("actual_period_bucket") == "through_may_2026"
                and (r.get("month") or "") <= m["t_month"]
            ]
            trend_block = trend_mod.analyze(monthly_upto, m["t_month"], project_key, key)
            reliabilities = _asof_reliabilities(m["owner_pct_to_t"], trend_block)
            ests = _asof_estimates(m, reliabilities)
            if not ests:
                continue
            bundle = _asof_bundle(
                m, ctx.get("budget_amounts") or {}, trend_block.get("trend_signal")
            )
            realized = m["realized_final"]
            if realized <= 0:
                continue
            recommendation = reconcile_final.select_final(
                key, project_key, ests, bundle, calibration
            )
            recommended = D(recommendation["recommended_final_cost"])
            worst = D(recommendation["worst_credible_final_cost"])
            ape = (recommended - realized).copy_abs() / realized
            bias = (recommended - realized) / realized
            in_ceiling = realized <= worst
            rec_apes.append(ape)
            rec_biases.append(bias)
            within_ceiling += 1 if in_ceiling else 0
            per_target[str(target)].append(ape)
            cohort_keys.add(key)

            # Recalibrated variant: same inputs, p75 stage-gate ON.
            recal = reconcile_final.select_final(
                key, project_key, ests, bundle, calibration, p75_stage_gate=True
            )
            recal_recommended = D(recal["recommended_final_cost"])
            recal_worst = D(recal["worst_credible_final_cost"])
            recal_ape = (recal_recommended - realized).copy_abs() / realized
            recal_bias = (recal_recommended - realized) / realized
            recal_apes.append(recal_ape)
            recal_biases.append(recal_bias)
            recal_within_ceiling += 1 if realized <= recal_worst else 0
            recal_per_target[str(target)].append(recal_ape)

            erp = m.get("erp_projected")
            naive_ape = None
            if erp is not None and erp > 0:
                n_ape = (erp - realized).copy_abs() / realized
                naive_apes.append(n_ape)
                naive_ape = _q4(n_ape)

            detail.append(
                OrderedDict(
                    [
                        ("project_key", project_key),
                        ("budget_code_key", key),
                        ("asof_target", str(target)),
                        ("asof_month", m["t_month"]),
                        ("asof_owner_percent_complete", str(m["owner_pct_to_t"])),
                        ("recommended_final_cost", money_str(recommended)),
                        ("worst_credible_final_cost", money_str(worst)),
                        ("realized_actual", money_str(realized)),
                        ("reconciled_abs_pct_error", _q4(ape)),
                        ("reconciled_signed_bias", _q4(bias)),
                        ("realized_within_worst_ceiling", in_ceiling),
                        ("erp_naive_abs_pct_error", naive_ape),
                        ("recalibrated_recommended_final_cost", money_str(recal_recommended)),
                        ("recalibrated_abs_pct_error", _q4(recal_ape)),
                        ("recalibrated_signed_bias", _q4(recal_bias)),
                        ("reconciliation_basis", recommendation.get("reconciliation_basis")),
                    ]
                )
            )

    detail.sort(key=lambda r: (r["budget_code_key"], r["asof_target"]))
    n_obs = len(rec_apes)
    rec_mape = _mean(rec_apes)
    rec_bias = _mean(rec_biases)
    naive_mape = _mean(naive_apes)
    recal_mape = _mean(recal_apes)
    recal_bias = _mean(recal_biases)
    mape_improvement = (
        (rec_mape - recal_mape) if (rec_mape is not None and recal_mape is not None) else None
    )
    bias_abs_improvement = (
        (abs(rec_bias) - abs(recal_bias))
        if (rec_bias is not None and recal_bias is not None)
        else None
    )

    # Best single method (from backtest_strong's per-method summary) for the blending-value comparison.
    best_method = best_method_mape = None
    for row in method_summary or []:
        mp = row.get("mape")
        if mp is None:
            continue
        v = dec(mp)
        if v is not None and (best_method_mape is None or v < best_method_mape):
            best_method_mape, best_method = v, row.get("method")

    blend_minus_best = (
        (rec_mape - best_method_mape)
        if (rec_mape is not None and best_method_mape is not None)
        else None
    )
    rec_minus_naive = (
        (rec_mape - naive_mape) if (rec_mape is not None and naive_mape is not None) else None
    )

    return {
        "project_key": project_key,
        "cohort_size": len(cohort_keys),
        "observation_count": n_obs,
        "asof_targets": [str(t) for t in bts.ASOF_TARGETS],
        "reconciled_final_mape": _q4(rec_mape) if rec_mape is not None else None,
        "reconciled_final_mean_bias": _q4(rec_bias) if rec_bias is not None else None,
        "worst_credible_coverage_rate": _q4(Decimal(within_ceiling) / Decimal(n_obs))
        if n_obs
        else None,
        "best_single_method": best_method,
        "best_single_method_mape": _q4(best_method_mape) if best_method_mape is not None else None,
        "blend_minus_best_method_delta": _q4(blend_minus_best)
        if blend_minus_best is not None
        else None,
        "naive_erp_mape": _q4(naive_mape) if naive_mape is not None else None,
        "reconciled_minus_naive_delta": _q4(rec_minus_naive)
        if rec_minus_naive is not None
        else None,
        "per_target_mape": OrderedDict(
            (t, _q4(mv)) for t, v in per_target.items() if v and (mv := _mean(v)) is not None
        ),
        "recalibrated": {
            "stage_gate_lo": str(reconcile_final.STAGE_GATE_LO),
            "stage_gate_hi": str(reconcile_final.STAGE_GATE_HI),
            "recalibrated_final_mape": _q4(recal_mape) if recal_mape is not None else None,
            "recalibrated_final_mean_bias": _q4(recal_bias) if recal_bias is not None else None,
            "recalibrated_worst_credible_coverage_rate": _q4(
                Decimal(recal_within_ceiling) / Decimal(n_obs)
            )
            if n_obs
            else None,
            "mape_improvement": _q4(mape_improvement) if mape_improvement is not None else None,
            "bias_abs_improvement": _q4(bias_abs_improvement)
            if bias_abs_improvement is not None
            else None,
            "recalibrated_per_target_mape": OrderedDict(
                (t, _q4(mv))
                for t, v in recal_per_target.items()
                if v and (mv := _mean(v)) is not None
            ),
            "note": "p75 overrun-bump stage-gate ON (ramped 0 at/below LO completion -> full at/above "
            "HI or unknown). Production flag default-off; this measures what flipping it would buy.",
        },
        "detail_rows": detail,
        "methodology": (
            "Reconstruct each near-complete code's state at 40/60/80% owner progress (backtest_strong "
            "cohort + as-of truncation), feed the as-of per-method EACs through the real "
            "reconcile_final.select_final (same calibration weights production uses), and score the "
            "blended recommended_final_cost vs realized actual-to-date. MAPE/bias = mean over "
            "observations; coverage = fraction with realized <= worst_credible; naive baseline = trust "
            "the ERP projected cost. Negative blend_minus_best / reconciled_minus_naive => the "
            "production blend adds value."
        ),
        "reconstruction_fidelity_caveats": [
            "Per-method reliability is the REAL estimators_uncapped rule at the as-of point (owner via "
            "owner%, trend via reconstructed months+CoV); commitment is floored to 'low' (pipeline "
            "ratio not reconstructable at as-of) and cpi is always 'low'.",
            "Trend signal is reconstructed via the real trend.analyze on the as-of-truncated monthly "
            "series (not neutral); owner SOV value not reconstructed.",
            "Per-method EAC values still use backtest_strong._predict's simplified forms (full "
            "estimator-formula fidelity via as-of bundle rebuild is deferred).",
            "Schedule method has no history and is absent (same as backtest_strong).",
            "Realized truth = current actual-to-date, valid only for the owner>=95% near-complete cohort.",
        ],
    }
