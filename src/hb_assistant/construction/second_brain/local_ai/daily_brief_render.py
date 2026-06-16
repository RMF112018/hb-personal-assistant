"""Phase 10 — daily-brief rendering / consumption (read-only, advisory, no writeback).

Closes the local-agent loop: renders the V51 ranking/assembly overlay
(``daily_brief_assembly_sections`` + ``daily_brief_action_candidates``) into a consumable,
deterministic, user-facing daily brief — an operator action plan in structured JSON + polished
Markdown — and, only on explicit request, writes that Markdown to a path-safe file.

When an assembly overlay exists for the date, render consumes it: items are grouped and ordered by
the assembly's authoritative ``candidate_ids_json`` (Top Priorities first), Procore rows are
aggregated by project + signal type, calendar rows get safe labels, and the email/follow-up family
is always represented (candidates or a polished data-gap card). When no overlay exists, render falls
back to family grouping — through the *same* sanitization. All user-facing copy is produced by the
pure :mod:`daily_brief_presentation` layer and passes its output fence (no internal ids, sentinels,
hash labels, ``next:review``, table/column names, or raw subjects/bodies/URLs/emails).

Read-only by design: ``render_daily_brief`` performs zero writes and reads only the safe columns
exposed by the overlay read models (titles/reasons are redacted at write time). Ordering is
deterministic (no wall-clock): assembly display order, then priority, then candidate id.

File writing is off by default and has two modes, both marker-bounded + atomic + path-redacted and
reusing the approved ``daily_brief.output`` primitives:
- governed vault write via ``output.write_brief_output`` (the established brief path), and
- an explicit ``--output-path`` write that must be ABSOLUTE and OUTSIDE the repo (so private brief
  content can never land in git), refusing to clobber a foreign file that lacks the brief marker.
No raw bodies, HTML, join URLs, attendee emails, prompts, responses, tokens, or secrets are ever
emitted or written.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from hb_assistant.config.path_policy import PathPolicy

from ..daily_brief.output import (
    SECTION_END,
    SECTION_START,
    _atomic_write_text,
    _ensure_markers,
    _replace_bounded,
    _sha256,
)
from .daily_brief_presentation import (
    ASSEMBLY_KEY_TO_GROUP,
    CALENDAR_MAX_LINES,
    DISPLAY_GROUP_ORDER,
    FAMILY_TO_GROUP,
    aggregate_procore_lines,
    assert_clean_display,
    cap_lines,
    collapse_duplicate_lines,
    email_followup_gap_card,
    render_data_gap_lines,
    render_item_line,
)


def _short_id(candidate_id: Optional[str]) -> str:
    """Short, stable trace indicator (the id is a deterministic hash, not private)."""
    cid = str(candidate_id or "")
    return cid[:18] if cid else ""


def _calendar_source_ref(event_index_id: Any) -> str:
    """Recompute the calendar candidate source_ref exactly as calendar-prep does."""
    return "cal:" + hashlib.sha256(str(event_index_id).encode("utf-8")).hexdigest()[:32]


def _build_raw_enrichment(
    *, store: Any, brief_date: str, sections_present: set[str]
) -> dict[str, dict[str, Any]]:
    """Map each persisted candidate id → REAL (un-redacted) content from the LOCAL raw tables.

    Forward-map: candidate ids are deterministic hashes of (brief_date, section, group_key), so we
    recompute them from each source row and join. Read-only; the real content fetched here is for
    LOCAL consumption only (caller surfaces it to stdout / a non-repo file) and is never persisted,
    logged, or written to the repo. Each source read is guarded so a missing table is a no-op.
    """
    enrichment: dict[str, dict[str, Any]] = {}

    # Calendar (Graph): real subject / location / organizer from calendar_event_raw_content.
    if "calendar" in sections_present:
        try:
            for row in store.list_calendar_event_raw_content(limit=1_000_000):
                eid = row.get("event_index_id")
                if not eid:
                    continue
                cid = store.daily_brief_action_candidate_id_for(
                    brief_date, "calendar", _calendar_source_ref(eid)
                )
                subject = str(row.get("subject") or "").strip()
                detail_bits: list[str] = []
                if row.get("location_display"):
                    detail_bits.append(f"loc:{str(row['location_display']).strip()}")
                if row.get("organizer_name"):
                    detail_bits.append(f"organizer:{str(row['organizer_name']).strip()}")
                enrichment[cid] = {
                    "raw_title": subject or None,
                    "raw_detail": " · ".join(detail_bits) or None,
                }
        except Exception:
            pass

    # Procore: real per-signal titles backing each (project, signal_type) rollup candidate. The
    # minimal list_procore_action_signals reader omits title_redacted (which holds the REAL label),
    # so read it directly. Guarded so a missing table/path is a no-op.
    if "procore" in sections_present:
        try:
            from hb_assistant.store.connection import get_connection

            conn = get_connection(getattr(store, "_db_path", None))
            cur = conn.execute(
                "SELECT project_key, signal_type, title_redacted FROM procore_action_signals "
                "WHERE signal_status = 'open' AND COALESCE(length(title_redacted), 0) > 0"
            )
            groups: dict[str, list[str]] = {}
            for project_key, signal_type, title in cur.fetchall():
                groups.setdefault(f"{project_key}|{signal_type}", []).append(str(title).strip())
            for gk, titles in groups.items():
                cid = store.daily_brief_action_candidate_id_for(brief_date, "procore", gk)
                uniq = list(dict.fromkeys(t for t in titles if t))[:5]
                enrichment[cid] = {"raw_title": None, "raw_detail": "; ".join(uniq) or None}
        except Exception:
            pass

    return enrichment


def _latest_assembly_sections(store: Any, brief_date: str) -> Optional[list[dict[str, Any]]]:
    """Return the newest assembly run's sections (display order) for ``brief_date``, or ``None``.

    ``None`` means no overlay exists for the date — render falls back to family grouping. Guarded so
    a missing overlay table is treated as "no overlay" rather than an error.
    """
    try:
        runs = store.list_assembly_runs(brief_date=brief_date, limit=1)
    except Exception:
        return None
    if not runs:
        return None
    run_id = str(runs[0].get("assembly_run_id") or "")
    if not run_id:
        return None
    try:
        return store.list_assembly_sections(assembly_run_id=run_id, limit=10_000)
    except Exception:
        return None


def _eligible(
    row: dict[str, Any], *, section_filter: Optional[set[str]], project_key: Optional[str]
) -> bool:
    """Apply the optional internal-section and project-key filters to a candidate detail row."""
    if section_filter is not None and str(row.get("section") or "") not in section_filter:
        return False
    return not (project_key is not None and str(row.get("project_key") or "") != str(project_key))


def _section_ids(sec: dict[str, Any]) -> list[str]:
    """Parse a section's ``candidate_ids_json`` into a list of candidate id strings (guarded)."""
    try:
        return [str(c) for c in json.loads(str(sec.get("candidate_ids_json") or "[]"))]
    except (ValueError, TypeError):
        return []


