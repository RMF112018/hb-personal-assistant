"""Phase 10 (252) — "New Today" overnight change digest (deterministic, source-linked, raw-safe).

Builds the first, authoritative section of the daily brief: a human-readable digest of the meaningful
business changes introduced by the most recent overnight refresh cycle (nightly refresh ~8:00 PM ET →
brief ~5:00 AM ET). The product principle (reviewer's overriding correction) is that every item is a
**business record / source event** — never a candidate label or signal category. "22 payment-due
invoice signals" is the failure mode; "Coastal Pipeline submitted Invoice #1842 for Tropical, not yet
reviewed" is the goal.

Design contract:

- **Deterministic facts are authoritative.** Names, timestamps, project, record number/title/status,
  amount, meeting time, and source refs all come from the already-projected source tables. The
  optional local-model overlay (:mod:`ollama_new_today`) only polishes wording; it cannot invent
  facts and is applied *after* this module by the caller.
- **Refresh-window contract** (:func:`compute_refresh_window`): the brief summarizes the most recent
  successful nightly refresh. When run markers exist the actual refresh boundary is used; otherwise a
  deterministic fallback window (ending at the brief generation anchor, starting before the prior
  scheduled refresh) is used. The resolved window + rationale are returned for the evidence bundle.
- **Detail-or-drop (Procore):** a Procore change renders as a New Today business item only when real
  record detail joins (invoice number/vendor/amount/status; RFI number/title/status/impact). When it
  cannot, the item is demoted to a diagnostic data-quality item, never rendered as "…signal".
- **Email usefulness gate:** "email follow-up unavailable" is a degraded signal, not a successful
  item. When email substrate exists in the window but no actionable email event is derived, the
  digest reports ``email_degraded`` so the run classifies degraded.

Read-only and raw-safe: reads only the safe scalar columns of the source projections (never raw
bodies, join URLs, tokens, or addresses), formats every user-facing string through
:func:`~hb_assistant.construction.second_brain.local_ai.model_eval_metrics.scan_text_for_forbidden`,
and writes nothing. Persistence (V54) is a separate, optional step the caller performs.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from hb_assistant.store.connection import get_connection

from .model_eval_metrics import scan_text_for_forbidden
from .project_aliases import project_display_name, resolve_project

# --- Constants --------------------------------------------------------------------------------

_TZ = ZoneInfo("America/New_York")
_BRIEF_HOUR = 5  # the 5:00 AM ET brief generation anchor
#: Fallback refresh-window span when no usable run markers exist — covers a ~8PM→next-5AM cycle.
_FALLBACK_LOOKBACK_HOURS = 33
#: Boundaries within this many hours of the latest are treated as the SAME refresh cycle (so a
#: frequently-looping refresh does not collapse the window to seconds).
_MIN_CYCLE_GAP_HOURS = 6
DEFAULT_LOOKAHEAD_DAYS = 7  # subhead "prep through {+7d}" + calendar upcoming horizon
_PER_TYPE_CAP = 8  # max items surfaced per Procore record type / file batch (no silent truncation)

SOURCE_EMAIL = "email"
SOURCE_CALENDAR = "calendar"
SOURCE_PROCORE = "procore"
SOURCE_SHAREPOINT = "sharepoint"

NEEDS_ATTENTION = "needs_attention"
TEAM_FOLLOW_UP = "team_follow_up"
AWARENESS = "awareness"
ATTENTION_ORDER = (NEEDS_ATTENTION, TEAM_FOLLOW_UP, AWARENESS)
ATTENTION_LABEL: dict[str, str] = {
    NEEDS_ATTENTION: "Needs your attention",
    TEAM_FOLLOW_UP: "Team follow-up / monitor",
    AWARENESS: "Awareness only",
}

#: Public-provider domains that do not imply a company name.
_GENERIC_DOMAINS = frozenset(
    {
        "gmail.com",
        "outlook.com",
        "hotmail.com",
        "yahoo.com",
        "icloud.com",
        "aol.com",
        "live.com",
        "me.com",
        "msn.com",
    }
)
_KNOWN_COMPANY_BY_DOMAIN: dict[str, str] = {"hedrickbrothers.com": "Hedrick Brothers"}


# --- Models -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class RefreshWindow:
    """The resolved overnight refresh window the brief summarizes (raw-free, evidence-safe)."""

    start_utc: str
    end_utc: str
    source: str  # run_markers | partial_markers | fallback_window
    rationale: str


@dataclass
class DailyBriefChangeEvent:
    """One source-linked business change for the New Today digest (deterministic facts authoritative).

    Model fields (``summary_text`` / ``why_it_matters`` / ``recommended_action`` /
    ``attention_class``) start deterministic and may be polished by the advisory model overlay; every
    string is raw-safe (passes the forbidden-token scan). ``source_refs`` are hash-only linkages.
    """

    event_id: str
    brief_date: str
    refresh_window_start: str
    refresh_window_end: str
    source_family: str
    source_record_id: str
    source_refs: list[dict[str, str]] = field(default_factory=list)
    project_key: Optional[str] = None
    project_display_name: Optional[str] = None
    actor_display_name: Optional[str] = None
    actor_company: Optional[str] = None
    event_type: str = ""
    event_timestamp: Optional[str] = None
    business_record_type: Optional[str] = None
    business_record_number: Optional[str] = None
    business_record_title: Optional[str] = None
    business_record_status: Optional[str] = None
    amount: Optional[str] = None
    due_date: Optional[str] = None
    meeting_start: Optional[str] = None
    meeting_end: Optional[str] = None
    meeting_location_or_mode: Optional[str] = None
    summary_text: str = ""
    why_it_matters: str = ""
    recommended_action: str = ""
    attention_class: str = AWARENESS
    confidence: float = 0.9
    enrichment_status: str = "deterministic"
    model_profile_id: Optional[str] = None
    model_name: Optional[str] = None
    model_run_receipt_id: Optional[str] = None
    is_actionable: bool = False

    @property
    def source_ref_count(self) -> int:
        return len(self.source_refs)


# --- Time helpers -----------------------------------------------------------------------------


def _parse_utc(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp (offset or ``Z``) to an aware UTC datetime, or ``None``."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        # Date-only ('YYYY-MM-DD') → midnight UTC.
        try:
            dt = datetime.fromisoformat(text[:10])
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _brief_anchor(brief_date: str) -> datetime:
    """The deterministic brief-generation anchor: ``brief_date`` 05:00 America/New_York, as UTC."""
    d = date.fromisoformat(brief_date)
    return datetime.combine(d, time(_BRIEF_HOUR, 0), tzinfo=_TZ).astimezone(timezone.utc)


def _humanize_when(event_dt: Optional[datetime], brief_date: str) -> str:
    """Deterministic relative phrasing ("yesterday at 4:30 PM", "next Thursday at 1:30 PM").

    Computed purely from ``brief_date`` (a date) and the event time localized to ET — no clock read.
    """
    if event_dt is None:
        return "recently"
    local = event_dt.astimezone(_TZ)
    ev_date = local.date()
    today = date.fromisoformat(brief_date)
    delta = (ev_date - today).days
    clock = local.strftime("%I:%M %p").lstrip("0")
    weekday = local.strftime("%A")
    if delta == 0:
        day = "today"
    elif delta == -1:
        day = "yesterday"
    elif delta == 1:
        day = "tomorrow"
    elif -6 <= delta < -1:
        day = f"last {weekday}"
    elif 1 < delta <= 7:
        day = f"this coming {weekday}"
    elif 7 < delta <= 13:
        day = f"next {weekday}"
    else:
        day = f"on {ev_date.isoformat()}"
    return f"{day} at {clock}"


def _in_window(value: Any, win: RefreshWindow) -> bool:
    """True when an ISO timestamp falls in ``(start, end]`` of the refresh window."""
    dt = _parse_utc(value)
    if dt is None:
        return False
    start = _parse_utc(win.start_utc)
    end = _parse_utc(win.end_utc)
    if start is None or end is None:
        return False
    return start < dt <= end


# --- Formatting helpers -----------------------------------------------------------------------


def _safe(text: Any) -> str:
    """Collapse to a stripped string and drop it if it carries any forbidden token."""
    s = str(text or "").strip()
    if not s:
        return ""
    return "" if scan_text_for_forbidden(s) else s


def _company_from_address(addr: Any) -> Optional[str]:
    """Best-effort company label from an email domain (never returns the address itself)."""
    m = re.search(r"@([A-Za-z0-9.\-]+)", str(addr or ""))
    if not m:
        return None
    domain = m.group(1).lower().strip(".")
    if not domain or domain in _GENERIC_DOMAINS:
        return None
    if domain in _KNOWN_COMPANY_BY_DOMAIN:
        return _KNOWN_COMPANY_BY_DOMAIN[domain]
    parts = domain.split(".")
    core = parts[-2] if len(parts) >= 2 else parts[0]
    label = core.replace("-", " ").strip()
    return label.title() if label else None


def _fmt_amount(value: Any) -> Optional[str]:
    """Format a decimal-ish amount as ``$1,842.00``; ``None`` when not parseable / non-positive."""
    if value in (None, ""):
        return None
    try:
        num = float(str(value).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None
    if num <= 0:
        return None
    return f"${num:,.2f}"


def _fmt_date(value: Any) -> Optional[str]:
    """Normalize a date/timestamp to ``MM/DD/YYYY`` for human copy, or ``None``.

    A bare ``YYYY-MM-DD`` (e.g. a pay-period end) is formatted as-is without timezone conversion; a
    full timestamp is localized to ET first.
    """
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return date.fromisoformat(text).strftime("%m/%d/%Y")
        except ValueError:
            return None
    dt = _parse_utc(value)
    if dt is None:
        return None
    return dt.astimezone(_TZ).strftime("%m/%d/%Y")


def _event_id(brief_date: str, family: str, record_id: str) -> str:
    return hashlib.sha256(f"{brief_date}|{family}|{record_id}".encode("utf-8")).hexdigest()[:32]


def _sref(table: str, value: Any) -> dict[str, str]:
    ref = hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:32]
    return {"source_table": table, "source_ref_hash": ref}


def _conn(store: Any):
    return get_connection(getattr(store, "_db_path", None))


def _query(store: Any, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Guarded SELECT → list of dict rows; a missing table/column is a clean no-op (``[]``)."""
    try:
        cur = _conn(store).execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    except Exception:
        return []


