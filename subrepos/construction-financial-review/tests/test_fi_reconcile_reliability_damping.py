"""Tests for the opt-in completion-stage reliability damping in reconcile_final.select_final."""

from __future__ import annotations

from decimal import Decimal

from construction_financial_review.common.money import D
from construction_financial_review.forecast_intelligence import reconcile_final as rf

# owner + trend high (overshooting), commitment + cpi lower (steadier). Damping should pull the
# weighted central DOWN at low completion by down-weighting owner + trend.
_ESTS = [
    {
        "method": "owner_progress_eac",
        "applicable": True,
        "eac": "200000.00",
        "reliability": "low",
        "association_scale": "1.0",
        "exceeds_erp_projected": True,
    },
    {
        "method": "trend_projection_eac",
        "applicable": True,
        "eac": "180000.00",
        "reliability": "low",
        "association_scale": "1.0",
        "exceeds_erp_projected": True,
    },
    {
        "method": "commitment_exposure_eac",
        "applicable": True,
        "eac": "110000.00",
        "reliability": "low",
        "association_scale": "1.0",
        "exceeds_erp_projected": False,
    },
    {
        "method": "cpi_blend_eac",
        "applicable": True,
        "eac": "120000.00",
        "reliability": "low",
        "association_scale": "1.0",
        "exceeds_erp_projected": False,
    },
]


def _bundle(owner_pct=None):
    b = {
        "actual_cost_all_source_to_date": "90000.00",
        "projected_costs": "100000.00",
        "trend_signal": None,
    }
    if owner_pct is not None:
        b["owner_latest_percent_complete"] = owner_pct
    return b


def _final(bundle, damp, p75=True):
    return D(
        rf.select_final("k", "t", _ESTS, bundle, {}, p75_stage_gate=p75, reliability_damping=damp)[
            "recommended_final_cost"
        ]
    )


def test_damp_factor_ramp():
    assert rf._reliability_damp_factor(None) == Decimal("1")  # unknown -> full weight
    assert rf._reliability_damp_factor(Decimal("0.30")) == rf.DAMP_MIN  # at/below LO -> floor
    assert rf._reliability_damp_factor(Decimal("0.90")) == Decimal("1")  # at/above HI -> full
    mid = rf._reliability_damp_factor(Decimal("0.55"))  # midpoint of [0.4,0.7]
    assert rf.DAMP_MIN < mid < Decimal("1")


def test_damping_lowers_central_at_low_completion():
    assert _final(_bundle("0.40"), damp=True) < _final(_bundle("0.40"), damp=False)


def test_damping_noop_at_high_completion():
    assert _final(_bundle("0.85"), damp=True) == _final(_bundle("0.85"), damp=False)


def test_damping_noop_when_completion_unknown():
    assert _final(_bundle(), damp=True) == _final(_bundle(), damp=False)


def test_damping_off_is_default_and_unchanged():
    # The default path (no kwargs) equals explicit damping-off.
    b = _bundle("0.40")
    default = D(
        rf.select_final("k", "t", _ESTS, b, {}, p75_stage_gate=True)["recommended_final_cost"]
    )
    assert default == _final(b, damp=False)


def test_damping_never_below_actual_floor():
    assert _final(_bundle("0.10"), damp=True) >= Decimal("90000.00")


def test_worst_credible_ceiling_unaffected_by_damping():
    # Reliability damping changes the weighted central, not the p90/commitment worst-case ceiling.
    on = rf.select_final(
        "k", "t", _ESTS, _bundle("0.40"), {}, p75_stage_gate=True, reliability_damping=True
    )
    off = rf.select_final(
        "k", "t", _ESTS, _bundle("0.40"), {}, p75_stage_gate=True, reliability_damping=False
    )
    assert on["worst_credible_final_cost"] == off["worst_credible_final_cost"]