def _group_from_overlay(
    sections: list[dict[str, Any]],
    detail_by_id: dict[str, dict[str, Any]],
    *,
    section_filter: Optional[set[str]],
    project_key: Optional[str],
) -> tuple[dict[str, list[dict[str, Any]]], Optional[str]]:
    """Resolve assembly sections → display groups of candidate details (authoritative order).

    The assembly's ``top_priorities`` membership is rendered first, as individual sanitized lines. The
    remaining candidates are routed to their dedicated display section *by family* — Procore rows to
    the aggregated Procore section, calendar rows to Calendar Prep — so the procore-aggregation and
    calendar-safe-label contracts hold regardless of which lifecycle bucket the overlay placed them
    in; every other family follows the assembly ``section_key`` mapping. Sections arrive in display
    order, so within-group order is deterministic. Returns ``(groups, degraded_reason)``.
    """
    groups: dict[str, list[dict[str, Any]]] = {g: [] for g in DISPLAY_GROUP_ORDER}
    degraded_reason: Optional[str] = None
    placed: set[str] = set()

    def _take(cid: str) -> Optional[dict[str, Any]]:
        if cid in placed:
            return None
        detail = detail_by_id.get(cid)
        if detail is None or not _eligible(
            detail, section_filter=section_filter, project_key=project_key
        ):
            return None
        placed.add(cid)
        return detail

    # Top Priorities first (authoritative selection + order), rendered as individual lines.
    for sec in sections:
        if str(sec.get("section_key") or "") != "top_priorities":
            continue
        for cid in _section_ids(sec):
            detail = _take(cid)
            if detail is not None:
                groups["Top Priorities"].append(detail)
        break

    # Remaining sections: Procore/calendar routed by family; others by assembly section_key.
    for sec in sections:
        key = str(sec.get("section_key") or "")
        if key == "top_priorities":
            continue
        if key == "data_gaps_degraded":
            degraded_reason = sec.get("degraded_reason")
            continue
        for cid in _section_ids(sec):
            detail = _take(cid)
            if detail is None:
                continue
            family = str(detail.get("section") or "")
            if family == "procore":
                group = "Procore Financial / Project Signals"
            elif family == "calendar":
                group = "Calendar Prep"
            else:
                group = ASSEMBLY_KEY_TO_GROUP.get(key, "Needs Review / Decisions")
            groups[group].append(detail)
    return groups, degraded_reason


