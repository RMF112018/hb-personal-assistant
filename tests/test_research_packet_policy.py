"""Phase 08A Prompt 07 — research-packet policy + deterministic context-quality scoring."""

from __future__ import annotations

from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract
from hb_assistant.construction.second_brain.research import (
    ResearchPacket,
    load_research_packet_policy_seed,
    requires_research_packet,
    score_context_quality,
    validate_research_packet_policy,
)


def _score(**overrides: object) -> dict[str, object]:
    base = {
        "total_items": 10,
        "tier3_count": 1,
        "stale_unknown_count": 0,
        "conflict_count": 0,
        "source_ref_completeness": 1.0,
        "source_coverage": 1.0,
    }
    base.update(overrides)
    return score_context_quality(**base)  # type: ignore[arg-type]


def test_requires_research_packet_for_complex_and_brief_paths() -> None:
    assert requires_research_packet("daily_brief") is True
    assert requires_research_packet("interactive_query") is True
    assert requires_research_packet("memory_extraction") is True
    assert requires_research_packet("chat_turn") is False


def test_empty_context_blocks() -> None:
    s = _score(total_items=0)
    assert s["degradation_mode"] == "blocked"
    assert s["context_quality_class"] == "insufficient"
    assert s["confidence_class"] == "low"


def test_missing_source_refs_blocks() -> None:
    s = _score(source_ref_completeness=0.5)
    assert s["degradation_mode"] == "blocked"


def test_conflicts_recommend_targeted_research() -> None:
    s = _score(conflict_count=2)
    assert s["degradation_recommendation"] == "ask_for_targeted_research"
    assert s["degradation_mode"] == "graceful_degraded"
    assert s["context_quality_class"] == "partial"


def test_high_tier3_density_advisory_only() -> None:
    s = _score(total_items=10, tier3_count=6)  # 0.6 > 0.35
    assert s["degradation_recommendation"] == "advisory_only"
    assert s["degradation_mode"] == "graceful_degraded"


def test_low_coverage_narrows_claims() -> None:
    s = _score(source_coverage=0.2)  # < 0.5
    assert s["degradation_recommendation"] == "narrow_claims"
    assert s["degradation_mode"] == "graceful_degraded"


def test_high_stale_density_narrows_claims() -> None:
    s = _score(total_items=10, stale_unknown_count=4)  # 0.4 > 0.30
    assert s["degradation_recommendation"] == "narrow_claims"


def test_strong_context_is_none() -> None:
    s = _score()
    assert s["degradation_mode"] == "none"
    assert s["context_quality_class"] == "sufficient"
    assert s["confidence_class"] == "high"


def test_model_covers_contract_required_fields() -> None:
    contract = load_phase_08a_contract("research_packet_contract")
    model_fields = set(ResearchPacket.model_fields)
    for field in contract["required_fields"]:
        assert field in model_fields, f"ResearchPacket missing contract field {field}"


def test_seed_loads_with_thresholds() -> None:
    seed = load_research_packet_policy_seed()
    thr = seed["quality_thresholds"]
    assert thr["max_tier_3_density_for_standard_synthesis"] == 0.35
    assert thr["min_source_coverage"] == 0.5


def test_validate_research_packet_policy_clean() -> None:
    v = validate_research_packet_policy()
    assert v["valid"] is True, v["violations"]
