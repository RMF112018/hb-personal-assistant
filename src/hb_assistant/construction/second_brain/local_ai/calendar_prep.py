"""Phase 10 — deterministic calendar meeting-prep candidates (advisory, no writeback).

Composes the redacted calendar read models (``calendar_event_index`` +
``calendar_event_attendees``, enriched per-event by the bounded ``calendar_event_action_packet``)
into reviewable, source-linked meeting-prep candidates for upcoming events, and (optionally, capped)
persists per-event rollup candidates into ``daily_brief_action_candidates`` (section ``calendar``) so
the prep can feed the daily-brief / review layer.

Deterministic-first: discovery, windowing, and priority come from safe redacted fields only
(``subject_redacted``, ``location_redacted``, organizer/attendee *domains*, start/end, online flag).
``now_utc`` is passed in by the caller (no clock read), so the lookahead window and ordering are
reproducible. The per-event body excerpt surfaced under ``--summary`` is the already-normalized,
join-URL/dial-in/passcode-redacted packet text (never raw HTML, never persisted).

Safety: no calendar/Graph/external writeback, never mutates calendar events. Never persists or emits
raw bodies, raw HTML, join URLs, dial-in/passcodes, full attendee lists, attendee names, or emails.
Source refs are deterministic (``cal:<sha256(event_index_id)>``); the project key falls back to
``__unassigned__`` when the index has none. The optional ``--synthesize`` narrative is fed ONLY
already-redacted aggregates (event/attendee counts + participant domains), is advisory and in-memory
(never persisted), and fails closed to the deterministic prep.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .calendar_category import resolve_calendar_category
from .calendar_classify import classify_calendar_event
from .daily_brief_candidate_writer import persist_candidate_with_refs
from .packet_builders import build_calendar_event_action_packet
from .project_aliases import summarize_unresolved_tokens

_SECTION = "calendar"

# The shared packet normalizer strips ``https://`` URLs + Teams boilerplate, but a meeting-prep
# excerpt must additionally drop scheme-less link/domain tokens (e.g. ``teams.microsoft.com/l/…``)
# and any email address before it is surfaced or persisted. Applied only to the calendar excerpt.
_EMAIL_RE = re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}")
_LINK_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|us|co|ms|gov|edu)\b(?:/\S*)?", re.IGNORECASE
)


def _safe_excerpt(text: str) -> str:
    """Defense-in-depth redaction for the calendar prep excerpt: drop emails and any scheme-less
    domain/link tokens the action-packet normalizer leaves behind, then collapse whitespace."""
    if not text:
        return ""
    for pat in (_EMAIL_RE, _LINK_RE, _DOMAIN_RE):
        text = pat.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


_SYNTH_SYSTEM = (
    "You are an executive assistant. Using ONLY the redacted aggregate counts and participant "
    "domains provided, write a brief advisory meeting-prep summary (3-5 sentences) and a short list "
    "of prep flags. Do not invent specific people, subjects, amounts, or links. Respond with JSON "
    'only: {"narrative": "<text>", "prep_flags": ["<flag>", ...]}.'
)

# Priority by proximity to the meeting (lower = surfaced first).
_SOON_DAYS = 2
_NEAR_DAYS = 7
_PRIORITY_SOON = 10
_PRIORITY_NEAR = 30
_PRIORITY_LATER = 60


def _parse_now(value: str) -> Optional[datetime]:
    """Parse the caller-supplied now/as-of into a naive-UTC datetime (tz dropped, deterministic)."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=None)


def _parse_window_bound(value: str) -> Optional[datetime]:
    """Parse a policy window bound (may carry a local UTC offset) into naive-UTC for comparison
    against the UTC-stored event stamps. Offset-aware inputs are converted to UTC first (unlike
    ``_parse_now``, which assumes its input is already UTC)."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None)


def _parse_event_dt(value: Any) -> Optional[datetime]:
    """Parse a stored UTC start/end stamp. Tolerates 7-digit fractional seconds by slicing to
    seconds resolution (``YYYY-MM-DDTHH:MM:SS``); calendar stamps are UTC, so naive compare is safe."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value[:19])
    except ValueError:
        return None


def _source_ref(event_index_id: str) -> str:
    return "cal:" + hashlib.sha256(str(event_index_id).encode("utf-8")).hexdigest()[:32]


