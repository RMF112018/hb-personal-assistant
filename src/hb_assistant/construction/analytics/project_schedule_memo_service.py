"""Schedule PM memo export — Markdown and HTML from hub read model."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any


class ProjectScheduleMemoService:
    def build_export(
        self,
        summary: dict[str, Any],
        *,
        export_format: str = "markdown",
    ) -> dict[str, Any]:
        fmt = (export_format or "markdown").lower()
        if fmt not in {"markdown", "html"}:
            raise ValueError("unsupported_export_format")
        body = self._markdown(summary) if fmt == "markdown" else self._html(summary)
        project_key = str(summary.get("project_key") or "project")
        as_of = str(summary.get("as_of_date") or datetime.now(timezone.utc).date().isoformat())
        filename = f"schedule-memo-{project_key}-{as_of}.{ 'md' if fmt == 'markdown' else 'html' }"
        content_type = "text/markdown; charset=utf-8" if fmt == "markdown" else "text/html; charset=utf-8"
        return {
            "available": True,
            "format": fmt,
            "filename": filename,
            "content_type": content_type,
            "body": body,
            "advisory_posture": "sequence_cues_not_causation",
        }

    def _markdown(self, summary: dict[str, Any]) -> str:
        story = summary.get("schedule_story") or {}
        command = summary.get("command_summary") or {}
        workbench = summary.get("review_workbench") or {}
        driver_hub = summary.get("change_driver_analysis") or {}
        prior = driver_hub.get("prior_update") or driver_hub
        lines = [
            f"# Schedule Review Memo — {summary.get('project_display_name') or summary.get('project_key')}",
            "",
            f"As of {summary.get('as_of_date')}",
            "",
            "## Headline",
            str(story.get("headline") or "Schedule update ready for review."),
            "",
            "## Synopsis",
            str(story.get("synopsis") or ""),
            "",
            "## What Changed",
            str(story.get("what_changed") or "Not available."),
            "",
            "## Why It Matters",
            str(story.get("why_it_matters") or "Not available."),
            "",
            "## Primary Driver (sequence cue)",
            str(story.get("primary_driver_narrative") or story.get("primary_change_driver") or "Not available."),
            "",
            "## Command Summary",
            f"- Forecast finish: {command.get('forecast_finish') or '—'} ({command.get('forecast_finish_delta_days')} days vs prior)",
            f"- Remaining activities: {command.get('remaining_activity_count') or '—'}",
            f"- Critical / near-critical: {command.get('critical_remaining_count') or 0} / {command.get('near_critical_remaining_count') or 0}",
            f"- Negative float (remaining): {command.get('negative_float_remaining_count') or 0}",
            "",
        ]
        if workbench.get("available"):
            wb_summary = workbench.get("summary") or {}
            lines.extend(
                [
                    "## Review Workbench",
                    f"- Open: {wb_summary.get('open_count', 0)}",
                    f"- Watching: {wb_summary.get('watching_count', 0)}",
                    f"- Reviewed: {wb_summary.get('reviewed_count', 0)}",
                    "",
                ]
            )
            for item in workbench.get("preview") or []:
                lines.append(
                    f"- [{item.get('review_status')}] P{item.get('priority')} {item.get('item_title')}"
                )
                if item.get("pm_notes"):
                    lines.append(f"  - Notes: {item['pm_notes']}")
            lines.append("")

        if prior.get("available"):
            top = (prior.get("top_drivers") or [None])[0] or {}
            lines.extend(
                [
                    "## Top Candidate Driver",
                    f"- Activity: {top.get('activity_name') or top.get('activity_id') or '—'}",
                    f"- WBS: {top.get('wbs_code') or '—'}",
                    f"- Downstream moved later: {top.get('downstream_moved_later_count') or 0}",
                    "",
                ]
            )

        caveats = story.get("caveats") or []
        if caveats:
            lines.append("## Caveats")
            for caveat in caveats:
                lines.append(f"- {caveat}")
            lines.append("")

        lines.append(
            "_Sequence cues only — not causation findings. This memo does not determine delay responsibility, entitlement, or compensability._"
        )
        return "\n".join(lines)

    def _html(self, summary: dict[str, Any]) -> str:
        md = self._markdown(summary)
        paragraphs = []
        for block in md.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            if block.startswith("# "):
                paragraphs.append(f"<h1>{html.escape(block[2:])}</h1>")
            elif block.startswith("## "):
                paragraphs.append(f"<h2>{html.escape(block[3:])}</h2>")
            elif block.startswith("- "):
                items = "".join(f"<li>{html.escape(line[2:])}</li>" for line in block.splitlines() if line.startswith("- "))
                paragraphs.append(f"<ul>{items}</ul>")
            elif block.startswith("_") and block.endswith("_"):
                paragraphs.append(f"<p><em>{html.escape(block.strip('_'))}</em></p>")
            else:
                paragraphs.append(f"<p>{html.escape(block).replace(chr(10), '<br/>')}</p>")
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
            "<title>Schedule Review Memo</title></head><body>"
            + "".join(paragraphs)
            + "</body></html>"
        )