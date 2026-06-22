"""Tests for the opt-in completion-stage reliability damping (overshooter-targeted, monotonic-down)."""

from __future__ import annotations

from decimal import Decimal

from construction_financial_review.common.money import D
from construction_financial_review.forecast_intelligence import reconcile_final as rf


def _est(method, eac, rel="low", exceeds=False):
    return {
        "method": method,
        "applicable": True,
        "eac": eac,
        "reliability": rel,
        "association_scale": "1.0",
        "exceeds_erp_projected": exceeds,
    }


def _bundle(owner_pct=None, actual="80000.00", projected="90000.00"):
    b = {
        "actual_cost_all_source_to_date": actual,
        "projected_costs": projected,
        "trend_signal": None,
    }
    if owner_pct is not None:
        b["owner_latest_percent_complete"] = owner_pct
    return b


def _final(ests, bundle, damp):
    return D(
        rf.select_final("k", "t", ests, bundle, {}, p75_stage_gate=True, reliability_damping=damp)[
            "recommended_final_cost"
        ]
    )


# owner + trend high (the overshooters here), commitment + cpi lower.
_OWNER_HIGH = [
    _est("owner_progress_eac", "200000.00", "medium", exceeds=True),
    _est("trend_projection_eac", "180000.00", exceeds=True),
    _est("commitment_exposure_eac", "100000.00", "medium"),
    _est("cpi_blend_eac", "110000.00"),
]
# owner + trend LOW, a different method (procore) is the real overshooter -- the +$113k shape.
_PROCORE_HIGH = [
    _est("owner_progress_eac", "120000.00", "medium"),
    _est("trend_projection_eac", "95000.00"),
    _est("procore_progress_eac", "900000.00", exceeds=True),
    _est("cpi_blend_eac", "200000.00", exceeds=True),
    _est("commitment_exposure_eac", "130000.00", "medium"),
]


def test_damp_factor_ramp():
    assert rf._reliability_damp_factor(None) == Decimal("1")
    assert rf._reliability_damp_factor(Decimal("0.30")) == rf.DAMP_MIN
    assert rf._reliability_damp_factor(Decimal("0.90")) == Decimal("1")
    assert rf.DAMP_MIN < rf._reliability_damp_factor(Decimal("0.55")) < Decimal("1")


def test_monotonic_down_owner_high():
    assert _final(_OWNER_HIGH, _bundle("0.40"), True) < _final(_OWNER_HIGH, _bundle("0.40"), False)


def test_monotonic_down_when_overshooter_is_not_owner_or_trend():
    # The previously-broken shape: owner/trend are the LOW anchors; the overshooter is another method.
    # Position-based damping targets the high estimates, so the central goes DOWN (never up).
    off = _final(_PROCORE_HIGH, _bundle("0.30"), False)
    on = _final(_PROCORE_HIGH, _bundle("0.30"), True)
    assert on < off  # reduces (was a +$113k INCREASE under the old fixed-method damping)


def test_no_op_at_high_completion():
    assert _final(_OWNER_HIGH, _bundle("0.85"), True) == _final(_OWNER_HIGH, _bundle("0.85"), False)


def test_no_op_when_completion_unknown():
    assert _final(_OWNER_HIGH, _bundle(), True) == _final(_OWNER_HIGH, _bundle(), False)


def test_default_off_equals_explicit_off():
    b = _bundle("0.40")
    default = D(
        rf.select_final("k", "t", _OWNER_HIGH, b, {}, p75_stage_gate=True)["recommended_final_cost"]
    )
    assert default == _final(_OWNER_HIGH, b, False)


def test_never_below_actual_floor():
    assert _final(_OWNER_HIGH, _bundle("0.10", actual="80000.00"), True) >= Decimal("80000.00")


def test_worst_credible_ceiling_unaffected():
    on = rf.select_final(
        "k", "t", _PROCORE_HIGH, _bundle("0.30"), {}, p75_stage_gate=True, reliability_damping=True
    )
    off = rf.select_final(
        "k", "t", _PROCORE_HIGH, _bundle("0.30"), {}, p75_stage_gate=True, reliability_damping=False
    )
    assert on["worst_credible_final_cost"] == off["worst_credible_final_cost"]


def test_damp_ref_is_median_of_independent_eacs():
    assert rf._median(
        [D("95000.00"), D("120000.00"), D("130000.00"), D("200000.00"), D("900000.00")]
    ) == D("130000.00")
