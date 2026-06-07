"""Phase 10 Prompt 01 — contracts, seeds, policy, and proof tests.

Covers: contract load (success + unknown/stale fail-closed), seed validation (success + invalid
+ missing fail-closed), the ActionCandidate enforcement model (source-ref requirement, forbidden
raw fields, high-stakes review routing), the contracts proof envelope, and the CLI exit codes.
No DB, no Ollama, no network — declarative substrate only.
"""

from __future__ import annotations

import json

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai import (
    ActionCandidate,
    Phase10ContractError,
    RawContentPolicy,
    build_phase_10_contracts_proof,
    load_ai_job_policy,
    load_all_phase_10_contracts,
    load_local_model_profiles,
    load_mcp_packet_policy,
    load_obsidian_vault_policy,
    load_phase_10_contract,
    load_raw_content_policy,
)
from hb_assistant.construction.second_brain.local_ai import contracts as c10

runner = CliRunner()

PHASE_10_CONTRACT_NAMES = sorted(c10.PHASE_10_CONTRACT_FILES)


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------
def test_all_contracts_load() -> None:
    contracts = load_all_phase_10_contracts()
    assert len(contracts) == 11  # 10 original + phase_10a raw_content_policy_contract
    for name, body in contracts.items():
        assert isinstance(body, dict) and body, name
    # The action candidate schema is a JSON Schema; the rest carry a logical schema id + version.
    assert contracts["action_candidate_output_schema"]["title"] == "Phase10ActionCandidate"
    assert contracts["ai_job_contract"]["version"] == "1.0.0"
    # Prompt 01 addendum: raw content policy contract present
    assert "raw_content_policy_contract" in contracts


def test_contract_provenance_requires_source_refs() -> None:
    schema = load_phase_10_contract("action_candidate_output_schema")
    assert {"source_refs", "confidence"} <= set(schema["required"])
    assert schema["properties"]["source_refs"]["minItems"] == 1
    assert schema["properties"]["external_action_requires_approval"]["const"] is True


def test_unknown_contract_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        load_phase_10_contract("does_not_exist")


