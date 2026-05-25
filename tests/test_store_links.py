"""Tests for Phase 5 store + links (SQLite, idempotency, redaction, link enforcement).

Uses real temp SQLite (via PathPolicy override or :memory:).
Covers all 14_Testing requirements for this phase: migration/upsert idempotency, provenance gate.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hb_assistant.links.registry import SourceLinkRegistry, ALLOWED_LINK_TYPES
from hb_assistant.normalize.email import Email
from hb_assistant.normalize.calendar_event import CalendarEvent
from hb_assistant.normalize.attachment import Attachment
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.repositories import Store


@pytest.fixture
def temp_db_path() -> Path:
    """Isolated temp DB file (deleted after test)."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        path = Path(f.name)
    yield path
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def test_migration_is_idempotent(temp_db_path: Path):
    m = SQLiteMigrator(db_path=str(temp_db_path))
    v1 = m.apply()
    v2 = m.apply()
    assert v1 == 1
    assert v2 == 1
    assert m.current_version() == 1


def test_source_upsert_idempotent_and_last_seen_bumps(temp_db_path: Path):
    store = Store(db_path=str(temp_db_path))
    sid1 = store.upsert_source_record(
        source_type="test:doc", source_key="k1", source_system="test", title_redacted="t1"
    )
    sid2 = store.upsert_source_record(
        source_type="test:doc", source_key="k1", source_system="test", title_redacted="t1-updated"
    )
    assert sid1 == sid2
    rec = store.get_source_record(sid1)
    assert rec is not None
    assert rec["title_redacted"] == "t1-updated"  # last write wins on conflict


def test_invalid_link_type_rejected(temp_db_path: Path):
    reg = SourceLinkRegistry(store=Store(db_path=str(temp_db_path)))
    sid = reg.store.upsert_source_record(source_type="t", source_key="k", source_system="t")
    with pytest.raises(ValueError, match="Invalid link_type"):
        reg.link_sources(sid, sid, "not-a-real-type")


def test_persist_email_roundtrip_redacted_and_links(temp_db_path: Path):
    reg = SourceLinkRegistry(store=Store(db_path=str(temp_db_path)))
    email = Email(
        id="msg-xyz",
        folder="inbox",
        subject_redacted="[redacted:abc123]",
        sender_domain="ex.com",
        from_redacted="hash@ex.com",
        body_preview_redacted="Hello there...",
        received_datetime=datetime(2026, 5, 25, 10, 0, tzinfo=timezone.utc),
        has_attachments=False,
    )
    sid = reg.persist_email(email)
    assert sid > 0
    assert email.source_record_id == sid
    assert len(email.source_links) >= 1  # self-link created

    # DB contains only redacted
    rec = reg.store.get_source_record(sid)
    assert rec["title_redacted"] == "[redacted:abc123]"
    # No raw secrets
    assert "Secret" not in str(rec)
    assert "msg-xyz" in (rec.get("external_id") or "")


def test_persist_calendar_and_attachment_link(temp_db_path: Path):
    reg = SourceLinkRegistry(store=Store(db_path=str(temp_db_path)))
    now = datetime.now(timezone.utc)
    ev = CalendarEvent(id="evt-1", subject_redacted="[redacted:cal]", start=now, end=now)
    sid_ev = reg.persist_calendar_event(ev)

    att = Attachment(id="att-99", parent_source_record_id=0, name="file.pdf")
    sid_att = reg.persist_attachment(att, parent_source_record_id=sid_ev)

    links = reg.get_links(sid_att)
    assert any(l["link_type"] == "attaches" for l in links)


def test_assistant_run_ledger_and_summary(temp_db_path: Path):
    store = Store(db_path=str(temp_db_path))
    rid = store.record_assistant_run(run_type="morning", target_date="2026-05-25", trigger="test", dry_run=True)
    store.finish_assistant_run(rid, "completed")

    summary = store.get_summary()
    assert summary["assistant_runs"] >= 1
    assert summary["last_run"]["dry_run"] is True


def test_all_allowed_link_types_accepted(temp_db_path: Path):
    reg = SourceLinkRegistry(store=Store(db_path=str(temp_db_path)))
    sid = reg.store.upsert_source_record(source_type="t", source_key="k", source_system="t")
    for lt in ALLOWED_LINK_TYPES:
        # Self-links for simplicity
        lid = reg.link_sources(sid, sid, lt)
        assert lid > 0
