"""Phase 08A Synthesized Prompt 03 — model-profile enforcement (offline).

Proves the model-profiles seed validates against the model-profile contract: the
five profiles exist, the router/Haiku/Sonnet/Opus/checklist intent holds, and no
profile permits raw prompt/response persistence.
"""

from __future__ import annotations

import json

from hb_assistant.construction.second_brain.agents import (
    build_agent_model_profile_proof,
    load_model_profiles,
    validate_model_profiles,
)
from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract


def _contract() -> dict:
    return load_phase_08a_contract("model_profile_contract")


def test_seed_validates_against_contract() -> None:
    report = validate_model_profiles(load_model_profiles(), _contract())
    assert report["valid"] is True
    assert report["profile_count"] == 5
    assert report["missing_profiles"] == []
    assert report["violations"] == []


def test_intent_mapping_holds() -> None:
    profiles = {p["profile_id"]: p for p in _contract()["profiles"]}
    assert profiles["deterministic_router"]["default_model"] is None
    assert profiles["fast_summary"]["default_model"] == "claude-haiku-4-5"
    assert profiles["default_reasoning"]["default_model"] == "claude-sonnet-4-6"
    assert profiles["deep_reasoning"]["default_model"] == "claude-opus-4-8"
    assert profiles["evaluator"]["output_mode"] == "checklist_json"


def test_no_raw_persistence_in_seed_or_contract() -> None:
    contract = _contract()
    assert contract["persistence_policy"]["persist_raw_prompt"] is False
    assert contract["persistence_policy"]["persist_raw_response"] is False
    for prof in load_model_profiles()["profiles"].values():
        assert prof["raw_prompt_persisted"] is False
        assert prof["raw_response_persisted"] is False


def test_missing_profile_flagged() -> None:
    seed = {
        "version": "x",
        "profiles": {
            "fast_summary": {
                "model": "claude-haiku-4-5",
                "raw_prompt_persisted": False,
                "raw_response_persisted": False,
            }
        },
    }
    report = validate_model_profiles(seed, _contract())
    assert report["valid"] is False
    assert "deterministic_router" in report["missing_profiles"]


def test_seed_model_mismatch_flagged() -> None:
    seed = load_model_profiles()
    seed["profiles"]["deep_reasoning"]["model"] = "claude-haiku-4-5"  # wrong
    report = validate_model_profiles(seed, _contract())
    assert report["valid"] is False
    assert any(v["code"] == "seed_model_mismatch" for v in report["violations"])


def test_raw_persistence_flag_flagged() -> None:
    seed = load_model_profiles()
    seed["profiles"]["fast_summary"]["raw_prompt_persisted"] = True
    report = validate_model_profiles(seed, _contract())
    assert report["valid"] is False
    assert any(v["code"] == "seed_raw_prompt_persisted" for v in report["violations"])


def test_model_profile_proof_passes_and_no_raw() -> None:
    proof = build_agent_model_profile_proof()
    assert proof["proof"] == "phase_08a_agent_model_profile"
    assert proof["proof_passed"] is True
    assert proof["profile_count"] == 5
    assert proof["no_raw_persistence"] is True
    assert proof["guardrails"]["mcp_implemented"] is False
    assert set(proof["intent_map"]) == {
        "deterministic_router",
        "fast_summary",
        "default_reasoning",
        "deep_reasoning",
        "evaluator",
    }
    blob = json.dumps(proof)
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "token", "secret"):
        assert forbidden not in blob.replace("raw_prompt_persisted", "").replace(
            "raw_response_persisted", ""
        )
