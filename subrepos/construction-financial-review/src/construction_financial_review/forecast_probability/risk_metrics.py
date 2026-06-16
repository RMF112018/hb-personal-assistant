"""Reducers over the simulated matrices: percentiles, exceedance probabilities, tail metrics,
downside drivers, monthly risk. Pure numpy; money/probabilities are serialized as Decimal strings.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

import numpy as np
from scipy.stats import percentileofscore

from ..common.money import money_str

PCTS = (10, 50, 80, 90, 95)
P4 = Decimal("0.0001")
P2 = Decimal("0.01")


def m(x) -> str:
    """Money string (2dp) from a numpy/python float."""
    return money_str(float(x))


def p4(x) -> str:
    """Unit-interval probability / ratio as a 4dp Decimal string."""
    return str(Decimal(str(float(x))).quantize(P4))


def p2(x) -> str:
    return str(Decimal(str(float(x))).quantize(P2))


def _pctiles(arr) -> dict:
    vals = np.percentile(arr, PCTS)
    return OrderedDict((f"p{p}", m(v)) for p, v in zip(PCTS, vals))


def project_summary(sim, arrays, project, params) -> OrderedDict:
    pf = sim["project_finals"]
    det_rec = project["total_recommended_final_cost"]
    det_worst = project["total_worst_credible_final_cost"]
    det_proj = project["total_current_projected_cost"]
    det_actual = project["total_actual_to_date"]
    det_rb = project["total_revised_budget"]
    over_rb = np.maximum(pf - det_rb, 0.0)          # project overrun vs revised budget, floored at 0
    mean = float(pf.mean())
    p90 = float(np.percentile(pf, 90))
    p50 = float(np.percentile(pf, 50))
    tail = pf[pf >= p90]
    cvar90 = float(tail.mean()) if tail.size else p90
    return OrderedDict([
        ("runs", sim["runs"]), ("seed", sim["seed"]),
        ("simulation_method", "shifted_lognormal_ctc + one_factor_gaussian_copula"),
        ("antithetic_variates", sim["antithetic"]), ("latin_hypercube_systemic", sim["lhs"]),
        ("systemic_correlation_rho", p4(arrays["rho"])),
        ("total_actual_to_date", m(det_actual)),
        ("deterministic_current_projected_cost", m(det_proj)),
        ("deterministic_recommended_final_cost", m(det_rec)),
        ("deterministic_worst_credible_final_cost", m(det_worst)),
        ("simulated_final_cost_percentiles", _pctiles(pf)),
        ("simulated_mean_final_cost", m(mean)),
        ("simulated_std_final_cost", m(float(pf.std(ddof=1)))),
        ("value_at_risk_p90", m(p90)),
        ("conditional_value_at_risk_p90", m(cvar90)),
        ("prob_meets_or_exceeds_recommended_final", p4((pf >= det_rec).mean())),
        ("prob_exceeds_recommended_final", p4((pf > det_rec).mean())),
        ("prob_exceeds_worst_credible_final", p4((pf > det_worst).mean())),
        ("prob_exceeds_current_projected_total", p4((pf > det_proj).mean())),
        # Project-level revised-budget probability (mirrors the per-code revised-budget metric).
        ("revised_budget_total", m(det_rb)),
        ("probability_project_exceeds_revised_budget_total", p4((pf > det_rb).mean())),
        ("expected_project_overrun_vs_revised_budget_total", m(float(over_rb.mean()))),
        ("p80_overrun_vs_revised_budget_total", m(float(np.percentile(over_rb, 80)))),
        ("p90_overrun_vs_revised_budget_total", m(float(np.percentile(over_rb, 90)))),
        ("p95_overrun_vs_revised_budget_total", m(float(np.percentile(over_rb, 95)))),
        ("recommended_final_percentile_rank", p2(percentileofscore(pf, det_rec, kind="mean"))),
        ("worst_credible_final_percentile_rank", p2(percentileofscore(pf, det_worst, kind="mean"))),
        ("current_projected_percentile_rank", p2(percentileofscore(pf, det_proj, kind="mean"))),
        ("revised_budget_final_percentile_rank", p2(percentileofscore(pf, det_rb, kind="mean"))),
        ("systemic_variance_share", p4(_systemic_share(sim, arrays))),
        ("p50_minus_deterministic_recommended", m(p50 - det_rec)),
        # Carry-forward reconciliation: separates accounting actual, the deterministic prior-month
        # forecast carried forward (0 unless a later --forecast-start-month is used), the simulated
        # remaining-window CTC, and the simulated final. Carried forecast is NOT actual cost.
        ("window_reconciliation", OrderedDict([
            ("forecast_start_override_active", bool(project.get("window_override_active", False))),
            ("accounting_actual_cost_to_date", m(det_actual)),
            ("deterministic_prior_forecast_before_probability_window",
             m(float(project.get("total_carried_prior_forecast", 0.0)))),
            ("simulated_probability_window_cost_to_complete",
             m(mean - det_actual - float(project.get("total_carried_prior_forecast", 0.0)))),
            ("simulated_final_cost_including_carried_forecast", m(mean)),
            ("identity",
             "simulated_final = accounting_actual + deterministic_prior_forecast + simulated_window_ctc"),
        ])),
    ])


def _systemic_share(sim, arrays):
    """Empirical share of project-total variance explained by the shared systemic factor.

    Regress project totals on the systemic standard-normal draws; R^2 is the systemic share.
    """
    pf = sim["project_finals"]
    z = sim["systemic_normals"]
    if pf.std() == 0 or z.std() == 0:
        return 0.0
    r = float(np.corrcoef(pf, z)[0, 1])
    return max(0.0, min(1.0, r * r))


def code_rows(sim, arrays, operator_value_constraints=None) -> list:
    finals = sim["final_costs"]
    keys = arrays["keys"]
    actual = arrays["actual"]
    rec = arrays["recommended_final"]
    worst = arrays["worst_credible_final"]
    proj = arrays["current_projected"]
    rb = arrays["revised_budget"]
    near = arrays["near_complete"]
    constraints = operator_value_constraints or {}
    pct = np.percentile(finals, PCTS, axis=0)        # (5, n)
    mean = finals.mean(axis=0)
    std = finals.std(axis=0, ddof=1)
    rows = []
    for j, key in enumerate(keys):
        col = finals[:, j]
        row = OrderedDict([
            ("project_key", "tropical"), ("budget_code_key", key),
            ("cost_code", _cc(key)),
            ("actual_cost_to_date", m(actual[j])),
            ("deterministic_recommended_final_cost", m(rec[j])),
            ("deterministic_worst_credible_final_cost", m(worst[j])),
            ("current_projected_cost", m(proj[j])),
            ("revised_budget", m(rb[j])),
            ("near_complete", bool(near[j])),
            ("simulated_p10", m(pct[0, j])), ("simulated_p50", m(pct[1, j])),
            ("simulated_p80", m(pct[2, j])), ("simulated_p90", m(pct[3, j])),
            ("simulated_p95", m(pct[4, j])),
            ("simulated_mean", m(mean[j])), ("simulated_std", m(std[j])),
            ("prob_exceeds_current_projected_cost", p4((col > proj[j]).mean())),
            ("prob_exceeds_revised_budget", p4((col > rb[j]).mean())),
            ("prob_exceeds_recommended_final_cost", p4((col > rec[j]).mean())),
            ("requires_human_acceptance", True),
        ])
        _disclose_operator_constraint(row, constraints.get(key))
        rows.append(row)
    return rows


def _disclose_operator_constraint(row, c) -> None:
    """Append operator value-cap disclosure to a code row. A binding accepted not_to_exceed cap is an
    operator constraint (p50==p90==controlled final, no simulated upside), NOT a hidden model cap; a
    reference below actuals is a disclosed floor event where actuals win. Counterfactual uncapped risk
    evidence is preserved either way. Untouched codes get no extra fields."""
    if not c:
        return
    base = OrderedDict([
        ("operator_value_constraint_policy", c["value_constraint_policy"]),
        ("operator_control_id", c.get("control_id")),
        ("reference_source", c["reference_source"]),
        ("reference_field", c["reference_field"]),
        ("reference_value", m(c["reference_value"])),
        ("acceptance_status", "accepted"),
        ("requires_human_acceptance_operator_constraint", True),
        ("deterministic_controlled_final_cost", m(c["controlled_final"])),
        ("uncapped_model_final", m(c["uncapped_model_final"])),
        ("uncapped_p50", m(c.get("uncapped_p50", c["uncapped_model_final"]))),
        ("uncapped_p90", m(c.get("uncapped_p90", c["uncapped_model_final"]))),
        ("cap_delta_to_uncapped_model", m(c.get("cap_delta_to_uncapped_model", 0.0))),
    ])
    if c.get("operator_constrained"):
        base["cap_binding"] = True
        base["upside_simulated"] = False
        base["probability_treatment"] = "operator_constrained_not_to_exceed"
        base["reason"] = "accepted_not_to_exceed_projected_cost"
    elif c.get("floor_event"):
        base["cap_binding"] = False
        base["upside_simulated"] = True
        base["probability_treatment"] = "actuals_floor_over_reference"
        base["reason"] = "reference_below_actual_cost_to_date_actuals_floor_wins"
    else:
        base["cap_binding"] = False
        base["upside_simulated"] = True
        base["probability_treatment"] = "operator_reference_non_binding"
        base["reason"] = "reference_at_or_above_model_final_no_constraint"
    row.update(base)


def overrun_probability_rows(sim, arrays) -> list:
    finals = sim["final_costs"]
    keys = arrays["keys"]
    proj = arrays["current_projected"]
    rb = arrays["revised_budget"]
    rows = []
    for j, key in enumerate(keys):
        col = finals[:, j]
        over_proj = col[col > proj[j]]
        expected_overrun = float((col - proj[j]).clip(min=0).mean())
        cvar = float(over_proj.mean() - proj[j]) if over_proj.size else 0.0
        rows.append(OrderedDict([
            ("project_key", "tropical"), ("budget_code_key", key),
            ("prob_exceeds_current_projected_cost", p4((col > proj[j]).mean())),
            ("prob_exceeds_revised_budget", p4((col > rb[j]).mean())),
            ("expected_overrun_vs_current_projected", m(expected_overrun)),
            ("conditional_overrun_given_exceed", m(cvar)),
            ("requires_human_acceptance", True),
        ]))
    return rows


def downside_ranking(sim, arrays) -> list:
    """Per-code contribution to the project downside (co-tail attribution).

    In the runs where the project total is in its top decile (>= project P90), each code's mean cost
    above its own overall mean is its contribution to the bad case. Ranked descending.
    """
    finals = sim["final_costs"]
    pf = sim["project_finals"]
    keys = arrays["keys"]
    p90 = np.percentile(pf, 90)
    mask = pf >= p90
    overall_mean = finals.mean(axis=0)
    tail_mean = finals[mask].mean(axis=0) if mask.any() else overall_mean
    contrib = tail_mean - overall_mean
    order = np.argsort(-contrib)
    rows = []
    for rank, j in enumerate(order, start=1):
        rows.append(OrderedDict([
            ("project_key", "tropical"), ("budget_code_key", keys[j]),
            ("cost_code", _cc(keys[j])),
            ("downside_contribution_to_project_p90", m(contrib[j])),
            ("tail_mean_final_cost", m(tail_mean[j])),
            ("overall_mean_final_cost", m(overall_mean[j])),
            ("rank", rank),
        ]))
    return rows


def monthly_rows(sim, arrays, project) -> list:
    """Per code per month: simulated P50/P90 monthly cost + prob the month carries overrun exposure."""
    mc = sim["month_costs"]                # (runs, n, nm)
    keys = arrays["keys"]
    months = _months(arrays)
    rows = []
    p50 = np.percentile(mc, 50, axis=0)    # (n, nm)
    p90 = np.percentile(mc, 90, axis=0)
    mean = mc.mean(axis=0)
    for j, key in enumerate(keys):
        for t, month in enumerate(months):
            rows.append(OrderedDict([
                ("project_key", "tropical"), ("budget_code_key", key),
                ("forecast_month", month),
                ("simulated_p50_month_cost", m(p50[j, t])),
                ("simulated_p90_month_cost", m(p90[j, t])),
                ("simulated_mean_month_cost", m(mean[j, t])),
            ]))
    return rows


def project_monthly_rows(sim, arrays, project) -> list:
    mc = sim["month_costs"]                              # (runs, n, nm)
    months = _months(arrays)
    proj_month = mc.sum(axis=1)                          # (runs, nm)
    cum = proj_month.cumsum(axis=1) + project["total_actual_to_date"]   # cumulative actual+forecast
    det_proj = project["total_current_projected_cost"]
    rows = []
    for t, month in enumerate(months):
        col = proj_month[:, t]
        cum_t = cum[:, t]
        rows.append(OrderedDict([
            ("project_key", "tropical"), ("forecast_month", month), ("month_sequence", t + 1),
            ("simulated_p10_month_cost", m(np.percentile(col, 10))),
            ("simulated_p50_month_cost", m(np.percentile(col, 50))),
            ("simulated_p90_month_cost", m(np.percentile(col, 90))),
            ("simulated_mean_month_cost", m(col.mean())),
            ("cumulative_actual_plus_forecast_p50", m(np.percentile(cum_t, 50))),
            ("cumulative_actual_plus_forecast_p90", m(np.percentile(cum_t, 90))),
            ("prob_cumulative_exceeds_current_projected_total", p4((cum_t > det_proj).mean())),
        ]))
    return rows


def monthly_risk_ranking(project_month_rows) -> OrderedDict:
    by_cost = sorted(project_month_rows, key=lambda r: float(r["simulated_p50_month_cost"]), reverse=True)
    by_overrun = sorted(project_month_rows,
                        key=lambda r: float(r["prob_cumulative_exceeds_current_projected_total"]),
                        reverse=True)
    return OrderedDict([
        ("months_ranked_by_simulated_p50_cost",
         [OrderedDict([("forecast_month", r["forecast_month"]),
                       ("simulated_p50_month_cost", r["simulated_p50_month_cost"]),
                       ("simulated_p90_month_cost", r["simulated_p90_month_cost"])]) for r in by_cost]),
        ("months_ranked_by_overrun_probability",
         [OrderedDict([("forecast_month", r["forecast_month"]),
                       ("prob_cumulative_exceeds_current_projected_total",
                        r["prob_cumulative_exceeds_current_projected_total"])]) for r in by_overrun]),
        ("highest_cost_month", by_cost[0]["forecast_month"] if by_cost else None),
        ("highest_overrun_risk_month", by_overrun[0]["forecast_month"] if by_overrun else None),
    ])


def _cc(key):
    parts = key.split(".")
    return parts[1] if len(parts) == 3 else None


def _months(arrays):
    return arrays["months"]
