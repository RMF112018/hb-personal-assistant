"""Phase 06B operational Obsidian outputs — project health, meeting prep, daily digest.

Three deterministic, marker-bounded Obsidian notes rendered from the Phase 06B **local SQLite read
models** (never live Procore): ``build_project_health`` / ``build_operational_digest`` /
``build_overdue_queue`` / ``build_risks`` + open action signals. Read-only; dry-run builds the
rendered note, ``apply_*`` writes a single marker-bounded note into the configured local vault
(``01_Projects/``). Output carries freshness + review-required warnings and only already-redacted
columns (``title_redacted`` / counts / status / ``due_at_utc`` / ``source_url_redacted`` /
``record_key``) plus a local query-command reference — never raw payload bodies, signed URLs, or
tokens, and **no determinations** (intelligence / review aids only). ``review_required`` records are
surfaced as warning refs, never inlined with sensitive content.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..store.connection import get_connection
from .obsidian import PROCORE_GUARDRAILS, _write_procore_artifact
from .obsidian_register import _section, _table

_MEETING_ENDPOINTS = ("meetings", "meeting-detail")
_MEETING_SIGNAL_TYPES = {"meeting_topic_open_high_priority"}

_NOTES = {
    "project_health": ("OPERATIONAL-PROJECT-HEALTH", "procore-project-health.md",
                       "procore_project_health"),
    "meeting_prep": ("OPERATIONAL-MEETING-PREP", "procore-meeting-prep.md", "procore_meeting_prep"),
    "daily_digest": ("OPERATIONAL-DAILY-DIGEST", "procore-daily-digest.md", "procore_daily_digest"),
}


def _warnings_md(stale: List[Dict[str, Any]], review_count: int) -> str:
    """A small freshness + review-required warning banner (counts / refs only)."""
    lines: List[str] = []
    if stale:
        eps = ", ".join(str(s.get("endpoint_id")) for s in stale[:10])
        lines.append(f"> ⚠️ **Freshness:** {len(stale)} stale/never-synced endpoint(s): {eps}.")
    if review_count:
        lines.append(
            f"> ⚠️ **Review required:** {review_count} record(s) flagged — see "
            "`procore live project-health` / the review queue (not inlined here)."
        )
    if not lines:
        lines.append("> ✅ No freshness or review-required warnings.")
    return "\n".join(lines)


def _render_note(
    *, note_type: str, project_key: str, title: str, now_utc: str,
    since_utc: Optional[str], order: List[str], sections: Dict[str, str], warnings_md: str,
) -> str:
    frontmatter = "\n".join([
        "---",
        f"type: {note_type}",
        f"project_key: {project_key}",
        "source: procore_phase06b_read_models_sqlite",
        "review_sensitive: false",
        f"generated_utc: {now_utc}",
        "---",
    ])
    window = f"_Window since: {since_utc}._ " if since_utc else ""
    body = "\n\n".join(sections[k] for k in order)
    guardrails = "\n".join(f"- {k}: {v}" for k, v in PROCORE_GUARDRAILS.items())
    return (
        f"{frontmatter}\n\n# {title} — {project_key}\n\n"
        f"{window}_Local SQLite read-model projection — no Procore call._\n\n"
        f"{warnings_md}\n\n{body}\n\n## Guardrails\n\n{guardrails}\n"
    )


def _result(
    *, command: str, project_key: str, now_utc: str, since_utc: Optional[str],
    sections: Dict[str, str], rendered: str, counts: Dict[str, int], warnings: Dict[str, Any],
) -> Dict[str, Any]:
    out = {
        "command": command,
        "project_key": project_key,
        "generated_utc": now_utc,
        "sections": sections,
        "section_keys": list(sections),
        "rendered": rendered,
        "counts": counts,
        "warnings": warnings,
        "review_sensitive": False,
        "guardrails": dict(PROCORE_GUARDRAILS),
    }
    if since_utc is not None:
        out["since_utc"] = since_utc
    return out


# --------------------------------------------------------------------------- #
# project-health
# --------------------------------------------------------------------------- #


def build_project_health_note(
    project_key: str, *, now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    from ..store.procore_project_health import build_project_health

    health = build_project_health(project_key, now_utc=now_utc, db_path=db_path)
    sc = health["score_components"]
    counts = health["counts"]
    q = f"hb-assistant procore live project-health --project {project_key} --json"

    component_rows = [
        ["Open signals", counts["open_signals"]],
        ["High-importance signals", counts["high_importance_signals"]],
        ["Review-required records", counts["review_required_records"]],
        ["Cost exposure signals", sc["cost_exposure"]["open_signals"]],
        ["Schedule exposure signals", sc["schedule_exposure"]["open_signals"]],
        ["Safety/quality/compliance signals", sc["safety_quality_compliance"]["open_signals"]],
        ["Overdue signals", sc["overdue"]["open_signals"]],
        ["Stale endpoints", sc["freshness"]["stale_endpoints"]],
        ["Records missing responsibility edge",
         sc["relationship_quality"]["records_missing_responsibility_edge"]],
    ]
    risk_rows = [
        [r.get("importance"), r.get("signal_type"), r.get("endpoint_id"), r.get("due_at_utc") or "",
         ", ".join(r.get("dimensions") or []), r.get("title_redacted") or ""]
        for r in health["top_risks"]
    ]
    stale_rows = [
        [s.get("endpoint_id"), s.get("state"), s.get("age_days") if s.get("age_days") is not None
         else "", s.get("last_success_at_utc") or ""]
        for s in health["stale_endpoints"]
    ]
    review_rows = [
        [r.get("endpoint_id"), r.get("procore_record_id"), r.get("sensitive_reason") or "",
         r.get("source_url_redacted") or ""]
        for r in health["review_required_items"]
    ]

    sections = {
        "status": _section(
            "Health Status", q,
            f"**{health['health_status']}** — triggers: "
            f"{', '.join(health['status_reason'])}\n",
        ),
        "components": _section(
            "Score Components", q,
            _table(["Component", "Count"], component_rows, empty="No components."),
        ),
        "top_risks": _section(
            "Top Risks", q,
            _table(["Importance", "Signal", "Endpoint", "Due", "Dimensions", "Title"], risk_rows,
                   empty="No top risks."),
        ),
        "stale": _section(
            "Stale Endpoints", q,
            _table(["Endpoint", "State", "Age (days)", "Last success"], stale_rows,
                   empty="No stale endpoints."),
        ),
        "review_required": _section(
            "Review-Required Items", q,
            _table(["Endpoint", "Record ID", "Reason", "Source"], review_rows,
                   empty="No review-required items."),
        ),
    }
    counts_out = {
        "top_risks": len(risk_rows), "stale_endpoints": len(stale_rows),
        "review_required_items": len(review_rows), "open_signals": counts["open_signals"],
    }
    warnings = {"stale_endpoints": sc["freshness"]["stale_endpoints"],
                "review_required_records": counts["review_required_records"]}
    warnings_md = _warnings_md(health["stale_endpoints"], counts["review_required_records"])
    rendered = _render_note(
        note_type=_NOTES["project_health"][2], project_key=project_key,
        title="Procore Project Health", now_utc=now_utc, since_utc=None,
        order=["status", "components", "top_risks", "stale", "review_required"],
        sections=sections, warnings_md=warnings_md,
    )
    return _result(
        command="hb-assistant procore obsidian project-health", project_key=project_key,
        now_utc=now_utc, since_utc=None, sections=sections, rendered=rendered, counts=counts_out,
        warnings=warnings,
    )


# --------------------------------------------------------------------------- #
# meeting-prep
# --------------------------------------------------------------------------- #


def _health_warnings(project_key: str, now_utc: str, db_path: Optional[Path]) -> Dict[str, Any]:
    from ..store.procore_project_health import build_project_health

    health = build_project_health(project_key, now_utc=now_utc, db_path=db_path)
    return {
        "stale_list": health["stale_endpoints"],
        "stale_endpoints": health["score_components"]["freshness"]["stale_endpoints"],
        "review_required_records": health["counts"]["review_required_records"],
    }


def build_meeting_prep(
    project_key: str, *, since_utc: str, now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    from ..store.procore_enrichment import get_procore_action_signals
    from ..store.procore_operational import build_risks

    # --- open meeting-topic action items ---
    signals = get_procore_action_signals(
        project_key=project_key, signal_status="open", db_path=db_path
    )
    meeting_actions = [
        s for s in signals
        if s.get("signal_type") in _MEETING_SIGNAL_TYPES
        or (s.get("endpoint_id") in _MEETING_ENDPOINTS)
    ]
    action_rows = [
        [s.get("importance"), s.get("signal_type"), s.get("endpoint_id"),
         s.get("due_at_utc") or "", s.get("record_key"), s.get("title_redacted") or ""]
        for s in meeting_actions
    ]

    # --- recent/upcoming meeting records (review_required diverted to warnings) ---
    conn = get_connection(db_path)
    placeholders = ", ".join("?" for _ in _MEETING_ENDPOINTS)
    rows = conn.execute(
        f"""
        SELECT endpoint_id, procore_record_id, procore_record_number, title_redacted, status,
               updated_at_utc, source_url_redacted, review_required
          FROM procore_live_records
         WHERE project_key = ? AND endpoint_id IN ({placeholders})
           AND (updated_at_utc IS NULL OR updated_at_utc >= ?)
         ORDER BY updated_at_utc DESC, procore_record_id
        """,
        (project_key, *_MEETING_ENDPOINTS, since_utc),
    ).fetchall()
    meeting_rows: List[List[Any]] = []
    flagged_meetings = 0
    for r in rows:
        if bool(r["review_required"]):
            flagged_meetings += 1
            continue
        meeting_rows.append([
            r["procore_record_number"] or r["procore_record_id"],
            r["title_redacted"] or "", r["status"] or "", r["updated_at_utc"] or "",
            f"[{r['procore_record_id']}]({r['source_url_redacted'] or '#'})",
        ])

    # --- carryover risks ---
    risks = build_risks(project_key, now_utc=now_utc, db_path=db_path)["risks"]
    risk_rows = [
        [r.get("importance"), r.get("signal_type"), r.get("endpoint_id"),
         ", ".join(r.get("dimensions") or []), r.get("title_redacted") or ""]
        for r in risks
    ]

    sections = {
        "actions": _section(
            "Open Meeting Actions",
            f"hb-assistant procore live actions --project {project_key} --status open --json",
            _table(["Importance", "Signal", "Endpoint", "Due", "Record Key", "Title"], action_rows,
                   empty="No open meeting actions."),
        ),
        "meetings": _section(
            "Recent / Upcoming Meetings",
            f'hb-assistant procore live records count --project {project_key} --json',
            _table(["Number", "Title", "Status", "Updated", "Source"], meeting_rows,
                   empty="No meetings in the window (review-flagged meetings excluded)."),
        ),
        "risks": _section(
            "Carryover Risks",
            f"hb-assistant procore live risks --project {project_key} --json",
            _table(["Importance", "Signal", "Endpoint", "Dimensions", "Title"], risk_rows,
                   empty="No carryover risks."),
        ),
    }
    hw = _health_warnings(project_key, now_utc, db_path)
    review_total = hw["review_required_records"] + flagged_meetings
    counts_out = {"meeting_actions": len(action_rows), "meetings": len(meeting_rows),
                  "carryover_risks": len(risk_rows), "review_flagged_meetings": flagged_meetings}
    warnings = {"stale_endpoints": hw["stale_endpoints"], "review_required_records": review_total}
    warnings_md = _warnings_md(hw["stale_list"], review_total)
    rendered = _render_note(
        note_type=_NOTES["meeting_prep"][2], project_key=project_key,
        title="Procore Meeting Prep", now_utc=now_utc, since_utc=since_utc,
        order=["actions", "meetings", "risks"], sections=sections, warnings_md=warnings_md,
    )
    return _result(
        command="hb-assistant procore obsidian meeting-prep", project_key=project_key,
        now_utc=now_utc, since_utc=since_utc, sections=sections, rendered=rendered,
        counts=counts_out, warnings=warnings,
    )


# --------------------------------------------------------------------------- #
# daily-digest
# --------------------------------------------------------------------------- #


def build_daily_digest(
    project_key: str, *, since_utc: str, now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    from ..store.procore_action_queue import build_overdue_queue
    from ..store.procore_history import get_procore_changes
    from ..store.procore_operational import build_operational_digest, build_risks

    digest = build_operational_digest(project_key, now_utc=now_utc, db_path=db_path)
    headline = digest["headline"]
    overdue = build_overdue_queue(project_key, now_utc=now_utc, db_path=db_path)
    overdue_items = [it for it in overdue["queue"] if it.get("status") == "overdue"][:15]
    risks = build_risks(project_key, now_utc=now_utc, db_path=db_path)["risks"]
    changes = [
        c for c in get_procore_changes(project_key=project_key, db_path=db_path)
        if (c.get("detected_at_utc") or "") >= since_utc
    ]

    headline_rows = [[k.replace("_", " ").title(), v] for k, v in headline.items()]
    overdue_rows = [
        [it.get("importance"), it.get("signal_type"), it.get("endpoint_id"),
         it.get("due_at_utc") or "", it.get("days_overdue"), it.get("title_redacted") or ""]
        for it in overdue_items
    ]
    risk_rows = [
        [r.get("importance"), r.get("signal_type"), r.get("endpoint_id"),
         ", ".join(r.get("dimensions") or []), r.get("title_redacted") or ""]
        for r in risks
    ]
    change_rows = [
        [c.get("detected_at_utc"), c.get("endpoint_id"), c.get("procore_record_id"),
         c.get("field_path"), c.get("change_category"), c.get("record_key")]
        for c in changes
    ]

    sections = {
        "headline": _section(
            "Headline",
            f"hb-assistant procore live digest --project {project_key} --json",
            f"Health: **{digest['health_status']}** — "
            f"{', '.join(digest['status_reason'])}\n\n"
            + _table(["Metric", "Count"], headline_rows, empty="No headline metrics."),
        ),
        "overdue": _section(
            "Overdue",
            f"hb-assistant procore live overdue --project {project_key} --json",
            _table(["Importance", "Signal", "Endpoint", "Due", "Days Overdue", "Title"], overdue_rows,
                   empty="No overdue items."),
        ),
        "risks": _section(
            "Top Risks",
            f"hb-assistant procore live risks --project {project_key} --json",
            _table(["Importance", "Signal", "Endpoint", "Dimensions", "Title"], risk_rows,
                   empty="No top risks."),
        ),
        "changes": _section(
            "Changes In Window",
            f'hb-assistant procore live changes --project {project_key} --since "24 hours ago" --json',
            _table(["Detected", "Endpoint", "Record ID", "Field", "Category", "Record Key"],
                   change_rows, empty="No changes in the window."),
        ),
    }
    counts_out = {"overdue": len(overdue_rows), "top_risks": len(risk_rows),
                  "changes_in_window": len(change_rows)}
    warnings = {"stale_endpoints": headline["stale_endpoints"],
                "review_required_records": headline["review_required_records"]}
    # reuse the project-health stale list for the banner detail
    hw = _health_warnings(project_key, now_utc, db_path)
    warnings_md = _warnings_md(hw["stale_list"], headline["review_required_records"])
    rendered = _render_note(
        note_type=_NOTES["daily_digest"][2], project_key=project_key,
        title="Procore Daily Digest", now_utc=now_utc, since_utc=since_utc,
        order=["headline", "overdue", "risks", "changes"], sections=sections,
        warnings_md=warnings_md,
    )
    return _result(
        command="hb-assistant procore obsidian daily-digest", project_key=project_key,
        now_utc=now_utc, since_utc=since_utc, sections=sections, rendered=rendered,
        counts=counts_out, warnings=warnings,
    )


# --------------------------------------------------------------------------- #
# apply (marker-bounded write to the configured local vault)
# --------------------------------------------------------------------------- #


def _apply(result: Dict[str, Any], project_key: str, note_key: str) -> Dict[str, Any]:
    from ..construction.manifests.vault_writer import ConstructionVaultWriter

    marker_kind, suffix, _ = _NOTES[note_key]
    writer = ConstructionVaultWriter()
    if not writer.configured:
        result["written_paths"] = []
        result["vault_configured"] = False
        return result
    path = _write_procore_artifact(
        writer.root, f"{project_key}.{suffix}", result["rendered"], marker_kind,
    )
    result["written_paths"] = [str(path)]
    result["vault_configured"] = True
    return result


def apply_project_health_note(
    project_key: str, *, now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    return _apply(build_project_health_note(project_key, now_utc=now_utc, db_path=db_path),
                  project_key, "project_health")


def apply_meeting_prep(
    project_key: str, *, since_utc: str, now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    return _apply(
        build_meeting_prep(project_key, since_utc=since_utc, now_utc=now_utc, db_path=db_path),
        project_key, "meeting_prep",
    )


def apply_daily_digest(
    project_key: str, *, since_utc: str, now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    return _apply(
        build_daily_digest(project_key, since_utc=since_utc, now_utc=now_utc, db_path=db_path),
        project_key, "daily_digest",
    )


__all__ = [
    "build_project_health_note", "apply_project_health_note",
    "build_meeting_prep", "apply_meeting_prep",
    "build_daily_digest", "apply_daily_digest",
]
