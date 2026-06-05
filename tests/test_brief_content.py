from __future__ import annotations

from datetime import date

from hb_assistant.obsidian.brief import DailyBriefGenerator
from hb_assistant.retrieval import WorkstreamContextBuilder
from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.repositories import Store


def test_daily_brief_seeded_db_outputs_real_sections(tmp_path):
    dbp = tmp_path / "brief-seeded.sqlite"
    store = Store(db_path=str(dbp))

    sid_mail = store.upsert_source_record(
        source_type="graph:mail",
        source_key="mail:1",
        source_system="microsoft-graph",
        title_redacted="[redacted:mail-subject]",
    )
    sid_event = store.upsert_source_record(
        source_type="graph:event",
        source_key="event:1",
        source_system="microsoft-graph",
        title_redacted="[redacted:event-subject]",
    )
    sid_file = store.upsert_source_record(
        source_type="graph:drive-item",
        source_key="file:1",
        source_system="microsoft-graph",
        title_redacted="Quarterly Report.pdf",
    )

    c = get_connection(str(dbp))
    with transaction(c):
        c.execute(
            "INSERT INTO action_items (stable_key, action_type, status, title, confidence) VALUES (?,?,?,?,?)",
            ("a1", "task", "open", "Review vendor proposal", 0.9),
        )
        c.execute(
            "INSERT INTO action_items (stable_key, action_type, status, title, confidence) VALUES (?,?,?,?,?)",
            ("a2", "waiting_on", "open", "Waiting on legal review", 0.8),
        )
        c.execute(
            "INSERT INTO emails (source_record_id, folder, conversation_id, internet_message_id, sender_domain, body_checked, body_mention_detected, has_attachments, web_link) VALUES (?,?,?,?,?,?,?,?,?)",
            (sid_mail, "inbox", "c1", "im1", "ex.com", 1, 1, 0, "https://example.test/mail/1"),
        )
        c.execute(
            "INSERT INTO calendar_events (source_record_id, ical_uid, start_datetime, end_datetime, timezone, is_cancelled, is_private, web_link) VALUES (?,?,?,?,?,?,?,?)",
            (
                sid_event,
                "ical1",
                "2026-05-26T09:00:00+00:00",
                "2026-05-26T10:00:00+00:00",
                "UTC",
                0,
                0,
                "https://example.test/event/1",
            ),
        )
        c.execute(
            "INSERT INTO files (source_record_id, drive_item_id, name, size_bytes, web_url, download_status, parse_status) VALUES (?,?,?,?,?,?,?)",
            (
                sid_file,
                "d1",
                "Quarterly Report.pdf",
                12345,
                "https://example.test/file/1",
                "not_downloaded",
                "not_parsed",
            ),
        )
        c.execute(
            "INSERT INTO parser_outputs (file_source_record_id, parser_name, parser_version, content_hash, extraction_status, text_excerpt, char_count) VALUES (?,?,?,?,?,?,?)",
            (
                sid_file,
                "p",
                "1",
                "h",
                "success",
                "Action items and waiting on legal are noted in this quarterly report.",
                88,
            ),
        )
        c.execute(
            "INSERT INTO source_links (from_source_record_id, to_source_record_id, link_type, confidence) VALUES (?,?,?,?)",
            (sid_file, sid_mail, "references", 0.7),
        )

    ctx = WorkstreamContextBuilder(store=store).build_for_today(
        focus_queries=["action", "waiting", "report"], limit_per=3
    )
    inner, fm = DailyBriefGenerator(store=store).generate_for_date(date(2026, 5, 25), context=ctx)

    assert "## Priority Actions" in inner
    assert "Review vendor proposal" in inner
    assert "## Waiting On" in inner
    assert "Waiting on legal review" in inner
    assert "## Meeting Prep & Follow-Ups" in inner
    assert "Meeting source" in inner
    assert "## File Review Queue" in inner
    assert "Quarterly Report.pdf" in inner
    assert "## Project / Workstream Signals" in inner
    assert "retrieval hit" in inner
    assert "## Sources" in inner
    assert "src=" in inner
    assert fm["type"] == "brief"


def test_daily_brief_empty_states_and_no_stale_placeholders(tmp_path):
    dbp = tmp_path / "brief-empty.sqlite"
    store = Store(db_path=str(dbp))

    inner, _ = DailyBriefGenerator(store=store).generate_for_date(date(2026, 5, 25))

    assert "No current file review candidates found." in inner
    assert "No meeting prep items found for the configured window." in inner
    assert "Populated from calendar events + extraction in later runs" not in inner
    assert "after Phase 9" not in inner
    assert "later phase" not in inner
