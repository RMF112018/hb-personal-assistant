"""Tests for the opt-in completion-stage p75 overrun-bump gate in reconcile_final.select_final."""

from __future__ import annotations

from decimal import Decimal

from construction_financial_review.common.money import D
from construction_financial_review.forecast_intelligence import reconcile_final as rf

# Two disagreeing methods, the higher exceeding ERP -> the overrun branch fires (max(weighted_mean,p75)).
_ESTS = [
    {
        "method": "owner_progress_eac",
        "applicable": True,
        "eac": "150000.00",
        "reliability": "medium",
        "association_scale": "1.0",
        "exceeds_erp_projected": True,
    },
    {
        "method": "trend_projection_eac",
        "applicable": True,
        "eac": "100000.00",
        "reliability": "medium",
        "association_scale": "1.0",
        "exceeds_erp_projected": False,
    },
]


def _bundle(owner_pct=None, schedule=None):
    b = {
        "actual_cost_all_source_to_date": "80000.00",
        "projected_costs": "90000.00",
        "trend_signal": None,
    }
    if owner_pct is not None:
        b["owner_latest_percent_complete"] = owner_pct
    if schedule is not None:
        b["schedule_remaining_work_status"] = schedule
    return b


def _final(bundle, gate):
    return D(
        rf.select_final("k", "tropical", _ESTS, bundle, {}, p75_stage_gate=gate)[
            "recommended_final_cost"
        ]
    )


def test_default_off_keeps_p75_bump():
    off = _final(_bundle(owner_pct="0.40"), False)
    assert off == Decimal("137500.00")  # max(weighted_mean=125k, p75=137.5k)


def test_stage_gate_tempers_at_low_completion():
    low = _final(_bundle(owner_pct="0.40"), True)
    off = _final(_bundle(owner_pct="0.40"), False)
    assert low < off  # tempered below the full p75 bump
    assert low == Decimal("125000.00")  # factor 0 at/below LO -> weighted_mean


def test_stage_gate_full_bump_at_high_completion():
    assert _final(_bundle(owner_pct="0.85"), True) == _final(_bundle(owner_pct="0.85"), False)


def test_stage_gate_full_bump_when_completion_unknown():
    # No owner %, no schedule-complete -> unknown -> full bump (conservative; same as off).
    assert _final(_bundle(), True) == _final(_bundle(), False)


def test_stage_gate_partial_ramp_midrange():
    # Owner 0.65 is midway in [0.5, 0.8] -> factor 0.5 -> halfway between weighted_mean and p75.
    mid = _final(_bundle(owner_pct="0.65"), True)
    assert Decimal("125000.00") < mid < Decimal("137500.00")


def test_stage_gate_never_below_actual_floor():
    # Even fully tempered, recommended stays >= actuals.
    assert _final(_bundle(owner_pct="0.10"), True) >= Decimal("80000.00")


def test_schedule_complete_treated_as_full_completion():
    # schedule complete -> completion 1.0 -> full bump even with gate on.
    assert _final(_bundle(schedule="complete"), True) == _final(_bundle(schedule="complete"), False)
