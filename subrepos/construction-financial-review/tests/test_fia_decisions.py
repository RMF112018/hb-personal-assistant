"""Improvement support-decision table tests."""
from construction_financial_review.forecast_improvement_audit.decisions import (
    DECISION_ENUM,
    build_decisions,
    data_inventory,
    sqlite_inventory,
)

from tests._fia_fixtures import minimal_inputs


def test_seven_decisions_in_enum_and_evidence_linked():
    decisions = build_decisions(minimal_inputs(), {})
    assert len(decisions) == 7
    ids = [d["improvement_id"] for d in decisions]
    assert ids == [f"priority_{i}" for i in range(1, 8)]
    for d in decisions:
        assert d["decision"] in DECISION_ENUM
        assert d["evidence"], f"{d['improvement_id']} has no evidence"
        assert d["changes_output_contract"] is False
        assert d["advisory_only"] is True


def test_priority_1_implemented_and_validated():
    decisions = build_decisions(minimal_inputs(), {})
    assert decisions[0]["decision"] == "implemented_and_validated"


def test_priority_7_unsupported_when_db_absent():
    decisions = build_decisions(minimal_inputs(db={"db_present": False}), {})
    p7 = next(d for d in decisions if d["improvement_id"] == "priority_7")
    assert p7["decision"] == "unsupported_data_gap"


def test_inventories_shape():
    inputs = minimal_inputs()
    di = data_inventory(inputs)
    assert di["project_key"] == "tropical" and "packages" in di
    si = sqlite_inventory(inputs)
    assert si["mutation_performed"] is False
    assert si["read_only_mode"].endswith("mode=ro")