def _priority_for(days_until: float) -> int:
    if days_until <= _SOON_DAYS:
        return _PRIORITY_SOON
    if days_until <= _NEAR_DAYS:
        return _PRIORITY_NEAR
    return _PRIORITY_LATER


def build_calendar_prep_candidates(
    *,
    store: Any,
    now_utc: str,
    db_path: Optional[str] = None,
    project_key: Optional[str] = None,
    limit: int = 50,
    lookahead_days: int = 14,
    window_start_iso: Optional[str] = None,
    window_end_iso: Optional[str] = None,
    dry_run: bool = True,
    max_persist: Optional[int] = None,
    synthesize: bool = False,
    client: Any = None,
    user_domains: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build deterministic, source-linked calendar meeting-prep candidates (dry-run-first).

    Discovers upcoming, non-cancelled, non-private events within ``[now_utc, now_utc+lookahead_days)``
    — or, when the central weekday policy supplies ``window_start_iso``/``window_end_iso`` (offset-aware
    local bounds, converted to UTC here), within that explicit window instead of ``lookahead_days`` —
    (bounded by ``limit``, soonest-first), enriches each with a bounded/redacted prep excerpt, and
    builds one prep candidate per event. Dry-run is the default (zero writes). ``--apply``
    (dry_run=False) requires ``max_persist`` and caps ACTUAL inserts into
    ``daily_brief_action_candidates``; once the cap is hit, remaining new events are counted
    (``would_persist``) but not written. Persisted rows are idempotent per (brief_date, ``calendar``,
    source_ref). No raw content, no calendar/external writeback.
    """
    if not dry_run and max_persist is None:
        raise ValueError("apply requires max_persist (cap on actual persisted candidates)")

    brief_date = now_utc[:10]
    now_dt = _parse_now(now_utc)
    if now_dt is None:
        raise ValueError(f"invalid now_utc/as-of: {now_utc!r}")
    # Window: the central weekday policy's explicit bounds take precedence over lookahead_days.
    window_start_dt = _parse_window_bound(window_start_iso) if window_start_iso else now_dt
    if window_start_dt is None:
        raise ValueError(f"invalid window_start_iso: {window_start_iso!r}")
    window_end = (
        _parse_window_bound(window_end_iso)
        if window_end_iso
        else now_dt + timedelta(days=max(0, lookahead_days))
    )
    if window_end is None:
        raise ValueError(f"invalid window_end_iso: {window_end_iso!r}")

    # Safe redacted fields only — never subjects/bodies/join URLs/attendee names/emails.
    raw_events = store.list_calendar_prep_source_events(project_key=project_key, limit=100000)

    # Raw subject/location map for PROJECT RESOLUTION ONLY (the persisted subject_redacted is a
    # hash placeholder in real data, so resolving on it yields 0 — the audit's calendar resolution
    # rate of 0.0). We read the real subject/location to resolve project/category, but persist ONLY
    # the redacted title; the raw subject is never persisted, logged, or emitted to status.
    raw_subjects: dict[str, dict[str, str]] = {}
    try:
        for row in store.list_calendar_event_raw_content(limit=100000):
            eid = row.get("event_index_id")
            if eid:
                raw_subjects[str(eid)] = {
                    "subject": str(row.get("subject") or "").strip(),
                    "location": str(row.get("location_display") or "").strip(),
                }
    except Exception:
        raw_subjects = {}

    existing_ids = {
        str(r.get("daily_brief_action_candidate_id"))
        for r in store.list_daily_brief_action_candidates(
            brief_date=brief_date, section=_SECTION, limit=100000
        )
    }

    summary: dict[str, Any] = {
        "events_in_window": 0,
        "events_considered": 0,
        "skipped_no_source_refs": 0,
        "skipped_out_of_window": 0,
        "would_persist": 0,
        "persisted": 0,
        "skipped_existing": 0,
    }

    # Window + bound to limit (soonest-first; reader already orders by start). True in-window total is
    # reported separately so truncation by --limit is visible (no silent cap).
    in_window: list[dict[str, Any]] = []
    for ev in raw_events:
        start = _parse_event_dt(ev.get("start_datetime_utc"))
        if start is None or not (window_start_dt <= start < window_end):
            summary["skipped_out_of_window"] += 1
            continue
        in_window.append(ev)
    summary["events_in_window"] = len(in_window)
    considered = in_window[: max(0, limit)]
    summary["events_considered"] = len(considered)

    event_views: list[dict[str, Any]] = []
    remaining: Optional[int] = max_persist if (not dry_run and max_persist is not None) else None

    for ev in considered:
        event_index_id = str(ev.get("event_index_id") or "")
        if not event_index_id:
            summary["skipped_no_source_refs"] += 1
            continue
        source_ref = _source_ref(event_index_id)
        start = _parse_event_dt(ev.get("start_datetime_utc"))
        days_until = ((start - now_dt).total_seconds() / 86400.0) if start else 0.0
        priority = _priority_for(days_until)

        # Bounded, redacted advisory enrichment (join-URL/dial-in/passcode stripped, body→text,
        # attendees→domains). We take ONLY the normalized excerpt + has_join_url flag — never the
        # packet's raw subject.
        packet = build_calendar_event_action_packet(
            event_index_id=event_index_id, store=store, user_domains=user_domains
        )
        pkt_event = (packet.get("content", {}).get("events") or [{}])[0]
        prep_excerpt = _safe_excerpt(str(pkt_event.get("body_text") or ""))
        has_join = bool(packet.get("has_join_url"))

        title = str(ev.get("subject_redacted") or "").strip() or "Meeting prep"
        location_redacted = ev.get("location_redacted")
        domains = ev.get("participant_domains") or []
        attendee_count = int(ev.get("attendee_count") or 0)
        location_class = "online" if ev.get("is_online_meeting") else "in_person_or_unspecified"

        # Category + project: prefer the index's project_key; else delegate to the deterministic
        # category resolver (project arm = the canonical alias matcher; internal/PTO/training/
        # needs-review classification around it). Resolve from the REAL subject/location (the
        # redacted title is a hash placeholder in real data); persist only the redacted title.
        # Low-confidence project-looking text becomes ``__needs_review__`` (review-safe).
        indexed_proj = ev.get("project_key")
        raw = raw_subjects.get(event_index_id) or {}
        resolution = resolve_calendar_category(
            subject=raw.get("subject") or title,
            location=raw.get("location") or str(location_redacted or ""),
            organizer_domain=ev.get("organizer_domain"),
            attendees=attendee_count,
            indexed_project_key=indexed_proj,
        )
        proj = resolution.project_key

        # Deterministic value tier (pre-model noise filter); the synthesis packet uses this to
        # demote/exclude low-value meetings before the local model ever sees them.
        classification = classify_calendar_event(
            title=title,
            location=str(location_redacted or ""),
            attendee_count=attendee_count,
            is_online=bool(ev.get("is_online_meeting")),
            has_project=resolution.category == "project",
            days_until=days_until,
        )
        reason = f"{attendee_count} attendees · {len(domains)} domains · {location_class}"

        view = {
            "event_index_id": event_index_id,
            "source_ref": source_ref,
            "project_key": proj,
            "category": resolution.category,
            "category_reason": resolution.reason,
            "matched_alias": resolution.matched_alias,
            "needs_review": resolution.needs_review,
            "resolution_confidence": resolution.confidence,
            "project_inferred": bool(resolution.category == "project" and not indexed_proj),
            "calendar_class": classification.klass,
            "calendar_class_reason": classification.reason_code,
            "calendar_visible": classification.visible,
            "title_redacted": title,
            "start": ev.get("start_datetime_utc"),
            "end": ev.get("end_datetime_utc"),
            "is_online_meeting": bool(ev.get("is_online_meeting")),
            "has_join_url": has_join,
            "attendee_count": attendee_count,
            "participant_domains": domains,
            "location_redacted": location_redacted,
            "organizer_domain": ev.get("organizer_domain"),
            "priority": priority,
            "reason_redacted": reason,
            "prep_excerpt": prep_excerpt,
            "source_refs": [
                {"source_family": "calendar_event_raw_content", "source_ref": source_ref}
            ],
        }
        event_views.append(view)

        row_id = store.daily_brief_action_candidate_id_for(brief_date, _SECTION, source_ref)
        if row_id in existing_ids:
            summary["skipped_existing"] += 1
            continue
        summary["would_persist"] += 1
        if dry_run or (remaining is not None and remaining <= 0):
            continue
        receipt = persist_candidate_with_refs(
            store,
            brief_date=brief_date,
            section=_SECTION,
            title_redacted=title,
            confidence=resolution.confidence,
            project_key=proj,
            priority=priority,
            reason_redacted=reason,
            recommended_next_action="review",
            group_key=source_ref,
            source_refs=view["source_refs"],
        )
        if receipt.inserted:
            summary["persisted"] += 1
            existing_ids.add(row_id)
            if remaining is not None:
                remaining -= 1
        else:
            summary["skipped_existing"] += 1

    # Category + value-tier rollups (project vs internal vs review, class distribution) + a small
    # diagnostic of frequently-unresolved project tokens so alias coverage can be improved over time.
    # "assigned" = resolved to a real project; "unassigned" = needs-review/unknown (NOT internal).
    summary["projects_assigned"] = sum(1 for v in event_views if v.get("category") == "project")
    summary["projects_unassigned"] = sum(
        1 for v in event_views if v.get("category") in ("needs_review", "unknown")
    )
    summary["projects_inferred"] = sum(1 for v in event_views if v.get("project_inferred"))
    summary["needs_review_count"] = sum(
        1 for v in event_views if v.get("category") == "needs_review"
    )
    by_category: dict[str, int] = {}
    for v in event_views:
        cat = str(v.get("category") or "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
    summary["category_distribution"] = by_category
    by_class: dict[str, int] = {}
    for v in event_views:
        cls = str(v.get("calendar_class") or "fyi")
        by_class[cls] = by_class.get(cls, 0) + 1
    summary["by_calendar_class"] = by_class
    summary["unresolved_project_tokens"] = summarize_unresolved_tokens(
        [
            v["title_redacted"]
            for v in event_views
            if v.get("category") in ("needs_review", "unknown")
        ],
        top=10,
    )

    synthesis = _maybe_synthesize(synthesize=synthesize, client=client, event_views=event_views)

    return {
        "command": "second-brain calendar-prep build",
        "ok": True,
        "applied": not dry_run,
        "now_utc": now_utc,
        "brief_date": brief_date,
        "project_filter": project_key,
        "lookahead_days": lookahead_days,
        "summary": summary,
        "events": event_views,
        "synthesis": synthesis,
        "guardrails": {
            "dry_run_default": True,
            "apply_requires_max_persist": True,
            "deterministic_no_clock": True,
            "source_linked_only": True,
            "no_raw_persistence": True,
            "no_join_url_emitted": True,
            "no_full_attendee_arrays": True,
            "no_calendar_mutation": True,
            "no_external_writeback": True,
            "no_cloud_llm": True,
            "advisory_only": True,
        },
    }


def _redacted_aggregate(event_views: list[dict[str, Any]]) -> dict[str, Any]:
    """The ONLY thing fed to the optional model: counts + participant domains, no titles/excerpts."""
    domains: dict[str, None] = {}
    online = 0
    for ev in event_views:
        for d in ev.get("participant_domains") or []:
            domains.setdefault(d, None)
        if ev.get("is_online_meeting"):
            online += 1
    return {
        "event_count": len(event_views),
        "online_event_count": online,
        "participant_domains": list(domains)[:30],
    }


def _maybe_synthesize(
    *, synthesize: bool, client: Any, event_views: list[dict[str, Any]]
) -> dict[str, Any]:
    """Optional bounded advisory narrative (off by default; in-memory only; fails closed)."""
    if not synthesize:
        return {"requested": False}
    if client is None:
        return {"requested": True, "ok": False, "reason": "no_local_model_client"}
    payload = _redacted_aggregate(event_views)
    try:
        raw = client.generate_json(system=_SYNTH_SYSTEM, prompt=json.dumps(payload))
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("model output is not a JSON object")
        narrative = str(data.get("narrative") or "")[:2000]
        flags = [str(x) for x in (data.get("prep_flags") or []) if isinstance(x, (str, int, float))]
        return {"requested": True, "ok": True, "narrative": narrative, "prep_flags": flags[:20]}
    except Exception as e:
        return {"requested": True, "ok": False, "reason": f"synthesis_failed: {type(e).__name__}"}
