"""Phase 09 Addendum — daily-brief handoff packet (DailyBriefHandoffPacketV1) tests."""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile

import pytest

from hb_assistant.construction.second_brain.daily_brief import packet as pkt
from hb_assistant.construction.second_brain.daily_brief.packet import (
    DailyBriefPacketError,
    build_daily_brief_packet,
    build_daily_brief_packet_proof,
    load_daily_brief_packet_contract,
)

_SECRET_OR_URL = re.compile(
    r"Bearer\s+[A-Za-z0-9]|-----BEGIN|eyJ[A-Za-z0-9_-]{5,}|https?://|access_token|refresh_token|client_secret"
)

_SECTIONS = [
    "recent_changes",
    "review_required_items",
    "aging_watchlist",
    "meeting_prep",
    "risk_watchlist",
    "stale_or_low_confidence_warnings",
    "accepted_memory_context",
]


def _seeded_packet():
    tmp = tempfile.mkdtemp()
    db = f"{tmp}/seeded.sqlite3"
    pkt._seed_proof_db(db)
    return build_daily_brief_packet(brief_date="2026-06-02", project_key="P1", db_path=db), db


def test_packet_validates_against_contract() -> None:
    contract = load_daily_brief_packet_contract()
    packet, _db = _seeded_packet()
    for field in contract["required_packet_fields"]:
        assert field in packet, f"missing packet field {field}"
    item_fields = contract["item_fields"]
    items = [i for s in _SECTIONS for i in packet[s]]
    assert items, "expected at least one source-linked item"
    for item in items:
        for f in item_fields:
            assert f in item, f"item missing field {f}"


def test_packet_is_metadata_only() -> None:
    packet, _db = _seeded_packet()
    blob = json.dumps(packet, default=str)
    assert not _SECRET_OR_URL.search(blob)
    # No raw source_ref leaks: top-level refs are hashed only.
    for ref in packet["source_refs"]:
        assert "source_ref" not in ref
        assert ref["source_ref_hash"] and len(ref["source_ref_hash"]) == 48


def test_packet_preserves_review_flags() -> None:
    packet, _db = _seeded_packet()
    review_items = packet["review_required_items"]
    assert review_items
    assert all(i["review_required"] is True for i in review_items)
    assert any(i["review_tier"] == 3 for i in review_items)


def test_packet_preserves_stale_low_confidence_warnings() -> None:
    packet, _db = _seeded_packet()
    stale = packet["stale_or_low_confidence_warnings"]
    assert stale
    assert any(i["stale_warning"] for i in stale)


def test_packet_includes_source_coverage() -> None:
    packet, _db = _seeded_packet()
    cov = packet["source_coverage_summary"]
    assert isinstance(cov["source_coverage"], float)
    assert cov["source_ref_count"] > 0
    assert cov["families_present"]


def test_packet_accepted_memory_is_advisory_only() -> None:
    packet, _db = _seeded_packet()
    memory = packet["accepted_memory_context"]
    assert memory
    for i in memory:
        assert i["allowed_use"] == "advisory_context_only"
        assert "final_determination" in i["blocked_uses"]


def test_packet_rejects_raw_shaped_values() -> None:
    packet, _db = _seeded_packet()
    from hb_assistant.construction.second_brain.financial_review_routing import _assert_no_raw

    # Real packet passes the no-raw gate.
    _assert_no_raw(json.dumps(packet, default=str), "packet")
    # A planted raw-shaped value is rejected.
    tampered = dict(packet)
    tampered["what_matters_today"] = ["see https://example.com/raw"]
    with pytest.raises(ValueError):
        _assert_no_raw(json.dumps(tampered, default=str), "tampered packet")


def test_final_determination_language_is_flagged() -> None:
    assert pkt._reject_final_determination("Approve payment of the claim as a final determination")
    packet, _db = _seeded_packet()
    items = [i for s in _SECTIONS for i in packet[s]]
    assert not any(pkt._reject_final_determination(i["title_redacted"]) for i in items)
    assert not any(pkt._reject_final_determination(b) for b in packet["what_matters_today"])


def test_packet_generation_does_not_write_to_external_systems() -> None:
    packet, db = _seeded_packet()
    assert packet["read_only"] is True
    assert packet["packet_receipt_emitted"] is False
    assert packet["guardrails"]["no_writeback"] is True
    conn = sqlite3.connect(db)
    try:
        runs = conn.execute("SELECT COUNT(*) FROM daily_brief_runs").fetchone()[0]
    finally:
        conn.close()
    assert runs == 0


def test_packet_guardrails_block_is_exact() -> None:
    packet, _db = _seeded_packet()
    assert packet["guardrails"] == {
        "advisory_only": True,
        "source_linked": True,
        "metadata_only": True,
        "no_raw": True,
        "no_writeback": True,
        "no_final_determinations": True,
        "claude_rendering_only": True,
    }
    instr = packet["rendering_instructions"]["instructions"]
    assert any("executive brief" in s for s in instr)
    assert any("final determinations" in s for s in instr)
    assert any("do not ask for raw records" in s.lower() for s in instr)


def test_proof_passes_and_writes_artifacts(tmp_path) -> None:
    proof = build_daily_brief_packet_proof(evidence_dir=str(tmp_path), write_evidence=True)
    assert proof["proof_passed"] is True
    for key in (
        "required_fields_present",
        "item_fields_present",
        "metadata_only",
        "review_flags_preserved",
        "stale_or_low_confidence_preserved",
        "source_coverage_present",
        "accepted_memory_advisory_only",
        "raw_shaped_rejected",
        "final_determination_flagged",
        "no_external_writeback",
    ):
        assert proof[key] is True, f"{key} not True"
    pj = tmp_path / "daily-brief-packet-proof.json"
    pm = tmp_path / "daily-brief-packet-proof.md"
    assert pj.exists() and pm.exists()
    assert not _SECRET_OR_URL.search(pj.read_text())


def test_missing_contract_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import hb_assistant.construction.second_brain.contracts as contracts

    def _boom(name: str):
        raise KeyError(name)

    monkeypatch.setattr(contracts, "load_phase_09_contract", _boom)
    with pytest.raises((DailyBriefPacketError, KeyError)):
        build_daily_brief_packet(brief_date="2026-06-02", project_key="P1")
