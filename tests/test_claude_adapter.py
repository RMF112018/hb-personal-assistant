"""Phase 08A Prompt 03 — Claude adapter boundary (deterministic, offline).

Proves the mock-first synthesis path, the pre-synthesis gate (no model call until
research-packet / context / source checks pass; Tier 3 never auto-accepted), the
no-raw-content envelope boundary, and that live mode fails closed without the SDK.
"""

from __future__ import annotations

import importlib.util

import pytest
from pydantic import ValidationError

from hb_assistant.construction.second_brain.config import SecondBrainConfig
from hb_assistant.construction.second_brain.reasoning import (
    AnthropicUnavailable,
    ContextEnvelope,
    LiveClaudeAdapter,
    MockClaudeAdapter,
    build_claude_adapter,
)


def _good_envelope(**overrides: object) -> ContextEnvelope:
    base: dict[str, object] = {
        "question": "What changed on project tropical?",
        "source_references": [{"source_id": "S1"}, {"source_hash": "abc123"}],
        "review_tier": 1,
        "review_reason_code": "T1_DETERMINISTIC_SOURCE_BACKED",
        "confidence_class": "high",
        "research_packet_ok": True,
        "context_quality": "sufficient",
        "coverage_warnings": ["partial coverage on RFIs"],
    }
    base.update(overrides)
    return ContextEnvelope(**base)  # type: ignore[arg-type]


def test_mock_synthesizes_tier1() -> None:
    result = MockClaudeAdapter().synthesize(_good_envelope())
    assert result.synthesized is True
    assert result.mode == "mock"
    assert result.review_status == "auto_advisory"
    assert result.degradation_mode == "none"
    assert result.confidence == "high"
    assert result.review_tier == 1
    assert result.source_references == [{"source_id": "S1"}, {"source_hash": "abc123"}]
    assert result.coverage_warnings == ["partial coverage on RFIs"]


def test_mock_is_deterministic() -> None:
    env = _good_envelope()
    a = MockClaudeAdapter().synthesize(env)
    b = MockClaudeAdapter().synthesize(env)
    assert a.answer == b.answer
    assert a.answer  # non-empty


def test_tier2_degrades_to_review_recommended() -> None:
    result = MockClaudeAdapter().synthesize(
        _good_envelope(review_tier=2, review_reason_code="T2_STRONG_HEURISTIC")
    )
    assert result.synthesized is True
    assert result.review_status == "review_recommended"
    assert result.degradation_mode == "graceful_degraded"


def test_tier3_is_blocked_and_review_required() -> None:
    result = MockClaudeAdapter().synthesize(
        _good_envelope(review_tier=3, review_reason_code="T3_SENSITIVE_HIGH_IMPACT")
    )
    assert result.synthesized is False  # never auto-accepted as fact
    assert result.review_status == "review_required"
    assert result.degradation_mode == "blocked"
    assert result.answer == ""
    assert "tier_3_mandatory_review" in result.coverage_warnings


def test_blocked_when_no_source_references() -> None:
    result = MockClaudeAdapter().synthesize(
        _good_envelope(source_references=[])
    )
    assert result.synthesized is False
    assert result.degradation_mode == "blocked"
    assert "no_source_references" in result.coverage_warnings


def test_blocked_when_research_packet_not_passed() -> None:
    result = MockClaudeAdapter().synthesize(_good_envelope(research_packet_ok=False))
    assert result.synthesized is False
    assert "research_packet_not_passed" in result.coverage_warnings


def test_blocked_when_context_insufficient() -> None:
    result = MockClaudeAdapter().synthesize(_good_envelope(context_quality="insufficient"))
    assert result.synthesized is False
    assert "context_quality_insufficient" in result.coverage_warnings


def test_envelope_rejects_forbidden_raw_fields() -> None:
    for field in ("signed_url", "download_url", "raw_body", "token", "secret"):
        with pytest.raises(ValidationError):
            ContextEnvelope(
                question="q",
                source_references=[{field: "x"}],
                research_packet_ok=True,
            )


def test_envelope_rejects_invalid_tier() -> None:
    with pytest.raises(ValidationError):
        ContextEnvelope(question="q", source_references=[{"source_id": "S1"}], review_tier=4)


def test_result_carries_no_raw_content() -> None:
    result = MockClaudeAdapter().synthesize(_good_envelope())
    blob = result.model_dump_json()
    for forbidden in ("signed_url", "download_url", "raw_body", "raw_document_text"):
        assert forbidden not in blob


def test_factory_maps_modes() -> None:
    assert build_claude_adapter(SecondBrainConfig(mode="disabled")) is None
    assert isinstance(build_claude_adapter(SecondBrainConfig(mode="mock")), MockClaudeAdapter)
    assert isinstance(build_claude_adapter(SecondBrainConfig(mode="live")), LiveClaudeAdapter)


def test_live_adapter_fails_closed_without_sdk() -> None:
    assert importlib.util.find_spec("anthropic") is None
    adapter = LiveClaudeAdapter(SecondBrainConfig(mode="live"))
    with pytest.raises(AnthropicUnavailable):
        adapter.synthesize(_good_envelope())


def test_live_adapter_gate_runs_before_sdk_lookup() -> None:
    # A blocked envelope must NOT attempt the live call (no SDK error raised).
    adapter = LiveClaudeAdapter(SecondBrainConfig(mode="live"))
    result = adapter.synthesize(_good_envelope(review_tier=3))
    assert result.synthesized is False
    assert result.degradation_mode == "blocked"
