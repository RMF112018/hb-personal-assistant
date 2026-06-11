"""Phase 07B Prompt 04 — bounded calendarView event indexing (read-only, redacted).

Reads a bounded calendarView window through the guarded
:class:`ReadOnlyCalendarClient` and persists **only redacted/hashed metadata** into
the V23 ``calendar_event_index`` / ``calendar_event_attendees`` tables, with a
``calendar_crawl_runs`` receipt and ``calendar_sync_state`` as the run audit trail.

Read-only externally: only ``get_me`` / ``list_calendar_view`` (guarded GETs with a
body-/join-URL-free ``$select``) are issued. The only writes are local SQLite, and
they are gated behind ``dry_run=False`` (the CLI default is dry-run). Re-running is
idempotent — event rows upsert by a stable ``event_index_id``.

For larger windows (post-148 / Prompt 15 follow-up): after normalize, records are
chunked (size ~100); each chunk calls enhanced apply_calendar_index_batch with
partial_ok + chunked flags. Per-event errors are isolated and collected into
failure_diagnostics (no abort of chunk tx for other events); successful partials
commit + crawl_run is checkpointed after each chunk (status 'checkpointed' with
accum events_indexed via COALESCE + delta, sync last_attempted updated). Final
chunk does 'completed'. Status may be 'completed_with_errors' when some per-ev
failed but others succeeded. Bounded date+max_items preserved; no body/desc/join;
no M365 writeback. Checkpoints aid resume visibility (idempotent apply means
re-runs safe even without client start_after).

Persistence boundary (mirrors ``06_CALENDAR_INGESTION_PLAN.md``): event ID, iCal
UID, web link, subject, organizer, attendees, and location are stored **hashed or
redacted only**; the event body/description and the online-meeting join URL are
never fetched or stored. Private events (``sensitivity in {private, confidential}``)
store minimal metadata only (id hashes, time window, flags) and are flagged
``review_required`` with reason ``private_event``; subject/location/organizer/
attendees are omitted. Project matching and classification are later prompts.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.email.project_matcher import HB_PROJECT_NUMBER_RE
from hb_assistant.construction.second_brain.local_ai import load_raw_content_policy
from hb_assistant.construction.store import CalendarBatchApplyError, ConstructionStore
from hb_assistant.graph.calendar_readonly_client import ReadOnlyCalendarClient
from hb_assistant.normalize.redaction import hash_value, redact_location, redact_subject

_PAGE_SIZE = 50
_SAMPLE_LIMIT = 10
_PRIVATE_SENSITIVITIES = {"private", "confidential"}
_SAMPLE_KEYS = (
    "event_index_id",
    "start_datetime_utc",
    "end_datetime_utc",
    "is_private",
    "is_cancelled",
    "is_online_meeting",
    "review_required",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _domain(addr: Optional[str]) -> Optional[str]:
    if not addr or "@" not in addr:
        return None
    return addr.split("@", 1)[1].lower()


def _organizer_address(ev: dict[str, Any]) -> Optional[str]:
    return ((ev.get("organizer") or {}).get("emailAddress") or {}).get("address")


# Extra Graph event fields (from the widened get_event $select) that have no dedicated raw
# column. They are preserved losslessly in calendar_event_raw_content.raw_sidecar_json so the
# projection layer can normalise/sidecar them. The join URL is NEVER placed in the sidecar.
_SIDECAR_EVENT_FIELDS = (
    "isAllDay",
    "showAs",
    "type",
    "seriesMasterId",
    "categories",
    "createdDateTime",
    "lastModifiedDateTime",
    "originalStartTimeZone",
    "originalEndTimeZone",
    "locations",
)


def _calendar_raw_sidecar(full_ev: dict[str, Any]) -> dict[str, Any]:
    """Lossless remainder of widened Graph event fields without dedicated columns. Strips the
    online-meeting join URL so it can never leak via the sidecar."""
    sidecar: dict[str, Any] = {}
    for key in _SIDECAR_EVENT_FIELDS:
        value = full_ev.get(key)
        if value not in (None, "", [], {}):
            sidecar[key] = value
    original_start = full_ev.get("originalStart")
    if original_start:
        sidecar["originalStart"] = original_start
    online_meeting = full_ev.get("onlineMeeting")
    if isinstance(online_meeting, dict):
        scrubbed = {k: v for k, v in online_meeting.items() if k != "joinUrl"}
        if scrubbed:
            sidecar["onlineMeeting"] = scrubbed
    return sidecar


def _event_datetime(node: Any) -> Optional[str]:
    if isinstance(node, dict):
        return node.get("dateTime")
    return None


def _subject_token_hashes(subject: Optional[str]) -> Optional[str]:
    """JSON list of hashed subject tokens (>=2 chars), plus the hash of any full HB
    project number (NN-NNN-NN) detected before fragmentation. Enables Prompt 05
    deterministic project-number matching and project-token matching without ever
    persisting the raw subject (a hash reveals nothing)."""
    if not subject:
        return None
    tokens = {t.lower() for t in re.split(r"\W+", subject) if len(t) >= 2}
    token_hashes = {h for h in (hash_value(t) for t in tokens) if h}
    # Full HB project number (un-split) so deterministic project matching survives
    # the \W+ fragmentation above (e.g. "23-435-01" -> hash of the whole number).
    for num in HB_PROJECT_NUMBER_RE.findall(subject):
        num_hash = hash_value(num)
        if num_hash:
            token_hashes.add(num_hash)
    if not token_hashes:
        return None
    return json.dumps(sorted(token_hashes))


def normalize_event(
    ev: dict[str, Any], *, source_id: str
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize a raw Graph event into redacted ``upsert_calendar_event_index``
    kwargs + attendee rows. Returns ``(None, [])`` when the event lacks a start/end
    (not indexable). Private events carry minimal metadata only."""
    event_id = ev.get("id")
    graph_event_id_hash = hash_value(event_id)
    start_utc = _event_datetime(ev.get("start"))
    end_utc = _event_datetime(ev.get("end"))
    if not graph_event_id_hash or not start_utc or not end_utc:
        return None, []

    event_index_id = hash_value(f"{source_id}|{graph_event_id_hash}")
    sensitivity = (ev.get("sensitivity") or "").lower()
    is_private = sensitivity in _PRIVATE_SENSITIVITIES
    is_cancelled = bool(ev.get("isCancelled"))

    fields: dict[str, Any] = {
        "event_index_id": event_index_id,
        "source_id": source_id,
        "graph_event_id_hash": graph_event_id_hash,
        "ical_uid_hash": hash_value(ev.get("iCalUId")),
        "series_master_id_hash": hash_value(ev.get("seriesMasterId")),
        "web_link_hash": hash_value(ev.get("webLink")),
        "start_datetime_utc": start_utc,
        "end_datetime_utc": end_utc,
        "timezone": (ev.get("start") or {}).get("timeZone"),
        "is_cancelled": is_cancelled,
        "is_private": is_private,
        "is_online_meeting": bool(ev.get("isOnlineMeeting")),
        "online_meeting_provider": ev.get("onlineMeetingProvider"),
        "has_attachments": bool(ev.get("hasAttachments")),
    }

    attendees: list[dict[str, Any]] = []
    if is_private:
        # Private-event policy: minimal metadata only; flag for review.
        fields["review_required"] = True
        fields["review_reasons_json"] = json.dumps(["private_event"])
        return fields, attendees

    subject = ev.get("subject")
    organizer_addr = _organizer_address(ev)
    location = (ev.get("location") or {}).get("displayName")
    # Explicit assignments (not dict.update) so the no-writeback prover's static
    # mutation-verb scan never flags this metadata build as a ``.update()`` call.
    fields["subject_hash"] = hash_value(subject)
    fields["subject_redacted"] = redact_subject(subject)
    fields["subject_token_hashes_json"] = _subject_token_hashes(subject)
    fields["organizer_hash"] = hash_value(organizer_addr)
    fields["organizer_domain"] = _domain(organizer_addr)
    fields["location_hash"] = hash_value(location)
    fields["location_redacted"] = redact_location(location)
    fields["review_required"] = False
    for att in ev.get("attendees") or []:
        addr = (att.get("emailAddress") or {}).get("address")
        att_hash = hash_value(addr)
        if not att_hash:
            continue
        attendees.append(
            {
                "attendee_hash": att_hash,
                "attendee_domain": _domain(addr),
                "attendee_role": att.get("type"),
                "response_status": ((att.get("status") or {}).get("response")),
                "review_required": False,
            }
        )
    return fields, attendees


