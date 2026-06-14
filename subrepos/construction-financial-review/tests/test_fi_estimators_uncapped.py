"""Uncapped estimators: floored only to actuals, may exceed ERP/budget, ETC != EAC."""
from decimal import Decimal

from construction_financial_review.common.money import D
from construction_financial_review.forecast_intelligence import estimators_uncapped as est


def _bundle(**over):
    b = {
        "actual_cost_all_source_to_date": "100000.00",
        "projected_costs": "120000.00",
        "revised_budget": "110000.00",
        "committed_costs": "0.00",
        "owner_mapping_status": "none",
        "procore_mapping_status": "none",
        "avg_monthly_burn": "0.00",
        "schedule_influences_estimate": False,
        "schedule_confidence": "0.0",
    }
    b.update(over)
    return b


def test_owner_progress_uncapped_exceeds_erp_and_budget():
    b = _bundle(owner_mapping_status="mapped", owner_latest_percent_complete="0.5")
    e = est.owner_progress_eac(b)
    assert e["applicable"] is True
    assert D(e["eac"]) == Decimal("200000.00")          # actual / 0.5, uncapped
    assert D(e["etc"]) == Decimal("100000.00")          # ETC = EAC - actual, distinct field
    assert e["exceeds_erp_projected"] is True
    assert e["exceeds_revised_budget"] is True


def test_every_estimate_floored_to_actuals():
    # Owner over-billed (pct > 1) would imply EAC < actual; must floor to actual.
    b = _bundle(owner_mapping_status="mapped", owner_latest_percent_complete="1.5")
    e = est.owner_progress_eac(b)
    assert D(e["eac"]) >= D(b["actual_cost_all_source_to_date"])


def test_commitment_exposure_uncapped_above_erp():
    b = _bundle(committed_costs="500000.00", pending_cost_changes="0.00")
    e = est.commitment_exposure_eac(b)
    assert e["applicable"] is True
    assert D(e["eac"]) == Decimal("500000.00")          # committed > ERP projected, not capped
    assert e["exceeds_erp_projected"] is True


def test_near_complete_still_overrun_capable():
    # Owner reports 97% (near complete) but committed cost already exceeds ERP -> overrun-capable.
    b = _bundle(owner_mapping_status="mapped", owner_latest_percent_complete="0.97",
                committed_costs="300000.00")
    comm = est.commitment_exposure_eac(b)
    assert comm["applicable"] is True
    assert D(comm["eac"]) == Decimal("300000.00")
    assert comm["exceeds_erp_projected"] is True        # not suppressed by near-completion


def test_schedule_etc_scaled_but_uncapped_and_etc_distinct():
    b = _bundle(avg_monthly_burn="50000.00", assoc_remaining_duration_days="43.34",
                schedule_influences_estimate=True, schedule_confidence="0.6",
                schedule_association="cost_code_family")
    e = est.schedule_remaining_work_eac(b)
    assert e["applicable"] is True
    # ETC = 50000 * (43.34 / 21.67) = 100000 future cost; EAC = actual + ETC
    assert D(e["etc"]) == Decimal("100000.00")
    assert D(e["eac"]) == Decimal("200000.00")
    assert e["association_scale"] == "0.6"


def test_erp_references_never_independent():
    b = _bundle()
    refs = [est.erp_projected_reference(b), est.erp_eac_reference(b)]
    for r in refs:
        assert r["source"] == "erp_reference"
        assert r["applicable"] is False
        assert "REFERENCE ONLY" in r["note"]