def _group_from_family(
    all_rows: list[dict[str, Any]],
    *,
    section_filter: Optional[set[str]],
    project_key: Optional[str],
) -> dict[str, list[dict[str, Any]]]:
    """Fallback grouping (no overlay): bucket candidates by source family into display groups."""
    groups: dict[str, list[dict[str, Any]]] = {g: [] for g in DISPLAY_GROUP_ORDER}
    for r in all_rows:
        if not _eligible(r, section_filter=section_filter, project_key=project_key):
            continue
        group = FAMILY_TO_GROUP.get(str(r.get("section") or ""), "Needs Review / Decisions")
        groups[group].append(r)
    for g in groups:
        groups[g].sort(
            key=lambda r: (
                int(r.get("priority") or 100),
                str(r.get("daily_brief_action_candidate_id") or ""),
            )
        )
    return groups


def render_daily_brief(
    *,
    store: Any,
    brief_date: str,
    sections: Optional[list[str]] = None,
    project_key: Optional[str] = None,
    limit: int = 200,
    include_raw: bool = False,
    relationship_limit: int = 10,
) -> dict[str, Any]:
    """Render the daily brief for one date as a user-facing action plan (read-only).

    Consumes the V51 assembly overlay when one exists for ``brief_date`` (Top Priorities first,
    Procore aggregated, calendar safe-labelled, email/follow-up always represented); otherwise falls
    back to family grouping through the same sanitization. ``sections`` filters by internal family;
    ``project_key`` filters by project; ``limit`` caps per-group item lines. Returns a dict with
    ``summary`` counts, structured ``sections`` (display groups → safe lines), and a clean ``markdown``
    string (it passes the presentation output fence). Writes nothing.

    ``include_raw`` (LOCAL CONSUMPTION ONLY) attaches the REAL (un-redacted) content from the local
    raw tables onto the JSON items for local inspection — never into the Markdown, never persisted,
    logged, or committed. The user-facing Markdown is always the sanitized, raw-safe form.
    """
    section_filter = {str(s) for s in sections} if sections else None

    all_rows = store.list_daily_brief_action_candidates(brief_date=brief_date, limit=1_000_000)
    total = len(all_rows)
    detail_by_id = {str(r.get("daily_brief_action_candidate_id") or ""): r for r in all_rows}

    overlay_sections = _latest_assembly_sections(store, brief_date)
    used_overlay = overlay_sections is not None
    if used_overlay:
        groups, degraded_reason = _group_from_overlay(
            overlay_sections or [],
            detail_by_id,
            section_filter=section_filter,
            project_key=project_key,
        )
    else:
        groups = _group_from_family(
            all_rows, section_filter=section_filter, project_key=project_key
        )
        degraded_reason = None

    # Optional LOCAL-only enrichment: real content from raw tables, attached to JSON items only.
    enrichment: dict[str, dict[str, Any]] = {}
    if include_raw:
        sections_present = {str(r.get("section") or "") for items in groups.values() for r in items}
        enrichment = _build_raw_enrichment(
            store=store, brief_date=brief_date, sections_present=sections_present
        )

    # Email/follow-up family is never silently omitted — unless a section filter deliberately scopes
    # it out. When in scope and empty, surface a data-gap card (count of unconverted summaries).
    email_families = {"actions", "waiting", "follow_up"}
    email_gap_enabled = section_filter is None or bool(section_filter & email_families)
    thread_count = 0
    if email_gap_enabled and not groups["Email / Follow-up"]:
        try:
            thread_count = len(store.list_email_thread_summaries(limit=1_000_000))
        except Exception:
            thread_count = 0

    # Build each display group's sanitized body once; markdown, JSON sections, and counts derive
    # from these, so what the operator reads and what the summary reports never drift apart.
    bodies = _ordered_bodies(
        groups,
        degraded_reason=degraded_reason,
        thread_count=thread_count,
        limit=limit,
        email_gap_enabled=email_gap_enabled,
    )

    markdown = _render_markdown(brief_date=brief_date, bodies=bodies)
    sections_out = _structured_sections(
        bodies, groups, limit=limit, include_raw=include_raw, enrichment=enrichment
    )

    return {
        "command": "second-brain daily-brief render",
        "ok": True,
        "brief_date": brief_date,
        "project_filter": project_key,
        "section_filter": sorted(section_filter) if section_filter else None,
        "include_raw": include_raw,
        "used_assembly_overlay": used_overlay,
        "summary": {
            "total_for_date": total,
            "rendered": sum(len(body) for body in bodies.values()),
            "by_group": {group: len(body) for group, body in bodies.items()},
            "email_followup_thread_summaries": thread_count,
        },
        "sections": sections_out,
        "markdown": markdown,
        "guardrails": {
            "read_only": True,
            "deterministic": True,
            "consumes_assembly_overlay": used_overlay,
            "source_linked_candidate_ids": True,
            "user_facing_markdown_sanitized": True,
            # include_raw attaches REAL content to JSON items for LOCAL consumption only; the Markdown
            # stays sanitized, persisted rows + repo artifacts stay redacted, nothing raw is committed.
            "redacted_markdown_always": True,
            "raw_local_consumption_only": include_raw,
            "no_raw_persistence": True,
            "no_writeback": True,
            "advisory_only": True,
        },
    }


