"""Phase 10 correction — bounded, source-linked context packet for daily-brief synthesis.

Assembles the local model's ONLY view of the day: a normalized, date-window-aware, capped,
source-linked packet built from the same already-redacted local read models the deterministic brief
uses (action candidates, accepted tasks/commitments, follow-up watch items, relationship candidates,
Procore action signals, and classified calendar events). Every item carries a short stable source/
candidate ID for traceability.

Boundaries (the packet is the model-context surface, so it is deliberately conservative):
- redacted fields only — titles/reasons are redacted at write time; calendar bodies are the
  join-URL/dial-in/passcode-stripped prep excerpt (bounded);
- NO unbounded DB dumps, NO full bodies, NO join/signed URLs, NO tokens, NO attendee emails/names,
  NO full attendee arrays (domains/counts only);
- low-value calendar events are demoted/excluded BEFORE they reach the packet (calendar_classify).

Read-only: no writeback, no clock read (``now_utc`` is supplied by the caller).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .calendar_classify import classify_calendar_event
from .calendar_prep import build_calendar_prep_candidates
from .daily_brief_window import DailyBriefWindow
from .project_aliases import resolve_project, summarize_unresolved_tokens

# Conservative caps (the packet must stay bounded regardless of DB size).
_MAX_CANDIDATES_PER_SECTION = 12
_MAX_MEETINGS = 15
_MAX_FYI_MEETINGS = 8
_MAX_RELATIONSHIPS = 8
_MAX_TASKS = 15
_MAX_PROCORE_GROUPS = 20
_MAX_EXCERPT_CHARS = 300
_SHORT_ID = 18


def _short(value: Any) -> str:
    s = str(value or "")
    return s[:_SHORT_ID]


def _to_local_time(iso_utc: Any, tz: str) -> str:
    """Format a stored UTC stamp into a local weekday + time label (e.g. ``Mon 9:00 AM``)."""
    try:
        dt = datetime.fromisoformat(str(iso_utc)[:19]).replace(tzinfo=timezone.utc)
        local = dt.astimezone(ZoneInfo(tz))
        hour12 = local.strftime("%I").lstrip("0") or "12"
        return f"{local.strftime('%a')} {hour12}:{local.strftime('%M %p')}"
    except Exception:
        return ""


def _is_overdue(due_at_utc: Any, now_utc: str) -> bool:
    try:
        return bool(due_at_utc) and str(due_at_utc)[:19] < now_utc[:19]
    except Exception:
        return False


def _days_until(start_iso: Any, now_utc: str) -> float:
    try:
        s = datetime.fromisoformat(str(start_iso)[:19])
        n = datetime.fromisoformat(str(now_utc)[:19].replace("Z", ""))
        return (s - n).total_seconds() / 86400.0
    except Exception:
        return 0.0


def build_daily_brief_context_packet(
    *,
    store: Any,
    brief_date: str,
    window: DailyBriefWindow,
    now_utc: str,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Build the bounded, source-linked context packet for one brief date (deterministic)."""
    tz = window.timezone

    # --- Date window facts (so the model writes a correct carryover / next-week section) ----------
    date_window = {
        "run_date": window.run_date,
        "run_weekday": window.run_weekday,
        "label": window.label,
        "explanation": window.explanation,
        "lookback_start": window.lookback_start,
        "lookback_end": window.lookback_end,
        "lookahead_start": window.lookahead_start,
        "lookahead_end": window.lookahead_end,
        "previous_business_day": window.previous_business_day,
        "next_business_day": window.next_business_day,
        "carryover_section_label": window.carryover_section_label,
        "catch_up": window.catch_up,
    }

    # --- Open commitments / tasks / follow-ups (who owes what, what is stale) ---------------------
    def _open(rows: list[dict[str, Any]], id_key: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in rows:
            if str(r.get("status") or "").lower() in {"completed", "done", "closed"}:
                continue
            out.append(
                {
                    "id": _short(r.get(id_key)),
                    "title": r.get("title_redacted"),
                    "project": r.get("project_key") or "Needs Project Review",
                    "waiting_state": r.get("waiting_state"),
                    "due_at_utc": r.get("due_at_utc"),
                    "overdue": _is_overdue(r.get("due_at_utc"), now_utc),
                    "safety_category": r.get("safety_category"),
                }
            )
            if len(out) >= _MAX_TASKS:
                break
        return out

    accepted_tasks = _open(store.list_accepted_tasks(limit=1000), "accepted_task_id")
    accepted_commitments = _open(
        store.list_accepted_commitments(limit=1000), "accepted_commitment_id"
    )

    watch_items: list[dict[str, Any]] = []
    for w in store.list_follow_up_watch_items(limit=1000):
        watch_items.append(
            {
                "id": _short(w.get("watch_item_id")),
                "project": w.get("project_key") or "Needs Project Review",
                "watch_status": w.get("watch_status"),
                "waiting_state": w.get("waiting_state"),
                "reason": w.get("reason_redacted"),
                "stale": str(w.get("watch_status") or "") == "stale",
            }
        )
        if len(watch_items) >= _MAX_TASKS:
            break

    # --- Persisted action candidates for this date, grouped by section (capped) -------------------
    candidates_by_section: dict[str, list[dict[str, Any]]] = {}
    for r in store.list_daily_brief_action_candidates(brief_date=brief_date, limit=100000):
        sec = str(r.get("section") or "__unassigned__")
        bucket = candidates_by_section.setdefault(sec, [])
        if len(bucket) >= _MAX_CANDIDATES_PER_SECTION:
            continue
        bucket.append(
            {
                "id": _short(r.get("daily_brief_action_candidate_id")),
                "title": r.get("title_redacted"),
                "project": r.get("project_key") or "Needs Project Review",
                "priority": r.get("priority"),
                "reason": r.get("reason_redacted"),
                "next_action": r.get("recommended_next_action"),
            }
        )

    # --- Relationship candidates → reason codes only (transformed, never raw technical rows) ------
    relationships: list[dict[str, Any]] = []
    try:
        rel_rows = store.list_phase10_relationship_candidates(limit=_MAX_RELATIONSHIPS)
    except Exception:
        rel_rows = []
    for r in rel_rows:
        relationships.append(
            {
                "id": _short(r.get("relationship_candidate_id")),
                "type": r.get("relationship_type"),
                "confidence_class": r.get("confidence_class"),
                "project": r.get("project_key") or "Needs Project Review",
                "reason_codes": [c for c in str(r.get("reason_redacted") or "").split(",") if c],
                "review_required": str(r.get("confidence_class") or "") == "moderate",
            }
        )

    # --- Procore action signals → grouped by (project, type) with overdue/open counts -------------
    procore_groups: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        signals = store.list_procore_action_signals(signal_status="open", limit=100000)
    except Exception:
        signals = []
    for s in signals:
        proj = str(s.get("project_key") or "Needs Project Review")
        stype = str(s.get("signal_type") or "signal")
        g = procore_groups.setdefault(
            (proj, stype), {"project": proj, "signal_type": stype, "open": 0, "overdue": 0}
        )
        g["open"] = int(g["open"]) + 1
        if _is_overdue(s.get("due_at_utc"), now_utc):
            g["overdue"] = int(g["overdue"]) + 1
    procore_signals = sorted(
        procore_groups.values(),
        key=lambda g: (-int(g["overdue"]), -int(g["open"]), str(g["project"])),
    )[:_MAX_PROCORE_GROUPS]

    # --- Calendar events: classified pre-model (visible vs fyi; excluded only counted) ------------
    cal = build_calendar_prep_candidates(
        store=store,
        now_utc=now_utc,
        db_path=db_path,
        window_start_iso=window.calendar_prep_start,
        window_end_iso=window.calendar_prep_end,
        dry_run=True,
        limit=200,
    )
    event_views = cal.get("events") or []

    # Raw-subject enrichment for the MODEL CONTEXT only (an approved raw surface): in real data the
    # persisted ``subject_redacted`` is a hash placeholder, so deterministic project inference +
    # classification run on the redacted token find nothing. Here we read the real subject/location
    # (bounded) to give the model meaningful meeting titles and to re-infer project + value tier. The
    # raw subject is NEVER persisted (calendar_prep persists only the redacted title) and never enters
    # status/logs — it lives only in the model packet + the private Obsidian/browser brief.
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

    meetings: list[dict[str, Any]] = []
    fyi_meetings: list[dict[str, Any]] = []
    excluded_count = 0
    for ev in event_views:
        eid = str(ev.get("event_index_id") or "")
        raw = raw_subjects.get(eid) or {}
        raw_subject = raw.get("subject") or ""
        title = raw_subject or str(ev.get("title_redacted") or "")
        # Prefer the index/redacted-resolved project; else infer from the real subject/location.
        proj = ev.get("project_key")
        project_inferred = bool(ev.get("project_inferred"))
        if (not proj or proj == "__unassigned__") and raw_subject:
            inferred = resolve_project(raw_subject, raw.get("location") or "")
            if inferred:
                proj, project_inferred = inferred, True
        proj_label = proj if proj and proj != "__unassigned__" else "Needs Project Review"

        # Re-classify on the real subject (the redacted hash hides prep keywords like RFI/OAC/PTO).
        if raw_subject:
            cls = classify_calendar_event(
                title=raw_subject,
                location=raw.get("location") or "",
                attendee_count=int(ev.get("attendee_count") or 0),
                is_online=bool(ev.get("is_online_meeting")),
                has_project=proj_label != "Needs Project Review",
                days_until=_days_until(ev.get("start"), now_utc),
            )
            klass = str(cls.klass)
            class_reason = cls.reason_code
        else:
            klass = str(ev.get("calendar_class") or "fyi")
            class_reason = ev.get("calendar_class_reason")

        if klass == "excluded":
            excluded_count += 1
            continue
        item = {
            "id": _short(ev.get("source_ref")).replace("cal:", ""),
            "local_time": _to_local_time(ev.get("start"), tz),
            "title": title,
            "project": proj_label,
            "project_inferred": project_inferred,
            "klass": klass,
            "class_reason": class_reason,
            "attendee_count": ev.get("attendee_count"),
            "prep_excerpt": str(ev.get("prep_excerpt") or "")[:_MAX_EXCERPT_CHARS],
        }
        if klass in {"requires_prep", "key_meeting"} and len(meetings) < _MAX_MEETINGS:
            meetings.append(item)
        elif len(fyi_meetings) < _MAX_FYI_MEETINGS:
            fyi_meetings.append(item)

    # Assigned/unassigned + unresolved-token diagnostics from the raw-enriched items (the redacted
    # calendar_prep counts are all-unassigned in real data because subjects are hash placeholders).
    visible = meetings + fyi_meetings
    assigned = sum(1 for m in visible if m["project"] != "Needs Project Review")
    unresolved_titles: list[str | None] = [
        m["title"] for m in visible if m["project"] == "Needs Project Review"
    ]
    calendar = {
        "meetings": meetings,
        "fyi_meetings": fyi_meetings,
        "excluded_count": excluded_count,
        "assigned": assigned,
        "unassigned": len(visible) - assigned,
        "inferred": sum(1 for m in visible if m.get("project_inferred")),
        "unresolved_project_tokens": summarize_unresolved_tokens(unresolved_titles, top=10),
    }

    # --- Data-gap signals (so the brief explains what is missing / needs review) ------------------
    data_gaps: list[str] = []
    if calendar["unassigned"]:
        data_gaps.append(
            f"{calendar['unassigned']} calendar item(s) could not be assigned to a project"
        )
    if not procore_signals:
        data_gaps.append("no Procore action signals available for this run")
    if not (accepted_tasks or accepted_commitments or watch_items):
        data_gaps.append("no accepted tasks/commitments or follow-up watch items available")

    return {
        "brief_date": brief_date,
        "date_window": date_window,
        "open_commitments": {
            "accepted_tasks": accepted_tasks,
            "accepted_commitments": accepted_commitments,
            "follow_up_watch_items": watch_items,
        },
        "candidates_by_section": candidates_by_section,
        "relationships": relationships,
        "procore_signals": procore_signals,
        "calendar": calendar,
        "data_gaps": data_gaps,
        "caps": {
            "max_candidates_per_section": _MAX_CANDIDATES_PER_SECTION,
            "max_meetings": _MAX_MEETINGS,
            "max_relationships": _MAX_RELATIONSHIPS,
            "max_procore_groups": _MAX_PROCORE_GROUPS,
            "max_tasks": _MAX_TASKS,
        },
    }
