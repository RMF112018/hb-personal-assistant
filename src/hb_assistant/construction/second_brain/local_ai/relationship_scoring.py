"""Phase 10A — deterministic email-thread ↔ calendar-event relationship scoring.

The local model must never decide whether two records are related. This module scores that link
*deterministically* from metadata-safe signals, producing an explainable, source-linked relationship
candidate with reason codes and per-feature score components. Only links that pass threshold may form
a combined ``related_context_action_packet``.

Classification (mirrors ``phase_10_relationship_candidate_contract.json``):
- confidence >= 0.80 → strong (may compile a related packet)
- 0.55 <= confidence < 0.80 → moderate (may compile only with review_required=true)
- confidence < 0.55 → weak (do not combine for extraction)

Pure/deterministic: no clock reads inside the scorer (time proximity compares event vs message
timestamps from the data); ``created_at_utc`` is stamped by the caller.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

STRONG_THRESHOLD = 0.80
MODERATE_THRESHOLD = 0.55

# Per-feature contributions (sum, clamped to [0,1]). Mirror contract score components.
_WEIGHTS = {
    "same_project": 0.25,
    "subject_similarity": 0.20,  # scaled by token Jaccard
    "explicit_meeting_reference": 0.15,
    "participant_overlap": 0.20,
    "time_proximity_24h": 0.15,
    "time_proximity_72h": 0.10,
    "shared_record_reference": 0.20,
    "teams_join_reference_match": 0.10,
    "generic_title_penalty": -0.15,
    "private_sensitive_penalty": -0.10,
}

_GENERIC_TITLES = {
    "meeting", "follow up", "follow-up", "followup", "coordination call", "coordination",
    "check in", "check-in", "sync", "touch base", "weekly", "call", "catch up", "1:1", "standup",
}
_RECORD_TOKENS = (
    "rfi", "submittal", "oac", "agenda", "minutes", "proposal", "bid", "bid review", "change order",
    "co", "pco", "punch", "schedule", "pay app", "pay application", "draw",
)
_MEETING_WORDS = re.compile(
    r"\b(meeting|meet|call|agenda|oac|kickoff|kick-off|walk[- ]?through|coordination|review|huddle)\b",
    re.IGNORECASE,
)
_JOIN_HINT = re.compile(
    r"(teams\.microsoft\.com|meetup-join|join the meeting|join meeting|webex|zoom\.us)", re.IGNORECASE
)
_STOPWORDS = {"the", "a", "an", "of", "to", "for", "re", "fw", "fwd", "and", "on", "in", "with", "-"}


def _domain(addr: Any) -> Optional[str]:
    if isinstance(addr, dict):
        addr = addr.get("address") or addr.get("email") or addr.get("attendee_domain")
    if isinstance(addr, str):
        if addr.startswith("@"):
            return addr[1:].lower()
        if "@" in addr:
            return addr.split("@", 1)[1].lower()
        if "." in addr and " " not in addr:  # already a bare domain
            return addr.lower()
    return None


def _tokens(text: Optional[str]) -> set[str]:
    if not text:
        return set()
    raw = re.split(r"[^a-z0-9]+", str(text).lower())
    return {t for t in raw if t and t not in _STOPWORDS and len(t) > 2}


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _thread_signals(thread: dict[str, Any]) -> dict[str, Any]:
    raw_msgs = thread.get("messages")
    msgs: list[Any] = raw_msgs if isinstance(raw_msgs, list) else []
    domains: set[str] = set()
    text_parts: list[str] = [str(thread.get("thread_subject") or "")]
    times: list[datetime] = []
    for m in msgs:
        for key in ("from_address", "from_name"):
            d = _domain(m.get(key))
            if d:
                domains.add(d)
        for r in m.get("to_recipients") or []:
            d = _domain(r)
            if d:
                domains.add(d)
        text_parts.append(str(m.get("subject") or ""))
        text_parts.append(str(m.get("body_text") or ""))
        dt = _parse_dt(m.get("sent_at_utc")) or _parse_dt(m.get("received_at_utc"))
        if dt:
            times.append(dt)
    for key in ("first_message_datetime", "last_message_datetime"):
        dt = _parse_dt(thread.get(key))
        if dt:
            times.append(dt)
    return {
        "project_key": thread.get("project_key"),
        "subject": str(thread.get("thread_subject") or ""),
        "domains": domains,
        "text": " ".join(text_parts).lower(),
        "times": times,
    }


def _event_signals(event: dict[str, Any]) -> dict[str, Any]:
    domains: set[str] = set()
    d = _domain(event.get("organizer_email")) or _domain(event.get("organizer_domain"))
    if d:
        domains.add(d)
    for a in event.get("attendees") or []:
        ad = _domain(a)
        if ad:
            domains.add(ad)
    subject = str(event.get("subject") or "")
    return {
        "project_key": event.get("project_key"),
        "subject": subject,
        "domains": domains,
        "text": f"{subject} {event.get('body_text') or ''}".lower(),
        "start": _parse_dt(event.get("start_datetime_utc")),
        "has_join": bool(event.get("join_url") or event.get("online_meeting_provider")),
        "is_private": bool(event.get("is_private") or event.get("sensitive")),
    }


def score_email_calendar_relationship(
    thread: dict[str, Any], event: dict[str, Any]
) -> dict[str, Any]:
    """Score one thread↔event link. Returns relationship metadata (no clock read; caller stamps time)."""
    t = _thread_signals(thread)
    e = _event_signals(event)
    comp: dict[str, float] = {}

    if t["project_key"] and e["project_key"] and t["project_key"] == e["project_key"]:
        comp["same_project"] = _WEIGHTS["same_project"]

    t_tok, e_tok = _tokens(t["subject"]), _tokens(e["subject"])
    if t_tok and e_tok:
        jac = len(t_tok & e_tok) / len(t_tok | e_tok)
        if jac >= 0.2:
            comp["subject_similarity"] = round(_WEIGHTS["subject_similarity"] * min(1.0, jac / 0.5), 3)

    if e_tok and (e_tok & _tokens(t["text"])) and _MEETING_WORDS.search(t["text"]):
        comp["explicit_meeting_reference"] = _WEIGHTS["explicit_meeting_reference"]

    if t["domains"] & e["domains"]:
        comp["participant_overlap"] = _WEIGHTS["participant_overlap"]

    if e["start"] and t["times"]:
        deltas = [abs((e["start"] - mt).total_seconds()) / 3600.0 for mt in t["times"]]
        nearest = min(deltas)
        if nearest <= 24:
            comp["time_proximity"] = _WEIGHTS["time_proximity_24h"]
        elif nearest <= 72:
            comp["time_proximity"] = _WEIGHTS["time_proximity_72h"]

    shared_records = [
        tok for tok in _RECORD_TOKENS if tok in t["text"] and tok in e["text"]
    ]
    if shared_records:
        comp["shared_record_reference"] = _WEIGHTS["shared_record_reference"]

    if _JOIN_HINT.search(t["text"]) and e["has_join"]:
        comp["teams_join_reference_match"] = _WEIGHTS["teams_join_reference_match"]

    if e["subject"].strip().lower() in _GENERIC_TITLES:
        comp["generic_title_penalty"] = _WEIGHTS["generic_title_penalty"]
    if e["is_private"]:
        comp["private_sensitive_penalty"] = _WEIGHTS["private_sensitive_penalty"]

    confidence = max(0.0, min(1.0, round(sum(comp.values()), 3)))
    positive = [k for k, v in comp.items() if v > 0]
    reason_codes = positive or ["no_signal"]
    if confidence >= STRONG_THRESHOLD:
        relationship_class = "strong"
    elif confidence >= MODERATE_THRESHOLD:
        relationship_class = "moderate"
    else:
        relationship_class = "weak"
    review_required = relationship_class == "moderate" or "private_sensitive_penalty" in comp

    return {
        "relationship_type": "email_calendar",
        "from_source_family": "email_thread_raw_context",
        "from_source_ref": thread.get("thread_ref") or thread.get("raw_thread_context_id"),
        "to_source_family": "calendar_event_raw_content",
        "to_source_ref": event.get("event_index_id") or event.get("raw_calendar_event_id"),
        "project_key": t["project_key"] or e["project_key"],
        "confidence": confidence,
        "relationship_class": relationship_class,
        "review_required": review_required,
        "reason_codes": reason_codes,
        "score_components": {k: round(v, 3) for k, v in comp.items()},
        "may_combine": relationship_class in ("strong", "moderate"),
    }


def find_email_calendar_relationships(
    *,
    store: Any,
    project_key: Optional[str] = None,
    limit: int = 50,
    scan_threads: int = 50,
    scan_events: int = 50,
    min_confidence: float = MODERATE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Score recent thread×event pairs (bounded scan); return combinable candidates, best first."""
    threads = store.list_email_thread_raw_context(project_key=project_key, limit=scan_threads)
    events = store.list_calendar_event_raw_content(project_key=project_key, limit=scan_events)
    out: list[dict[str, Any]] = []
    for th in threads:
        for ev in events:
            rel = score_email_calendar_relationship(th, ev)
            if rel["confidence"] >= min_confidence:
                out.append(rel)
    out.sort(key=lambda r: r["confidence"], reverse=True)
    return out[: max(0, limit)]
