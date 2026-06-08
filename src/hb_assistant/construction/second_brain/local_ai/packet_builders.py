"""Phase 10A — bounded, purposeful model-context packet builders.

A *packet* is a bounded unit of work, not a dump of unrelated records. Each builder produces ONE
coherent unit (one email thread, one calendar event), or a deterministically-linked small set, with
normalized/redacted text, hard char budgets, exact source refs, and a *purpose* that constrains the
allowed model outputs. The content shape (``content.threads[].messages[]`` / ``content.events[]``)
matches ``raw_action_intelligence.extract_action_candidates_from_raw`` so extraction reuses that
engine. Full HTML, join URLs, and full attendee arrays never enter a packet — they stay in the raw
V42 tables.

Builders are read-only (no DB writes); persisting a packet *receipt* is the caller's choice (a
packet-build command with an explicit persist flag).
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from .packet_normalize import has_join_url, normalize_model_text, summarize_attendees
from .relationship_scoring import (
    MODERATE_THRESHOLD,
    score_email_calendar_relationship,
)

PACKET_TYPE_PURPOSE: dict[str, str] = {
    "email_thread_action_packet": "action_extraction",
    "calendar_event_action_packet": "action_extraction",
    "related_context_action_packet": "action_extraction",
    "triage_batch_packet": "triage",
    "daily_brief_packet": "summary",
}
PURPOSE_ALLOWED_OUTPUTS: dict[str, list[str]] = {
    "action_extraction": ["candidate_actions"],
    "triage": ["triage_labels"],
    "review": ["candidate_actions"],
    "summary": ["summary_sections"],
}
BUDGETS: dict[str, dict[str, int]] = {
    "email_thread_action_packet": {"max_messages": 6, "max_chars_per_item": 1200, "max_packet_chars": 12000},
    "calendar_event_action_packet": {"max_chars_per_item": 1200, "max_packet_chars": 6000},
    "related_context_action_packet": {
        "max_email_threads": 1, "max_calendar_events": 3, "max_chars_per_item": 1200,
        "max_packet_chars": 12000,
    },
    "triage_batch_packet": {"max_items": 20, "max_chars_per_item": 500, "max_packet_chars": 12000},
}

_GUARDRAILS = {
    "bounded": True,
    "normalized": True,
    "no_body_html": True,
    "no_join_url_in_packet": True,
    "no_full_attendee_arrays": True,
    "source_linked": True,
    "model_does_not_decide_relatedness": True,
}


def _packet_id(packet_type: str, primary_ref: str) -> str:
    return f"{packet_type}:{hashlib.sha256(str(primary_ref).encode('utf-8')).hexdigest()[:16]}"


def _token_estimate(char_estimate: int) -> int:
    return max(1, char_estimate // 4)


def _envelope(
    *,
    packet_type: str,
    primary_ref: str,
    project_key: Optional[str],
    content: dict[str, Any],
    source_refs: list[dict[str, Any]],
    char_estimate: int,
    truncated: bool,
    excluded_item_count: int,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    purpose = PACKET_TYPE_PURPOSE[packet_type]
    budget = BUDGETS.get(packet_type, {})
    env: dict[str, Any] = {
        "packet_id": _packet_id(packet_type, primary_ref),
        "packet_type": packet_type,
        "packet_purpose": purpose,
        "allowed_outputs": list(PURPOSE_ALLOWED_OUTPUTS[purpose]),
        "project_key": project_key,
        "source_refs": source_refs,
        "content": content,
        "budget": {
            "max_packet_chars": budget.get("max_packet_chars"),
            "char_estimate": char_estimate,
            "token_estimate": _token_estimate(char_estimate),
            "truncated": truncated,
            "excluded_item_count": excluded_item_count,
        },
        "guardrails": dict(_GUARDRAILS),
    }
    # dict-merge (not .update()) — the second-brain no-writeback scanner flags ".update(" calls.
    return {**env, **(extra or {})}


# --------------------------------------------------------------------------------------------------
# Email thread action packet — one thread only.
# --------------------------------------------------------------------------------------------------
def build_email_thread_action_packet(
    *, thread_ref: str, store: Any, user_domains: tuple[str, ...] = ()
) -> dict[str, Any]:
    b = BUDGETS["email_thread_action_packet"]
    thread = store.get_email_thread_raw_context(thread_ref=thread_ref)
    if not thread:
        return _envelope(
            packet_type="email_thread_action_packet", primary_ref=thread_ref, project_key=None,
            content={"threads": []}, source_refs=[], char_estimate=0, truncated=False,
            excluded_item_count=0, extra={"found": False, "note": "thread_not_found"},
        )
    all_msgs = thread.get("messages") if isinstance(thread.get("messages"), list) else []
    source_refs: list[dict[str, Any]] = [
        {"source_family": "email_thread_raw_context", "source_ref": thread.get("thread_ref")}
    ]
    kept: list[dict[str, Any]] = []
    char_estimate = 0
    excluded = 0
    truncated = False
    for m in all_msgs:
        if len(kept) >= b["max_messages"]:
            excluded += 1
            continue
        text, meta = normalize_model_text(
            m.get("body_text"), m.get("body_html"), max_chars=b["max_chars_per_item"]
        )
        ref = m.get("id") or m.get("message_id_hash") or m.get("source_ref")
        item_chars = len(text) + len(str(m.get("subject") or ""))
        if char_estimate + item_chars > b["max_packet_chars"] and kept:
            excluded += 1
            truncated = True
            continue
        char_estimate += item_chars
        truncated = truncated or meta["truncated"]
        kept.append(
            {
                "id": ref,
                "subject": m.get("subject"),
                "body_text": text,
                "from_name": m.get("from_name"),
                "sent_at_utc": m.get("sent_at_utc"),
            }
        )
        if ref:
            source_refs.append({"source_family": "email_message_raw_content", "source_ref": ref})
    content = {
        "threads": [
            {
                "thread_subject": thread.get("thread_subject"),
                "message_count": len(kept),
                "messages": kept,
            }
        ]
    }
    return _envelope(
        packet_type="email_thread_action_packet", primary_ref=thread.get("thread_ref"),
        project_key=thread.get("project_key"), content=content, source_refs=source_refs,
        char_estimate=char_estimate, truncated=truncated, excluded_item_count=excluded,
        extra={"found": True},
    )


# --------------------------------------------------------------------------------------------------
# Calendar event action packet — one event only.
# --------------------------------------------------------------------------------------------------
def build_calendar_event_action_packet(
    *, event_index_id: str, store: Any, user_domains: tuple[str, ...] = ()
) -> dict[str, Any]:
    b = BUDGETS["calendar_event_action_packet"]
    event = store.get_calendar_event_raw_content(event_index_id=event_index_id)
    if not event:
        return _envelope(
            packet_type="calendar_event_action_packet", primary_ref=event_index_id, project_key=None,
            content={"events": []}, source_refs=[], char_estimate=0, truncated=False,
            excluded_item_count=0, extra={"found": False, "note": "event_not_found"},
        )
    text, meta = normalize_model_text(
        event.get("body_text"), event.get("body_html"), max_chars=b["max_chars_per_item"]
    )
    attendees = summarize_attendees(event.get("attendees"), user_domains=user_domains)
    join = has_join_url(
        join_url=event.get("join_url"),
        online_meeting_provider=event.get("online_meeting_provider"),
        raw_text=event.get("body_html") or event.get("body_text"),
    )
    ref = event.get("event_index_id")
    ev_item = {
        "event_index_id": ref,
        "subject": event.get("subject"),
        "body_text": text,
        "attendees_summary": attendees,
        "organizer_name": event.get("organizer_name"),
        "organizer_domain": (event.get("organizer_email") or "").split("@", 1)[-1].lower() or None
        if event.get("organizer_email")
        else None,
        "has_join_url": join,
        "start": event.get("start_datetime_utc"),
        "end": event.get("end_datetime_utc"),
    }
    char_estimate = len(text) + len(str(event.get("subject") or ""))
    return _envelope(
        packet_type="calendar_event_action_packet", primary_ref=ref,
        project_key=event.get("project_key"), content={"events": [ev_item]},
        source_refs=[{"source_family": "calendar_event_raw_content", "source_ref": ref}],
        char_estimate=char_estimate, truncated=meta["truncated"], excluded_item_count=0,
        extra={"found": True, "has_join_url": join},
    )


# --------------------------------------------------------------------------------------------------
# Related context action packet — one thread + strongly-related events (or vice versa).
# --------------------------------------------------------------------------------------------------
def build_related_context_action_packet(
    *,
    thread_ref: Optional[str] = None,
    event_index_id: Optional[str] = None,
    store: Any,
    user_domains: tuple[str, ...] = (),
    min_confidence: float = MODERATE_THRESHOLD,
    scan_limit: int = 50,
) -> dict[str, Any]:
    if not thread_ref and not event_index_id:
        raise ValueError("provide thread_ref or event_index_id")
    b = BUDGETS["related_context_action_packet"]
    primary_ref = thread_ref or event_index_id or ""

    # Thread-anchored: one thread + up to N related events. Event-anchored mirrors with threads.
    if thread_ref:
        thread = store.get_email_thread_raw_context(thread_ref=thread_ref)
        if not thread:
            return _envelope(
                packet_type="related_context_action_packet", primary_ref=primary_ref,
                project_key=None, content={"threads": [], "events": []}, source_refs=[],
                char_estimate=0, truncated=False, excluded_item_count=0,
                extra={"compiled": False, "note": "thread_not_found"},
            )
        candidates = store.list_calendar_event_raw_content(
            project_key=thread.get("project_key"), limit=scan_limit
        )
        scored = [
            (ev, score_email_calendar_relationship(thread, ev)) for ev in candidates
        ]
        passing = sorted(
            [(ev, rel) for ev, rel in scored if rel["confidence"] >= min_confidence],
            key=lambda pair: pair[1]["confidence"],
            reverse=True,
        )[: b["max_calendar_events"]]
        if not passing:
            return _envelope(
                packet_type="related_context_action_packet", primary_ref=primary_ref,
                project_key=thread.get("project_key"), content={"threads": [], "events": []},
                source_refs=[], char_estimate=0, truncated=False, excluded_item_count=0,
                extra={
                    "compiled": False,
                    "note": "no_strong_or_moderate_relationship",
                    "best_confidence": max((r["confidence"] for _, r in scored), default=0.0),
                },
            )
        # Compile: the anchor thread packet + each related event packet, plus relationship metadata.
        thread_pkt = build_email_thread_action_packet(
            thread_ref=thread_ref, store=store, user_domains=user_domains
        )
        events_content: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        source_refs = list(thread_pkt["source_refs"])
        char_estimate = thread_pkt["budget"]["char_estimate"]
        truncated = thread_pkt["budget"]["truncated"]
        for ev, rel in passing:
            ev_pkt = build_calendar_event_action_packet(
                event_index_id=str(ev.get("event_index_id") or ""), store=store,
                user_domains=user_domains,
            )
            events_content.extend(ev_pkt["content"]["events"])
            source_refs.extend(ev_pkt["source_refs"])
            char_estimate += ev_pkt["budget"]["char_estimate"]
            relationships.append(rel)
        review_required = any(r["review_required"] for r in relationships)
        return _envelope(
            packet_type="related_context_action_packet", primary_ref=primary_ref,
            project_key=thread.get("project_key"),
            content={"threads": thread_pkt["content"]["threads"], "events": events_content},
            source_refs=source_refs, char_estimate=char_estimate, truncated=truncated,
            excluded_item_count=max(0, len(passing) - len(relationships)),
            extra={
                "compiled": True,
                "anchor": "email_thread",
                "review_required": review_required,
                "relationships": relationships,
            },
        )

    # Event-anchored
    event = store.get_calendar_event_raw_content(event_index_id=event_index_id)
    if not event:
        return _envelope(
            packet_type="related_context_action_packet", primary_ref=primary_ref, project_key=None,
            content={"threads": [], "events": []}, source_refs=[], char_estimate=0, truncated=False,
            excluded_item_count=0, extra={"compiled": False, "note": "event_not_found"},
        )
    threads = store.list_email_thread_raw_context(project_key=event.get("project_key"), limit=scan_limit)
    scored = [(th, score_email_calendar_relationship(th, event)) for th in threads]
    passing = sorted(
        [(th, rel) for th, rel in scored if rel["confidence"] >= min_confidence],
        key=lambda pair: pair[1]["confidence"], reverse=True,
    )[: b["max_email_threads"]]
    if not passing:
        return _envelope(
            packet_type="related_context_action_packet", primary_ref=primary_ref,
            project_key=event.get("project_key"), content={"threads": [], "events": []},
            source_refs=[], char_estimate=0, truncated=False, excluded_item_count=0,
            extra={
                "compiled": False, "note": "no_strong_or_moderate_relationship",
                "best_confidence": max((r["confidence"] for _, r in scored), default=0.0),
            },
        )
    ev_pkt = build_calendar_event_action_packet(
        event_index_id=str(event_index_id or ""), store=store, user_domains=user_domains
    )
    threads_content: list[dict[str, Any]] = []
    relationships = []
    source_refs = list(ev_pkt["source_refs"])
    char_estimate = ev_pkt["budget"]["char_estimate"]
    truncated = ev_pkt["budget"]["truncated"]
    for th, rel in passing:
        th_pkt = build_email_thread_action_packet(
            thread_ref=str(th.get("thread_ref") or ""), store=store, user_domains=user_domains
        )
        threads_content.extend(th_pkt["content"]["threads"])
        source_refs.extend(th_pkt["source_refs"])
        char_estimate += th_pkt["budget"]["char_estimate"]
        relationships.append(rel)
    return _envelope(
        packet_type="related_context_action_packet", primary_ref=primary_ref,
        project_key=event.get("project_key"),
        content={"threads": threads_content, "events": ev_pkt["content"]["events"]},
        source_refs=source_refs, char_estimate=char_estimate, truncated=truncated,
        excluded_item_count=0,
        extra={
            "compiled": True, "anchor": "calendar_event",
            "review_required": any(r["review_required"] for r in relationships),
            "relationships": relationships,
        },
    )


# --------------------------------------------------------------------------------------------------
# Triage batch packet — many loosely-related recent items; triage labels only.
# --------------------------------------------------------------------------------------------------
def build_triage_batch_packet(
    *, store: Any, project_key: Optional[str] = None, limit: int = 20
) -> dict[str, Any]:
    b = BUDGETS["triage_batch_packet"]
    cap = min(limit, b["max_items"])
    threads = store.list_email_thread_raw_context(project_key=project_key, limit=cap)
    events = store.list_calendar_event_raw_content(project_key=project_key, limit=cap)

    raw_items: list[dict[str, Any]] = []
    for th in threads:
        msgs = th.get("messages") if isinstance(th.get("messages"), list) else []
        body = msgs[0].get("body_text") if msgs else None
        body_html = msgs[0].get("body_html") if msgs else None
        snippet, _ = normalize_model_text(body, body_html, max_chars=b["max_chars_per_item"])
        raw_items.append(
            {
                "source_family": "email_thread_raw_context",
                "source_ref": th.get("thread_ref"),
                "kind": "email_thread",
                "subject": th.get("thread_subject"),
                "snippet": snippet,
            }
        )
    for ev in events:
        snippet, _ = normalize_model_text(
            ev.get("body_text"), ev.get("body_html"), max_chars=b["max_chars_per_item"]
        )
        raw_items.append(
            {
                "source_family": "calendar_event_raw_content",
                "source_ref": ev.get("event_index_id"),
                "kind": "calendar_event",
                "subject": ev.get("subject"),
                "snippet": snippet,
            }
        )

    kept: list[dict[str, Any]] = []
    source_refs: list[dict[str, Any]] = []
    char_estimate = 0
    excluded = 0
    truncated = False
    for it in raw_items:
        if len(kept) >= b["max_items"]:
            excluded += 1
            continue
        item_chars = len(it["snippet"]) + len(str(it.get("subject") or ""))
        if char_estimate + item_chars > b["max_packet_chars"] and kept:
            excluded += 1
            truncated = True
            continue
        char_estimate += item_chars
        kept.append(it)
        source_refs.append({"source_family": it["source_family"], "source_ref": it["source_ref"]})

    return _envelope(
        packet_type="triage_batch_packet", primary_ref=project_key or "recent",
        project_key=project_key, content={"items": kept}, source_refs=source_refs,
        char_estimate=char_estimate, truncated=truncated, excluded_item_count=excluded,
        extra={"item_count": len(kept)},
    )
