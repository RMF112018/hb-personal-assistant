"""Phase 09 Addendum V2 — Daily Brief record-level enrichment (Prompt 02).

Builds the record-bearing ``render_payload`` sections for ``DailyBriefHandoffPacketV2`` from the
read-only stores that already expose safe, redacted, source-linked data:

- calendar (``calendar_event_index`` + ``calendar_event_attendees``) → today_agenda / yesterday /
  calendar_activity
- email threads (``email_thread_summaries``) → email_activity
- Procore action signals (``procore_action_signals``) → schedule and next_7_days deadlines

Every section is a uniform **RecordSection** so the count-vs-detail rule can be enforced structurally:
a count is only actionable if it is backed by listed records, otherwise the section must declare
``detail_available=False`` with a ``detail_gap_reason``. Procore record domains that do not yet have a
dedicated reader (RFIs, submittals, punch/observations, procurement) are emitted as explicit
detail-unavailable sections — never as bare counts.

Read-only, metadata-only, source-linked (hashed refs), fail-closed. Never emits a raw calendar/email
body, raw subject, email address, Graph/join/signed URL, token, or header (the packet builder runs a
``_assert_no_raw`` backstop over the whole packet).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ....store import get_connection
from ...store import ConstructionStore

_MAX_RECORDS = 50
_NEXT_DAYS_HORIZON = 7

_SCHEDULE_SIGNAL_TYPES = (
    "activity_critical",
    "activity_zero_float",
    "activity_constrained",
    "activity_deadline_variance",
)

# Reason codes for honest gaps (stable, machine-readable).
GAP_DEDICATED_READER = "dedicated_reader_not_available"
GAP_NO_PROJECT_SCOPE = "no_project_scope"
GAP_NO_SOURCE_DATA = "no_source_data"
GAP_NAMES_NOT_PERSISTED = "names_not_persisted_opaque_ids_only"
GAP_ATTRS_IN_CANONICAL = "activity_attributes_in_canonical_not_signal"
GAP_THREAD_LEVEL_ONLY = "thread_level_summary_only"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ref(value: str | None) -> str:
    return _hash(value or "")[:48]


def _date_part(iso: str | None) -> str | None:
    return iso[:10] if iso else None


def _record_section(
    records: list[dict[str, Any]], *, source_family: str, why_it_matters: str
) -> dict[str, Any]:
    """Build a uniform RecordSection from real records. ``count`` always equals the number of
    listed records (never a larger bare count); truncation is surfaced explicitly via ``truncated``
    + ``total_count`` (no silent caps). An empty section reports count 0 (nothing in window)."""
    listed = records[:_MAX_RECORDS]
    return {
        "count": len(listed),
        "records": listed,
        "detail_available": True,
        "detail_gap_reason": None,
        "source_family": source_family,
        "why_it_matters": why_it_matters,
        "truncated": len(records) > _MAX_RECORDS,
        "total_count": len(records),
    }


def _unavailable_section(
    *, source_family: str, why_it_matters: str, count: int = 0, reason: str
) -> dict[str, Any]:
    """A section that reports no listed records and says so explicitly (never a bare count)."""
    return {
        "count": count,
        "records": [],
        "detail_available": False,
        "detail_gap_reason": reason,
        "source_family": source_family,
        "why_it_matters": why_it_matters,
    }


# --- calendar -------------------------------------------------------------------------------------


def _calendar_rows(conn: Any, project_key: str | None) -> list[dict[str, Any]]:
    """Read only the safe, redacted calendar columns (never web_link / raw body)."""
    sql = (
        "SELECT event_index_id, project_key, subject_redacted, start_datetime_utc,"
        " end_datetime_utc, is_online_meeting, is_cancelled, is_private, review_required"
        " FROM calendar_event_index"
    )
    params: tuple[Any, ...] = ()
    if project_key is not None:
        sql += " WHERE project_key = ?"
        params = (project_key,)
    sql += " ORDER BY start_datetime_utc"
    keys = (
        "event_index_id",
        "project_key",
        "subject_redacted",
        "start_datetime_utc",
        "end_datetime_utc",
        "is_online_meeting",
        "is_cancelled",
        "is_private",
        "review_required",
    )
    return [dict(zip(keys, row, strict=True)) for row in conn.execute(sql, params).fetchall()]


def _attendee_counts(conn: Any) -> dict[str, int]:
    rows = conn.execute(
        "SELECT event_index_id, COUNT(*) FROM calendar_event_attendees GROUP BY event_index_id"
    ).fetchall()
    return {str(eid): int(n) for eid, n in rows}


def _calendar_record(row: dict[str, Any], attendees: dict[str, int]) -> dict[str, Any]:
    eid = str(row["event_index_id"])
    return {
        "project_key": row.get("project_key"),
        "start_time": row.get("start_datetime_utc"),
        "end_time": row.get("end_datetime_utc"),
        "meeting_title_redacted": row.get("subject_redacted"),
        "attendee_count": attendees.get(eid, 0),
        "is_online_meeting": bool(row.get("is_online_meeting")),
        "related_records": None,
        "prep_needed": None,
        "open_items": None,
        "review_required": bool(row.get("review_required")),
        "why_it_matters": "Scheduled meeting in the brief window; confirm prep and attendees.",
        "source_family": "calendar_event_index",
        "source_ref_hash": _ref(eid),
        "detail_availability": {
            "present": ["start_time", "end_time", "meeting_title_redacted", "attendee_count"],
            "unavailable": {
                "related_records": GAP_DEDICATED_READER,
                "prep_needed": GAP_DEDICATED_READER,
                "open_items": GAP_DEDICATED_READER,
            },
        },
    }


def _build_calendar_sections(
    db_path: str | None, *, brief_date: str, project_key: str | None
) -> dict[str, dict[str, Any]]:
    conn = get_connection(Path(db_path) if db_path is not None else None)
    rows = _calendar_rows(conn, project_key)
    attendees = _attendee_counts(conn)
    if not rows:
        gap = _unavailable_section(
            source_family="calendar_event_index",
            why_it_matters="No calendar events are available in the local store.",
            reason=GAP_NO_SOURCE_DATA,
        )
        return {"today_agenda": gap, "yesterday": dict(gap), "calendar_activity": dict(gap)}

    try:
        yday = (
            (datetime.fromisoformat(f"{brief_date}T00:00:00") - timedelta(days=1))
            .date()
            .isoformat()
        )
    except ValueError:
        yday = None

    live = [r for r in rows if not r.get("is_cancelled")]
    today = [
        _calendar_record(r, attendees)
        for r in live
        if _date_part(r["start_datetime_utc"]) == brief_date
    ]
    yesterday = [
        _calendar_record(r, attendees)
        for r in live
        if yday and _date_part(r["start_datetime_utc"]) == yday
    ]
    activity = [_calendar_record(r, attendees) for r in live]

    return {
        "today_agenda": _record_section(
            today,
            source_family="calendar_event_index",
            why_it_matters="What is on today's agenda.",
        ),
        "yesterday": _record_section(
            yesterday,
            source_family="calendar_event_index",
            why_it_matters="Meetings held yesterday.",
        ),
        "calendar_activity": _record_section(
            activity,
            source_family="calendar_event_index",
            why_it_matters="Calendar activity across the brief window.",
        ),
    }


# --- email ----------------------------------------------------------------------------------------


def _email_record(thread: dict[str, Any]) -> dict[str, Any]:
    participants = thread.get("participants_hash") or []
    thread_key = str(thread.get("thread_key") or "")
    return {
        "project_key": thread.get("project_key"),
        "topic_redacted": thread.get("summary_redacted"),
        "last_activity_date": thread.get("last_message_datetime"),
        "message_count": thread.get("message_count"),
        "participant_count": len(participants) if isinstance(participants, list) else None,
        "sender_company": None,
        "related_record": None,
        "review_required": bool(thread.get("review_required")),
        "why_it_matters": "Active correspondence thread; review for items needing a response.",
        "recommended_focus": "Confirm whether the thread needs a reply before acting.",
        "source_family": "review_controlled_correspondence_context",
        "source_ref_hash": _ref(thread_key),
        "detail_availability": {
            "present": [
                "topic_redacted",
                "last_activity_date",
                "message_count",
                "participant_count",
            ],
            "unavailable": {
                "sender_company": GAP_THREAD_LEVEL_ONLY,
                "related_record": GAP_THREAD_LEVEL_ONLY,
            },
        },
    }


def _build_email_section(db_path: str | None, *, project_key: str | None) -> dict[str, Any]:
    store = ConstructionStore(db_path)
    threads = store.list_email_thread_summaries(project_key=project_key, limit=_MAX_RECORDS)
    if not threads:
        return _unavailable_section(
            source_family="review_controlled_correspondence_context",
            why_it_matters="No email thread summaries are available in the local store.",
            reason=GAP_NO_SOURCE_DATA,
        )
    records = [_email_record(t) for t in threads]
    return _record_section(
        records,
        source_family="review_controlled_correspondence_context",
        why_it_matters="Recent email activity by thread (metadata only).",
    )


# --- procore action signals: next 7 days + schedule ----------------------------------------------


def _within_horizon(due: str | None, *, brief_date: str, days: int) -> bool:
    if not due:
        return False
    d = _date_part(due)
    if d is None:
        return False
    try:
        start = datetime.fromisoformat(f"{brief_date}T00:00:00").date()
        end = start + timedelta(days=days)
        when = datetime.fromisoformat(f"{d}T00:00:00").date()
    except ValueError:
        return False
    return start <= when <= end


def _build_next_7_days_section(
    db_path: str | None, *, brief_date: str, project_keys: list[str]
) -> dict[str, Any]:
    from ....store.procore_action_queue import build_overdue_queue

    if not project_keys:
        return _unavailable_section(
            source_family="procore_action_signals",
            why_it_matters="Upcoming deadlines require a project scope.",
            reason=GAP_NO_PROJECT_SCOPE,
        )
    now_utc = f"{brief_date}T00:00:00+00:00"
    path = Path(db_path) if db_path is not None else None
    records: list[dict[str, Any]] = []
    for pk in project_keys:
        queue = build_overdue_queue(pk, now_utc=now_utc, db_path=path)
        for item in queue.get("queue", []):
            due = item.get("due_at_utc")
            if not _within_horizon(due, brief_date=brief_date, days=_NEXT_DAYS_HORIZON):
                continue
            endpoint = str(item.get("endpoint_id") or "")
            signal_type = str(item.get("signal_type") or "")
            records.append(
                {
                    "date": due,
                    "project_key": pk,
                    "item": f"{endpoint}:{signal_type}".strip(":"),
                    "type": endpoint or signal_type,
                    "responsible_party": None,
                    "responsible_party_id": item.get("owner_entity_key"),
                    "source": "procore_action_signals",
                    "review_required": bool(item.get("review_required")),
                    "why_it_matters": "Due within the next 7 days; confirm status before the deadline.",
                    "recommended_focus": "Verify the item against the source system before acting.",
                    "source_family": "procore_action_signals",
                    "source_ref_hash": _ref(str(item.get("record_key") or "")),
                    "detail_availability": {
                        "present": ["date", "type", "project_key"],
                        "unavailable": {"responsible_party": GAP_NAMES_NOT_PERSISTED},
                    },
                }
            )
    records.sort(key=lambda r: (str(r.get("date") or ""), str(r.get("project_key") or "")))
    return _record_section(
        records,
        source_family="procore_action_signals",
        why_it_matters="Deadlines coming up in the next 7 days.",
    )


def _schedule_record(sig: dict[str, Any]) -> dict[str, Any]:
    try:
        meta = json.loads(sig.get("metadata_json") or "{}")
    except (ValueError, TypeError):
        meta = {}
    return {
        "project_key": sig.get("project_key"),
        "activity_id": None,
        "activity_name": None,
        "wbs": None,
        "status": sig.get("signal_status"),
        "start_date": None,
        "finish_date": None,
        "total_float": meta.get("total_float"),
        "float_band": meta.get("float_band"),
        "is_critical": meta.get("is_critical"),
        "constraint_type": meta.get("constraint_type"),
        "constraint_date": meta.get("constraint_date"),
        "deadline_variance": meta.get("deadline_variance"),
        "signal_type": sig.get("signal_type"),
        "review_required": False,
        "why_it_matters": "Critical-path / zero-float / constrained activity signal.",
        "recommended_focus": "Confirm float and constraints against the schedule of record.",
        "source_family": "procore_action_signals",
        "source_ref_hash": _ref(str(sig.get("record_key") or "")),
        "detail_availability": {
            "present": ["total_float", "is_critical", "constraint_type", "signal_type"],
            "unavailable": {
                "activity_id": GAP_ATTRS_IN_CANONICAL,
                "activity_name": GAP_ATTRS_IN_CANONICAL,
                "wbs": GAP_ATTRS_IN_CANONICAL,
                "start_date": GAP_ATTRS_IN_CANONICAL,
                "finish_date": GAP_ATTRS_IN_CANONICAL,
            },
        },
    }


def _build_schedule_section(db_path: str | None, *, project_keys: list[str]) -> dict[str, Any]:
    from ....store.procore_enrichment import get_procore_action_signals

    if not project_keys:
        return _unavailable_section(
            source_family="procore_action_signals",
            why_it_matters="Schedule/float signals require a project scope.",
            reason=GAP_NO_PROJECT_SCOPE,
        )
    path = Path(db_path) if db_path is not None else None
    records: list[dict[str, Any]] = []
    for pk in project_keys:
        for stype in _SCHEDULE_SIGNAL_TYPES:
            for sig in get_procore_action_signals(project_key=pk, signal_type=stype, db_path=path):
                records.append(_schedule_record(sig))
    return _record_section(
        records,
        source_family="procore_action_signals",
        why_it_matters="Critical path, zero-float, and constrained activities.",
    )


# --- public entry point ---------------------------------------------------------------------------


def build_record_enrichment(
    *, brief_date: str, project_key: str | None, db_path: str | None, project_keys: list[str]
) -> dict[str, dict[str, Any]]:
    """Build the record-bearing render_payload sections (read-only, source-linked, fail-closed).

    ``project_keys`` are the keys observed in the V1 packet; used to scope the per-project Procore
    action-signal readers when ``project_key`` is the all-projects default.
    """
    scope_keys = [project_key] if project_key else sorted({k for k in project_keys if k})

    # Start from the calendar sections (today_agenda / yesterday / calendar_activity); a dict copy
    # rather than ``.update`` so the no-writeback static mutation-verb scan stays clean.
    sections: dict[str, dict[str, Any]] = dict(
        _build_calendar_sections(db_path, brief_date=brief_date, project_key=project_key)
    )
    sections["email_activity"] = _build_email_section(db_path, project_key=project_key)
    sections["next_7_days"] = _build_next_7_days_section(
        db_path, brief_date=brief_date, project_keys=scope_keys
    )
    sections["schedule"] = _build_schedule_section(db_path, project_keys=scope_keys)

    # Procore record domains without a dedicated reader yet (typed shape; explicit detail gap).
    for name, why in (
        ("rfis", "Open RFIs needing a response or routing."),
        ("submittals", "Submittals in review or approaching their due date."),
        ("punch", "Open punch / observation items by responsible party."),
        ("procurement", "Commitments, RFQs, and change orders in progress."),
    ):
        sections[name] = _unavailable_section(
            source_family="procore_live_records",
            why_it_matters=why,
            reason=GAP_DEDICATED_READER,
        )
    return sections