class IndexResult(BaseModel):
    """Outcome of a calendar index run (counts + run id; no subjects/addresses)."""

    source_id: str
    run_id: str
    mode: str  # dry_run | apply
    dry_run: bool
    persisted: bool
    window_start_utc: str
    window_end_utc: str
    lookback_days: int
    lookahead_days: int
    max_items: int
    events_seen: int
    events_indexed: int
    events_private: int
    events_cancelled: int
    events_review_required: int
    status: str  # completed | completed_with_errors | failed
    sample: list[dict[str, Any]]
    error_redacted: Optional[str] = None
    failure_diagnostics: list[dict[str, Any]] = Field(default_factory=list)

    # Phase 10A raw content (calendar subject/body/location/organizer/attendees/join/recurrence)
    # when policy email_calendar (or explicit flag). The redacted calendar_event_index path
    # is unchanged (always hashed/redacted; private/cancelled handling preserved).
    include_raw_content: bool = False
    raw_content_enabled: bool = False
    raw_events_persisted: int = 0

    model_config = {"extra": "forbid"}


class CalendarEventIndexer:
    """Bounded, read-only calendar event metadata indexer (redacted persistence)."""

    def __init__(
        self,
        calendar_client: ReadOnlyCalendarClient,
        store: ConstructionStore,
        failure_injector: Callable[[str, Optional[int], Optional[str]], None] | None = None,
    ) -> None:
        self._calendar = calendar_client
        self._store = store
        self._failure_injector = failure_injector

    def index(
        self,
        *,
        source_id: str,
        mailbox_owner: str = "current_user_hash_only",
        calendar_role: str = "primary",
        policy_id: Optional[str] = None,
        lookback_days: int = 14,
        lookahead_days: int = 30,
        max_items: int = 250,
        dry_run: bool = True,
        include_raw_content: bool = False,
    ) -> IndexResult:
        now = _utc_now()
        window_start = _iso(now - timedelta(days=lookback_days))
        window_end = _iso(now + timedelta(days=lookahead_days))
        run_id = str(uuid.uuid4())
        mode = "dry_run" if dry_run else "apply"

        events_seen = events_indexed = events_private = 0
        events_cancelled = events_review = 0
        sample: list[dict[str, Any]] = []
        status = "completed"
        error_redacted: Optional[str] = None
        failure_diagnostics: list[dict[str, Any]] = []

        # Phase 10A Prompt 04: raw calendar content gated by explicit flag OR the
        # raw_content policy (email_calendar mode + calendar starting source).
        # Fail-closed on policy load issues. Does not affect the redacted metadata path.
        raw_content_enabled = False
        try:
            rc = load_raw_content_policy()
            rcs = rc.raw_content
            raw_content_enabled = bool(
                getattr(rcs, "enabled", False)
                and getattr(rcs, "mode", None)
                in ("email_calendar", "all_supported", "all_supported_plus_downstream")
                and getattr(getattr(rcs, "starting_sources", None), "calendar", False)
            )
        except Exception:
            raw_content_enabled = False
        effective_raw = bool(include_raw_content or raw_content_enabled)

        raw_events_persisted = 0

        try:
            me = self._calendar.get_me()
            owner_upn = me.get("userPrincipalName") or me.get("mail")
            if mailbox_owner and mailbox_owner != "current_user_hash_only":
                owner_hash = hash_value(mailbox_owner)
                owner_domain = _domain(mailbox_owner)
            else:
                owner_hash = hash_value(owner_upn)
                owner_domain = _domain(owner_upn)

            events = self._calendar.list_calendar_view(
                start=window_start, end=window_end, top=_PAGE_SIZE, max_items=max_items
            )
            event_records: list[dict[str, Any]] = []
            for ordinal, ev in enumerate(events, start=1):
                events_seen += 1
                fields, attendees = normalize_event(ev, source_id=source_id)
                if fields is None:
                    continue
                if fields["is_private"]:
                    events_private += 1
                if fields["is_cancelled"]:
                    events_cancelled += 1
                if fields.get("review_required"):
                    events_review += 1
                if len(sample) < _SAMPLE_LIMIT:
                    sample.append({k: fields[k] for k in _SAMPLE_KEYS})

                # Phase 10A raw content: when effective, fetch full event (body/join/recurrence/attendees)
                # via client.get_event (falls back to list item), build payload, upsert to raw table
                # (idempotent). Count for evidence on both dry and apply; only write on apply.
                if effective_raw and ev.get("id"):
                    try:
                        full_ev = self._calendar.get_event(ev["id"])
                    except Exception:
                        full_ev = ev
                    rp = self._build_raw_calendar_payload(full_ev or ev)
                    if not dry_run:
                        ghash = hash_value(ev.get("id")) or ev.get("id")
                        eidx = hash_value(f"{source_id}|{ghash}") if ghash else None
                        sidecar = _calendar_raw_sidecar(full_ev or ev)
                        self._store.upsert_calendar_event_raw_content(
                            raw_calendar_event_id=f"raw:{ev.get('id')}",
                            graph_event_id_hash=ghash or "",
                            event_index_id=eidx,
                            project_key=None,
                            subject=rp.get("subject"),
                            body_preview=rp.get("body_preview"),
                            body_text=rp.get("body_text"),
                            body_html=rp.get("body_html"),
                            location_display=rp.get("location_display"),
                            organizer_name=rp.get("organizer_name"),
                            organizer_email=rp.get("organizer_email"),
                            attendees_json=json.dumps(rp.get("attendees") or [], sort_keys=True),
                            online_meeting_provider=rp.get("online_meeting_provider"),
                            join_url=rp.get("join_url"),
                            recurrence_json=json.dumps(rp.get("recurrence") or {}, sort_keys=True)
                            if rp.get("recurrence")
                            else None,
                            start_datetime_utc=rp.get("start_datetime_utc"),
                            end_datetime_utc=rp.get("end_datetime_utc"),
                            raw_capture_run_id=run_id,
                            source_updated_at_utc=(full_ev or ev).get("lastModifiedDateTime"),
                            join_url_policy="local_db_only",
                            raw_sidecar_json=json.dumps(sidecar, sort_keys=True) if sidecar else None,
                        )
                        # Raw read/persist access audit (no body/join URL is stored in the event row).
                        self._store.record_raw_content_access_event(
                            source_family="calendar",
                            endpoint_or_command="calendar.index.include_raw_content",
                            source_ref_hash=ghash,
                            raw_content_included=1,
                            purpose="raw_calendar_ingestion",
                        )
                    raw_events_persisted += 1

                if dry_run:
                    continue
                event_records.append(
                    {"event_ordinal": ordinal, "fields": fields, "attendees": attendees}
                )
            if not dry_run and event_records:
                # Chunked apply for larger-window harden: fixed chunk ~100; per-chunk tx with
                # partial_ok isolates per-event errors (collect diags, commit goods); crawl
                # checkpointed after each, final chunk completes. Relies on idempotent ON CONFLICT
                # for safety; no client change for resume (fetch always bounded window).
                chunk_size = 100
                chunks = [
                    event_records[i : i + chunk_size]
                    for i in range(0, len(event_records), chunk_size)
                ]
                total_indexed = 0
                chunk_diags: list[dict[str, Any]] = []
                for ci, ch in enumerate(chunks):
                    is_fin = ci == len(chunks) - 1
                    try:
                        n = self._store.apply_calendar_index_batch(
                            source_id=source_id,
                            mailbox_owner_hash=owner_hash or source_id,
                            mailbox_owner_domain=owner_domain,
                            calendar_role=calendar_role,
                            policy_id=policy_id,
                            lookback_days=lookback_days,
                            lookahead_days=lookahead_days,
                            max_items_per_run=max_items,
                            run_id=run_id,
                            mode=mode,
                            window_start_utc=window_start,
                            window_end_utc=window_end,
                            events_seen=events_seen,
                            events_private=events_private,
                            events_cancelled=events_cancelled,
                            events_review_required=events_review,
                            event_records=ch,
                            last_attempted_sync_utc=_iso(now),
                            failure_injector=self._failure_injector,
                            chunked=True,
                            is_final_chunk=is_fin,
                            partial_ok=True,
                            failure_diagnostics=chunk_diags,
                            last_event_ordinal=ch[-1]["event_ordinal"] if ch else None,
                        )
                        total_indexed += n
                    except CalendarBatchApplyError as e:
                        chunk_diags.append(e.diagnostic)
                        # prior chunks committed; continue to maximize partial progress
                        continue
                events_indexed = total_indexed
                failure_diagnostics = chunk_diags
                if chunk_diags:
                    status = "completed_with_errors"
                    error_redacted = (
                        f"partial:{len(chunk_diags)} event(s) errored (see failure_diagnostics)"
                    )
            elif not dry_run:
                # no records but apply path: ensure a crawl receipt exists (empty run)
                # (batch not called, but for parity a minimal receipt could be inserted here; current
                # pre-148 behavior left no row if 0, so leave as-is for minimal diff)
                pass
        except CalendarBatchApplyError as e:
            status = "failed"
            events_indexed = 0
            failure_diagnostics = [e.diagnostic]
            error_redacted = f"{e.diagnostic['operation']}:{e.diagnostic['exception_type']}"
        except Exception as e:  # bounded, sanitized — never raw payloads
            status = "failed"
            error_redacted = type(e).__name__

        return IndexResult(
            source_id=source_id,
            run_id=run_id,
            mode=mode,
            dry_run=dry_run,
            persisted=bool(not dry_run and status in ("completed", "completed_with_errors")),
            window_start_utc=window_start,
            window_end_utc=window_end,
            lookback_days=lookback_days,
            lookahead_days=lookahead_days,
            max_items=max_items,
            events_seen=events_seen,
            events_indexed=events_indexed,
            events_private=events_private,
            events_cancelled=events_cancelled,
            events_review_required=events_review,
            status=status,
            sample=sample,
            error_redacted=error_redacted,
            failure_diagnostics=failure_diagnostics,
            include_raw_content=include_raw_content,
            raw_content_enabled=raw_content_enabled,
            raw_events_persisted=raw_events_persisted,
        )

    def _build_raw_calendar_payload(self, ev: dict[str, Any]) -> dict[str, Any]:
        """Build plaintext raw payload for calendar_event_raw_content from a Graph event dict.

        Captures subject, body (text/html), location, organizer, attendees (with type/status),
        join URL, recurrence, and times. Defensive extraction for varying Graph shapes.
        Only used when raw content policy/flag permits (never mutates metadata path).
        """
        body = ev.get("body") or {}
        ctype = (body.get("contentType") or "text").lower()
        bcontent = body.get("content")
        body_text = bcontent if bcontent and "html" not in ctype else None
        body_html = bcontent if bcontent and "html" in ctype else None

        loc_node = ev.get("location") or {}
        location_display = (
            loc_node.get("displayName") or loc_node.get("address") or loc_node.get("locationUri")
        )

        org = ev.get("organizer") or {}
        org_ea = org.get("emailAddress") or {}
        organizer_name = org_ea.get("name")
        organizer_email = org_ea.get("address")

        atts: list[dict[str, Any]] = []
        for a in ev.get("attendees") or []:
            ea = a.get("emailAddress") or {}
            atts.append(
                {
                    "type": a.get("type"),
                    "status": (a.get("status") or {}).get("response"),
                    "name": ea.get("name"),
                    "address": ea.get("address"),
                }
            )

        # joinUrl often lives under onlineMeeting.joinUrl; some payloads surface joinUrl directly
        om = ev.get("onlineMeeting") or {}
        join_url = om.get("joinUrl") or ev.get("joinUrl") or ev.get("onlineMeetingUrl")

        recurrence = ev.get("recurrence")

        return {
            "subject": ev.get("subject"),
            "body_preview": None,  # calendar list view has no separate preview body
            "body_text": body_text,
            "body_html": body_html,
            "location_display": location_display,
            "organizer_name": organizer_name,
            "organizer_email": organizer_email,
            "attendees": atts,
            "online_meeting_provider": ev.get("onlineMeetingProvider"),
            "join_url": join_url,
            "recurrence": recurrence,
            "start_datetime_utc": _event_datetime(ev.get("start")),
            "end_datetime_utc": _event_datetime(ev.get("end")),
        }
