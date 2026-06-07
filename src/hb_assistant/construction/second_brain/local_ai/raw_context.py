"""Phase 10A Prompt 06 — Raw Model Context Packet Builder.

Builds model-ready packets that carry **actual** (non-redacted) email and
calendar raw content from the V42 tables (email_message_raw_content,
email_thread_raw_context, calendar_event_raw_content) when the raw_content
policy's model_context.include_raw_content is true and the source is enabled.

Packets are bounded using the policy ModelContextConfig (max threads/events,
max messages per thread, max body chars).

Every packet includes source refs (hashes + stable refs to the raw rows)
and a token_estimate. The packet is persisted to raw_content_model_context_packets
for audit/replay and returned to the caller (CLI, future local model runner).

Public entry points (additive):
  build_raw_email_context_packet(*, project_key=None, store=None, policy=None) -> dict
  build_raw_calendar_context_packet(*, project_key=None, store=None, policy=None) -> dict

CLI (added to phase-10):
  hb-assistant second-brain phase-10 raw-email-packet --project P1 --json
  hb-assistant second-brain phase-10 raw-calendar-packet --project P1 --json

The builders are read-only with respect to external systems; they only read the
local raw tables (already captured under policy at ingest time) and write the
derived packet row (local only).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

# lazy: imports of list_email_threads / list_calendar_events (and raw list fns) are inside
# the builder functions to prevent circular package initialization at import time.
from hb_assistant.construction.second_brain.local_ai import (
    RawContentPolicy,
    load_raw_content_policy,
)
from hb_assistant.construction.store import ConstructionStore


def _load_policy() -> RawContentPolicy:
    try:
        return load_raw_content_policy()
    except Exception:
        # Fail closed: return a disabled policy
        class _Dummy:
            raw_content = type(
                "rc",
                (),
                {
                    "enabled": False,
                    "mode": "disabled",
                    "model_context": type(
                        "mc",
                        (),
                        {
                            "include_raw_content": False,
                            "max_threads_per_run": 0,
                            "max_messages_per_thread": 0,
                            "max_body_chars_per_message": 0,
                            "max_events_per_run": 0,
                            "max_calendar_body_chars_per_event": 0,
                        },
                    )(),
                    "starting_sources": type("ss", (), {"email": False, "calendar": False})(),
                },
            )()

        return _Dummy()  # type: ignore[return-value]


def _effective_for_email(rc: Any) -> bool:
    if not getattr(rc, "enabled", False):
        return False
    mode = getattr(rc, "mode", None)
    if mode not in ("email_calendar", "all_supported", "all_supported_plus_downstream"):
        return False
    ss = getattr(rc, "starting_sources", None)
    return bool(
        ss
        and getattr(ss, "email", False)
        and getattr(rc, "model_context", None)
        and getattr(rc.model_context, "include_raw_content", False)
    )


def _effective_for_calendar(rc: Any) -> bool:
    if not getattr(rc, "enabled", False):
        return False
    mode = getattr(rc, "mode", None)
    if mode not in ("email_calendar", "all_supported", "all_supported_plus_downstream"):
        return False
    ss = getattr(rc, "starting_sources", None)
    return bool(
        ss
        and getattr(ss, "calendar", False)
        and getattr(rc, "model_context", None)
        and getattr(rc.model_context, "include_raw_content", False)
    )


def _truncate(text: Optional[str], max_chars: int) -> Optional[str]:
    if not text:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…[truncated]"


def _estimate_tokens(obj: Any) -> int:
    """Very rough token estimate (chars/4). Good enough for bounded context."""
    try:
        s = json.dumps(obj, sort_keys=True, ensure_ascii=False)
        return max(1, len(s) // 4)
    except Exception:
        return 0


def build_raw_email_context_packet(
    *,
    project_key: Optional[str] = None,
    store: Optional[ConstructionStore] = None,
    policy: Optional[RawContentPolicy] = None,
) -> dict[str, Any]:
    """Build a bounded, source-referenced packet of actual raw email content.

    Uses the P05 email endpoints (which already gate on raw policy) to obtain
    plaintext when effective. Applies ModelContextConfig bounds. Persists a
    row to raw_content_model_context_packets and returns the packet envelope.
    """
    s = store or ConstructionStore()
    rc = policy or _load_policy()
    mc = getattr(getattr(rc, "raw_content", None), "model_context", None)

    # Lazy to break init cycle
    from hb_assistant.construction.email import list_email_threads  # noqa: F401 (used below)

    effective = _effective_for_email(getattr(rc, "raw_content", None))
    if not effective or not mc or not getattr(mc, "include_raw_content", False):
        # Return a metadata-only empty packet (still persisted for audit)
        packet_id = f"raw-email:{uuid.uuid4()}"
        pkt: dict[str, Any] = {
            "packet_id": packet_id,
            "packet_type": "raw_email_context",
            "project_key": project_key,
            "raw_content_included": 0,
            "source_refs": [],
            "content": {"threads": []},
            "bounds": {},
            "token_estimate": 0,
        }
        s.upsert_raw_content_model_context_packet(
            packet_id=packet_id,
            packet_type="raw_email_context",
            source_family="email_message_raw_content",
            project_key=project_key,
            raw_content_included=0,
            packet_json=json.dumps(pkt, sort_keys=True),
            token_estimate=0,
        )
        return pkt

    max_threads = int(getattr(mc, "max_threads_per_run", 5) or 5)
    max_msgs = int(getattr(mc, "max_messages_per_thread", 10) or 10)
    max_chars = int(getattr(mc, "max_body_chars_per_message", 2000) or 2000)

    # Pull via the policy-respecting endpoint surface (P05)
    thread_rows = list_email_threads(
        project_key=project_key,
        limit=max_threads,
        include_raw=True,
        store=s,
    )

    threads_out: list[dict[str, Any]] = []
    source_refs: list[dict[str, Any]] = []

    for t in thread_rows[:max_threads]:
        raw = t.get("raw_content") or {}
        msgs = (raw.get("messages") or [])[:max_msgs]
        bounded_msgs = []
        for m in msgs:
            bounded_msgs.append(
                {
                    "subject": m.get("subject"),
                    "body_text": _truncate(m.get("body_text"), max_chars),
                    "body_html": _truncate(m.get("body_html"), max_chars),
                    "from_name": m.get("from_name"),
                    "from_address": m.get("from_address"),
                    "to_recipients": m.get("to_recipients") or m.get("to") or [],
                    "sent_at_utc": m.get("sent_at_utc"),
                    "received_at_utc": m.get("received_at_utc"),
                }
            )
            if m.get("id"):
                source_refs.append(
                    {
                        "source_family": "email_message_raw_content",
                        "source_ref": m.get("id"),
                        "thread_ref": t.get("thread_key") or raw.get("thread_ref"),
                    }
                )
        if bounded_msgs or raw.get("thread_subject"):
            threads_out.append(
                {
                    "thread_subject": raw.get("thread_subject") or t.get("subject_redacted"),
                    "message_count": raw.get("message_count") or len(bounded_msgs),
                    "participant_count": raw.get("participant_count"),
                    "messages": bounded_msgs,
                }
            )
            if raw.get("thread_ref") or t.get("thread_key"):
                source_refs.append(
                    {
                        "source_family": "email_thread_raw_context",
                        "source_ref": raw.get("thread_ref") or t.get("thread_key"),
                    }
                )

    # Fallback to direct raw tables if the meta list_ (which joins summaries) yielded nothing.
    # This makes packet construction robust for pure-raw seeds (as in fixture tests) and
    # still produces actual content + source refs.
    if not threads_out:
        # Re-pull using direct (the list_ above may have been empty due to missing summaries)
        try:
            from hb_assistant.construction.email.endpoints import list_email_message_raw_content as _list_raw_msgs  # type: ignore
            raw_msgs = _list_raw_msgs(project_key=project_key, limit=max_threads * max_msgs, include_raw=True, store=s)
        except Exception:
            raw_msgs = []
        # Group by conversation or just emit as a flat thread for the packet
        grouped: dict[str, list[dict[str, Any]]] = {}
        for rm in raw_msgs[: max_threads * max_msgs]:
            key = rm.get("conversation_id_hash") or rm.get("message_id_hash") or "flat"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(rm)
        for key, lst in list(grouped.items())[:max_threads]:
            bmsgs = []
            for m in lst[:max_msgs]:
                bmsgs.append({
                    "subject": m.get("subject"),
                    "body_text": _truncate(m.get("body_text"), max_chars),
                    "body_html": _truncate(m.get("body_html"), max_chars),
                    "from_name": m.get("from_name"),
                    "from_address": m.get("from_address"),
                    "to_recipients": m.get("to_recipients") or [],
                    "sent_at_utc": m.get("sent_at_utc"),
                    "received_at_utc": m.get("received_at_utc"),
                })
            if bmsgs:
                threads_out.append({
                    "thread_subject": (lst[0].get("subject") if lst else None),
                    "message_count": len(bmsgs),
                    "participant_count": None,
                    "messages": bmsgs,
                })
            for m in lst:
                source_refs.append({
                    "source_family": "email_message_raw_content",
                    "source_ref": m.get("message_id_hash"),
                })

    content = {"threads": threads_out}
    token_est = _estimate_tokens(content)
    packet_id = f"raw-email:{uuid.uuid4()}"

    pkt = {
        "packet_id": packet_id,
        "packet_type": "raw_email_context",
        "project_key": project_key,
        "raw_content_included": 1,
        "source_refs": source_refs[: max_threads * max_msgs + 10],
        "content": content,
        "bounds": {  # type: ignore[dict-item]
            "max_threads_per_run": max_threads,
            "max_messages_per_thread": max_msgs,
            "max_body_chars_per_message": max_chars,
        },
        "token_estimate": token_est,
    }

    s.upsert_raw_content_model_context_packet(
        packet_id=packet_id,
        packet_type="raw_email_context",
        source_family="email_message_raw_content",
        project_key=project_key,
        raw_content_included=1,
        packet_json=json.dumps(pkt, sort_keys=True),
        token_estimate=token_est,
    )
    return pkt


def build_raw_calendar_context_packet(
    *,
    project_key: Optional[str] = None,
    store: Optional[ConstructionStore] = None,
    policy: Optional[RawContentPolicy] = None,
) -> dict[str, Any]:
    """Build a bounded, source-referenced packet of actual raw calendar content."""
    s = store or ConstructionStore()
    rc = policy or _load_policy()
    mc = getattr(getattr(rc, "raw_content", None), "model_context", None)

    # Lazy to break init cycle
    from hb_assistant.construction.calendar import list_calendar_events  # noqa: F401 (used below)

    effective = _effective_for_calendar(getattr(rc, "raw_content", None))
    if not effective or not mc or not getattr(mc, "include_raw_content", False):
        packet_id = f"raw-calendar:{uuid.uuid4()}"
        pkt: dict[str, Any] = {
            "packet_id": packet_id,
            "packet_type": "raw_calendar_context",
            "project_key": project_key,
            "raw_content_included": 0,
            "source_refs": [],
            "content": {"events": []},
            "bounds": {},
            "token_estimate": 0,
        }
        s.upsert_raw_content_model_context_packet(
            packet_id=packet_id,
            packet_type="raw_calendar_context",
            source_family="calendar_event_raw_content",
            project_key=project_key,
            raw_content_included=0,
            packet_json=json.dumps(pkt, sort_keys=True),
            token_estimate=0,
        )
        return pkt

    max_events = int(getattr(mc, "max_events_per_run", 20) or 20)
    max_chars = int(getattr(mc, "max_calendar_body_chars_per_event", 3000) or 3000)

    event_rows = list_calendar_events(
        source_id=None,
        limit=max_events,
        include_raw=True,
        store=s,
    )

    events_out: list[dict[str, Any]] = []
    source_refs: list[dict[str, Any]] = []

    for e in event_rows[:max_events]:
        raw = e.get("raw_content") or {}
        ev = {
            "subject": raw.get("subject") or e.get("subject_hash"),
            "body_text": _truncate(raw.get("body_text"), max_chars),
            "body_html": _truncate(raw.get("body_html"), max_chars),
            "location": raw.get("location") or raw.get("location_display"),
            "organizer": raw.get("organizer"),
            "attendees": raw.get("attendees") or [],
            "join_url": raw.get("join_url"),
            "start": raw.get("start") or e.get("start_datetime_utc"),
            "end": raw.get("end") or e.get("end_datetime_utc"),
            "recurrence": raw.get("recurrence"),
        }
        events_out.append(ev)
        if e.get("event_index_id"):
            source_refs.append(
                {
                    "source_family": "calendar_event_raw_content",
                    "source_ref": e.get("event_index_id"),
                    "graph_event_id_hash": e.get("graph_event_id_hash"),
                }
            )

    # Fallback direct raw for tests / cases where index list + enrichment didn't surface (pure raw seed)
    if not events_out:
        try:
            from hb_assistant.construction.calendar.endpoints import list_calendar_event_raw_content as _list_raw_cal  # type: ignore
            raws = _list_raw_cal(project_key=project_key, limit=max_events, include_raw=True, store=s)
        except Exception:
            raws = []
        for r in raws[:max_events]:
            events_out.append({
                "subject": r.get("subject"),
                "body_text": _truncate(r.get("body_text"), max_chars),
                "body_html": _truncate(r.get("body_html"), max_chars),
                "location": r.get("location_display"),
                "organizer": {"name": r.get("organizer_name"), "email": r.get("organizer_email")},
                "attendees": r.get("attendees") or [],
                "join_url": r.get("join_url"),
                "start": r.get("start_datetime_utc"),
                "end": r.get("end_datetime_utc"),
                "recurrence": r.get("recurrence"),
            })
            if r.get("event_index_id") or r.get("raw_calendar_event_id"):
                source_refs.append({
                    "source_family": "calendar_event_raw_content",
                    "source_ref": r.get("event_index_id") or r.get("raw_calendar_event_id"),
                })

    content = {"events": events_out}
    token_est = _estimate_tokens(content)
    packet_id = f"raw-calendar:{uuid.uuid4()}"

    pkt = {
        "packet_id": packet_id,
        "packet_type": "raw_calendar_context",
        "project_key": project_key,
        "raw_content_included": 1,
        "source_refs": source_refs,
        "content": content,
        "bounds": {  # type: ignore[dict-item]
            "max_events_per_run": max_events,
            "max_calendar_body_chars_per_event": max_chars,
        },
        "token_estimate": token_est,
    }

    s.upsert_raw_content_model_context_packet(
        packet_id=packet_id,
        packet_type="raw_calendar_context",
        source_family="calendar_event_raw_content",
        project_key=project_key,
        raw_content_included=1,
        packet_json=json.dumps(pkt, sort_keys=True),
        token_estimate=token_est,
    )
    return pkt
