"""Phase 10 — raw follow-up window sanitizer + local-preview tests (synthetic data only).

All fixtures are synthetic. Proves the bounded raw email window: excludes attachments + HTML, strips
quoted replies / signatures / disclaimers, redacts URLs / join links / tokens / secrets / emails,
enforces per-message + per-thread + total caps, returns stable hashes + opaque aliases, never
persists, and gates the local preview behind an explicit opt-in.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.local_ai.raw_followup_window import (
    RawWindowCaps,
    build_raw_followup_window,
    build_raw_local_preview,
    sanitize_followup_message_text,
)
from hb_assistant.construction.store import ConstructionStore

# --- Synthetic raw bodies (NOT real user content) -------------------------------------------------

_QUOTED_REPLY = """Please send the updated RFI response by Friday.

On Mon, Jun 1 2026, Jane Doe <jane@example.com> wrote:
> Here is the original question about the slab.
> Thanks, Jane
"""

_OUTLOOK_QUOTE = """Confirming the submittal schedule is on track.

-----Original Message-----
From: bob@contoso.com
Sent: Tuesday, June 2, 2026
To: team@contoso.com
Subject: Submittal
Old content that must be dropped.
"""

_SIGNATURE = """Approved. Proceed with the change order.

--
Bob Builder
Senior PM | Example Co
bob@example.com
+1 (555) 123-4567
"""

_DISCLAIMER = """The inspection is scheduled for Thursday.

