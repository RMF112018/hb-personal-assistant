"""Schedule monthly phasing: project-level never phases; direct needs deterministic link."""
from decimal import Decimal

from construction_financial_review.forecast_monthly import schedule_monthly_phasing as smp

MONTHS = ["2026-06", "2026-07", "2026-08"]


def test_project_level_never_phases():
    assoc = {"schedule_association": "project_level", "schedule_confidence": "0.0",
             "influences_code_estimate": False, "latest_schedule_finish": "2026-08-01"}
    row, vec = smp.analyze(assoc, [], MONTHS, "2026-05-26", "tropical", "K")
    assert vec is None
    assert row["used_for_budget_code_phasing"] is False


def test_none_association_no_vector():
    assoc = {"schedule_association": "none", "schedule_confidence": "0.0",
             "influences_code_estimate": False}
    row, vec = smp.analyze(assoc, [], MONTHS, "2026-05-26", "tropical", "K")
    assert vec is None


def test_direct_builds_vector_from_open_features():
    assoc = {"schedule_association": "direct", "schedule_confidence": "1.0",
             "influences_code_estimate": True, "latest_schedule_finish": "2026-08-15",
             "open_activity_count": 2, "direct_mapped_activity_count": 2, "activity_refs": ["A1", "A2"]}
    feats = [{"remaining_start": "2026-06-01", "remaining_finish": "2026-07-31"},
             {"remaining_start": "2026-07-01", "remaining_finish": "2026-08-15"}]
    row, vec = smp.analyze(assoc, feats, MONTHS, "2026-05-26", "tropical", "K")
    assert vec is not None
    assert row["used_for_budget_code_phasing"] is True
    assert sum(vec.values(), Decimal("0")) == Decimal("1")
    assert set(vec).issubset(set(MONTHS))


def test_family_uses_synthetic_span():
    assoc = {"schedule_association": "cost_code_family", "schedule_confidence": "0.6",
             "influences_code_estimate": True, "latest_schedule_finish": "2026-08-01",
             "open_activity_count": 0}
    row, vec = smp.analyze(assoc, [], MONTHS, "2026-05-26", "tropical", "K")
    assert vec is not None       # synthetic span from data date -> latest finish
    assert row["used_for_budget_code_phasing"] is True
