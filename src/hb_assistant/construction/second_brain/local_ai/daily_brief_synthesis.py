"""Phase 10 — daily-brief candidate synthesis (advisory, no writeback).

Convergence layer for the local-agent family: unifies the email side (accepted tasks +
follow-up watch items) and the Procore side (digest candidates already written by the
Procore digest agent) into reviewable ``daily_brief_action_candidates`` rows grouped by
section, and returns a single advisory brief view.

Deterministic, source-linked (each candidate carries the originating accepted_task_id /
watch_item_id), dry-run by default. ``--apply`` is explicit and capped. No raw content,
no email/calendar/Procore/external writeback — only redacted titles + reason codes move.
"""

from __future__ import annotations

from typing import Any, Optional

_WAITING_STATES = {"waiting_on_me", "waiting_on_others"}
# Lower priority = surfaced first.
_PRIORITY = {"waiting": 20, "follow_up": 30, "actions": 60, "procore": 50}


def build_daily_brief_candidates(
    *,
    store: Any,
    now_utc: str,
    limit: int = 200,
    dry_run: bool = True,
    max_persist: Optional[int] = None,
) -> dict[str, Any]:
    """Synthesize unified daily-brief candidates from accepted tasks + watch items.

    Dry-run is the default (zero writes). ``--apply`` (dry_run=False) requires ``max_persist``
    and caps ACTUAL inserts into ``daily_brief_action_candidates``; once the cap is hit, remaining
    new candidates are counted (``would_persist``) but not written. Idempotent per
    (brief_date, section, source id). The returned ``brief`` also includes any ``procore`` section
    rows already written by the Procore digest agent for this date.
    """
    if not dry_run and max_persist is None:
        raise ValueError("apply requires max_persist (cap on actual persisted candidates)")

    brief_date = now_utc[:10]
    accepted = store.list_accepted_tasks(limit=limit)
    watch = store.list_follow_up_watch_items(limit=limit)

    existing = store.list_daily_brief_action_candidates(brief_date=brief_date, limit=100000)
    existing_ids = {str(r.get("daily_brief_action_candidate_id")) for r in existing}

    # Build the synthesis units (accepted tasks → actions/waiting; stale watch → follow_up).
    units: list[dict[str, Any]] = []
    for t in accepted:
        waiting = str(t.get("waiting_state") or "")
        section = "waiting" if waiting in _WAITING_STATES else "actions"
        units.append(
            {
                "section": section,
                "group_key": f"accepted-task|{t.get('accepted_task_id')}",
                "title_redacted": str(t.get("title_redacted") or "Untitled task"),
                "project_key": t.get("project_key"),
                "priority": _PRIORITY.get(section, 60),
                "reason_redacted": waiting or "accepted_task",
                "source_id": t.get("accepted_task_id"),
            }
        )
    for w in watch:
        if str(w.get("watch_status")) != "stale":
            continue  # escalation only — non-stale watch items stay in the email family
        reason = str(w.get("reason_redacted") or "stale")
        units.append(
            {
                "section": "follow_up",
                "group_key": f"watch|{w.get('watch_item_id')}",
                "title_redacted": f"Stale follow-up: {reason}",
                "project_key": w.get("project_key"),
                "priority": _PRIORITY["follow_up"],
                "reason_redacted": reason,
                "source_id": w.get("watch_item_id"),
            }
        )

    # Deterministic apply order: priority asc, then section, then group_key.
    units.sort(key=lambda u: (u["priority"], u["section"], u["group_key"]))

    by_section: dict[str, int] = {}
    summary = {
        "scanned_accepted": len(accepted),
        "scanned_watch": len(watch),
        "would_persist": 0,
        "persisted": 0,
        "skipped_existing": 0,
    }
    remaining: Optional[int] = max_persist if (not dry_run and max_persist is not None) else None

    for u in units:
        by_section[u["section"]] = by_section.get(u["section"], 0) + 1
        row_id = store.daily_brief_action_candidate_id_for(brief_date, u["section"], u["group_key"])
        if row_id in existing_ids:
            summary["skipped_existing"] += 1
            continue
        summary["would_persist"] += 1
        if dry_run or (remaining is not None and remaining <= 0):
            continue
        inserted = store.insert_daily_brief_action_candidate(
            brief_date=brief_date,
            section=u["section"],
            title_redacted=u["title_redacted"],
            confidence=1.0,
            project_key=u["project_key"],
            priority=u["priority"],
            reason_redacted=u["reason_redacted"],
            recommended_next_action="review",
            group_key=u["group_key"],
        )
        if inserted:
            summary["persisted"] += 1
            existing_ids.add(row_id)
            if remaining is not None:
                remaining -= 1
        else:
            summary["skipped_existing"] += 1

    # Unified advisory brief: union of synthesized units + already-persisted rows (incl. procore).
    brief = _build_brief_view(units=units, existing=existing)

    return {
        "command": "second-brain daily-brief synthesize-candidates",
        "ok": True,
        "applied": not dry_run,
        "now_utc": now_utc,
        "brief_date": brief_date,
        "summary": summary,
        "by_section": dict(sorted(by_section.items())),
        "brief": brief,
        "guardrails": {
            "dry_run_default": True,
            "apply_requires_max_persist": True,
            "deterministic_no_clock": True,
            "source_linked_only": True,
            "no_raw_persistence": True,
            "no_writeback": True,
            "advisory_only": True,
        },
    }


def _build_brief_view(
    *, units: list[dict[str, Any]], existing: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Unified, source-linked brief by section (synthesized units + already-persisted rows)."""
    sections: dict[str, list[dict[str, Any]]] = {}
    for u in units:
        sections.setdefault(u["section"], []).append(
            {
                "title_redacted": u["title_redacted"],
                "project_key": u["project_key"],
                "priority": u["priority"],
                "reason_redacted": u["reason_redacted"],
                "source": u["group_key"],
            }
        )
    # Include already-persisted sections the synthesis didn't generate (e.g. procore digest rows).
    synthesized_sections = {u["section"] for u in units}
    for r in existing:
        sec = str(r.get("section"))
        if sec in synthesized_sections:
            continue  # already represented by the fresh units
        sections.setdefault(sec, []).append(
            {
                "title_redacted": r.get("title_redacted"),
                "project_key": r.get("project_key"),
                "priority": r.get("priority"),
                "reason_redacted": r.get("reason_redacted"),
                "source": "daily_brief_action_candidate",
            }
        )
    for sec in sections:
        sections[sec].sort(key=lambda x: (x.get("priority") or 100, str(x.get("title_redacted"))))
    return sections