# --- Refresh window ---------------------------------------------------------------------------


def compute_refresh_window(store: Any, brief_date: str) -> RefreshWindow:
    """Resolve the overnight refresh window the brief summarizes (deterministic contract).

    Collects successful-refresh boundary timestamps across families (Procore live sync runs, email/
    calendar raw ingestion runs, drive source sync state). ``end`` is the most recent boundary (or the
    brief anchor when none exist); ``start`` is the prior boundary (or a fixed fallback lookback before
    the anchor). The ``source`` + ``rationale`` explain the choice for the evidence bundle.
    """
    anchor = _brief_anchor(brief_date)
    boundaries: list[datetime] = []
    for sql, col in (
        (
            "SELECT completed_at_utc FROM procore_live_sync_runs "
            "WHERE completed_at_utc IS NOT NULL AND lower(COALESCE(state,status,'')) "
            "IN ('success','partial_success','ok')",
            "completed_at_utc",
        ),
        (
            "SELECT completed_utc FROM email_calendar_raw_ingestion_runs "
            "WHERE completed_utc IS NOT NULL AND lower(COALESCE(status,'')) IN ('success','ok','completed')",
            "completed_utc",
        ),
        (
            "SELECT last_successful_sync_utc FROM construction_source_sync_state "
            "WHERE last_successful_sync_utc IS NOT NULL",
            "last_successful_sync_utc",
        ),
    ):
        for row in _query(store, sql):
            dt = _parse_utc(row.get(col))
            # Only boundaries at/after the anchor would be in the future; keep those strictly before.
            if dt is not None and dt <= anchor:
                boundaries.append(dt)

    boundaries = sorted(set(boundaries))
    if boundaries:
        end_dt = boundaries[-1]
        # The window must span the most recent *nightly cycle*, not the gap between two rapid loop
        # completions. A frequently-looping refresh writes many boundaries seconds apart; only a
        # boundary at least one cycle-gap before the latest belongs to an earlier refresh cycle. When
        # none qualifies (all boundaries are intra-cycle), fall back to the fixed nightly lookback so
        # the window never collapses and silently drops the night's changes.
        cycle_gap = timedelta(hours=_MIN_CYCLE_GAP_HOURS)
        prior_cycle = [b for b in boundaries if b <= end_dt - cycle_gap]
        if prior_cycle:
            start_dt = prior_cycle[-1]
            source = "run_markers"
            rationale = (
                "Window spans the prior nightly refresh boundary (the most recent boundary at least "
                f"{_MIN_CYCLE_GAP_HOURS}h before the latest) to the most recent refresh completion."
            )
        else:
            start_dt = end_dt - timedelta(hours=_FALLBACK_LOOKBACK_HOURS)
            source = "fallback_window"
            rationale = (
                "Refresh boundaries are clustered within one cycle (a frequently-looping refresh); "
                "window ends at the latest completion and starts a fixed nightly lookback before it."
            )
    else:
        end_dt = anchor
        start_dt = anchor - timedelta(hours=_FALLBACK_LOOKBACK_HOURS)
        source = "fallback_window"
        rationale = (
            "No refresh run markers found; window ends at the 5:00 AM brief anchor and starts a fixed "
            "lookback before the prior scheduled ~8:00 PM refresh."
        )
    return RefreshWindow(
        start_utc=start_dt.isoformat(),
        end_utc=end_dt.isoformat(),
        source=source,
        rationale=rationale,
    )


