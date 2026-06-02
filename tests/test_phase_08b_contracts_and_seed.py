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


def test_launchd_scheduling_reason_codes_declared() -> None:
    # Prompt 04 — the LaunchAgent-scheduling + catch-up reason codes are seeded and contract-backed.
    seed = load_phase_08b_automation_policy_seed()
    new_codes = {
        "LAUNCHD_INSTALLED_OK",
        "LAUNCHD_INSTALL_DISABLED_BY_POLICY",
        "CATCH_UP_NEEDED",
        "CATCH_UP_NOT_NEEDED",
        "CATCH_UP_STALE",
    }
    assert new_codes <= set(seed["reason_codes"])
    assert seed["first_run_after_wake"]["enabled"] is True
    assert seed["first_run_after_wake"]["stale_after_days"] == 3
    # Validation (seed reason-codes subset of the contract vocabulary) still passes.
    assert validate_phase_08b_automation_policy()["valid"] is True
    gates = load_phase_08b_contract("data_quality_gates_contract")
    assert new_codes <= set(gates["reason_codes"])


def test_run_registry_locking_reason_codes_declared() -> None:
    # Prompt 05 — the no-overlap-locking + run-registry reason codes are seeded + contract-backed.
    seed = load_phase_08b_automation_policy_seed()
    new_codes = {
        "LOCK_ACQUIRED",
        "RUN_OVERLAP_BLOCKED",
        "STALE_LOCK_RECLAIMED",
        "LOCK_RELEASED",
        "LOCK_RELEASE_TOKEN_MISMATCH",
        "RUN_REGISTERED",
        "RUN_STEP_RECORDED",
    }
    assert new_codes <= set(seed["reason_codes"])
    assert seed["no_overlap_locking"]["enabled"] is True
    assert seed["no_overlap_locking"]["stale_lock_seconds"] == 3600
    assert seed["run_registry"]["enabled"] is True
    assert validate_phase_08b_automation_policy()["valid"] is True
    gates = load_phase_08b_contract("data_quality_gates_contract")
    assert new_codes <= set(gates["reason_codes"])
    # The new substrate gate is a required field (covered) and not a deferred surface.
    assert "run_registry_locking" in gates["required_fields"]
    assert "run_registry_locking" not in gates["deferred_surfaces"]


def test_retry_recovery_reason_codes_declared() -> None:
    # Prompt 06 — retry/backoff + run-recovery reason codes are seeded + contract-backed.
    seed = load_phase_08b_automation_policy_seed()
    new_codes = {
        "RETRY_SCHEDULED",
        "RETRY_SUCCEEDED",
        "RETRY_ATTEMPT_RECORDED",
        "RECOVERY_NEEDED",
        "RECOVERY_NOT_NEEDED",
        "RECOVERY_BLOCKED",
        "RUN_ORPHANED",
        "RUN_RECOVERED",
    }
    assert new_codes <= set(seed["reason_codes"])
    assert seed["retry"]["scheduled_reason_code"] == "RETRY_SCHEDULED"
    assert seed["run_recovery"]["enabled"] is True
    assert seed["run_recovery"]["orphan_status"] == "started"
    assert validate_phase_08b_automation_policy()["valid"] is True
    gates = load_phase_08b_contract("data_quality_gates_contract")
    assert new_codes <= set(gates["reason_codes"])
    assert "retry_recovery" in gates["required_fields"]
    assert "retry_recovery" not in gates["deferred_surfaces"]


def test_freshness_observability_reason_codes_declared() -> None:
    # Prompt 07 — source/runtime/retrieval freshness reason codes are seeded + contract-backed.
    seed = load_phase_08b_automation_policy_seed()
    new_codes = {
        "SOURCE_FRESH",
        "SOURCE_STALE",
        "SOURCE_FRESHNESS_UNKNOWN",
        "RETRIEVAL_FRESH",
        "RETRIEVAL_STALE",
        "RETRIEVAL_INDEX_MISSING",
        "RUNTIME_HEALTH_OK",
        "RUNTIME_HEALTH_DEGRADED",
        "OBSERVABILITY_OK",
        "OBSERVABILITY_DEGRADED",
    }
    assert new_codes <= set(seed["reason_codes"])
    assert seed["freshness"]["enabled"] is True
    assert seed["freshness"]["source_max_age_hours"] == 48
    assert validate_phase_08b_automation_policy()["valid"] is True
    gates = load_phase_08b_contract("data_quality_gates_contract")
    assert new_codes <= set(gates["reason_codes"])
    assert "freshness_observability" in gates["required_fields"]
    assert "freshness_observability" not in gates["deferred_surfaces"]


def test_daily_brief_job_health_reason_codes_declared() -> None:
    # Prompt 08 — daily-brief job-health reason codes are seeded + contract-backed.
    seed = load_phase_08b_automation_policy_seed()
    new_codes = {"JOB_HEALTHY", "JOB_DEGRADED", "JOB_STALE", "JOB_NEVER_RUN"}
    assert new_codes <= set(seed["reason_codes"])
    assert seed["daily_brief_job_health"]["enabled"] is True
    assert seed["daily_brief_job_health"]["max_age_hours"] == 36
    assert validate_phase_08b_automation_policy()["valid"] is True
    gates = load_phase_08b_contract("data_quality_gates_contract")
    assert new_codes <= set(gates["reason_codes"])
    assert "daily_brief_job_health" in gates["required_fields"]
    assert "daily_brief_job_health" not in gates["deferred_surfaces"]