def _group_body_lines(
    group: str,
    items: list[dict[str, Any]],
    *,
    degraded_reason: Optional[str],
    thread_count: int,
    limit: int,
) -> list[str]:
    """Sanitized Markdown bullet lines for one display group (procore aggregated; email gap card)."""
    if group == "Procore Financial / Project Signals":
        return aggregate_procore_lines(items)
    if group == "Calendar Prep":
        # Safe-labelled per-meeting lines, deduped, then capped with an explicit overflow summary.
        lines = collapse_duplicate_lines([render_item_line(d, group=group) for d in items])
        return cap_lines(
            lines, max_lines=min(CALENDAR_MAX_LINES, max(0, limit)), more_noun="meetings"
        )
    if group == "Email / Follow-up":
        if items:
            return collapse_duplicate_lines(
                [render_item_line(d, group=group) for d in items[: max(0, limit)]]
            )
        return email_followup_gap_card(thread_count)
    if group == "Data Gaps / Degraded":
        if degraded_reason is None:
            return []
        return render_data_gap_lines(degraded_reason)
    return collapse_duplicate_lines(
        [render_item_line(d, group=group) for d in items[: max(0, limit)]]
    )


def _ordered_bodies(
    groups: dict[str, list[dict[str, Any]]],
    *,
    degraded_reason: Optional[str],
    thread_count: int,
    limit: int,
    email_gap_enabled: bool = True,
) -> dict[str, list[str]]:
    """Build each display group's sanitized body lines, in display order (non-empty groups only).

    The email/follow-up data-gap card renders when the email family is in scope but has no
    candidates; it is suppressed when a section filter scopes the email family out, and on an
    otherwise-empty brief (so an empty date reads "no review candidates" rather than only a card).
    """
    bodies: dict[str, list[str]] = {}
    for group in DISPLAY_GROUP_ORDER:
        items = groups.get(group) or []
        if group == "Email / Follow-up" and not items and not email_gap_enabled:
            continue
        body = _group_body_lines(
            group,
            items,
            degraded_reason=degraded_reason,
            thread_count=thread_count,
            limit=limit,
        )
        if body:
            bodies[group] = body

    email_group_empty = not groups.get("Email / Follow-up")
    if email_group_empty and "Email / Follow-up" in bodies:
        others = [g for g in bodies if g != "Email / Follow-up"]
        if not others:
            del bodies["Email / Follow-up"]
    return bodies