This email and any attachments are confidential and intended solely for the addressee.
If you are not the intended recipient please delete it.
"""

_URLS_TOKENS = (
    "Join the meeting now https://teams.microsoft.com/l/meetup-join/abc123?tid=xyz "
    "Download here https://files.example.com/get?sig=SECRETSIG&download_url=1 "
    "Authorization: Bearer eyJhbGciOiJIUzI1Nitesttoken12345 "
    "api_key=sk-livedeadbeef0123456789 contact me at vendor@subcontractor.com or 555-987-6543"
)


def test_sanitize_strips_quoted_reply() -> None:
    text, meta = sanitize_followup_message_text(_QUOTED_REPLY)
    assert "updated RFI response" in text
    assert "original question about the slab" not in text
    assert meta["quotes_stripped"] is True


def test_sanitize_strips_outlook_quote() -> None:
    text, meta = sanitize_followup_message_text(_OUTLOOK_QUOTE)
    assert "submittal schedule is on track" in text
    assert "Old content that must be dropped" not in text
    assert meta["quotes_stripped"] is True


def test_sanitize_strips_signature() -> None:
    text, meta = sanitize_followup_message_text(_SIGNATURE)
    assert "change order" in text
    assert "Senior PM" not in text
    assert meta["signatures_stripped"] is True


def test_sanitize_strips_disclaimer() -> None:
    text, meta = sanitize_followup_message_text(_DISCLAIMER)
    assert "inspection is scheduled" in text
    assert "confidential" not in text.lower()
    assert meta["disclaimers_stripped"] is True


def test_sanitize_redacts_urls_join_links_tokens_emails_phones() -> None:
    text, meta = sanitize_followup_message_text(_URLS_TOKENS, max_chars=4000)
    low = text.lower()
    assert "http://" not in low and "https://" not in low
    assert "teams.microsoft.com" not in low
    assert "meetup-join" not in low
    assert "bearer" not in low
    assert "eyj" not in low
    assert "sk-livedeadbeef" not in low
    assert "secretsig" not in low
    assert "download_url=1" not in low
    assert "@subcontractor.com" not in low
    assert "555-987-6543" not in text and "555-9876543" not in text
    assert meta["urls_redacted"] is True
    assert meta["tokens_redacted"] is True
    assert meta["emails_redacted"] is True
    assert meta["html_excluded"] is True


def test_sanitize_truncates_to_max_chars() -> None:
    text, meta = sanitize_followup_message_text("word " * 2000, max_chars=200)
    assert len(text) <= 200
    assert meta["truncated"] is True


def _store_with_thread(db: str, *, n_messages: int = 2, with_html_only: bool = False) -> ConstructionStore:
    store = ConstructionStore(db_path=db)
    refs = []
    for i in range(n_messages):
        mid = f"msg-hash-{i}"
        store.upsert_email_message_raw_content(
            raw_email_id=f"raw-{i}",
            message_id_hash=mid,
            conversation_id_hash="conv-1",
            source_ref_hash=f"srh-{i}",
            project_key="P1",
            subject="RFI response needed by Friday",
            body_text=None if with_html_only else f"Message {i}: please confirm the schedule.",
            body_html="<html><body>SECRET HTML BODY should be ignored</body></html>",
            from_address="vendor@subcontractor.com",
            received_at_utc=f"2026-06-0{i + 1}T10:00:00+00:00",
            has_attachments=1,
            attachment_metadata_json='[{"name": "drawing.pdf", "size": 1024}]',
        )
        refs.append(
            {
                "source_family": "email_message",
                "source_table": "email_message_raw_content",
                "source_primary_key_hash": mid,
                "source_ref_hash": f"srh-{i}",
            }
        )
    store._refs = refs  # type: ignore[attr-defined]  # convenience for tests
    return store


def test_no_window_without_source_refs() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = ConstructionStore(db_path=str(Path(td) / "w.db"))
        win = build_raw_followup_window(
            candidate_id="c1", candidate_type="task", source_refs=[], store=store
        )
        assert not win.available
        assert "no_source_refs" in win.blockers
        assert win.window_text == ""


def test_non_email_refs_skipped_safely() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = ConstructionStore(db_path=str(Path(td) / "w.db"))
        win = build_raw_followup_window(
            candidate_id="c1",
            candidate_type="task",
            source_refs=[{"source_family": "procore_rfi", "source_ref_hash": "x"}],
            store=store,
        )
        assert not win.available
        assert any("skipped_non_email_ref" in b for b in win.blockers)


def test_window_excludes_html_and_attachments() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store_with_thread(str(Path(td) / "w.db"))
        win = build_raw_followup_window(
            candidate_id="c1", candidate_type="task",
            source_refs=store._refs, store=store,  # type: ignore[attr-defined]
        )
        assert win.available
        assert "SECRET HTML BODY" not in win.window_text
        assert "drawing.pdf" not in win.window_text
        assert win.meta["html_excluded"] is True
        assert win.meta["attachments_excluded"] is True


def test_html_only_body_yields_no_leaked_html() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store_with_thread(str(Path(td) / "w.db"), with_html_only=True)
        win = build_raw_followup_window(
            candidate_id="c1", candidate_type="task",
            source_refs=store._refs, store=store,  # type: ignore[attr-defined]
        )
        # body_text was None and HTML is never read → no content, no leak.
        assert "SECRET HTML BODY" not in win.window_text
        assert not win.window_text.strip()
        assert "no_raw_content_available" in win.blockers


def test_window_caps_messages_and_total_chars() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store_with_thread(str(Path(td) / "w.db"), n_messages=10)
        caps = RawWindowCaps(max_messages_per_thread=3, max_total_chars=120)
        win = build_raw_followup_window(
            candidate_id="c1", candidate_type="task",
            source_refs=store._refs, store=store, caps=caps,  # type: ignore[attr-defined]
        )
        assert win.message_count <= 3
        # The full assembled window_text (headers included) is bounded by max_total_chars.
        assert len(win.window_text) <= 120
        assert "messages_capped" in win.blockers


def test_hashes_are_stable() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "w.db")
        store = _store_with_thread(db)
        w1 = build_raw_followup_window(
            candidate_id="c1", candidate_type="task",
            source_refs=store._refs, store=store,  # type: ignore[attr-defined]
        )
        w2 = build_raw_followup_window(
            candidate_id="c1", candidate_type="task",
            source_refs=store._refs, store=store,  # type: ignore[attr-defined]
        )
        assert w1.raw_excerpt_hash == w2.raw_excerpt_hash
        assert w1.raw_excerpt_hash.startswith("sha256:")
        assert all(a.startswith("email_msg:") for a in w1.source_aliases)


def test_preview_requires_explicit_opt_in() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store_with_thread(str(Path(td) / "w.db"))
        win = build_raw_followup_window(
            candidate_id="c1", candidate_type="task",
            source_refs=store._refs, store=store,  # type: ignore[attr-defined]
        )
        with pytest.raises(ValueError):
            build_raw_local_preview(win, opt_in=False)
        preview = build_raw_local_preview(win, opt_in=True)
        assert preview.is_persistable is False
        assert "RAW-LOCAL PREVIEW" in preview.banner
        assert "NEVER copy into evidence" in preview.banner


def test_window_and_preview_are_marked_non_persistable() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store_with_thread(str(Path(td) / "w.db"))
        win = build_raw_followup_window(
            candidate_id="c1", candidate_type="task",
            source_refs=store._refs, store=store,  # type: ignore[attr-defined]
        )
        assert win.is_persistable is False
        assert build_raw_local_preview(win, opt_in=True).is_persistable is False
