"""N8C-5 — enrichment result contracts (pure; no DB, no model).

Validators are total: oversized or malformed model output raises rather than being silently
truncated + ingested. compute_job_id is deterministic (idempotent enqueue).
"""

from __future__ import annotations

import json

import pytest

from hb_assistant.obsidian_mcp import enrichment_models as em


def test_compute_job_id_deterministic_and_type_sensitive() -> None:
    a = em.compute_job_id("source_summary", "s1", None)
    b = em.compute_job_id("source_summary", "s1", None)
    c = em.compute_job_id("claim_extraction", "s1", None)
    assert a == b and a != c
    assert len(a) == 24


def test_source_summary_parse_ok_and_bounds() -> None:
    raw = json.dumps({"summary": "x" * (em.SUMMARY_MAX_CHARS + 50),
                      "key_points": [f"p{i}" for i in range(em.KEY_POINTS_MAX + 5)],
                      "confidence": 3.0})
    parsed = em.parse_result("source_summary", raw)
    assert len(parsed.result["summary"]) == em.SUMMARY_MAX_CHARS
    assert len(parsed.result["key_points"]) == em.KEY_POINTS_MAX
    assert parsed.result["confidence"] == 1.0  # clamped
    assert "summary_bounded" in parsed.safety_flags
    assert "key_points_bounded" in parsed.safety_flags


def test_source_summary_missing_summary_rejected() -> None:
    with pytest.raises(em.EnrichmentValidationError):
        em.parse_result("source_summary", json.dumps({"key_points": []}))


def test_claim_extraction_parse_keeps_valid_rejects_unsupported() -> None:
    raw = json.dumps({"claims": [
        {"claim_type": "fact", "claim_text": "A", "evidence_excerpt": "evi A", "confidence": 0.5},
        {"claim_type": "bogus_type", "claim_text": "B", "evidence_excerpt": "evi B"},  # unknown type
        {"claim_type": "risk", "claim_text": "C", "evidence_excerpt": ""},             # no evidence
        {"claim_type": "date", "claim_text": "", "evidence_excerpt": "evi"},           # empty text
    ]})
    parsed = em.parse_result("claim_extraction", raw)
    assert len(parsed.claim_candidates) == 1
    assert parsed.claim_candidates[0].claim_type == "fact"
    assert parsed.result["count"] == 1
    assert any(f.startswith("claims_rejected:3") for f in parsed.safety_flags)


def test_claim_extraction_evidence_bounded() -> None:
    raw = json.dumps({"claims": [
        {"claim_type": "fact", "claim_text": "A", "evidence_excerpt": "z" * 5000, "confidence": 0.5}]})
    parsed = em.parse_result("claim_extraction", raw)
    from hb_assistant.obsidian_mcp.claim_models import EVIDENCE_MAX_CHARS
    assert len(parsed.claim_candidates[0].evidence_excerpt) <= EVIDENCE_MAX_CHARS


def test_backlink_parse_store_only() -> None:
    raw = json.dumps({"suggestions": [{"target": "Note X", "reason": "topic", "confidence": 0.4}]})
    parsed = em.parse_result("backlink_suggestions", raw)
    assert parsed.result["suggestions"][0]["target"] == "Note X"
    assert parsed.claim_candidates == []  # backlinks never produce claims


def test_oversized_output_rejected_not_truncated() -> None:
    raw = '{"summary": "' + "y" * (em.RESULT_MAX_CHARS + 10) + '"}'
    with pytest.raises(em.OversizedModelOutput):
        em.parse_result("source_summary", raw)


def test_invalid_json_rejected() -> None:
    with pytest.raises(em.EnrichmentValidationError):
        em.parse_result("source_summary", "not json {")


def test_unsupported_job_type_rejected() -> None:
    with pytest.raises(em.EnrichmentValidationError):
        em.parse_result("claim_validation", "{}")


def test_dumps_capped_raises_over_cap() -> None:
    with pytest.raises(em.EnrichmentValidationError):
        em.dumps_capped({"k": "z" * 100}, 20)
