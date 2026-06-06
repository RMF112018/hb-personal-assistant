"""Phase 09 Addendum V2 — daily-brief handoff packet (DailyBriefHandoffPacketV2) tests.

Proves the render_payload / governance_metadata split: render payload exists, governance metadata is
separated (and never leaks into the render body), required sections exist, source refs are preserved,
raw-shaped values are rejected, review/stale/confidence flags are preserved, and final-determination
language is rejected.
"""

from __future__ import annotations

import json
import re
import tempfile

import pytest

from hb_assistant.construction.second_brain.daily_brief import packet as pkt
from hb_assistant.construction.second_brain.daily_brief.packet import (
    FORBIDDEN_IN_RENDER_PAYLOAD,
    RENDER_ITEM_FIELDS,
    RENDER_PAYLOAD_SECTIONS,
    build_daily_brief_packet_v2,
    build_daily_brief_packet_v2_proof,
    load_daily_brief_packet_v2_contract,
)

_SECRET_OR_URL = re.compile(
    r"Bearer\s+[A-Za-z0-9]|-----BEGIN|eyJ[A-Za-z0-9_-]{5,}|https?://|access_token|refresh_token|client_secret"
)


def _seeded_v2_packet():
    tmp = tempfile.mkdtemp()
    db = f"{tmp}/seeded.sqlite3"
    pkt._seed_proof_db(db)
    return build_daily_brief_packet_v2(brief_date="2026-06-02", project_key="P1", db_path=db), db


def test_render_payload_exists() -> None:
    packet, _db = _seeded_v2_packet()
    assert "render_payload" in packet
    render = packet["render_payload"]
    assert isinstance(render, dict) and render
    for section in RENDER_PAYLOAD_SECTIONS:
        assert section in render, f"render_payload missing section {section}"


def test_governance_metadata_is_separated() -> None:
    packet, _db = _seeded_v2_packet()
    assert "governance_metadata" in packet
    governance = packet["governance_metadata"]
    render = packet["render_payload"]
    # Governance fields live in governance_metadata...
    contract = load_daily_brief_packet_v2_contract()
    for field in contract["governance_metadata_fields"]:
        assert field in governance, f"governance_metadata missing field {field}"
    # ...and no governance key leaks into the render body.
    for forbidden in FORBIDDEN_IN_RENDER_PAYLOAD:
        assert forbidden not in render, f"governance key {forbidden} leaked into render_payload"


def test_required_sections_exist() -> None:
    packet, _db = _seeded_v2_packet()
    contract = load_daily_brief_packet_v2_contract()
    render = packet["render_payload"]
    for section in contract["render_payload_sections"]:
        assert section in render, f"missing required render section {section}"
    # Renderable items carry the full required item field set.
    for item in render["needs_attention"]:
        for field in RENDER_ITEM_FIELDS:
            assert field in item, f"needs_attention item missing field {field}"


def test_source_refs_are_preserved() -> None:
    packet, _db = _seeded_v2_packet()
    governance = packet["governance_metadata"]
    render = packet["render_payload"]
    # Hashed top-level refs in governance.
    assert governance["source_refs"], "expected preserved source refs"
    for ref in governance["source_refs"]:
        assert "source_ref_hash" in ref and "source_ref" not in ref
    assert isinstance(governance["source_coverage_summary"], dict)
    # Each renderable item carries its hashed source ref + family.
    assert render["needs_attention"]
    for item in render["needs_attention"]:
        assert item["source_family"] and item["source_ref_hash"]


def test_raw_shaped_values_are_rejected() -> None:
    packet, _db = _seeded_v2_packet()
    from hb_assistant.construction.second_brain.financial_review_routing import _assert_no_raw

    # The real packet passes the no-raw gate.
    _assert_no_raw(json.dumps(packet, default=str), "v2 packet")
    assert not _SECRET_OR_URL.search(json.dumps(packet, default=str))
    # A planted raw-shaped value is rejected.
    tampered = json.loads(json.dumps(packet, default=str))
    tampered["render_payload"]["needs_attention"].append({"title": "see https://example.com/raw"})
    with pytest.raises(ValueError):
        _assert_no_raw(json.dumps(tampered, default=str), "tampered v2 packet")


def test_review_stale_confidence_flags_preserved() -> None:
    packet, _db = _seeded_v2_packet()
    needs_attention = packet["render_payload"]["needs_attention"]
    assert needs_attention
    for item in needs_attention:
        assert "review_tier" in item
        assert "review_required" in item
        assert "confidence_class" in item
        assert "freshness_label" in item
        assert "stale_warning" in item
    assert any(i["review_required"] is True for i in needs_attention)
    assert any(i["stale_warning"] for i in needs_attention)


def test_final_determination_language_is_rejected() -> None:
    from hb_assistant.construction.second_brain.daily_brief.packet import _reject_final_determination

    packet, _db = _seeded_v2_packet()
    render = packet["render_payload"]
    # Planted final-determination language is flagged.
    assert _reject_final_determination("Approve payment of the claim as a final determination")
    # Real render text carries none.
    texts = [str(i.get("title") or "") for i in render["needs_attention"]]
    texts += [
        str(i.get(k) or "")
        for i in render["needs_attention"]
        for k in ("why_it_matters", "recommended_focus")
    ]
    texts += [str(g.get("reason") or "") for g in render["data_gaps"]]
    assert not any(_reject_final_determination(t) for t in texts)


def test_deferred_sections_are_empty_with_data_gaps() -> None:
    packet, _db = _seeded_v2_packet()
    render = packet["render_payload"]
    for section in ("yesterday", "today_agenda", "next_7_days", "calendar_activity", "email_activity"):
        assert render[section] == [], f"{section} should be empty (deferred to Prompt 02)"
    gap_sections = {g["section"] for g in render["data_gaps"]}
    for section in ("yesterday", "today_agenda", "next_7_days", "calendar_activity", "email_activity"):
        assert section in gap_sections, f"missing data_gaps entry for {section}"


def test_proof_passes_and_writes_artifacts(tmp_path) -> None:
    proof = build_daily_brief_packet_v2_proof(evidence_dir=str(tmp_path), write_evidence=True)
    assert proof["proof_passed"] is True
    for key in (
        "render_payload_present",
        "governance_metadata_separated",
        "required_sections_present",
        "item_fields_present",
        "source_refs_preserved",
        "metadata_only",
        "raw_shaped_rejected",
        "review_stale_confidence_preserved",
        "final_determination_rejected",
        "no_external_writeback",
    ):
        assert proof[key] is True, f"{key} not True"
    pj = tmp_path / "daily-brief-packet-v2-proof.json"
    pm = tmp_path / "daily-brief-packet-v2-proof.md"
    assert pj.exists() and pm.exists()
    assert not _SECRET_OR_URL.search(pj.read_text())