# --- Email ------------------------------------------------------------------------------------


def _followup_candidates_in_window(store: Any, win: RefreshWindow) -> list[dict[str, Any]]:
    """Newly-derived actionable email follow-ups (task + commitment candidates) created in-window."""
    rows: list[dict[str, Any]] = []
    rows += _query(
        store,
        "SELECT title_redacted, project_key, waiting_state, urgency, reason_redacted, "
        "recommended_next_action, assignee_class AS actor_class, created_utc, stable_key "
        "FROM task_candidates",
    )
    rows += _query(
        store,
        "SELECT title_redacted, project_key, waiting_state, urgency, reason_redacted, "
        "recommended_next_action, commitment_actor_class AS actor_class, created_utc, stable_key "
        "FROM commitment_candidates",
    )
    return [r for r in rows if _in_window(r.get("created_utc"), win)]


def _attention_for_followup(row: dict[str, Any]) -> tuple[str, bool]:
    """Map a follow-up candidate to (attention_class, is_actionable)."""
    waiting = str(row.get("waiting_state") or "").lower()
    urgency = str(row.get("urgency") or "").lower()
    if waiting in ("waiting_on_me", "response_needed") or urgency in ("high", "urgent"):
        return NEEDS_ATTENTION, True
    if waiting in ("waiting_on_others", "team", "delegated"):
        return TEAM_FOLLOW_UP, True
    return AWARENESS, False


