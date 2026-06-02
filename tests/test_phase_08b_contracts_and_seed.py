"""Phase 08B Prompt 02 — 08B JSON contracts + automation policy YAML seed."""

from __future__ import annotations

from hb_assistant.construction.second_brain.automation_policy import (
    load_phase_08b_automation_policy_seed,
    validate_phase_08b_automation_policy,
)
from hb_assistant.construction.second_brain.contracts import (
    PHASE_08B_CONTRACT_FILES,
    load_all_phase_08b_contracts,
    load_phase_08b_contract,
)


def test_all_08b_contracts_load_with_versions() -> None:
    contracts = load_all_phase_08b_contracts()
    assert set(contracts) == set(PHASE_08B_CONTRACT_FILES)
    for name, contract in contracts.items():
        version = contract.get("version", "")
        assert version.startswith("phase_08b_"), f"{name} bad version {version!r}"


def test_unknown_contract_raises() -> None:
    try:
        load_phase_08b_contract("nope")
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected KeyError for unknown 08B contract")


def test_gates_contract_has_reason_codes() -> None:
    gates = load_phase_08b_contract("data_quality_gates_contract")
    assert gates["reason_codes"], "08B gates contract must declare a reason-code vocabulary"
    assert "HEALTH_CHECK_FAILED" in gates["reason_codes"]
    assert "RETRY_EXHAUSTED" in gates["reason_codes"]


def test_automation_policy_seed_validates() -> None:
    result = validate_phase_08b_automation_policy()
    assert result["valid"] is True, result["violations"]
    assert result["seed_version"] == "phase_08b_automation_policy_v1"
    assert result["reason_codes"]  # non-empty structured vocabulary


def test_automation_policy_alerting_is_local_only() -> None:
    seed = load_phase_08b_automation_policy_seed()
    assert seed["alerting"]["channel"] == "local_only"
    # No external delivery is ever permitted by the policy.
    assert seed["alerting"].get("emit") is False
