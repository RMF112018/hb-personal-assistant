"""Email revision identity divergence tests."""

from __future__ import annotations

from hb_assistant.apple_mcc.identity.email_revision import (
    account_locator_hash,
    canonical_message_key,
    email_payload_hash,
    email_raw_snapshot_id,
    email_revision_key,
)


def test_snapshot_id_from_revision_not_graph_id() -> None:
    rev = email_revision_key("ab" * 32, "cd" * 32)
    snap = email_raw_snapshot_id(rev)
    assert len(snap) == 64
    assert snap != rev


def test_payload_divergence_new_revision() -> None:
    acct = account_locator_hash("BF-Personal")
    csk = canonical_message_key(internet_message_id="<a@b.com>", account_hex=acct, local_id_hex="11" * 32)
    p1 = email_payload_hash(subject="A", body_text="one", body_html=None, body_preview=None, to_recipients_json="[]")
    p2 = email_payload_hash(subject="A", body_text="two", body_html=None, body_preview=None, to_recipients_json="[]")
    assert p1 != p2
    assert email_revision_key(csk, p1) != email_revision_key(csk, p2)


def test_imid_preferred_over_local() -> None:
    acct = account_locator_hash("BF-Personal")
    a = canonical_message_key(internet_message_id="<X@Y.COM>", account_hex=acct, local_id_hex="11" * 32)
    b = canonical_message_key(internet_message_id="<x@y.com>", account_hex=acct, local_id_hex="22" * 32)
    assert a == b