def _extract_email(
    store: Any, win: RefreshWindow, brief_date: str
) -> tuple[list[DailyBriefChangeEvent], bool, int]:
    """Email change events. Returns (events, substrate_present, actionable_count)."""
    messages = [
        m
        for m in _query(
            store,
            "SELECT message_id_hash, source_ref_hash, subject, from_name, from_address, "
            "received_at_utc, project_key, thread_ref FROM email_raw_message_structured "
            "WHERE COALESCE(is_current,1)=1",
        )
        if _in_window(m.get("received_at_utc"), win)
    ]
    candidates = _followup_candidates_in_window(store, win)
    substrate = bool(messages or candidates)

    # Index the most recent in-window message per project, to enrich a follow-up with sender/time.
    msg_by_project: dict[str, dict[str, Any]] = {}
    for m in sorted(messages, key=lambda r: str(r.get("received_at_utc") or "")):
        pk = str(m.get("project_key") or resolve_project(m.get("subject")) or "")
        if pk:
            msg_by_project[pk] = m

    events: list[DailyBriefChangeEvent] = []
    covered_projects: set[str] = set()
    actionable = 0

    # 1) Actionable layer: follow-up candidates derived this cycle, enriched by the latest message.
    for c in candidates:
        cpk: Optional[str] = str(c.get("project_key") or "") or None
        attention, is_act = _attention_for_followup(c)
        msg = msg_by_project.get(cpk or "")
        actor = _safe(msg.get("from_name")) if msg else ""
        company = _company_from_address(msg.get("from_address")) if msg else None
        when = (
            _humanize_when(_parse_utc(msg.get("received_at_utc")), brief_date)
            if msg
            else "recently"
        )
        pdisplay = project_display_name(cpk, store=store)
        topic = (
            _safe(c.get("title_redacted")) or (msg and _safe(msg.get("subject"))) or "an open item"
        )
        who = actor or (company or "Someone")
        co = f" ({company})" if company and company != actor else ""
        proj_clause = f" for {pdisplay}" if pdisplay else ""
        summary = f"{who}{co} emailed you {when} regarding {topic}{proj_clause}."
        why = _safe(c.get("reason_redacted")) or (
            "You may owe a response on this thread."
            if attention == NEEDS_ATTENTION
            else "A teammate or counterparty is awaiting movement."
        )
        action = _safe(c.get("recommended_next_action")) or (
            "Confirm whether the latest item is resolved or assign follow-up."
        )
        if msg:
            covered_projects.add(cpk or "")
        record_id = str(c.get("stable_key") or topic)
        refs = [_sref("task_candidates", c.get("stable_key"))]
        if msg:
            refs.append(_sref("email_raw_message_structured", msg.get("message_id_hash")))
        ev = DailyBriefChangeEvent(
            event_id=_event_id(brief_date, SOURCE_EMAIL, record_id),
            brief_date=brief_date,
            refresh_window_start=win.start_utc,
            refresh_window_end=win.end_utc,
            source_family=SOURCE_EMAIL,
            source_record_id=record_id,
            source_refs=refs,
            project_key=cpk,
            project_display_name=pdisplay,
            actor_display_name=actor or None,
            actor_company=company,
            event_type="email_followup",
            event_timestamp=str(msg.get("received_at_utc")) if msg else None,
            business_record_type="email",
            business_record_title=topic,
            summary_text=summary,
            why_it_matters=why,
            recommended_action=action,
            attention_class=attention,
            confidence=0.85,
            is_actionable=is_act,
        )
        events.append(ev)
        if is_act:
            actionable += 1

    # 2) Awareness layer: in-window messages on projects with no actionable follow-up.
    for pk, m in msg_by_project.items():
        if pk in covered_projects:
            continue
        actor = _safe(m.get("from_name")) or "A sender"
        company = _company_from_address(m.get("from_address"))
        subject = _safe(m.get("subject")) or "a new message"
        when = _humanize_when(_parse_utc(m.get("received_at_utc")), brief_date)
        pdisplay = project_display_name(pk, store=store)
        co = f" ({company})" if company and company != actor else ""
        proj_clause = f" for {pdisplay}" if pdisplay else ""
        summary = f"{actor}{co} emailed you {when} regarding {subject}{proj_clause}."
        record_id = str(m.get("message_id_hash") or subject)
        ev = DailyBriefChangeEvent(
            event_id=_event_id(brief_date, SOURCE_EMAIL, record_id),
            brief_date=brief_date,
            refresh_window_start=win.start_utc,
            refresh_window_end=win.end_utc,
            source_family=SOURCE_EMAIL,
            source_record_id=record_id,
            source_refs=[_sref("email_raw_message_structured", m.get("message_id_hash"))],
            project_key=pk or None,
            project_display_name=pdisplay,
            actor_display_name=actor,
            actor_company=company,
            event_type="email_received",
            event_timestamp=str(m.get("received_at_utc")),
            business_record_type="email",
            business_record_title=subject,
            summary_text=summary,
            why_it_matters="New correspondence on this project.",
            recommended_action="Review when convenient and decide whether a response is needed.",
            attention_class=AWARENESS,
            confidence=0.6,
            is_actionable=False,
        )
        events.append(ev)

    return events, substrate, actionable


# --- Calendar ---------------------------------------------------------------------------------


def _extract_calendar(
    store: Any, win: RefreshWindow, brief_date: str, lookahead_end: datetime
) -> list[DailyBriefChangeEvent]:
    anchor = _brief_anchor(brief_date)
    rows = _query(
        store,
        "SELECT event_index_id, source_ref_hash, subject, location_display, organizer_name, "
        "online_meeting_provider, start_datetime_utc, end_datetime_utc, project_key, attendee_count, "
        "source_updated_at_utc, created_utc FROM calendar_raw_event_structured "
        "WHERE COALESCE(is_current,1)=1",
    )
    events: list[DailyBriefChangeEvent] = []
    seen: set[str] = set()
    for r in rows:
        changed = _in_window(r.get("source_updated_at_utc"), win) or _in_window(
            r.get("created_utc"), win
        )
        start_dt = _parse_utc(r.get("start_datetime_utc"))
        upcoming = start_dt is not None and anchor < start_dt <= lookahead_end
        if not (changed or upcoming):
            continue
        eid = str(r.get("event_index_id") or "")
        if eid in seen:
            continue
        seen.add(eid)
        title = _safe(r.get("subject")) or "a meeting"
        organizer = _safe(r.get("organizer_name")) or "An organizer"
        pk = str(
            r.get("project_key")
            or resolve_project(r.get("subject"), r.get("location_display"))
            or ""
        )
        pdisplay = project_display_name(pk, store=store)
        when = _humanize_when(start_dt, brief_date)
        provider = _safe(r.get("online_meeting_provider"))
        location = _safe(r.get("location_display"))
        mode = "online" if provider else (location or "location TBD")
        proj_clause = f" for {pdisplay}" if pdisplay else ""
        loc_clause = f" ({mode})" if mode else ""
        verb = "moved/updated a meeting" if changed and not upcoming else "scheduled a meeting"
        summary = f'{organizer} {verb} {when}{proj_clause}: "{title}"{loc_clause}.'
        why = "Upcoming meeting in the look-ahead window — prepare beforehand."
        action = "Review related project emails, RFIs, and files before the meeting."
        attention = (
            TEAM_FOLLOW_UP
            if (upcoming and start_dt and start_dt - anchor <= timedelta(hours=48))
            else AWARENESS
        )
        record_id = eid or title
        events.append(
            DailyBriefChangeEvent(
                event_id=_event_id(brief_date, SOURCE_CALENDAR, record_id),
                brief_date=brief_date,
                refresh_window_start=win.start_utc,
                refresh_window_end=win.end_utc,
                source_family=SOURCE_CALENDAR,
                source_record_id=record_id,
                source_refs=[_sref("calendar_raw_event_structured", r.get("event_index_id"))],
                project_key=pk or None,
                project_display_name=pdisplay,
                actor_display_name=organizer,
                event_type="calendar_upcoming" if upcoming else "calendar_changed",
                event_timestamp=str(r.get("start_datetime_utc") or ""),
                business_record_type="meeting",
                business_record_title=title,
                meeting_start=str(r.get("start_datetime_utc") or "") or None,
                meeting_end=str(r.get("end_datetime_utc") or "") or None,
                meeting_location_or_mode=mode,
                summary_text=summary,
                why_it_matters=why,
                recommended_action=action,
                attention_class=attention,
                confidence=0.8,
                is_actionable=attention != AWARENESS,
            )
        )
    events.sort(key=lambda e: str(e.event_timestamp or ""))
    return events[: _PER_TYPE_CAP * 2]