def test_stale_contract_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing/empty packaged contract is fail-closed, not a silent empty dict."""
    monkeypatch.setattr(c10, "_load_json_resource", lambda _filename: {})
    with pytest.raises(Phase10ContractError):
        load_phase_10_contract("ai_job_contract")


# ---------------------------------------------------------------------------
# Seeds (success)
# ---------------------------------------------------------------------------
def test_seeds_validate() -> None:
    profiles = load_local_model_profiles()
    ids = {p.profile_id for p in profiles.profiles}
    assert "default_extract" in ids
    assert profiles.fallbacks["quality_reasoning"] == "default_extract"

    jobs = load_ai_job_policy()
    assert jobs.defaults.dry_run_default is True
    assert jobs.guardrails["no_external_writeback"] is True

    vault = load_obsidian_vault_policy()
    assert vault.target_daily_brief_folder in vault.allowlisted_folders

    mcp = load_mcp_packet_policy()
    assert mcp.guardrails["read_only"] is True
    assert "arbitrary_sql" in mcp.forbidden


# ---------------------------------------------------------------------------
# Seeds (invalid / missing — fail-closed)
# ---------------------------------------------------------------------------
def _write_seed(monkeypatch: pytest.MonkeyPatch, tmp_path, env_var: str, data: dict) -> None:
    path = tmp_path / "seed.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setenv(env_var, str(path))


def test_invalid_seed_extra_key_rejected(monkeypatch, tmp_path) -> None:
    base = load_mcp_packet_policy().model_dump()
    base["unexpected_field"] = True
    _write_seed(monkeypatch, tmp_path, "HB_PHASE_10_MCP_PACKET_POLICY", base)
    with pytest.raises(ValidationError):
        load_mcp_packet_policy()


def test_invalid_seed_bad_enum_rejected(monkeypatch, tmp_path) -> None:
    base = load_local_model_profiles().model_dump()
    base["profiles"][1]["provider"] = "openai"  # not in the closed provider enum
    _write_seed(monkeypatch, tmp_path, "HB_PHASE_10_LOCAL_MODEL_PROFILES", base)
    with pytest.raises(ValidationError):
        load_local_model_profiles()


def test_seed_guardrail_invariant_rejected(monkeypatch, tmp_path) -> None:
    base = load_ai_job_policy().model_dump()
    base["defaults"]["dry_run_default"] = False  # violates safe-by-default
    _write_seed(monkeypatch, tmp_path, "HB_PHASE_10_AI_JOB_POLICY", base)
    with pytest.raises(ValidationError):
        load_ai_job_policy()


def test_missing_seed_fail_closed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HB_PHASE_10_OBSIDIAN_VAULT_POLICY", str(tmp_path / "nope.yaml"))
    with pytest.raises(Phase10ContractError):
        load_obsidian_vault_policy()


# ---------------------------------------------------------------------------
# ActionCandidate enforcement model
# ---------------------------------------------------------------------------
def _valid_candidate(**overrides) -> dict:
    base = {
        "candidate_type": "task",
        "title": "Confirm revised sketch issuance",
        "source_refs": ["email_thread_summary:test:001"],
        "confidence": 0.82,
        "reason": "Sender asks for confirmation before tomorrow's meeting.",
        "recommended_next_action": "review",
        "external_action_requires_approval": True,
        "safety_category": "normal",
    }
    base.update(overrides)
    return base


def test_action_candidate_valid() -> None:
    cand = ActionCandidate.model_validate(_valid_candidate())
    assert cand.review_status == "pending"
    assert cand.assignee == "unknown"


def test_action_candidate_requires_source_refs() -> None:
    with pytest.raises(ValidationError):
        ActionCandidate.model_validate(_valid_candidate(source_refs=[]))


def test_action_candidate_rejects_blank_source_ref() -> None:
    with pytest.raises(ValidationError):
        ActionCandidate.model_validate(_valid_candidate(source_refs=["  "]))


def test_action_candidate_rejects_forbidden_raw_field() -> None:
    with pytest.raises(ValidationError):
        ActionCandidate.model_validate(_valid_candidate(raw_email_body="secret body"))


def test_action_candidate_external_approval_must_be_true() -> None:
    with pytest.raises(ValidationError):
        ActionCandidate.model_validate(
            _valid_candidate(external_action_requires_approval=False)
        )


def test_high_stakes_must_route_to_review() -> None:
    with pytest.raises(ValidationError):
        ActionCandidate.model_validate(
            _valid_candidate(safety_category="financial", recommended_next_action="accept")
        )


def test_high_stakes_cannot_be_model_accepted() -> None:
    with pytest.raises(ValidationError):
        ActionCandidate.model_validate(
            _valid_candidate(
                safety_category="contract",
                recommended_next_action="review",
                review_status="accepted",
            )
        )


def test_high_stakes_review_signal_ok() -> None:
    cand = ActionCandidate.model_validate(
        _valid_candidate(safety_category="legal", recommended_next_action="review")
    )
    assert cand.safety_category == "legal"


# ---------------------------------------------------------------------------
# Proof builder + CLI
# ---------------------------------------------------------------------------
def test_proof_passes_clean() -> None:
    result = build_phase_10_contracts_proof()
    assert result["proof_passed"] is True
    assert result["overall_status"] == "clean"
    assert result["contract_count"] == 11  # + raw_content_policy_contract
    assert result["seed_count"] == 5  # + raw_content_policy
    assert len(result["fixtures_validated"]) == 5
    assert result["forbidden_findings"] == []
    assert result["guard_attestation"]["no_external_writeback"] is True
    # Prompt 01 addendum attestation
    assert "raw_content_policy" in result
    assert result["raw_content_policy"]["mode"] == "email_calendar"
    assert result["raw_content_policy"]["writeback_prohibited"] is True


def test_proof_writes_evidence(tmp_path) -> None:
    result = build_phase_10_contracts_proof(evidence_dir=str(tmp_path), write_evidence=True)
    assert result["proof_passed"] is True
    written = result["evidence_written"]
    assert (tmp_path / "01-contracts-seeds-proof.json").exists()
    assert (tmp_path / "01-contracts-seeds-proof.md").exists()
    reloaded = json.loads((tmp_path / "01-contracts-seeds-proof.json").read_text())
    assert reloaded["proof_passed"] is True
    assert "json" in written and "markdown" in written


def test_cli_contracts_proof_exit_zero() -> None:
    result = runner.invoke(app, ["phase-10", "contracts-proof", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["proof_passed"] is True
    assert payload["phase"] == "10"
