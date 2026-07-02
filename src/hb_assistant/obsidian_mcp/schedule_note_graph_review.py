"""Safe JSON/Markdown review reports for schedule graph linking (Phase 20)."""

from __future__ import annotations

from typing import Any

from hb_assistant.obsidian_mcp.schedule_note_graph import (
    ScheduleGraphCandidate,
    ScheduleGraphNoteFact,
    assert_report_paths_safe,
)


def build_review_payload(
    *,
    facts: list[ScheduleGraphNoteFact],
    candidates: list[ScheduleGraphCandidate],
    tag_recommendations: dict[str, list[str]],
    llm_report: dict[str, Any] | None,
    apply_summary: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "notes_discovered": len(facts),
        "candidates_total": len(candidates),
        "candidates_recommended": sum(1 for c in candidates if c.recommended),
        "notes": [
            {
                "note_rel_path": f.note_rel_path,
                "note_title": f.note_title,
                "note_type": f.note_type,
                "project_key": f.project_key,
            }
            for f in facts
        ],
        "candidates": [
            {
                "candidate_key": c.candidate_key,
                "source_note": c.source_note,
                "target_note": c.target_note,
                "relationship_type": c.relationship_type,
                "confidence": c.confidence,
                "recommended": c.recommended,
                "requires_human_review": c.requires_human_review,
                "pm_safe_label": c.pm_safe_label,
                "basis": list(c.basis),
            }
            for c in candidates
        ],
        "tag_recommendations_report_only": tag_recommendations,
        "llm_suggestions_report_only": llm_report or {"enabled": False},
        "apply": apply_summary,
    }
    assert_report_paths_safe(payload)
    return payload


def render_review_markdown(payload: dict[str, Any]) -> str:
    assert_report_paths_safe(payload)
    lines = [
        "# Schedule Note Graph Review",
        "",
        f"- Notes discovered: {payload.get('notes_discovered', 0)}",
        f"- Candidates total: {payload.get('candidates_total', 0)}",
        f"- Recommended candidates: {payload.get('candidates_recommended', 0)}",
        "",
        "## Notes",
        "",
    ]
    for note in payload.get("notes") or []:
        title = note.get("note_title") or "Untitled"
        rel = note.get("note_rel_path") or ""
        lines.append(f"- {title} (`{rel}`)")
    lines.extend(["", "## Recommended Candidates", ""])
    for cand in payload.get("candidates") or []:
        if not cand.get("recommended"):
            continue
        lines.append(
            f"- {cand.get('relationship_type')} · "
            f"{cand.get('source_note')} → {cand.get('target_note')} "
            f"(confidence {float(cand.get('confidence') or 0):.2f})"
        )
    tags = payload.get("tag_recommendations_report_only") or {}
    if tags:
        lines.extend(["", "## Tag Recommendations (report-only)", ""])
        for rel, tag_list in sorted(tags.items()):
            lines.append(f"- `{rel}`: {', '.join(tag_list)}")
    llm = payload.get("llm_suggestions_report_only") or {}
    if llm.get("enabled"):
        lines.extend(["", "## LLM Suggestions (report-only)", ""])
        for key in llm.get("selected_keys") or []:
            lines.append(f"- candidate_key: {key}")
    apply = payload.get("apply") or {}
    lines.extend(
        [
            "",
            "## Apply Summary",
            "",
            f"- dry_run: {apply.get('dry_run')}",
            f"- notes_modified: {apply.get('notes_modified', 0)}",
            f"- links_written: {apply.get('links_written', 0)}",
            f"- write_attempts: {apply.get('write_attempts', 0)}",
        ]
    )
    return "\n".join(lines) + "\n"
