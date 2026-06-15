"""Cadence/frequency timing evidence for forecast_monthly — the SAME logic as the cost-frequency slice.

This adapter imports the cost-frequency slice's pure functions (one cadence logic, two consumers) and
returns the established monthly-evidence contract ``(row, weight_vector_or_None, confidence_band)``. It
contributes a weekday-normalized weight vector only for weekday cadence (configured staffing + observed
weekly) so codes that already phase well from cost/schedule/invoice are not perturbed; everything else
returns a None vector and the reconciler skips it. Gated by
``forecast_cost_frequency.forecast_monthly_integration_enabled`` — when off, returns None (no-op).

It only SHAPES months; it never produces or changes any cost. The reconciler scales the blended shape to
the accepted cost-to-complete, so the accepted final cost is unchanged by cadence.
"""
from __future__ import annotations

from collections import OrderedDict

from ..forecast_cost_frequency import frequency_detect, frequency_revalidation, staffing_codes
from ..forecast_cost_frequency import monthly_frequency_phasing as fphasing
from ..forecast_cost_frequency.weekday_calendar import add_months

_WEEKDAY_CLASSES = ("weekly_internal_staffing", "weekly_observed")


def _row(project_key, key, cost_code, category, applicable, is_staffing, effective, conf, basis):
    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", key),
        ("cost_code", cost_code),
        ("category", category),
        ("frequency_phasing_applicable", applicable),
        ("is_internal_staffing_code", is_staffing),
        ("effective_frequency_class", effective),
        ("frequency_phasing_confidence", conf),
        ("recommended_monthly_phasing_basis", basis),
    ])


def analyze(budget_code_key, cost_code, category, monthly_actuals, txn_dates, forecast_months,
            cfg_fcf, project_key):
    """Return (row, frequency_weight_vector_or_None, confidence_band). Pure + deterministic."""
    enabled = bool((cfg_fcf or {}).get("forecast_monthly_integration_enabled"))
    if not enabled or not forecast_months:
        return (_row(project_key, budget_code_key, cost_code, category, False, False, "disabled",
                     "none", "disabled"), None, "none")

    is_staffing = staffing_codes.is_internal_staffing_code(budget_code_key, cfg_fcf)
    boundary = add_months(forecast_months[0], -1)
    detected = frequency_detect.classify(monthly_actuals, txn_dates, boundary, cfg_fcf, is_staffing)
    if is_staffing:
        effective = "weekly_internal_staffing"
    else:
        reval = frequency_revalidation.revalidate(detected, cfg_fcf, boundary, is_staffing,
                                                  project_key, budget_code_key, cost_code)
        effective = reval["revalidated_effective_frequency_class"]

    # conservative: only weekday cadence shapes the monthly blend; other cadence defers to existing sources
    vector = fphasing.phasing_weight_vector(effective, forecast_months) if effective in _WEEKDAY_CLASSES else None
    conf = fphasing.phasing_confidence(effective, detected["frequency_confidence"], is_staffing) if vector else "none"
    basis = fphasing.recommended_basis(effective, is_staffing)
    return (_row(project_key, budget_code_key, cost_code, category, vector is not None, is_staffing,
                 effective, conf, basis), vector, conf)
