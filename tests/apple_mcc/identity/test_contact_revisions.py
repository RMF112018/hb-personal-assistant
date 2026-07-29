"""Contact revision identity tests."""

from __future__ import annotations

from hb_assistant.apple_mcc.identity.contact_revision import (
    contact_entity_id,
    contact_id_hash,
    contact_linkage_id,
    contact_payload_hash,
    contact_raw_snapshot_id,
    contact_revision_key,
    container_locator_hash,
)


def test_entity_and_revision() -> None:
    c = container_locator_hash("iCloud")
    cid = contact_id_hash(c, "CN-1")
    ent = contact_entity_id(c, cid)
    ph = contact_payload_hash('{"n":"Ada"}')
    rev = contact_revision_key(ent, ph)
    snap = contact_raw_snapshot_id(rev)
    assert len(ent) == 64 and len(rev) == 64 and len(snap) == 64


def test_unmatched_linkage_id() -> None:
    left = "ab" * 32
    u = contact_linkage_id(left, None, "unmatched")
    assert len(u) == 64
