"""Phase 04B meeting-detail enrichment projection.

Extracts attendees, categories, topics, minutes/descriptions, attachments, the
meeting-series chain, and mentioned records / action+risk signals from the
``meetings`` (grouped list) and ``meeting-detail`` payloads. Meetings have no
dedicated V7 tables, so enrichment lands in the cross-cutting tables (people /
attachment refs / record edges / action signals / text intelligence). Free text
goes through ``emit_text_intelligence`` (hash + length + tokens + short redacted
excerpt + encrypted full-text ref). Self-contained store module — no
``hb_assistant.procore`` import.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .procore_enrichment import (
    emit_action_signal,
    emit_record_edge,
    emit_text_intelligence,
    extract_attachment_refs,
    extract_people_refs,
)

_CLOSED_TOPIC_TOKENS = ("closed", "complete", "completed", "resolved", "done")
_HIGH_PRIORITY_TOKENS = ("high", "urgent", "critical")

# --- text scan patterns (tokens/keywords only; never prose) ---
_MENTION_PATTERNS = [
    ("rfi", "mentioned_rfi", re.compile(r"\bRFI[\s#:-]*(\d+)", re.I)),
    ("pco", "mentioned_pco", re.compile(r"\bPCO[\s#:-]*(\d+)", re.I)),
    ("submittal", "mentioned_submittal", re.compile(r"\b(?:submittal|SUB)[\s#:-]*(\d+)", re.I)),
]
_MENTION_KEYWORDS = [
    ("permit", "mentioned_permit", re.compile(r"\bpermits?\b", re.I)),
    ("closeout", "mentioned_closeout", re.compile(r"\bcloseout\b", re.I)),
    ("utilities", "mentioned_utilities", re.compile(r"\butilit(?:y|ies)\b", re.I)),
]
_ACTION_KEYWORDS = (
    "action item", "follow up", "follow-up", "to-do", "to do", "assigned to", "due by",
    "will provide", "needs to", "next steps", "decision:", "agreed to", "approved to",
)
_RISK_KEYWORDS = (
    "claim", "delay", "dispute", "deficien", "backcharge", "change order", "impact", "lien",
    "incident", "injury", "safety", "penalty", "liquidated", "stop work",
)
_TOPIC_KEYWORDS = (
    "schedule", "budget", "cost", "safety", "quality", "coordination", "rfi", "submittal",
    "design", "procurement", "inspection", "permit", "closeout", "utilities", "punch",
)


def _hash(*parts: Any) -> str:
    return hashlib.sha256("|".join("" if p is None else str(p) for p in parts).encode("utf-8")).hexdigest()[:32]


def _record_key(project_key: str, endpoint_id: str, parent: Optional[str], record_id: Any) -> str:
    return "|".join([project_key, endpoint_id, parent or "", str(record_id)])


def _topics_from_categories(raw: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    categories = raw.get("meeting_categories")
    if not isinstance(categories, list):
        return out
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        topics = cat.get("meeting_topic")
        if isinstance(topics, list):
            out.extend(t for t in topics if isinstance(t, dict))
        elif isinstance(topics, dict):
            out.append(topics)
    return out


def _scan_text(text: Any) -> Dict[str, List[Any]]:
    """Return {detected_topics, mentioned_records, action_candidates, risk_terms}.

    All values are tokens / keywords — never prose. ``mentioned_records`` entries
    are ``{"type","ref","edge"}`` dicts for both the JSON column and edge emission.
    """
    result: Dict[str, List[Any]] = {
        "detected_topics": [], "mentioned_records": [], "action_candidates": [], "risk_terms": [],
    }
    if not isinstance(text, str) or not text.strip():
        return result
    low = text.lower()
    seen_refs: set[str] = set()
    for kind, edge, pattern in _MENTION_PATTERNS:
        for m in pattern.finditer(text):
            ref = f"{kind}:{m.group(1)}"
            if ref not in seen_refs:
                seen_refs.add(ref)
                result["mentioned_records"].append({"type": kind, "ref": ref, "edge": edge})
    for token, edge, pattern in _MENTION_KEYWORDS:
        if pattern.search(text) and token not in seen_refs:
            seen_refs.add(token)
            result["mentioned_records"].append({"type": token, "ref": token, "edge": edge})
    result["detected_topics"] = sorted({k for k in _TOPIC_KEYWORDS if k in low})
    result["action_candidates"] = sorted({k for k in _ACTION_KEYWORDS if k in low})
    result["risk_terms"] = sorted({k for k in _RISK_KEYWORDS if k in low})
    return result


def _emit_text(
    *, record_key: str, endpoint_id: str, field: str, text: Any, project_key: str, now_utc: str,
    db_path: Optional[Path],
) -> List[Dict[str, Any]]:
    """Run the text scan + persist a text-intelligence row (hash + tokens +
    redacted excerpt + encrypted full text). Returns the mentioned-record dicts."""
    if not isinstance(text, str) or not text.strip():
        return []
    scan = _scan_text(text)
    emit_text_intelligence(
        project_key=project_key, record_key=record_key, endpoint_id=endpoint_id,
        source_field_path=field, text=text,
        topics=scan["detected_topics"],
        mentioned_records=[m["ref"] for m in scan["mentioned_records"]],
        action_candidates=scan["action_candidates"],
        risk_terms=scan["risk_terms"],
        review_required=bool(scan["risk_terms"]),
        store_encrypted=True, excerpt_chars=160, now_utc=now_utc, db_path=db_path,
    )
    return scan["mentioned_records"]


def _attendee_people(raw: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for att in raw.get("attendees") or []:
        if isinstance(att, dict) and isinstance(att.get("login_information"), dict):
            out.append(att["login_information"])
    return out


def project_meeting_detail(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str] = None,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    meeting_id = str(raw["id"])
    meeting_rk = _record_key(project_key, "meeting-detail", None, meeting_id)
    counts = {"attendees": 0, "categories": 0, "topics": 0, "signals": 0}

    # attendees + created_by -> people entities + edges
    for k in extract_people_refs(_attendee_people(raw), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=meeting_rk, edge_type="attendee",
                         source_endpoint_id="meeting-detail", to_entity_key=k, now_utc=now_utc, db_path=db_path)
        counts["attendees"] += 1
    if raw.get("created_by_id") is not None:
        for k in extract_people_refs({"id": raw["created_by_id"]}, now_utc=now_utc, db_path=db_path):
            emit_record_edge(project_key=project_key, from_record_key=meeting_rk, edge_type="created_by",
                             source_endpoint_id="meeting-detail", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    # meeting-level attachments
    extract_attachment_refs(
        raw.get("attachments"), project_key=project_key, source_record_key=meeting_rk,
        source_endpoint_id="meeting-detail", now_utc=now_utc, db_path=db_path,
    )
    # meeting-level free text
    _emit_text(record_key=meeting_rk, endpoint_id="meeting-detail", field="description",
               text=raw.get("description"), project_key=project_key, now_utc=now_utc, db_path=db_path)
    _emit_text(record_key=meeting_rk, endpoint_id="meeting-detail", field="conclusion",
               text=raw.get("conclusion"), project_key=project_key, now_utc=now_utc, db_path=db_path)

    # categories -> edges
    for cat in raw.get("meeting_categories") or []:
        if isinstance(cat, dict) and cat.get("id") is not None:
            cat_key = _hash("meeting_category", project_key, cat["id"])
            emit_record_edge(project_key=project_key, from_record_key=meeting_rk, edge_type="category",
                             source_endpoint_id="meeting-detail", to_entity_key=cat_key, now_utc=now_utc, db_path=db_path)
            counts["categories"] += 1

    # topics
    for topic in _topics_from_categories(raw):
        if topic.get("id") is None:
            continue
        topic_id = str(topic["id"])
        topic_rk = _record_key(project_key, "meeting-topics", meeting_id, topic_id)
        counts["topics"] += 1
        emit_record_edge(project_key=project_key, from_record_key=meeting_rk, to_record_key=topic_rk,
                         edge_type="has_topic", source_endpoint_id="meeting-detail", now_utc=now_utc, db_path=db_path)
        extract_attachment_refs(
            topic.get("attachments"), project_key=project_key, source_record_key=topic_rk,
            source_endpoint_id="meeting-topics", parent_record_key=meeting_rk, now_utc=now_utc, db_path=db_path,
        )
        mentioned: List[Dict[str, Any]] = []
        mentioned += _emit_text(record_key=topic_rk, endpoint_id="meeting-topics", field="description",
                                text=topic.get("description"), project_key=project_key, now_utc=now_utc, db_path=db_path)
        mentioned += _emit_text(record_key=topic_rk, endpoint_id="meeting-topics", field="minutes",
                                text=topic.get("minutes"), project_key=project_key, now_utc=now_utc, db_path=db_path)
        for m in mentioned:
            emit_record_edge(project_key=project_key, from_record_key=topic_rk, edge_type=m["edge"],
                             source_endpoint_id="meeting-topics", to_entity_key=m["ref"], now_utc=now_utc, db_path=db_path)
        status = str(topic.get("status") or "").lower()
        priority = str(topic.get("priority") or "").lower()
        is_open = not any(tok in status for tok in _CLOSED_TOPIC_TOKENS)
        if is_open and priority in _HIGH_PRIORITY_TOKENS:
            emit_action_signal(project_key=project_key, record_key=topic_rk, endpoint_id="meeting-topics",
                               signal_type="meeting_topic_open_high_priority", importance="high",
                               now_utc=now_utc, db_path=db_path)
            counts["signals"] += 1

    return {"projected": True, "record_key": meeting_rk, "counts": counts}


def project_meeting(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str] = None,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Meetings (grouped list) projection: series chain + distributor/creator people."""
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    meeting_id = str(raw["id"])
    meeting_rk = _record_key(project_key, "meetings", None, meeting_id)

    parent_id = raw.get("parent_id")
    if parent_id is not None and str(parent_id) not in ("", meeting_id):
        parent_rk = _record_key(project_key, "meetings", None, parent_id)
        emit_record_edge(project_key=project_key, from_record_key=meeting_rk, to_record_key=parent_rk,
                         edge_type="previous_meeting", source_endpoint_id="meetings", now_utc=now_utc, db_path=db_path)

    for k in extract_people_refs(raw.get("distributed_by"), now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=meeting_rk, edge_type="distributed_by",
                         source_endpoint_id="meetings", to_entity_key=k, now_utc=now_utc, db_path=db_path)
    if raw.get("created_by_id") is not None:
        for k in extract_people_refs({"id": raw["created_by_id"]}, now_utc=now_utc, db_path=db_path):
            emit_record_edge(project_key=project_key, from_record_key=meeting_rk, edge_type="created_by",
                             source_endpoint_id="meetings", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    return {"projected": True, "record_key": meeting_rk}


def project_meeting_family(
    endpoint_id: str, raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str] = None,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Dispatch a raw meeting-family payload to its projection."""
    if endpoint_id == "meeting-detail":
        return project_meeting_detail(raw, project_key=project_key, sync_run_id=sync_run_id, now_utc=now_utc, db_path=db_path)
    if endpoint_id == "meetings":
        return project_meeting(raw, project_key=project_key, sync_run_id=sync_run_id, now_utc=now_utc, db_path=db_path)
    return {"projected": False}


__all__ = ["project_meeting", "project_meeting_detail", "project_meeting_family"]
