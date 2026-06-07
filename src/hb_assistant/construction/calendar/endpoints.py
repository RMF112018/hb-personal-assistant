"""Phase 10A raw-content-capable calendar query endpoints.

These provide the backend "local API" surface for calendar events with
support for include_raw / raw_mode, resolved against raw_content policy.

Base shape is the redacted calendar_event_index (and related). When raw
inclusion is effective, a "raw_content" sub-dict is attached with the
actual subject/body/location/organizer/attendees/join_url/recurrence/start/end
captured at index time into calendar_event_raw_content.

This centralizes the enrichment pattern previously inline in meeting_prep
brief_builder (additive; brief_builder may continue using store.get or
switch to this for consistency).

Metadata/redacted mode (no raw fields) is always available by policy default,
explicit raw_mode=metadata_only, or when source/policy disallows.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from hb_assistant.construction.second_brain.local_ai import load_raw_content_policy
from hb_assistant.construction.store import ConstructionStore

RawMode = Literal["include", "metadata_only"]


def _load_policy_endpoints():
    try:
        rc = load_raw_content_policy()
        rcs = rc.raw_content
        ep = getattr(rcs, "endpoints", None)
        if ep is None:

            class _Ep:
                allow_include_raw_param = True
                default_raw_mode: RawMode = "include"

            ep = _Ep()
        return rcs, ep
    except Exception:

        class _Rcs:
            enabled = False
            mode = "disabled"
            default_endpoint_behavior: RawMode = "metadata_only"
            starting_sources = type("ss", (), {"email": False, "calendar": False})()

        class _Ep:
            allow_include_raw_param = True
            default_raw_mode: RawMode = "include"

        return _Rcs(), _Ep()


def _source_calendar_allowed(rcs: Any) -> bool:
    if not getattr(rcs, "enabled", False):
        return False
    mode = getattr(rcs, "mode", None)
    if mode not in ("email_calendar", "all_supported", "all_supported_plus_downstream"):
        return False
    ss = getattr(rcs, "starting_sources", None)
    return bool(ss and getattr(ss, "calendar", False))


def _resolve_include_raw(
    *,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
) -> bool:
    """Compute effective raw inclusion for calendar (fail-closed)."""
    rcs, ep = _load_policy_endpoints()
    if not _source_calendar_allowed(rcs):
        return False
    allow_param = bool(getattr(ep, "allow_include_raw_param", True))
    policy_default_is_raw = (
        getattr(rcs, "default_endpoint_behavior", "include_raw") == "include_raw"
    )

    if raw_mode is not None:
        if not allow_param:
            return policy_default_is_raw
        return raw_mode == "include"

    if include_raw is not None:
        if not allow_param:
            return policy_default_is_raw
        return bool(include_raw)

    return policy_default_is_raw


def list_calendar_events(
    *,
    source_id: Optional[str] = None,
    limit: int = 100000,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
    store: Optional[ConstructionStore] = None,
) -> list[dict[str, Any]]:
    """List calendar event index rows (redacted metadata base).

    When effective raw inclusion resolves true, for each event that has a
    matching calendar_event_raw_content row, attach "raw_content" containing
    the actual (non-redacted) subject, body, location, organizer, attendees
    list, join_url, recurrence, start/end.

    The base list shape (calendar_event_index columns) is unchanged when
    raw is not included; a _raw_content_included marker is added for
    telemetry.
    """
    s = store or ConstructionStore()
    effective = _resolve_include_raw(include_raw=include_raw, raw_mode=raw_mode)
    events = s.list_calendar_event_index(source_id=source_id, limit=limit)
    if not effective:
        for e in events:
            e["_raw_content_included"] = False
        return events

    # Enrich using the event_index_id (stable key)
    for e in events:
        e["_raw_content_included"] = False
        eid = e.get("event_index_id")
        if not eid:
            continue
        raw = s.get_calendar_event_raw_content(event_index_id=eid)
        if raw:
            e["raw_content"] = {
                "subject": raw.get("subject"),
                "body_preview": raw.get("body_preview"),
                "body_text": raw.get("body_text"),
                "body_html": raw.get("body_html"),
                "location": raw.get("location_display"),
                "organizer": {
                    "name": raw.get("organizer_name"),
                    "email": raw.get("organizer_email"),
                },
                "attendees": raw.get("attendees") or [],
                "online_meeting_provider": raw.get("online_meeting_provider"),
                "join_url": raw.get("join_url"),
                "recurrence": raw.get("recurrence") or {},
                "start": raw.get("start_datetime_utc"),
                "end": raw.get("end_datetime_utc"),
            }
            e["_raw_content_included"] = True
    return events


def get_calendar_event(
    *,
    event_index_id: str,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
    store: Optional[ConstructionStore] = None,
) -> Optional[dict[str, Any]]:
    """Get a single calendar event index row (metadata), with optional raw enrichment."""
    if not event_index_id:
        return None
    s = store or ConstructionStore()
    effective = _resolve_include_raw(include_raw=include_raw, raw_mode=raw_mode)
    meta = s.list_calendar_event_index(
        limit=1
    )  # inefficient but safe; filter client side for single
    # Better: since no direct get on index by id in some versions, we scan small or use list and find.
    # For correctness without adding store method, do a bounded list and pick.
    # In practice list is fast (local). For precision we accept the list+filter.
    events = s.list_calendar_event_index(limit=100000)
    meta = next((dict(ev) for ev in events if ev.get("event_index_id") == event_index_id), None)
    if not meta:
        return None
    meta["_raw_content_included"] = False
    if not effective:
        return meta
    raw = s.get_calendar_event_raw_content(event_index_id=event_index_id)
    if raw:
        meta["raw_content"] = {
            "subject": raw.get("subject"),
            "body_preview": raw.get("body_preview"),
            "body_text": raw.get("body_text"),
            "body_html": raw.get("body_html"),
            "location": raw.get("location_display"),
            "organizer": {
                "name": raw.get("organizer_name"),
                "email": raw.get("organizer_email"),
            },
            "attendees": raw.get("attendees") or [],
            "online_meeting_provider": raw.get("online_meeting_provider"),
            "join_url": raw.get("join_url"),
            "recurrence": raw.get("recurrence") or {},
            "start": raw.get("start_datetime_utc"),
            "end": raw.get("end_datetime_utc"),
        }
        meta["_raw_content_included"] = True
    return meta


def list_calendar_event_raw_content(
    *,
    project_key: Optional[str] = None,
    limit: int = 1000,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
    store: Optional[ConstructionStore] = None,
) -> list[dict[str, Any]]:
    """Direct raw calendar rows (when policy+params allow raw for this call)."""
    if not _resolve_include_raw(include_raw=include_raw, raw_mode=raw_mode):
        return []
    s = store or ConstructionStore()
    return s.list_calendar_event_raw_content(project_key=project_key, limit=limit)


def get_calendar_event_raw_content(
    *,
    event_index_id: Optional[str] = None,
    graph_event_id_hash: Optional[str] = None,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
    store: Optional[ConstructionStore] = None,
) -> Optional[dict[str, Any]]:
    """Direct single raw calendar row (when allowed)."""
    if not _resolve_include_raw(include_raw=include_raw, raw_mode=raw_mode):
        return None
    s = store or ConstructionStore()
    return s.get_calendar_event_raw_content(
        event_index_id=event_index_id, graph_event_id_hash=graph_event_id_hash
    )
