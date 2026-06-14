"""Independent EAC/ETC estimators. Every estimate is floored to actual-to-date.

Each estimator is a pure function of a signal bundle returning a normalized estimate dict. ERP-sourced
baselines (``baseline_projected``, ``baseline_erp_eac``) are tagged ``source='erp'`` and are NOT
independent; the five independent methods (burn_rate, owner_percent_complete, commitment_floor,
schedule_etc, cpi_proxy) are what reconciliation leans on. Estimators never read or set the
authoritative rule-based recommendation.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.money import D, dec, money_str

WORKDAYS_PER_MONTH = Decimal("21.67")
OWNER_PCT_FLOOR = Decimal("0.05")     # below this, owner %-complete extrapolation is unreliable
COMPLETE_PCT = Decimal("0.999")
COMPLETE_PCT_NEAR = Decimal("0.95")   # at/above this, scope is treated as essentially complete

# Method registry order is stable for deterministic output.
INDEPENDENT_METHODS = ("burn_rate", "owner_percent_complete", "commitment_floor",
                       "schedule_etc", "cpi_proxy")
ERP_METHODS = ("baseline_projected", "baseline_erp_eac")


def _estimate(method: str, source: str, applicable: bool, eac: Optional[Decimal],
              actual: Decimal, reliability: str, inputs: dict, note: str) -> OrderedDict:
    """Build a normalized estimate; floors EAC to actual-to-date (never below what is spent)."""
    eac_floored = None
    etc = None
    if applicable and eac is not None:
        eac_floored = eac if eac >= actual else actual
        etc = eac_floored - actual
    return OrderedDict([
        ("method", method),
        ("source", source),                       # "erp" | "independent"
        ("applicable", bool(applicable and eac is not None)),
        ("eac", money_str(eac_floored) if eac_floored is not None else None),
        ("etc", money_str(etc) if etc is not None else None),
        ("floored_to_actuals", bool(eac_floored is not None and eac is not None and eac < actual)),
        ("reliability", reliability),             # "high" | "medium" | "low"
        ("inputs", inputs),
        ("note", note),
    ])


def baseline_projected(b: dict) -> OrderedDict:
    actual = D(b.get("actual_cost_all_source_to_date"))
    proj = dec(b.get("projected_costs"))
    return _estimate("baseline_projected", "erp", proj is not None, proj, actual, "medium",
                     {"projected_costs": b.get("projected_costs")},
                     "ERP workbook projected_costs (the number under review).")


def baseline_erp_eac(b: dict) -> OrderedDict:
    actual = D(b.get("actual_cost_all_source_to_date"))
    eac = dec(b.get("estimated_cost_at_completion"))
    return _estimate("baseline_erp_eac", "erp", eac is not None, eac, actual, "medium",
                     {"estimated_cost_at_completion": b.get("estimated_cost_at_completion")},
                     "ERP workbook estimated_cost_at_completion.")


def burn_rate(b: dict) -> OrderedDict:
    """actual_to_date + avg_monthly_burn x remaining months (project horizon).

    Not applicable to near-complete codes (owner >= 95% or schedule complete): burn extrapolation
    over the project horizon would over-forecast finished scope (backtest-confirmed weakness).
    """
    actual = D(b.get("actual_cost_all_source_to_date"))
    burn = dec(b.get("avg_monthly_burn"))
    rem = dec(b.get("remaining_months_project"))
    window = b.get("burn_window_months") or 0
    owner_pct = dec(b.get("owner_latest_percent_complete"))
    near_complete = (owner_pct is not None and owner_pct >= COMPLETE_PCT_NEAR) \
        or b.get("schedule_remaining_work_status") == "complete"
    applicable = (burn is not None and burn > 0 and rem is not None and rem > 0
                  and window >= 3 and actual > 0 and not near_complete)
    eac = (actual + burn * rem) if applicable else None
    rel = "low"
    if applicable:
        cov = dec(b.get("burn_volatility_cov"))
        rel = "medium" if window >= 6 and (cov is None or cov <= Decimal("0.75")) else "low"
    return _estimate("burn_rate", "independent", applicable, eac, actual, rel,
                     {"avg_monthly_burn": b.get("avg_monthly_burn"),
                      "remaining_months_project": b.get("remaining_months_project"),
                      "burn_window_months": window, "burn_volatility_cov": b.get("burn_volatility_cov")},
                     "Trailing-burn extrapolation over the project remaining window.")


def owner_percent_complete(b: dict) -> OrderedDict:
    """actual_to_date / owner_percent_complete (cost assumed proportional to owner progress)."""
    actual = D(b.get("actual_cost_all_source_to_date"))
    pct = dec(b.get("owner_latest_percent_complete"))
    mapped = b.get("owner_mapping_status") not in (None, "none")
    applicable = mapped and pct is not None and pct >= OWNER_PCT_FLOOR and actual > 0
    eac = None
    rel = "low"
    if applicable:
        eac = actual if pct >= COMPLETE_PCT else (actual / pct)
        rel = "medium" if pct >= Decimal("0.50") else "low"
    return _estimate("owner_percent_complete", "independent", applicable, eac, actual, rel,
                     {"owner_latest_percent_complete": b.get("owner_latest_percent_complete"),
                      "owner_mapping_status": b.get("owner_mapping_status")},
                     "Owner-reported progress as a completion proxy (advisory; progress != cost%).")


def commitment_floor(b: dict) -> OrderedDict:
    """max(committed_costs, erp_job_to_date, actual) as a contractual EAC floor."""
    actual = D(b.get("actual_cost_all_source_to_date"))
    committed = dec(b.get("committed_costs"))
    erp_jtd = dec(b.get("erp_job_to_date_costs"))
    applicable = committed is not None and committed > 0
    eac = None
    if applicable:
        eac = max(committed, erp_jtd if erp_jtd is not None else Decimal("0"), actual)
    pipeline = dec(b.get("commitment_pipeline_ratio"))
    rel = "medium" if (pipeline is not None and pipeline >= Decimal("0.50")) else "low"
    return _estimate("commitment_floor", "independent", applicable, eac, actual, rel,
                     {"committed_costs": b.get("committed_costs"),
                      "commitment_invoiced": b.get("commitment_invoiced"),
                      "commitment_pipeline_ratio": b.get("commitment_pipeline_ratio")},
                     "Contractual commitment floor (lower bound on at-completion cost).")


def schedule_etc(b: dict) -> OrderedDict:
    """actual_to_date + avg_monthly_burn x (remaining schedule duration in months)."""
    actual = D(b.get("actual_cost_all_source_to_date"))
    burn = dec(b.get("avg_monthly_burn"))
    rem_days = dec(b.get("schedule_remaining_duration_days"))
    mapped = b.get("schedule_mapping_status") == "mapped"
    open_ct = b.get("schedule_open_activity_count") or 0
    applicable = mapped and burn is not None and burn > 0 and rem_days is not None and rem_days > 0 \
        and open_ct > 0 and actual > 0
    eac = None
    if applicable:
        rem_months = rem_days / WORKDAYS_PER_MONTH
        eac = actual + burn * rem_months
    return _estimate("schedule_etc", "independent", applicable, eac, actual, "low",
                     {"avg_monthly_burn": b.get("avg_monthly_burn"),
                      "schedule_remaining_duration_days": b.get("schedule_remaining_duration_days"),
                      "schedule_open_activity_count": open_ct},
                     "Burn over remaining mapped schedule duration (working-day basis).")


def cpi_proxy(b: dict) -> OrderedDict:
    """EAC = revised_budget / CPI, with CPI = (blended_pct x revised_budget) / actual.

    Reduces to actual / blended_pct, where blended_pct averages available completion proxies
    (owner %, cost ratio actual/projected, schedule completion fraction).
    """
    actual = D(b.get("actual_cost_all_source_to_date"))
    revised = dec(b.get("revised_budget"))
    pcts = []
    owner_pct = dec(b.get("owner_latest_percent_complete"))
    if owner_pct is not None and owner_pct > 0:
        pcts.append(min(owner_pct, Decimal("1")))
    proj = dec(b.get("projected_costs"))
    if proj is not None and proj > 0 and actual > 0:
        pcts.append(min(actual / proj, Decimal("1")))
    # schedule completion fraction
    open_ct = b.get("schedule_open_activity_count") or 0
    # completed not directly in bundle; approximate from remaining-work status when fully complete
    if b.get("schedule_remaining_work_status") == "complete":
        pcts.append(Decimal("1"))
    blended = (sum(pcts, Decimal("0")) / Decimal(len(pcts))) if pcts else None
    applicable = revised is not None and revised > 0 and blended is not None \
        and blended >= OWNER_PCT_FLOOR and actual > 0
    eac = None
    if applicable:
        eac = actual if blended >= COMPLETE_PCT else (actual / blended)
    return _estimate("cpi_proxy", "independent", applicable, eac, actual, "low",
                     {"revised_budget": b.get("revised_budget"),
                      "blended_percent_complete": str(blended.quantize(Decimal("0.0001"))) if blended is not None else None},
                     "Earned-value CPI proxy using a blended completion percent (advisory).")


ALL_ESTIMATORS = (baseline_projected, baseline_erp_eac, burn_rate, owner_percent_complete,
                  commitment_floor, schedule_etc, cpi_proxy)


def estimate_all(b: dict) -> list[OrderedDict]:
    """Run every estimator on one signal bundle; deterministic order."""
    return [fn(b) for fn in ALL_ESTIMATORS]
