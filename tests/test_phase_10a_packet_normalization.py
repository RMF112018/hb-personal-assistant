"""Phase 10A — packet normalization: HTML fallback, Teams/redaction, attendee summary."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import (
    build_calendar_event_action_packet,
    build_email_thread_action_packet,
)
from hb_assistant.construction.second_brain.local_ai.packet_normalize import (
    has_join_url,
    normalize_model_text,
    summarize_attendees,
)
from hb_assistant.construction.store import ConstructionStore

_TEAMS_HTML = (
    "<p>Please confirm the submittal by Friday.</p>"
    "<div>________________________________</div>"
    "<p>Microsoft Teams meeting</p>"
    "<p>Join the meeting now https://teams.microsoft.com/l/meetup-join/abc</p>"
    "<p>Meeting ID: 123 456 789</p><p>Passcode: aB3xZ9</p>"
    "<p>Dial-in: +1 555-867-5309</p><p>Meeting options</p>"
)


def test_normalize_model_text_html_fallback_and_redaction() -> None:
    text, meta = normalize_model_text("", _TEAMS_HTML, max_chars=1200)
    assert "Please confirm the submittal by Friday." in text
    assert meta["derived_from_html"] is True
    assert meta["teams_boilerplate_stripped"] is True
    assert meta["redacted_join_artifacts"] is True
    for forbidden in ("teams.microsoft.com", "meetup-join", "123 456 789", "aB3xZ9",
                      "555", "Meeting ID", "Microsoft Teams", "Meeting options"):
        assert forbidden not in text, forbidden


def test_strong_body_text_is_used_verbatim() -> None:
    text, meta = normalize_model_text("Submit the revised RFI by Friday.", _TEAMS_HTML, max_chars=1200)
    assert text == "Submit the revised RFI by Friday."
    assert meta["derived_from_html"] is False


def test_has_join_url_metadata_only() -> None:
    assert has_join_url(join_url="https://teams.microsoft.com/x") is True
    assert has_join_url(online_meeting_provider="teamsForBusiness") is True
    assert has_join_url(raw_text="Join the meeting now") is True
    assert has_join_url() is False


def test_summarize_attendees_compact() -> None:
    out = summarize_attendees(
        [{"email": "a@hbcd.com"}, {"email": "b@sub.com"}, {"attendee_domain": "sub.com"}],
        user_domains=("hbcd.com",),
    )
    assert out["attendee_count"] == 3
    assert out["user_is_attendee"] is True
    assert set(out["participant_domains"]) == {"hbcd.com", "sub.com"}


def test_calendar_packet_redacts_and_summarizes() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "n.db"))
        s.upsert_calendar_event_raw_content(
            raw_calendar_event_id="raw:e1", event_index_id="e1", graph_event_id_hash="gh1",
            project_key="P", subject="Coordination", body_text="", body_html=_TEAMS_HTML,
            organizer_name="PM", organizer_email="pm@sub.com",
            attendees_json=json.dumps([{"email": "bob@hbcd.com"}, {"email": "x@sub.com"}]),
            join_url="https://teams.microsoft.com/l/meetup-join/abc",
            start_datetime_utc="2026-06-08T09:00:00+00:00", end_datetime_utc="2026-06-08T09:30:00+00:00",
        )
        pkt = build_calendar_event_action_packet(event_index_id="e1", store=s, user_domains=("hbcd.com",))
        ev = pkt["content"]["events"][0]
        assert ev["has_join_url"] is True
        assert ev["attendees_summary"]["attendee_count"] == 2
        blob = json.dumps(pkt["content"])
        assert "teams.microsoft.com" not in blob and "meetup-join" not in blob
        assert "Meeting ID" not in blob and "Passcode" not in blob
        assert "body_html" not in ev  # full HTML never enters the packet


def test_email_packet_normalizes_html_messages() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "n2.db"))
        s.upsert_email_thread_raw_context(
            raw_thread_context_id="rtc1", thread_ref="t1", project_key="P", message_count=1,
            thread_subject="Submittal",
            messages_json=json.dumps([{"id": "m1", "subject": "Submittal", "body_text": "",
                                       "body_html": _TEAMS_HTML, "sent_at_utc": "2026-06-07T12:00:00+00:00"}]),
            source_refs_json="[]", model_ready=1,
        )
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        body = pkt["content"]["threads"][0]["messages"][0]["body_text"]
        assert "Please confirm the submittal by Friday." in body
        assert "teams.microsoft.com" not in body and "Passcode" not in body
