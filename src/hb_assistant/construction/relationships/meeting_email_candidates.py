"""Phase 07B Prompt 08 — calendar event → email thread relationship candidates.

Pairs indexed, redacted calendar events with materialized email thread summaries and writes
confidence-labeled **candidate** rows to ``meeting_email_relationship_candidates``. Pure
local SQLite — no Microsoft Graph calls, no token, no writeback to any external system, and
**no auto-promotion**: every row carries ``promotion_status='candidate'`` and the calendar /
thread rows are never written.

Two safe, computable signals score each (event, thread) pair:

- **time_window** — does the event's ``[start, end]`` interval overlap the thread's
  ``[first_message, last_message]`` span? (margin recorded in hours.)
- **organizer domain** — is the event's ``organizer_domain`` among the thread messages'
  ``sender_domain`` values? (domain only — never a raw address.)

A candidate is emitted only for **temporally relevant** pairs — a shared domain alone is not
enough (the GC emails its own domain constantly), so a domain match must also fall within the
time window. Confidence class:

- ``strong`` (0.80): time overlap AND domain match
- ``moderate`` (0.60): domain match AND within the time window (no overlap)
- ``weak`` (0.40): time overlap only (no domain match)

``moderate``/``weak`` route to human review (contract ``review_required_classes``); all
classes are advisory candidates. Subject-topic overlap is not computable (thread summaries
expose no subject word-token hashes), so that signal column is left null.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.calendar.contracts import (
    load_meeting_email_relationship_candidate_contract,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value

# Confidence classes / scores (mirror meeting_email_relationship_candidate_contract.json).
_CONF_STRONG = ("strong", 0.80)
_CONF_MODERATE = ("moderate", 0.60)
_CONF_WEAK = ("weak", 0.40)
_REVIEW_CLASSES = {"moderate", "weak", "model_proposed", "sensitive"}
_MAX_SAMPLES = 10


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    # Normalize to UTC-aware so naive/aware stored timestamps compare safely.
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _intervals_overlap(
    a_start: Optional[datetime],
    a_end: Optional[datetime],
    b_start: Optional[datetime],
    b_end: Optional[datetime],
) -> bool:
    if a_start is None or b_start is None:
        return False
    a_lo, a_hi = a_start, (a_end or a_start)
    b_lo, b_hi = b_start, (b_end or b_start)
    return a_lo <= b_hi and b_lo <= a_hi


def _margin_hours(
    a_start: Optional[datetime],
    a_end: Optional[datetime],
    b_start: Optional[datetime],
    b_end: Optional[datetime],
) -> Optional[int]:
    """Gap in whole hours between the two intervals (0 if they overlap)."""
    if a_start is None or b_start is None:
        return None
    a_lo, a_hi = a_start, (a_end or a_start)
    b_lo, b_hi = b_start, (b_end or b_start)
    if a_lo <= b_hi and b_lo <= a_hi:
        return 0
    gap = (b_lo - a_hi) if b_lo > a_hi else (a_lo - b_hi)
    return int(abs(gap.total_seconds()) // 3600)


class MeetingEmailCandidateSample(BaseModel):
    """Evidence-safe preview of one candidate (redacted; no raw subject/address)."""

    event_ref: str
    thread_key_hash: str
    candidate_type: str
    confidence: float
    confidence_class: str
    review_required: bool

    model_config = {"extra": "forbid"}


class MeetingEmailCandidateReport(BaseModel):
    command: str = "graph calendar meeting-email-candidates"
    mode: str  # dry_run | apply
    target_project: Optional[str] = None
    summary: dict[str, int] = Field(default_factory=dict)
    samples: list[MeetingEmailCandidateSample] = Field(default_factory=list)
    disclaimer: str = (
        "candidates are advisory signals, not determinations; no auto-promotion "
        "(promotion_status='candidate'); moderate/weak route to human review; no raw "
        "subject, address, or body is read or persisted"
    )

    model_config = {"extra": "forbid"}


class _Candidate(BaseModel):
    candidate_id: str
    event_index_id: str
    thread_key: str
    thread_key_hash: str
    project_key: Optional[str]
    candidate_type: str
    confidence: float
    confidence_class: str
    review_required: bool
    time_window_signal: dict[str, Any]
    participant_signal: dict[str, Any]
    source_reference: dict[str, Any]

    model_config = {"extra": "forbid"}


class MeetingEmailCandidateBuilder:
    """Build calendar event → email thread relationship candidates (no Graph, no token)."""

    def __init__(self, store: ConstructionStore) -> None:
        self._store = store
        # Validate the contract (asserts auto_promotion_allowed is false).
        load_meeting_email_relationship_candidate_contract()

    def build(
        self,
        *,
        target_project: Optional[str] = None,
        source_id: Optional[str] = None,
        time_window_hours: int = 72,
        max_candidates: int = 1000,
        dry_run: bool = True,
    ) -> MeetingEmailCandidateReport:
        events = [
            e
            for e in self._store.list_calendar_event_index(source_id=source_id)
            if not e.get("is_private")
        ]
        threads = self._store.list_email_thread_summaries(project_key=target_project)
        thread_domains = self._thread_domain_map(threads)

        candidates: list[_Candidate] = []
        pairs_evaluated = 0
        for event in events:
            ev_start = _parse_dt(event.get("start_datetime_utc"))
            ev_end = _parse_dt(event.get("end_datetime_utc"))
            organizer_domain = (event.get("organizer_domain") or "").lower() or None
            for thread in threads:
                pairs_evaluated += 1
                cand = self._score(
                    event=event,
                    thread=thread,
                    ev_start=ev_start,
                    ev_end=ev_end,
                    organizer_domain=organizer_domain,
                    thread_domains=thread_domains.get(thread["thread_key"], set()),
                    time_window_hours=time_window_hours,
                )
                if cand is not None:
                    candidates.append(cand)
                    if len(candidates) >= max_candidates:
                        break
            if len(candidates) >= max_candidates:
                break

        if not dry_run:
            for cand in candidates:
                self._store.upsert_meeting_email_relationship_candidate(
                    candidate_id=cand.candidate_id,
                    event_index_id=cand.event_index_id,
                    thread_key_hash=cand.thread_key_hash,
                    project_key=cand.project_key,
                    candidate_type=cand.candidate_type,
                    time_window_signal=json.dumps(cand.time_window_signal, sort_keys=True),
                    participant_signal=json.dumps(cand.participant_signal, sort_keys=True),
                    subject_topic_signal=None,
                    source_reference_json=json.dumps(cand.source_reference, sort_keys=True),
                    confidence=cand.confidence,
                    confidence_class=cand.confidence_class,
                    deterministic=False,
                    model_proposed=False,
                    review_required=cand.review_required,
                    promotion_status="candidate",
                )

        summary = {
            "events_evaluated": len(events),
            "threads_evaluated": len(threads),
            "pairs_evaluated": pairs_evaluated,
            "candidates_created": len(candidates),
            "strong": sum(1 for c in candidates if c.confidence_class == "strong"),
            "moderate": sum(1 for c in candidates if c.confidence_class == "moderate"),
            "weak": sum(1 for c in candidates if c.confidence_class == "weak"),
            "review_routed": sum(1 for c in candidates if c.review_required),
        }
        samples = [
            MeetingEmailCandidateSample(
                event_ref=hash_value(c.event_index_id) or c.event_index_id,
                thread_key_hash=c.thread_key_hash,
                candidate_type=c.candidate_type,
                confidence=c.confidence,
                confidence_class=c.confidence_class,
                review_required=c.review_required,
            )
            for c in candidates[:_MAX_SAMPLES]
        ]
        return MeetingEmailCandidateReport(
            mode="dry_run" if dry_run else "apply",
            target_project=target_project,
            summary=summary,
            samples=samples,
        )

    def _thread_domain_map(self, threads: list[dict[str, Any]]) -> dict[str, set[str]]:
        """thread_key -> set of lowercased sender domains (from indexed messages)."""
        mapping: dict[str, set[str]] = {}
        for thread in threads:
            tk = thread["thread_key"]
            domains = {
                d.lower()
                for m in self._store.list_email_messages(thread_key=tk, limit=1000)
                for d in [m.get("sender_domain")]
                if d
            }
            mapping[tk] = domains
        return mapping

    def _score(
        self,
        *,
        event: dict[str, Any],
        thread: dict[str, Any],
        ev_start: Optional[datetime],
        ev_end: Optional[datetime],
        organizer_domain: Optional[str],
        thread_domains: set[str],
        time_window_hours: int,
    ) -> Optional[_Candidate]:
        th_start = _parse_dt(thread.get("first_message_datetime"))
        th_end = _parse_dt(thread.get("last_message_datetime"))
        time_overlap = _intervals_overlap(ev_start, ev_end, th_start, th_end)
        margin = _margin_hours(ev_start, ev_end, th_start, th_end)
        within_window = margin is not None and margin <= time_window_hours
        domain_match = bool(organizer_domain and organizer_domain in thread_domains)

        # A shared domain alone is not enough (the GC emails its own domain constantly):
        # it must also be temporally relevant. Time overlap is always a signal.
        if time_overlap and domain_match:
            ctype, (cclass, conf) = "time_and_domain", _CONF_STRONG
        elif domain_match and within_window:
            ctype, (cclass, conf) = "domain_and_time_window", _CONF_MODERATE
        elif time_overlap:
            ctype, (cclass, conf) = "time_overlap", _CONF_WEAK
        else:
            return None

        thread_key = thread["thread_key"]
        thread_key_hash = hash_value(thread_key) or thread_key
        time_window_signal = {
            "overlap": time_overlap,
            "margin_hours": margin,
            "within_window": bool(margin is not None and margin <= time_window_hours),
        }
        participant_signal = {"organizer_domain_present": domain_match}
        source_reference = {
            "event_index_id": event["event_index_id"],
            "thread_key_hash": thread_key_hash,
            "event_start_utc": event.get("start_datetime_utc"),
            "event_end_utc": event.get("end_datetime_utc"),
            "thread_first_message_datetime": thread.get("first_message_datetime"),
            "thread_last_message_datetime": thread.get("last_message_datetime"),
        }
        return _Candidate(
            candidate_id=hash_value(f"{event['event_index_id']}|{thread_key}|{ctype}")
            or f"{event['event_index_id']}:{thread_key}",
            event_index_id=event["event_index_id"],
            thread_key=thread_key,
            thread_key_hash=thread_key_hash,
            project_key=thread.get("project_key"),
            candidate_type=ctype,
            confidence=conf,
            confidence_class=cclass,
            review_required=cclass in _REVIEW_CLASSES,
            time_window_signal=time_window_signal,
            participant_signal=participant_signal,
            source_reference=source_reference,
        )