# --- Procore (detail-or-drop) -----------------------------------------------------------------


@dataclass
class _Diagnostic:
    source_family: str
    label: str
    reason: str


def _procore_in_window(r: dict[str, Any], win: RefreshWindow) -> tuple[bool, str]:
    """(in_window, event_type) using ingestion-first-seen (new) then source updated_at (updated)."""
    if _in_window(r.get("payload_seen_first_utc"), win):
        return True, "new"
    if _in_window(r.get("updated_at"), win) or _in_window(r.get("updated_at_utc"), win):
        return True, "updated"
    return False, ""


def _extract_procore(
    store: Any, win: RefreshWindow, brief_date: str
) -> tuple[list[DailyBriefChangeEvent], list[_Diagnostic]]:
    events: list[DailyBriefChangeEvent] = []
    diagnostics: list[_Diagnostic] = []

    def _project(pk: Any) -> tuple[Optional[str], Optional[str]]:
        key = str(pk or "") or None
        return key, project_display_name(key, store=store)

    # --- RFIs (endpoint table carries number/subject/status/impact/ball-in-court) ---
    rfi_rows = [
        r
        for r in _query(
            store,
            "SELECT record_id, project_key, number, full_number, subject, status, translated_status, "
            "ball_in_court_name, rfi_manager_name, cost_impact_status, schedule_impact_status, "
            "due_date, updated_at, payload_seen_first_utc FROM procore_ep_rfis "
            "WHERE COALESCE(is_current,1)=1",
        )
        if _procore_in_window(r, win)[0]
    ]
    for r in rfi_rows[:_PER_TYPE_CAP]:
        _evt = _procore_in_window(r, win)[1]
        number = _safe(r.get("full_number")) or _safe(r.get("number"))
        title = _safe(r.get("subject"))
        status = _safe(r.get("translated_status")) or _safe(r.get("status"))
        if not number or not status:
            diagnostics.append(
                _Diagnostic(SOURCE_PROCORE, "RFI missing number/status", "record detail unresolved")
            )
            continue
        pk, pdisplay = _project(r.get("project_key"))
        proj_clause = f" for {pdisplay}" if pdisplay else ""
        respondent = _safe(r.get("ball_in_court_name")) or _safe(r.get("rfi_manager_name"))
        impacts = []
        if _safe(r.get("cost_impact_status")).lower() in ("yes", "tbd", "potential"):
            impacts.append("cost impact")
        if _safe(r.get("schedule_impact_status")).lower() in ("yes", "tbd", "potential"):
            impacts.append("schedule impact")
        impact_clause = f" Flagged for {' and '.join(impacts)}." if impacts else ""
        title_clause = f' ("{title}")' if title else ""
        ball_clause = f" Ball in court: {respondent}." if respondent else ""
        summary = (
            f"RFI #{number}{title_clause}{proj_clause} is {status}.{impact_clause}{ball_clause}"
        )
        due_dt = _parse_utc(r.get("due_date"))
        is_overdue = due_dt is not None and due_dt < _brief_anchor(brief_date)
        attention = NEEDS_ATTENTION if (impacts or is_overdue) else TEAM_FOLLOW_UP
        why = (
            "Open RFI with cost/schedule exposure."
            if impacts
            else "Open RFI awaiting response — keep it moving."
        )
        action = (
            "Confirm pricing/schedule exposure and the response owner."
            if impacts
            else ("Confirm the response owner and expected turnaround.")
        )
        events.append(
            DailyBriefChangeEvent(
                event_id=_event_id(brief_date, SOURCE_PROCORE, f"rfi:{r.get('record_id')}"),
                brief_date=brief_date,
                refresh_window_start=win.start_utc,
                refresh_window_end=win.end_utc,
                source_family=SOURCE_PROCORE,
                source_record_id=f"rfi:{r.get('record_id')}",
                source_refs=[_sref("procore_ep_rfis", r.get("record_id"))],
                project_key=pk,
                project_display_name=pdisplay,
                actor_display_name=respondent or None,
                event_type=f"rfi_{_evt}",
                event_timestamp=str(r.get("updated_at") or ""),
                business_record_type="rfi",
                business_record_number=number,
                business_record_title=title or None,
                business_record_status=status,
                due_date=_fmt_date(r.get("due_date")),
                summary_text=summary,
                why_it_matters=why,
                recommended_action=action,
                attention_class=attention,
                confidence=0.9,
                is_actionable=True,
            )
        )

    # --- RFI responses (a respondent answered) ---
    resp_rows = [
        r
        for r in _query(
            store,
            "SELECT record_id, project_key, record_number, title_redacted, status, current_state, "
            "owner_name, assignee_name, responsible_party_name, source_updated_at_utc, "
            "payload_seen_first_utc FROM procore_raw_rfi_responses WHERE COALESCE(is_current,1)=1",
        )
        if _in_window(r.get("payload_seen_first_utc"), win)
        or _in_window(r.get("source_updated_at_utc"), win)
    ]
    for r in resp_rows[:_PER_TYPE_CAP]:
        number = _safe(r.get("record_number"))
        status = _safe(r.get("status")) or _safe(r.get("current_state"))
        if not number:
            diagnostics.append(
                _Diagnostic(
                    SOURCE_PROCORE, "RFI response missing number", "record detail unresolved"
                )
            )
            continue
        pk, pdisplay = _project(r.get("project_key"))
        proj_clause = f" for {pdisplay}" if pdisplay else ""
        respondent = (
            _safe(r.get("responsible_party_name"))
            or _safe(r.get("assignee_name"))
            or _safe(r.get("owner_name"))
            or "A respondent"
        )
        status_clause = f" The RFI is now {status}." if status else ""
        summary = f"{respondent} responded to RFI #{number}{proj_clause}.{status_clause}"
        events.append(
            DailyBriefChangeEvent(
                event_id=_event_id(brief_date, SOURCE_PROCORE, f"rfiresp:{r.get('record_id')}"),
                brief_date=brief_date,
                refresh_window_start=win.start_utc,
                refresh_window_end=win.end_utc,
                source_family=SOURCE_PROCORE,
                source_record_id=f"rfiresp:{r.get('record_id')}",
                source_refs=[_sref("procore_raw_rfi_responses", r.get("record_id"))],
                project_key=pk,
                project_display_name=pdisplay,
                actor_display_name=respondent,
                event_type="rfi_response",
                event_timestamp=str(r.get("source_updated_at_utc") or ""),
                business_record_type="rfi_response",
                business_record_number=number,
                business_record_status=status or None,
                summary_text=summary,
                why_it_matters="An RFI response may close a field issue or trigger a cost/schedule update.",
                recommended_action="Confirm whether this closes the issue or requires a change.",
                attention_class=TEAM_FOLLOW_UP,
                confidence=0.88,
                is_actionable=True,
            )
        )

    # --- Subcontractor invoices (vendor/number/amount/period/status) ---
    inv_rows = [
        r
        for r in _query(
            store,
            "SELECT record_id, project_key, invoice_number, number, vendor_name, status, "
            "requisition_start, requisition_end, billing_date, summary_current_payment_due, "
            "total_claimed_amount, updated_at, payload_seen_first_utc FROM procore_ep_subcontractor_invoices "
            "WHERE COALESCE(is_current,1)=1",
        )
        if _procore_in_window(r, win)[0]
    ]
    for r in inv_rows[:_PER_TYPE_CAP]:
        number = _safe(r.get("invoice_number")) or _safe(r.get("number"))
        vendor = _safe(r.get("vendor_name"))
        status = _safe(r.get("status"))
        if not number or not vendor or not status:
            diagnostics.append(
                _Diagnostic(
                    SOURCE_PROCORE,
                    "Invoice missing number/vendor/status",
                    "record detail unresolved",
                )
            )
            continue
        pk, pdisplay = _project(r.get("project_key"))
        proj_clause = f" for {pdisplay}" if pdisplay else ""
        amount = _fmt_amount(r.get("summary_current_payment_due")) or _fmt_amount(
            r.get("total_claimed_amount")
        )
        amt_clause = f" for {amount}" if amount else ""
        pend = _fmt_date(r.get("requisition_end")) or _fmt_date(r.get("billing_date"))
        period_clause = f" for the pay period ending {pend}" if pend else ""
        not_reviewed = status.lower() in ("draft", "submitted", "under review", "pending", "open")
        review_clause = " It has not been reviewed yet." if not_reviewed else f" Status: {status}."
        summary = f"{vendor} submitted Invoice #{number}{proj_clause}{period_clause}{amt_clause}.{review_clause}"
        attention = NEEDS_ATTENTION if not_reviewed else TEAM_FOLLOW_UP
        events.append(
            DailyBriefChangeEvent(
                event_id=_event_id(brief_date, SOURCE_PROCORE, f"inv:{r.get('record_id')}"),
                brief_date=brief_date,
                refresh_window_start=win.start_utc,
                refresh_window_end=win.end_utc,
                source_family=SOURCE_PROCORE,
                source_record_id=f"inv:{r.get('record_id')}",
                source_refs=[_sref("procore_ep_subcontractor_invoices", r.get("record_id"))],
                project_key=pk,
                project_display_name=pdisplay,
                actor_company=vendor,
                event_type=f"invoice_{_procore_in_window(r, win)[1]}",
                event_timestamp=str(r.get("updated_at") or ""),
                business_record_type="invoice",
                business_record_number=number,
                business_record_status=status,
                amount=amount,
                due_date=pend,
                summary_text=summary,
                why_it_matters="Open subcontractor invoice affecting the payment cycle.",
                recommended_action="Confirm who owns the review before the next payment cycle.",
                attention_class=attention,
                confidence=0.9,
                is_actionable=True,
            )
        )

    # --- Commitment change orders (number/status/amount) ---
    co_rows = [
        r
        for r in _query(
            store,
            "SELECT record_id, project_key, number, title, status, grand_total, created_by_name, "
            "paid, due_date, updated_at, payload_seen_first_utc FROM procore_ep_commitment_change_orders "
            "WHERE COALESCE(is_current,1)=1",
        )
        if _procore_in_window(r, win)[0]
    ]
    for r in co_rows[:_PER_TYPE_CAP]:
        number = _safe(r.get("number"))
        status = _safe(r.get("status"))
        if not number or not status:
            diagnostics.append(
                _Diagnostic(
                    SOURCE_PROCORE, "Change order missing number/status", "record detail unresolved"
                )
            )
            continue
        pk, pdisplay = _project(r.get("project_key"))
        proj_clause = f" for {pdisplay}" if pdisplay else ""
        title = _safe(r.get("title"))
        actor = _safe(r.get("created_by_name"))
        amount = _fmt_amount(r.get("grand_total"))
        amt_clause = f" worth {amount}" if amount else ""
        title_clause = f' ("{title}")' if title else ""
        summary = f"Change Order #{number}{title_clause}{proj_clause} is {status}{amt_clause}."
        events.append(
            DailyBriefChangeEvent(
                event_id=_event_id(brief_date, SOURCE_PROCORE, f"co:{r.get('record_id')}"),
                brief_date=brief_date,
                refresh_window_start=win.start_utc,
                refresh_window_end=win.end_utc,
                source_family=SOURCE_PROCORE,
                source_record_id=f"co:{r.get('record_id')}",
                source_refs=[_sref("procore_ep_commitment_change_orders", r.get("record_id"))],
                project_key=pk,
                project_display_name=pdisplay,
                actor_display_name=actor or None,
                event_type=f"change_order_{_procore_in_window(r, win)[1]}",
                event_timestamp=str(r.get("updated_at") or ""),
                business_record_type="change_order",
                business_record_number=number,
                business_record_title=title or None,
                business_record_status=status,
                amount=amount,
                due_date=_fmt_date(r.get("due_date")),
                summary_text=summary,
                why_it_matters="Commitment change order affecting committed cost/exposure.",
                recommended_action="Confirm review/approval and payment status.",
                attention_class=TEAM_FOLLOW_UP,
                confidence=0.88,
                is_actionable=True,
            )
        )

    # --- Commitment contracts (number/status/amount) ---
    com_rows = [
        r
        for r in _query(
            store,
            "SELECT record_id, project_key, number, title, status, grand_total, contract_date, "
            "updated_at, payload_seen_first_utc FROM procore_ep_commitment_contracts "
            "WHERE COALESCE(is_current,1)=1",
        )
        if _procore_in_window(r, win)[0]
    ]
    for r in com_rows[:_PER_TYPE_CAP]:
        number = _safe(r.get("number"))
        status = _safe(r.get("status"))
        if not number or not status:
            diagnostics.append(
                _Diagnostic(
                    SOURCE_PROCORE, "Commitment missing number/status", "record detail unresolved"
                )
            )
            continue
        pk, pdisplay = _project(r.get("project_key"))
        proj_clause = f" for {pdisplay}" if pdisplay else ""
        title = _safe(r.get("title"))
        amount = _fmt_amount(r.get("grand_total"))
        amt_clause = f" worth {amount}" if amount else ""
        title_clause = f' ("{title}")' if title else ""
        summary = f"Commitment #{number}{title_clause}{proj_clause} is {status}{amt_clause}."
        events.append(
            DailyBriefChangeEvent(
                event_id=_event_id(brief_date, SOURCE_PROCORE, f"com:{r.get('record_id')}"),
                brief_date=brief_date,
                refresh_window_start=win.start_utc,
                refresh_window_end=win.end_utc,
                source_family=SOURCE_PROCORE,
                source_record_id=f"com:{r.get('record_id')}",
                source_refs=[_sref("procore_ep_commitment_contracts", r.get("record_id"))],
                project_key=pk,
                project_display_name=pdisplay,
                event_type=f"commitment_{_procore_in_window(r, win)[1]}",
                event_timestamp=str(r.get("updated_at") or ""),
                business_record_type="commitment",
                business_record_number=number,
                business_record_title=title or None,
                business_record_status=status,
                amount=amount,
                summary_text=summary,
                why_it_matters="Commitment contract change affecting committed cost.",
                recommended_action="Confirm execution and downstream billing impact.",
                attention_class=AWARENESS,
                confidence=0.82,
                is_actionable=False,
            )
        )

    return events, diagnostics