def _render_markdown(*, brief_date: str, bodies: dict[str, list[str]]) -> str:
    """Deterministic, sanitized user-facing Markdown. Passes the presentation output fence."""
    disclaimer = (
        "_Advisory only. A deterministic, source-linked action plan from the local-agent family "
        "(email/follow-up, Procore, calendar). No raw source content._"
    )
    lines: list[str] = [f"# Daily Brief — {brief_date}", "", disclaimer, ""]
    for group, body in bodies.items():
        lines.append(f"## {group}")
        lines.extend(body)
        lines.append("")
    if not bodies:
        lines.append("_No review candidates for this date._")

    markdown = "\n".join(lines).strip() + "\n"
    # Output fence: fail loud if any internal artifact or raw private content leaked into the brief.
    assert_clean_display(markdown)
    return markdown


def _structured_sections(
    bodies: dict[str, list[str]],
    groups: dict[str, list[dict[str, Any]]],
    *,
    limit: int,
    include_raw: bool,
    enrichment: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the JSON ``sections`` payload (sanitized display lines + safe candidate metadata)."""
    sections_out: list[dict[str, Any]] = []
    for group, body in bodies.items():
        items = groups.get(group) or []
        json_items: list[dict[str, Any]] = []
        for r in items[: max(0, limit)]:
            full_id = str(r.get("daily_brief_action_candidate_id") or "")
            entry: dict[str, Any] = {
                "candidate_id": _short_id(full_id),
                "section": r.get("section"),
                # Sanitized single-item line (raw-free), reused by local consumers (browser/appendix).
                "display": render_item_line(r, group=group).removeprefix("- "),
            }
            if include_raw:
                enr = enrichment.get(full_id) or {}
                if enr.get("raw_title"):
                    entry["raw_title"] = enr["raw_title"]
                if enr.get("raw_detail"):
                    entry["raw_detail"] = enr["raw_detail"]
            json_items.append(entry)
        sections_out.append(
            {
                "display": group,
                "line_count": len(body),
                "item_count": len(items),
                "lines": body,
                "items": json_items,
            }
        )
    return sections_out


def _redact_path(target: Path) -> str:
    """Redact an output path to a non-sensitive form (relative-to-home, else parent/name)."""
    try:
        return "~/" + str(target.relative_to(Path.home()))
    except ValueError:
        return f"{target.parent.name}/{target.name}"


def write_rendered_brief_to_path(
    *,
    inner_markdown: str,
    output_path: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Write the rendered brief markdown to an EXPLICIT, path-safe file (marker-bounded, atomic).

    Path safety (mirrors the repo's "explicit absolute non-repo directory" convention): the path must
    be absolute and MUST NOT be inside the repo (so private brief content can never be committed). An
    existing target that lacks the brief marker is refused (no clobbering foreign files). Dry-run
    (default) reports the would-write path (redacted) + byte count + hash and writes nothing.
    """
    target = Path(output_path)
    if not target.is_absolute():
        return {"ok": False, "error": "output_path_must_be_absolute"}
    try:
        repo_root = PathPolicy().resolve_repo_root().resolve()
    except Exception:
        repo_root = None
    resolved = target.resolve()
    if repo_root is not None and (resolved == repo_root or repo_root in resolved.parents):
        return {"ok": False, "error": "output_path_inside_repo_refused"}

    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if existing and SECTION_START not in existing:
        return {"ok": False, "error": "refuse_overwrite_foreign_file"}

    framed = _ensure_markers(existing, SECTION_START, SECTION_END)
    new_content = _replace_bounded(framed, inner_markdown.strip(), SECTION_START, SECTION_END)
    content_hash = _sha256(new_content)
    byte_count = len(new_content.encode("utf-8"))

    if dry_run:
        return {
            "ok": True,
            "written": False,
            "would_write_path_redacted": _redact_path(target),
            "would_write_bytes": byte_count,
            "content_hash": content_hash,
        }

    _atomic_write_text(target, new_content)
    return {
        "ok": True,
        "written": True,
        "output_path_redacted": _redact_path(target),
        "bytes_written": byte_count,
        "content_hash": content_hash,
    }
