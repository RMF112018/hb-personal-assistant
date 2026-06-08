"""Phase 10A — packet budgeting: bounded, deterministic truncation/exclusion with reported counts."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import (
    build_email_thread_action_packet,
    build_related_context_action_packet,
)
from hb_assistant.construction.second_brain.local_ai.packet_builders import BUDGETS
from hb_assistant.construction.store import ConstructionStore


def _seed_big_thread(store: ConstructionStore, *, thread_ref: str, n_messages: int, body_len: int) -> None:
    body = "RFI status update. " * (body_len // 19 + 1)
    msgs = [
        {"id": f"m{i}", "subject": f"msg {i}", "body_text": body, "sent_at_utc": "2026-06-07T12:00:00+00:00"}
        for i in range(n_messages)
    ]
    store.upsert_email_thread_raw_context(
        raw_thread_context_id=f"rtc-{thread_ref}", thread_ref=thread_ref, project_key="P",
        message_count=n_messages, thread_subject="Big thread",
        messages_json=json.dumps(msgs), source_refs_json="[]", model_ready=1,
    )


def test_message_cap_excludes_overflow_messages() -> None:
    b = BUDGETS["email_thread_action_packet"]
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_big_thread(s, thread_ref="t1", n_messages=b["max_messages"] + 4, body_len=50)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        kept = pkt["content"]["threads"][0]["messages"]
        assert len(kept) == b["max_messages"]
        assert pkt["budget"]["excluded_item_count"] == 4


def test_per_message_truncation_marker_and_packet_char_budget() -> None:
    b = BUDGETS["email_thread_action_packet"]
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b2.db"))
        # Each message body far exceeds the per-message char cap.
        _seed_big_thread(s, thread_ref="t1", n_messages=6, body_len=b["max_chars_per_item"] * 3)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        assert pkt["budget"]["truncated"] is True
        # Total packet text stays within the hard packet-char budget.
        assert pkt["budget"]["char_estimate"] <= b["max_packet_chars"]
        assert pkt["budget"]["token_estimate"] >= 1
        # At least one kept message carries the truncation marker.
        bodies = [m["body_text"] for m in pkt["content"]["threads"][0]["messages"]]
        assert any("[truncated]" in body for body in bodies)


def test_budget_reports_are_deterministic() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b3.db"))
        _seed_big_thread(s, thread_ref="t1", n_messages=10, body_len=2000)
        a = build_email_thread_action_packet(thread_ref="t1", store=s)
        bpkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        assert a["budget"] == bpkt["budget"]
        assert a["packet_id"] == bpkt["packet_id"]  # deterministic packet id


def test_related_packet_budget_excludes_low_confidence(monkeypatch) -> None:
    # Force a tiny combined budget so the lowest-confidence related events are excluded.
    monkeypatch.setitem(BUDGETS["related_context_action_packet"], "max_packet_chars", 1500)
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "rb.db"))
        s.upsert_email_thread_raw_context(
            raw_thread_context_id="rtc-t1", thread_ref="t1", project_key="HILL", message_count=1,
            thread_subject="Hilltop RFI 42 coordination",
            messages_json=json.dumps([{"id": "m1", "subject": "Hilltop RFI 42 coordination",
                                       "from_address": "pm@sub.com", "to_recipients": ["bob@hbcd.com"],
                                       "body_text": "Confirm RFI 42 " * 80,
                                       "sent_at_utc": "2026-06-07T12:00:00+00:00"}]),
            source_refs_json="[]", model_ready=1,
        )
        # Three strongly-related events with large bodies (each capped to 1200 chars).
        for i in range(3):
            s.upsert_calendar_event_raw_content(
                raw_calendar_event_id=f"raw:e{i}", event_index_id=f"e{i}", graph_event_id_hash=f"gh{i}",
                project_key="HILL", subject="Hilltop RFI 42 coordination",
                body_text="Discuss RFI 42 " * 200, organizer_email="pm@sub.com",
                attendees_json=json.dumps([{"email": "bob@hbcd.com"}]),
                start_datetime_utc="2026-06-08T09:00:00+00:00",
                end_datetime_utc="2026-06-08T09:30:00+00:00",
            )
        pkt = build_related_context_action_packet(thread_ref="t1", store=s)
        assert pkt["compiled"] is True
        assert pkt["budget"]["truncated"] is True
        # Lower-confidence related events are excluded when the combined budget would overflow; the
        # anchor + highest-confidence counterpart are always kept (may individually exceed the cap).
        kept = len(pkt["content"]["events"])
        assert 1 <= kept < 3
        assert pkt["budget"]["excluded_item_count"] == 3 - kept
