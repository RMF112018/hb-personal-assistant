"""Deterministic Obsidian markdown for schedule second-brain notes (Phase 19)."""

from __future__ import annotations

import re
from typing import Any

MANAGED_BEGIN = "<!-- hb-schedule-note:begin managed -->"
MANAGED_END = "<!-- hb-schedule-note:end managed -->"

_FORBIDDEN_LANGUAGE = re.compile(
    r"\b(claim|liability|responsibility|fault|compensable|entitlement|delay damages|caused|causation|forensic)\b",
    re.IGNORECASE,
)

_FORBIDDEN_ID_TOKENS = re.compile(
    r"\b(schedule_version_key|import_id|package_id|cpm_run_id|procore_project_id|file_sha256|file_path|source_export_proxy)\b",
    re.IGNORECASE,
)


def _yaml_scalar(value: Any) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        return '""'
    if any(ch in text for ch in ':"\\#'):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def _title_for_payload(payload: dict[str, Any]) -> str:
    note_type = str(payload.get("note_type") or "schedule")
    project_label = str(payload.get("project_label") or payload.get("project_key") or "Schedule")
    schedule_date = str(payload.get("schedule_data_date") or payload.get("as_of") or "")
    if note_type == "portfolio_snapshot":
        return f"Portfolio Schedule Review — {schedule_date}"
    basis = str(payload.get("comparison_label") or payload.get("comparison_basis") or "")
    return f"Schedule Comparison — {project_label} — {schedule_date} — {basis}"


def note_filename(payload: dict[str, Any]) -> str:
    schedule_date = str(payload.get("schedule_data_date") or payload.get("as_of") or "undated")
    if schedule_date in {"—", "-", ""}:
        schedule_date = str(payload.get("as_of") or "undated")
    project_label = str(payload.get("project_label") or payload.get("project_key") or "Schedule")
    note_type = str(payload.get("note_type") or "schedule")
    if note_type == "portfolio_snapshot":
        return f"{schedule_date} - Portfolio Schedule Review.md"
    safe_project = re.sub(r"[^\w\s-]", "", project_label).strip().replace(" ", " ")
    basis = str(payload.get("comparison_label") or payload.get("comparison_basis") or "comparison")
    safe_basis = re.sub(r"[^\w\s-]", "", basis).strip().replace(" ", " ")
    return f"{schedule_date} - {safe_project} - Schedule Comparison - {safe_basis}.md"


def note_relative_path(payload: dict[str, Any]) -> str:
    filename = note_filename(payload)
    note_type = str(payload.get("note_type") or "")
    if note_type == "portfolio_snapshot":
        return f"Work/HB Personal Assistant/Schedule Review/Portfolio/{filename}"
    project_key = str(payload.get("project_key") or "unknown")
    return f"Work/HB Personal Assistant/Schedule Review/Projects/{project_key}/{filename}"


def _section_lines(payload: dict[str, Any]) -> list[str]:
    review = payload.get("review_status") or {}
    quality = payload.get("quality_controls") or {}
    lines = [
        "## Summary",
        "",
        f"- Project: {payload.get('project_label')}",
        f"- Schedule data date: {payload.get('schedule_data_date') or '—'}",
        f"- Comparison: {payload.get('comparison_label') or payload.get('comparison_basis')}",
        f"- As of: {payload.get('as_of')}",
        "",
        "## Trust Posture",
        "",
        f"- Analytics trust: {payload.get('analytics_trust_status')}",
        f"- Identity trust: {payload.get('identity_trust_status')}",
        f"- CPM trust: {payload.get('cpm_trust_status')}",
        f"- Quality trust: {payload.get('quality_trust_status')}",
        "",
        "## Comparison Basis",
        "",
        str(payload.get("comparison_label") or payload.get("comparison_basis") or "—"),
        "",
        "## Schedule Quality Controls",
        "",
        str(quality.get("headline") or quality.get("summary") or "Quality controls snapshot unavailable."),
        "",
        "## Review Status",
        "",
        str(review.get("pm_summary") or review.get("headline") or "Review status unavailable."),
        "",
        "## Recommended Follow-Up",
        "",
    ]
    actions = [str(item) for item in (payload.get("recommended_actions") or []) if str(item).strip()]
    if actions:
        lines.extend(f"- {action}" for action in actions)
    else:
        lines.append("- Review linked schedule surfaces and record operator disposition when appropriate.")
    lines.extend(["", "## Links", ""])
    for label, href in sorted((payload.get("safe_links") or {}).items()):
        if href:
            lines.append(f"- {label}: {href}")
    lines.extend(["", "## Capability Limitations", ""])
    for item in payload.get("capability_limitations") or []:
        lines.append(f"- {item}")
    body = str(payload.get("body_markdown") or "").strip()
    if body:
        lines.extend(["", "## Deterministic Export", "", body])
    return lines


def render_managed_body(payload: dict[str, Any], *, advisory_markdown: str | None = None) -> str:
    managed = list(_section_lines(payload))
    if advisory_markdown:
        managed.extend(["", "## Advisory Summary", "", advisory_markdown.strip(), ""])
    return "\n".join(managed).strip() + "\n"


def render_note_markdown(payload: dict[str, Any], *, advisory_markdown: str | None = None) -> str:
    frontmatter = [
        "---",
        "type: schedule_comparison",
        f"note_type: {_yaml_scalar(payload.get('note_type'))}",
        f"project_key: {_yaml_scalar(payload.get('project_key'))}",
        f"project_label: {_yaml_scalar(payload.get('project_label'))}",
        f"schedule_data_date: {_yaml_scalar(payload.get('schedule_data_date'))}",
        f"comparison_basis: {_yaml_scalar(payload.get('comparison_basis'))}",
        f"analytics_trust_status: {_yaml_scalar(payload.get('analytics_trust_status'))}",
        f"identity_trust_status: {_yaml_scalar(payload.get('identity_trust_status'))}",
        f"cpm_trust_status: {_yaml_scalar(payload.get('cpm_trust_status'))}",
        f"quality_trust_status: {_yaml_scalar(payload.get('quality_trust_status'))}",
        f"generated_by: hb-personal-assistant",
        f"generation_mode: {_yaml_scalar(payload.get('generation_mode') or 'deterministic')}",
        "---",
        "",
        f"# {_title_for_payload(payload)}",
        "",
        MANAGED_BEGIN,
        render_managed_body(payload, advisory_markdown=advisory_markdown).rstrip(),
        MANAGED_END,
        "",
    ]
    return "\n".join(frontmatter)


def assert_note_safe(markdown: str) -> None:
    from hb_assistant.construction.analytics.project_schedule_narrative_qa import validate_rendered_text

    qa = validate_rendered_text(markdown, surface="export")
    if not qa.get("passed"):
        raise ValueError(f"language_qa_failed:{qa.get('violations')}")
    if _FORBIDDEN_ID_TOKENS.search(markdown):
        raise ValueError("forbidden_id_token_detected")
    if MANAGED_BEGIN not in markdown or MANAGED_END not in markdown:
        raise ValueError("managed_block_missing")