# --- SharePoint / OneDrive --------------------------------------------------------------------


def _extract_sharepoint(
    store: Any, win: RefreshWindow, brief_date: str
) -> list[DailyBriefChangeEvent]:
    rows = [
        r
        for r in _query(
            store,
            "SELECT drive_item_id, name, last_modified_datetime, last_modified_by_display_name, "
            "project_key, project_number_detected, document_type_detected, updated_utc, last_seen_utc "
            "FROM construction_drive_items WHERE COALESCE(is_file,1)=1 AND COALESCE(deleted,0)=0",
        )
        if _in_window(r.get("last_modified_datetime"), win)
        or _in_window(r.get("updated_utc"), win)
        or _in_window(r.get("last_seen_utc"), win)
    ]
    events: list[DailyBriefChangeEvent] = []
    for r in rows[:_PER_TYPE_CAP]:
        name = _safe(r.get("name"))
        if not name:
            continue
        editor = _safe(r.get("last_modified_by_display_name"))
        pk = str(r.get("project_key") or r.get("project_number_detected") or "")
        pdisplay = project_display_name(pk, store=store)
        when = _humanize_when(_parse_utc(r.get("last_modified_datetime")), brief_date)
        doc_type = _safe(r.get("document_type_detected"))
        who = editor or "Someone"
        proj_clause = f" for {pdisplay}" if pdisplay else ""
        type_clause = f" ({doc_type})" if doc_type else ""
        summary = f'{who} updated "{name}"{type_clause}{proj_clause} {when}.'
        events.append(
            DailyBriefChangeEvent(
                event_id=_event_id(brief_date, SOURCE_SHAREPOINT, str(r.get("drive_item_id"))),
                brief_date=brief_date,
                refresh_window_start=win.start_utc,
                refresh_window_end=win.end_utc,
                source_family=SOURCE_SHAREPOINT,
                source_record_id=str(r.get("drive_item_id")),
                source_refs=[_sref("construction_drive_items", r.get("drive_item_id"))],
                project_key=pk or None,
                project_display_name=pdisplay,
                actor_display_name=editor or None,
                event_type="file_updated",
                event_timestamp=str(r.get("last_modified_datetime") or ""),
                business_record_type="document",
                business_record_title=name,
                summary_text=summary,
                why_it_matters="A project document changed — it may affect related work.",
                recommended_action="Open the file in its project folder if relevant.",
                attention_class=AWARENESS,
                confidence=0.7,
                is_actionable=False,
            )
        )
    return events


