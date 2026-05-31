"""Phase 07B Prompt 08 — calendar event → email thread relationship candidates.

Proves: time-window and organizer-domain signals produce strong/moderate/weak candidates;
candidates are persisted with promotion_status='candidate' (no auto-promotion onto the
event/thread rows); moderate/weak route to review while strong does not; dry-run persists
nothing; re-runs are idempotent; and the persisted signal / source_reference JSON carries no
raw subject/address/body values.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.relationships import MeetingEmailCandidateBuilder
from hb_assistant.construction.store import ConstructionStore

_EVENT_START = "2026-05-20T10:00:00Z"
_EVENT_END = "2026-05-20T11:00:00Z"


def _tmp_db() -> str:
    return str(Path(tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False).name))


def _store(db: str) -> ConstructionStore:
    store = ConstructionStore(db)
    store.upsert_calendar_source_location(source_id="primary_calendar", mailbox_owner_hash="owner")
    store.upsert_email_source_location(
        source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
    )
    # One event organized by vendor.com, 10:00-11:00.
    store.upsert_calendar_event_index(
        event_index_id="E1",
        source_id="primary_calendar",
        graph_event_id_hash="g1",
        start_datetime_utc=_EVENT_START,
        end_datetime_utc=_EVENT_END,
        organizer_domain="vendor.com",
    )
    return store


def _thread(
    store: ConstructionStore,
    thread_key: str,
    *,
    first: str,
    last: str,
    sender_domain: str,
) -> None:
    store.upsert_email_thread_summary(
        thread_key=thread_key,
        project_key="tropical",
        message_count=1,
        first_message_datetime=first,
        last_message_datetime=last,
        summary_redacted="thread: 1 message(s)",
        summary_policy="metadata_only",
    )
    store.upsert_email_message(
        message_id="m-" + thread_key,
        thread_key=thread_key,
        source_id="sx",
        sender_domain=sender_domain,
        received_datetime=first,
    )


def _seed_threads(store: ConstructionStore) -> None:
    # T1: vendor.com + overlaps the event → strong.
    _thread(store, "T1", first="2026-05-20T10:30:00Z", last="2026-05-20T10:45:00Z",
            sender_domain="vendor.com")
    # T2: vendor.com, next day (~23h, within 72h window, no overlap) → moderate.
    _thread(store, "T2", first="2026-05-21T10:00:00Z", last="2026-05-21T10:30:00Z",
            sender_domain="vendor.com")
    # T3: other.com but overlaps the event → time only → weak.
    _thread(store, "T3", first="2026-05-20T10:15:00Z", last="2026-05-20T10:50:00Z",
            sender_domain="other.com")
    # T4: vendor.com but far in time (outside window, no overlap) → dropped.
    _thread(store, "T4", first="2026-09-01T09:00:00Z", last="2026-09-01T09:30:00Z",
            sender_domain="vendor.com")
    # T5: other.com and far in time → no signal → dropped.
    _thread(store, "T5", first="2026-09-01T09:00:00Z", last="2026-09-01T09:30:00Z",
            sender_domain="other.com")


def test_signals_produce_strong_moderate_weak_and_route_review() -> None:
    db = _tmp_db()
    store = _store(db)
    _seed_threads(store)

    report = MeetingEmailCandidateBuilder(store).build(
        target_project="tropical", dry_run=False
    )
    s = report.summary
    assert s["candidates_created"] == 3
    assert s["strong"] == 1
    assert s["moderate"] == 1
    assert s["weak"] == 1
    assert s["review_routed"] == 2  # moderate + weak; strong is not review-required

    rows = store.list_meeting_email_relationship_candidates(project_key="tropical")
    by_class = {r["confidence_class"]: r for r in rows}
    assert set(by_class) == {"strong", "moderate", "weak"}
    assert by_class["strong"]["review_required"] is False
    assert by_class["moderate"]["review_required"] is True
    assert by_class["weak"]["review_required"] is True
    # Every row is a candidate — never auto-promoted.
    assert all(r["promotion_status"] == "candidate" for r in rows)
    assert all(r["deterministic"] is False and r["model_proposed"] is False for r in rows)
    assert by_class["strong"]["candidate_type"] == "time_and_domain"
    assert by_class["moderate"]["candidate_type"] == "domain_and_time_window"
    assert by_class["weak"]["candidate_type"] == "time_overlap"


def test_no_auto_promotion_onto_event_or_thread_rows() -> None:
    db = _tmp_db()
    store = _store(db)
    _seed_threads(store)
    MeetingEmailCandidateBuilder(store).build(target_project="tropical", dry_run=False)

    # The calendar event index project_key stays NULL; thread summaries unchanged.
    events = store.list_calendar_event_index()
    assert all(e["project_key"] is None for e in events)
    conn = sqlite3.connect(db)
    try:
        promoted = conn.execute(
            "SELECT COUNT(*) FROM meeting_email_relationship_candidates "
            "WHERE promotion_status != 'candidate'"
        ).fetchone()[0]
        guards = conn.execute(
            "SELECT SUM(raw_body_persisted), SUM(raw_prompt_persisted), "
            "SUM(raw_response_persisted), SUM(external_writeback_performed) "
            "FROM meeting_email_relationship_candidates"
        ).fetchone()
    finally:
        conn.close()
    assert promoted == 0
    assert guards == (0, 0, 0, 0)


def test_dry_run_persists_nothing() -> None:
    db = _tmp_db()
    store = _store(db)
    _seed_threads(store)
    report = MeetingEmailCandidateBuilder(store).build(target_project="tropical", dry_run=True)
    assert report.mode == "dry_run"
    assert report.summary["candidates_created"] == 3  # computed but not persisted
    conn = sqlite3.connect(db)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM meeting_email_relationship_candidates"
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 0


def test_idempotent_and_no_raw_values_in_signals() -> None:
    db = _tmp_db()
    store = _store(db)
    _seed_threads(store)
    builder = MeetingEmailCandidateBuilder(store)
    builder.build(target_project="tropical", dry_run=False)
    builder.build(target_project="tropical", dry_run=False)
    rows = store.list_meeting_email_relationship_candidates(project_key="tropical")
    assert len(rows) == 3  # stable candidate_id → no duplicates

    blob = json.dumps(rows)
    # No raw organizer/sender domain, subject, or address leaks into persisted signals.
    assert "vendor.com" not in blob
    assert "other.com" not in blob
    assert "@" not in blob
    # Source references carry only ids/hashes/datetimes.
    strong = next(r for r in rows if r["confidence_class"] == "strong")
    assert strong["source_reference_json"]["event_index_id"] == "E1"
    assert strong["time_window_signal"]["overlap"] is True
    assert strong["participant_signal"]["organizer_domain_present"] is True
    assert strong["subject_topic_signal"] is None
