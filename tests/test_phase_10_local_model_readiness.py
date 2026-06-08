"""Phase 10 — local model readiness (mistral-nemo default; qwen3-safe pull suggestions).

Hermetic (mock provider) tests for `build_local_model_status` + the updated profile seeds:
- ready=true when the required model (mistral-nemo:12b) is installed;
- the new profile set (default_extract→mistral-nemo:12b, high_recall_extract→llama3.1:8b,
  review_filter→qwen2.5:14b) is present and enabled;
- NO qwen3 pull recommendation by default; qwen3:30b (heavy_context) only when heavy is explicitly
  enabled;
- the contract's structured-extraction disabled prefixes are honored by enabled non-heavy profiles.
Fully offline — no Ollama daemon, no network.
"""

from __future__ import annotations

from hb_assistant.construction.second_brain.local_ai.contracts import (
    load_local_model_profiles,
    load_phase_10_contract,
)
from hb_assistant.construction.second_brain.local_ai.provider import (
    build_local_model_status,
    resolve_local_model_client,
)

_INSTALLED = {"mistral-nemo:12b", "llama3.1:8b", "qwen2.5:14b"}


def _by_id(status: dict) -> dict[str, dict]:
    return {p["profile_id"]: p for p in status["profiles"]}


def test_ready_true_with_mistral_nemo_installed() -> None:
    status = build_local_model_status(provider_name="mock", mock_models=_INSTALLED)
    assert status["ready"] is True
    assert status["overall_status"] == "ready"
    assert status["required_models"] == ["mistral-nemo:12b"]
    assert status["missing_required_models"] == []
    assert "mistral-nemo:12b" in status["present_models"]


def test_profile_set_uses_expected_models() -> None:
    profiles = {p.profile_id: p for p in load_local_model_profiles().profiles}
    assert profiles["default_extract"].model_name == "mistral-nemo:12b"
    assert profiles["default_extract"].enabled is True
    assert profiles["high_recall_extract"].model_name == "llama3.1:8b"
    assert profiles["review_filter"].model_name == "qwen2.5:14b"
    # fast_extract (qwen3:8b) has been removed.
    assert "fast_extract" not in profiles


def test_no_qwen3_pull_suggestion_by_default() -> None:
    # Nothing installed, heavy not enabled → suggestions must not include any qwen3 model.
    status = build_local_model_status(provider_name="mock", mock_models=set())
    pulls = status["suggested_pull_commands"]
    assert not any("qwen3" in c for c in pulls), pulls
    # The active, enabled extraction models are suggested instead.
    assert "ollama pull mistral-nemo:12b" in pulls
    assert "ollama pull llama3.1:8b" in pulls


def test_qwen3_only_suggested_when_heavy_explicitly_enabled() -> None:
    status = build_local_model_status(
        provider_name="mock", mock_models=set(), heavy_enabled=True
    )
    assert "ollama pull qwen3:30b" in status["suggested_pull_commands"]
    # heavy_context becomes a considered profile only under explicit enable.
    assert _by_id(status)["heavy_context"]["blocked_reason"] != "heavy_profile_requires_explicit_enable"


def test_disabled_profiles_are_not_pull_suggested() -> None:
    # quality_reasoning (gpt-oss, disabled, non-heavy) must not generate a pull recommendation.
    status = build_local_model_status(provider_name="mock", mock_models=set())
    assert "ollama pull gpt-oss:20b" not in status["suggested_pull_commands"]
    assert _by_id(status)["quality_reasoning"]["blocked_reason"] == "profile_disabled"


def test_resolve_live_client_defaults_to_mistral_nemo() -> None:
    client, model_name, reason = resolve_local_model_client()
    assert client is not None and reason is None
    assert model_name == "mistral-nemo:12b"
    assert client.model == "mistral-nemo:12b"


def test_resolve_live_client_model_override() -> None:
    client, model_name, reason = resolve_local_model_client(model="llama3.1:8b")
    assert client is not None and model_name == "llama3.1:8b" and reason is None


def test_resolve_live_client_unsupported_provider() -> None:
    client, _model, reason = resolve_local_model_client(provider="bogus")
    assert client is None and reason == "unsupported_provider"


def test_contract_disables_qwen3_for_structured_extraction() -> None:
    contract = load_phase_10_contract("local_model_profile_contract")
    disabled = contract.get("structured_extraction_disabled_model_prefixes") or []
    assert "qwen3" in disabled
    # No enabled, non-heavy profile may use a disabled prefix for structured extraction.
    for p in load_local_model_profiles().profiles:
        if p.enabled and not p.heavy_profile:
            assert not any(p.model_name.startswith(pref) for pref in disabled), p.model_name