# --- Orchestration ----------------------------------------------------------------------------


def build_new_today_digest(
    *, store: Any, brief_date: str, lookahead_days: int = DEFAULT_LOOKAHEAD_DAYS
) -> dict[str, Any]:
    """Build the deterministic New Today digest for ``brief_date`` (read-only; no persistence).

    Returns the refresh window, the in-memory change events (deterministic facts authoritative),
    demoted Procore diagnostics, the look-ahead end date for the subhead, and the usefulness gates
    (``email_degraded`` etc.). The caller may apply the advisory model overlay and/or persist.
    """
    win = compute_refresh_window(store, brief_date)
    lookahead_end_date = (
        date.fromisoformat(brief_date) + timedelta(days=lookahead_days)
    ).isoformat()
    lookahead_end_dt = datetime.combine(
        date.fromisoformat(lookahead_end_date), time(23, 59), tzinfo=_TZ
    ).astimezone(timezone.utc)

    email_events, email_substrate, email_actionable = _extract_email(store, win, brief_date)
    calendar_events = _extract_calendar(store, win, brief_date, lookahead_end_dt)
    procore_events, procore_diags = _extract_procore(store, win, brief_date)
    sharepoint_events = _extract_sharepoint(store, win, brief_date)

    events = email_events + calendar_events + procore_events + sharepoint_events

    email_degraded = bool(email_substrate and email_actionable == 0)
    by_family = dict.fromkeys((SOURCE_EMAIL, SOURCE_CALENDAR, SOURCE_PROCORE, SOURCE_SHAREPOINT), 0)
    for e in events:
        by_family[e.source_family] = by_family.get(e.source_family, 0) + 1

    diagnostics = [
        {"source_family": d.source_family, "label": d.label, "reason": d.reason}
        for d in procore_diags
    ]
    if email_degraded:
        diagnostics.append(
            {
                "source_family": SOURCE_EMAIL,
                "label": "Email substrate present but no actionable follow-up derived",
                "reason": "email_no_actionable_event",
            }
        )

    return {
        "brief_date": brief_date,
        "refresh_window": {
            "start_utc": win.start_utc,
            "end_utc": win.end_utc,
            "source": win.source,
            "rationale": win.rationale,
        },
        "lookahead_end_date": lookahead_end_date,
        "events": events,
        "diagnostics": diagnostics,
        "gates": {
            "email_substrate_present": email_substrate,
            "email_actionable_count": email_actionable,
            "email_degraded": email_degraded,
            "procore_demoted_count": len(procore_diags),
            "total_events": len(events),
            "by_family": by_family,
        },
    }


