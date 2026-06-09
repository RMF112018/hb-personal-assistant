"""Phase 10 — daily-brief rendering / consumption (read-only, advisory, no writeback).

Closes the local-agent loop: renders the already-redacted rows of the convergence table
``daily_brief_action_candidates`` (written by the email/follow-up, Procore, and calendar families)
into a consumable, deterministic daily brief — structured JSON + redacted Markdown — and, only on
explicit request, writes that Markdown to a path-safe file.

Read-only by design: ``render_daily_brief`` performs zero writes and reads only the 11 safe columns
exposed by ``list_daily_brief_action_candidates`` (titles/reasons are redacted at write time). The
per-candidate ``daily_brief_action_candidate_id`` is the stable traceback indicator. Ordering is
deterministic (no wall-clock): display-section order → project_key → priority → candidate id.

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

# Internal candidate section → display section. Ordered for deterministic rendering.
_DISPLAY_SECTIONS: list[tuple[str, str]] = [
    ("actions", "Today's Actions"),
    ("waiting", "Waiting / Follow-Up"),
    ("follow_up", "Risks / Watch Items"),
    ("procore", "Procore Project Signals"),
    ("calendar", "Calendar Prep"),
    ("__unassigned__", "Unassigned / Needs Review"),
]
_SECTION_TO_DISPLAY = dict(_DISPLAY_SECTIONS)
_DISPLAY_ORDER = {v: i for i, (_, v) in enumerate(_DISPLAY_SECTIONS)}
_UNASSIGNED_DISPLAY = "Unassigned / Needs Review"


def _display_for(section: Optional[str]) -> str:
    return _SECTION_TO_DISPLAY.get(str(section or ""), _UNASSIGNED_DISPLAY)


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


def render_daily_brief(
    *,
    store: Any,
    brief_date: str,
    sections: Optional[list[str]] = None,
    project_key: Optional[str] = None,
    limit: int = 200,
    include_raw: bool = False,
) -> dict[str, Any]:
    """Render ``daily_brief_action_candidates`` for one date into a brief (read-only).

    ``sections`` filters by internal section name; ``project_key`` filters by project; ``limit`` caps
    the rendered item count (deterministic order). Returns a dict with ``summary`` counts, structured
    ``sections`` (display groups → safe items), and a ``markdown`` string. Writes nothing.

    ``include_raw`` (LOCAL CONSUMPTION ONLY) enriches each item with the REAL (un-redacted) content
    from the local raw tables — calendar subjects/locations, Procore signal titles. This content is
    surfaced only to the caller (stdout / a non-repo file); it is never persisted, logged, or written
    to the repo. Default is False (byte-for-byte the redacted brief).
    """
    section_filter = {str(s) for s in sections} if sections else None

    # Read the full date set once (safe columns only), then filter/cap deterministically in Python.
    all_rows = store.list_daily_brief_action_candidates(brief_date=brief_date, limit=1_000_000)
    total = len(all_rows)

    filtered: list[dict[str, Any]] = []
    skipped_by_filter = 0
    for r in all_rows:
        if section_filter is not None and str(r.get("section") or "") not in section_filter:
            skipped_by_filter += 1
            continue
        if project_key is not None and str(r.get("project_key") or "") != str(project_key):
            skipped_by_filter += 1
            continue
        filtered.append(r)

    # Deterministic order: display-section, then project_key (None last), then priority, then id.
    def _key(r: dict[str, Any]) -> tuple[int, int, str, int, str]:
        disp = _display_for(r.get("section"))
        proj = r.get("project_key")
        return (
            _DISPLAY_ORDER.get(disp, len(_DISPLAY_SECTIONS)),
            1 if proj is None else 0,
            str(proj or ""),
            int(r.get("priority") or 100),
            str(r.get("daily_brief_action_candidate_id") or ""),
        )

    filtered.sort(key=_key)
    rendered = filtered[: max(0, limit)]
    skipped_by_limit = len(filtered) - len(rendered)

    # Optional LOCAL-only enrichment: real content from raw tables, keyed by candidate id.
    enrichment: dict[str, dict[str, Any]] = {}
    if include_raw:
        sections_present = {str(r.get("section") or "") for r in rendered}
        enrichment = _build_raw_enrichment(
            store=store, brief_date=brief_date, sections_present=sections_present
        )

    # Group rendered items by display section.
    grouped: dict[str, list[dict[str, Any]]] = {disp: [] for _, disp in _DISPLAY_SECTIONS}
    for r in rendered:
        disp = _display_for(r.get("section"))
        full_id = str(r.get("daily_brief_action_candidate_id") or "")
        title_redacted = r.get("title_redacted")
        item: dict[str, Any] = {
            "candidate_id": _short_id(full_id),
            "section": r.get("section"),
            "title_redacted": title_redacted,
            "reason_redacted": r.get("reason_redacted"),
            "project_key": r.get("project_key"),
            "priority": r.get("priority"),
            "confidence": r.get("confidence"),
            "status": r.get("status"),
            "recommended_next_action": r.get("recommended_next_action"),
            "display_title": title_redacted,
        }
        if include_raw:
            enr = enrichment.get(full_id) or {}
            if enr.get("raw_title"):
                item["display_title"] = enr["raw_title"]
                item["raw_title"] = enr["raw_title"]
            if enr.get("raw_detail"):
                item["raw_detail"] = enr["raw_detail"]
        grouped.setdefault(disp, []).append(item)

    by_section = {disp: len(items) for disp, items in grouped.items() if items}
    sections_out = [
        {"display": disp, "section_count": len(grouped[disp]), "items": grouped[disp]}
        for _, disp in _DISPLAY_SECTIONS
        if grouped[disp]
    ]

    markdown = _render_markdown(
        brief_date=brief_date,
        grouped=grouped,
        total_rendered=len(rendered),
        include_raw=include_raw,
    )

    return {
        "command": "second-brain daily-brief render",
        "ok": True,
        "brief_date": brief_date,
        "project_filter": project_key,
        "section_filter": sorted(section_filter) if section_filter else None,
        "include_raw": include_raw,
        "summary": {
            "total_for_date": total,
            "rendered": len(rendered),
            "skipped_by_filter": skipped_by_filter,
            "skipped_by_limit": skipped_by_limit,
            "by_section": by_section,
        },
        "sections": sections_out,
        "markdown": markdown,
        "guardrails": {
            "read_only": True,
            "deterministic": True,
            "source_linked_candidate_ids": True,
            # include_raw surfaces REAL content for LOCAL consumption only; persisted rows + repo
            # artifacts stay redacted, and nothing raw is logged or committed.
            "redacted_fields_only": not include_raw,
            "raw_local_consumption_only": include_raw,
            "no_raw_persistence": True,
            "no_writeback": True,
            "advisory_only": True,
        },
    }


def _render_markdown(
    *,
    brief_date: str,
    grouped: dict[str, list[dict[str, Any]]],
    total_rendered: int,
    include_raw: bool = False,
) -> str:
    """Deterministic Markdown. Uses ``display_title`` (real content when ``include_raw``, else the
    redacted title) + stable candidate ids. ``include_raw`` output is LOCAL-only — never committed."""
    disclaimer = (
        "_Advisory only. Source-linked review candidates from the local-agent family "
        "(email/follow-up, Procore, calendar)._"
        if include_raw
        else "_Advisory only. Source-linked review candidates from the local-agent family "
        "(email/follow-up, Procore, calendar). Redacted; no raw source content._"
    )
    lines: list[str] = [f"# Daily Brief — {brief_date}", "", disclaimer, ""]
    if total_rendered == 0:
        lines.append("_No review candidates for this date._")
        return "\n".join(lines).strip() + "\n"

    for _, disp in _DISPLAY_SECTIONS:
        items = grouped.get(disp) or []
        if not items:
            continue
        lines.append(f"## {disp}")
        for it in items:
            title = str(it.get("display_title") or it.get("title_redacted") or "(untitled)")
            parts: list[str] = []
            if it.get("raw_detail"):
                parts.append(str(it["raw_detail"]))
            if it.get("reason_redacted"):
                parts.append(str(it["reason_redacted"]))
            if it.get("project_key"):
                parts.append(f"project:{it['project_key']}")
            if it.get("recommended_next_action"):
                parts.append(f"next:{it['recommended_next_action']}")
            cid = it.get("candidate_id")
            if cid:
                parts.append(f"id:{cid}")
            suffix = f" — {' · '.join(parts)}" if parts else ""
            lines.append(f"- {title}{suffix}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


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
