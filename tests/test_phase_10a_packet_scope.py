"""Phase 10A — packet scope: one coherent unit per action packet; combine only on relationship score."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import (
    build_calendar_event_action_packet,
    build_email_thread_action_packet,
    build_related_context_action_packet,
)
from hb_assistant.construction.store import ConstructionStore


def _store(td: str) -> ConstructionStore:
    return ConstructionStore(db_path=str(Path(td) / "scope.db"))


def _seed_thread(store: ConstructionStore, *, thread_ref: str, project: str, subject: str, body: str) -> None:
    store.upsert_email_thread_raw_context(
        raw_thread_context_id=f"rtc-{thread_ref}", thread_ref=thread_ref, project_key=project,
        message_count=1, thread_subject=subject,
        messages_json=json.dumps([{"id": f"m-{thread_ref}", "subject": subject,
                                   "from_address": "pm@sub.com", "to_recipients": ["bob@hbcd.com"],
                                   "body_text": body, "sent_at_utc": "2026-06-07T12:00:00+00:00"}]),
        source_refs_json="[]", model_ready=1,
    )


def _seed_event(store: ConstructionStore, *, eid: str, project: str, subject: str, body: str = "",
                start: str = "2026-06-08T09:00:00+00:00") -> None:
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id=f"raw:{eid}", event_index_id=eid, graph_event_id_hash=f"gh-{eid}",
        project_key=project, subject=subject, body_text=body, organizer_name="PM",
        organizer_email="pm@sub.com", attendees_json=json.dumps([{"email": "bob@hbcd.com"}]),
        start_datetime_utc=start, end_datetime_utc="2026-06-08T09:30:00+00:00",
    )


def test_email_packet_contains_one_thread_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = _store(td)
        _seed_thread(s, thread_ref="t1", project="P", subject="RFI 42", body="Please review RFI 42.")
        _seed_thread(s, thread_ref="t2", project="P", subject="Other", body="Unrelated.")
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        assert pkt["packet_type"] == "email_thread_action_packet"
        assert len(pkt["content"]["threads"]) == 1
        assert pkt["content"]["threads"][0]["thread_subject"] == "RFI 42"
        assert "Other" not in json.dumps(pkt["content"])  # the second thread is never pulled in


def test_calendar_packet_contains_one_event_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = _store(td)
        _seed_event(s, eid="e1", project="P", subject="Coordination meeting")
        _seed_event(s, eid="e2", project="P", subject="Different event")
        pkt = build_calendar_event_action_packet(event_index_id="e1", store=s)
        assert pkt["packet_type"] == "calendar_event_action_packet"
        assert len(pkt["content"]["events"]) == 1
        assert pkt["content"]["events"][0]["event_index_id"] == "e1"
        assert "Different event" not in json.dumps(pkt["content"])


def test_related_packet_only_when_relationship_passes_threshold() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = _store(td)
        # Strongly related: same project, matching subject + RFI ref + participant + time proximity.
        _seed_thread(s, thread_ref="t1", project="HILL", subject="Hilltop RFI 42 coordination meeting",
                     body="Lets meet about RFI 42 at the coordination meeting on site.")
        _seed_event(s, eid="e1", project="HILL", subject="Hilltop RFI 42 coordination meeting",
                    body="Discuss RFI 42")
        related = build_related_context_action_packet(thread_ref="t1", store=s)
        assert related["compiled"] is True
        assert related["content"]["events"]  # combined with the related event
        assert related["relationships"][0]["relationship_class"] in ("strong", "moderate")


def test_unrelated_records_are_not_combined() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = _store(td)
        _seed_thread(s, thread_ref="t1", project="HILL", subject="Lunch order", body="sandwiches please")
        _seed_event(s, eid="e1", project="OTHER", subject="Budget review", body="numbers")
        related = build_related_context_action_packet(thread_ref="t1", store=s)
        assert related["compiled"] is False
        assert related["content"]["events"] == []
        assert related["note"] == "no_strong_or_moderate_relationship"