def persist_new_today_digest(
    store: Any, digest: dict[str, Any], *, max_persist: Optional[int]
) -> dict[str, Any]:
    """Persist a digest's change events + hash-only source refs (fail-closed on ``max_persist``).

    ``max_persist`` caps the TOTAL projected inserts (events + their source refs); when the projection
    would exceed it, nothing is written and ``capped`` is returned True. Mirrors the established
    "--max-persist = total projected, fail-closed" apply posture. Returns the persisted counts.
    """
    events = list(digest.get("events") or [])
    projected = sum(1 + e.source_ref_count for e in events)
    if max_persist is not None and projected > max_persist:
        return {
            "persisted": False,
            "capped": True,
            "projected_inserts": projected,
            "max_persist": max_persist,
            "persisted_events": 0,
            "persisted_refs": 0,
        }
    persisted_events = 0
    persisted_refs = 0
    for e in events:
        store.insert_daily_brief_change_event(
            change_event_id=e.event_id,
            brief_date=e.brief_date,
            source_family=e.source_family,
            attention_class=e.attention_class,
            refresh_window_start_utc=e.refresh_window_start,
            refresh_window_end_utc=e.refresh_window_end,
            source_record_id=e.source_record_id,
            source_ref_count=e.source_ref_count,
            project_key=e.project_key,
            project_display_name=e.project_display_name,
            actor_display_name=e.actor_display_name,
            actor_company=e.actor_company,
            event_type=e.event_type,
            event_timestamp_utc=e.event_timestamp,
            business_record_type=e.business_record_type,
            business_record_number=e.business_record_number,
            business_record_title_redacted=e.business_record_title,
            business_record_status=e.business_record_status,
            amount=e.amount,
            due_date=e.due_date,
            meeting_start_utc=e.meeting_start,
            meeting_end_utc=e.meeting_end,
            meeting_location_or_mode=e.meeting_location_or_mode,
            summary_text=e.summary_text,
            why_it_matters=e.why_it_matters,
            recommended_action=e.recommended_action,
            confidence=e.confidence,
            enrichment_status=e.enrichment_status,
            model_profile_id=e.model_profile_id,
            model_name=e.model_name,
            model_run_receipt_id=e.model_run_receipt_id,
        )
        persisted_events += 1
        for ref in e.source_refs:
            store.insert_daily_brief_change_event_ref(
                change_event_id=e.event_id,
                source_table=ref["source_table"],
                source_ref_hash=ref["source_ref_hash"],
            )
            persisted_refs += 1
    return {
        "persisted": True,
        "capped": False,
        "projected_inserts": projected,
        "max_persist": max_persist,
        "persisted_events": persisted_events,
        "persisted_refs": persisted_refs,
    }
