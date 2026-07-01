"""Schedule PM memo export — Markdown and HTML from hub read model."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from .project_schedule_narrative_qa import validate_summary

_PRINT_CSS = """
body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a; margin: 2rem; line-height: 1.5; }
h1, h2, h3 { font-family: Helvetica, Arial, sans-serif; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }
th { background: #f4f4f4; }
.disclaimer { margin-top: 2rem; font-size: 0.85rem; color: #555; }
@media print {
  body { margin: 0.75in; }
  h2 { page-break-after: avoid; }
  table { page-break-inside: avoid; }
}
"""


def _export_comparison_context_complete(ctx: dict[str, Any] | None) -> bool:
    if not ctx:
        return False
    required = (
        "project_key",
        "as_of",
        "comparison_basis",
        "comparison_label",
        "source_model",
        "slot_key",
        "slot_label",
        "current_schedule_version_key",
        "comparison_schedule_version_key",
        "baseline_schedule_version_key",
    )
    return all(ctx.get(key) not in (None, "") for key in required)


class ProjectScheduleMemoService:
    def build_export(
        self,
        summary: dict[str, Any],
        *,
        export_format: str = "markdown",
        variant: str = "standard",
        scope: str = "full",
    ) -> dict[str, Any]:
        fmt = (export_format or "markdown").lower()
        if fmt not in {"markdown", "html"}:
            raise ValueError("unsupported_export_format")
        export_variant = variant if variant in {"standard", "executive"} else "standard"
        export_scope = scope if scope in {"full", "review_items"} else "full"
        export_ctx = summary.get("export_comparison_context")
        qa = validate_summary(summary)
        export_warnings: list[str] = []
        export_mode = "narrative"
        if not qa.get("passed"):
            if _export_comparison_context_complete(export_ctx):
                export_warnings.append(
                    "Narrative QA unavailable; deterministic export generated."
                )
                export_mode = "deterministic_fallback"
            else:
                return {
                    "available": False,
                    "reason": "narrative_qa_failed",
                    "narrative_qa": qa,
                    "advisory_posture": qa.get("advisory_posture"),
                    "comparison_basis": summary.get("comparison_basis"),
                }
        if fmt == "markdown":
            if export_mode == "deterministic_fallback":
                body = self._deterministic_named_fallback_markdown(
                    summary, qa=qa, variant=export_variant, scope=export_scope, warnings=export_warnings
                )
            else:
                body = self._markdown(summary, qa=qa, variant=export_variant, scope=export_scope)
        else:
            if export_mode == "deterministic_fallback":
                body = self._html_from_markdown(
                    self._deterministic_named_fallback_markdown(
                        summary, qa=qa, variant=export_variant, scope=export_scope, warnings=export_warnings
                    )
                )
            else:
                body = (
                    self._executive_html(summary, qa=qa, scope=export_scope)
                    if export_variant == "executive"
                    else self._html(summary, qa=qa, variant=export_variant, scope=export_scope)
                )
        project_key = str(summary.get("project_key") or "project")
        as_of = str(summary.get("as_of_date") or datetime.now(timezone.utc).date().isoformat())
        suffix = "executive" if export_variant == "executive" and fmt == "html" else "memo"
        ext = "md" if fmt == "markdown" else "html"
        filename = f"schedule-{suffix}-{project_key}-{as_of}.{ext}"
        content_type = "text/markdown; charset=utf-8" if fmt == "markdown" else "text/html; charset=utf-8"
        return {
            "available": True,
            "format": fmt,
            "variant": export_variant,
            "scope": export_scope,
            "filename": filename,
            "content_type": content_type,
            "body": body,
            "advisory_posture": qa.get("advisory_posture"),
            "narrative_qa": qa,
            "export_mode": export_mode,
            "export_warnings": export_warnings,
            "comparison_basis": summary.get("comparison_basis"),
            "export_comparison_context": export_ctx,
            "analytics_trust": summary.get("analytics_trust"),
        }

    @staticmethod
    def _analytics_trust_section_lines(trust: dict[str, Any]) -> list[str]:
        if not trust:
            return []
        lines = [
            "## Analytics Trust",
            "",
            f"- Status: {trust.get('analytics_trust_status') or 'unknown'}",
        ]
        reasons = trust.get("trust_reasons") or []
        if reasons:
            lines.append("- Trust notes:")
            for reason in reasons[:8]:
                lines.append(f"  - {reason}")
        limitations = trust.get("capability_limitations") or []
        if limitations:
            lines.append("- Capability limitations:")
            for item in limitations[:4]:
                lines.append(f"  - {item}")
        if trust.get("failure_message_redacted"):
            lines.append(f"- CPM note: {trust.get('failure_message_redacted')}")
        lines.append("")
        return lines

    @staticmethod
    def _comparison_context_section_lines(ctx: dict[str, Any]) -> list[str]:
        return [
            "## Comparison Context",
            "",
            f"- Comparison Basis: {ctx.get('comparison_label') or ctx.get('comparison_basis')}",
            f"- Source Model: {ctx.get('source_model')}",
            f"- Slot: {ctx.get('slot_label')} ({ctx.get('slot_key')})",
            f"- Current Schedule Version: {ctx.get('current_schedule_version_key')}",
            f"- Comparison Schedule Version: {ctx.get('comparison_schedule_version_key')}",
            f"- Baseline Schedule Version: {ctx.get('baseline_schedule_version_key')}",
            f"- Current Data Date: {ctx.get('current_data_date') or '—'}",
            f"- Comparison Data Date: {ctx.get('comparison_data_date') or '—'}",
            "",
        ]

    def _deterministic_named_fallback_markdown(
        self,
        summary: dict[str, Any],
        *,
        qa: dict[str, Any] | None,
        variant: str,
        scope: str,
        warnings: list[str],
    ) -> str:
        ctx = summary.get("export_comparison_context") or {}
        change_impact = summary.get("change_impact") or {}
        movement = change_impact.get("direct_remaining_changes", {}).get("summary", {})
        later = int(movement.get("finish_moved_later_count") or 0)
        earlier = int(movement.get("finish_moved_earlier_count") or 0)
        worsened = int(movement.get("worsened_float_count") or 0)
        lines = [
            f"# Schedule Review Memo — {summary.get('project_display_name') or summary.get('project_key')}",
            "",
            f"As of {summary.get('as_of_date')}",
            "",
        ]
        lines.extend(self._comparison_context_section_lines(ctx))
        for warning in warnings:
            lines.extend([f"> **Warning:** {warning}", ""])
        lines.extend(
            [
                "## Deterministic Movement Summary",
                f"- Remaining activities moved later: {later}",
                f"- Remaining activities moved earlier: {earlier}",
                f"- Activities with worsened float: {worsened}",
                "",
            ]
        )
        driver_hub = summary.get("change_driver_analysis") or {}
        prior = driver_hub.get("baseline") or driver_hub.get("prior_update") or driver_hub
        if prior.get("available"):
            top = (prior.get("top_drivers") or [None])[0] or {}
            lines.extend(
                [
                    "## Top Candidate Driver",
                    f"- Activity: {top.get('activity_name') or top.get('activity_id') or '—'}",
                    f"- Downstream moved later: {top.get('downstream_moved_later_count') or 0}",
                    "",
                ]
            )
        moved = [
            m
            for m in (summary.get("milestones") or {}).get("items") or []
            if int(m.get("movement_days") or 0) != 0
        ]
        if moved:
            lines.extend(["## Milestone Impacts", ""])
            for item in moved[:12]:
                lines.append(
                    f"- {item.get('activity_name') or item.get('activity_id')}: {item.get('movement_days')} days"
                )
            lines.append("")
        review_items = self._review_items_for_export(summary, summary.get("review_workbench") or {})
        if review_items:
            lines.extend(self._review_items_section_lines(review_items, heading="## Review Workbench"))
        lines.append(
            "_Sequence cues only — not causation findings. This memo does not determine delay responsibility, entitlement, or compensability._"
        )
        return "\n".join(lines)

    def _html_from_markdown(self, md: str) -> str:
        paragraphs = []
        for block in md.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            if block.startswith("# "):
                paragraphs.append(f"<h1>{html.escape(block[2:])}</h1>")
            elif block.startswith("## "):
                paragraphs.append(f"<h2>{html.escape(block[3:])}</h2>")
            elif block.startswith("### "):
                paragraphs.append(f"<h3>{html.escape(block[4:])}</h3>")
            elif block.startswith("- "):
                items = "".join(
                    f"<li>{html.escape(line[2:])}</li>" for line in block.splitlines() if line.startswith("- ")
                )
                paragraphs.append(f"<ul>{items}</ul>")
            elif block.startswith("> "):
                paragraphs.append(f"<p><em>{html.escape(block[2:])}</em></p>")
            elif block.startswith("_") and block.endswith("_"):
                paragraphs.append(f"<p class='disclaimer'><em>{html.escape(block.strip('_'))}</em></p>")
            else:
                paragraphs.append(f"<p>{html.escape(block).replace(chr(10), '<br/>')}</p>")
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
            "<title>Schedule Review Memo</title>"
            f"<style>{_PRINT_CSS}</style></head><body>"
            + "".join(paragraphs)
            + "</body></html>"
        )

    def _markdown(
        self,
        summary: dict[str, Any],
        *,
        qa: dict[str, Any] | None = None,
        variant: str = "standard",
        scope: str = "full",
    ) -> str:
        if scope == "review_items":
            return self._review_items_markdown(summary)
        story = summary.get("schedule_story") or {}
        command = summary.get("command_summary") or {}
        workbench = summary.get("review_workbench") or {}
        driver_hub = summary.get("change_driver_analysis") or {}
        if _export_comparison_context_complete(summary.get("export_comparison_context")):
            prior = driver_hub.get("baseline") or driver_hub
        else:
            prior = driver_hub.get("prior_update") or driver_hub
        milestones = summary.get("milestones") or {}
        remaining_health = summary.get("remaining_health") or {}
        cpm = summary.get("computed_cpm") or {}
        lines = [
            f"# Schedule Review Memo — {summary.get('project_display_name') or summary.get('project_key')}",
            "",
            f"As of {summary.get('as_of_date')}",
            "",
        ]
        export_ctx = summary.get("export_comparison_context")
        if _export_comparison_context_complete(export_ctx):
            lines.extend(self._comparison_context_section_lines(export_ctx))
        analytics_trust = summary.get("analytics_trust") or {}
        if analytics_trust:
            lines.extend(self._analytics_trust_section_lines(analytics_trust))
        if variant == "executive":
            lines.extend(
                [
                    "## Executive Summary",
                    str(story.get("headline") or "Schedule update ready for review."),
                    str(story.get("synopsis") or ""),
                    "",
                    f"- Forecast finish: {command.get('forecast_finish') or '—'} ({command.get('forecast_finish_delta_days')} days vs prior)",
                    f"- Remaining activities: {command.get('remaining_activity_count') or '—'}",
                    f"- Negative float (remaining): {command.get('negative_float_remaining_count') or 0}",
                    "",
                ]
            )
        lines.extend(
            [
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
        )
        moved = [m for m in (milestones.get("items") or []) if int(m.get("movement_days") or 0) > 0]
        if moved:
            lines.extend(["## Milestone Impacts", ""])
            for item in moved[:12]:
                lines.append(
                    f"- {item.get('activity_name') or item.get('activity_id')}: +{item.get('movement_days')} days"
                )
            lines.append("")

        float_pressure = remaining_health.get("float_pressure") or {}
        lines.extend(
            [
                "## Float / CPM Pressure",
                f"- Negative float remaining: {float_pressure.get('negative_float_count') or command.get('negative_float_remaining_count') or 0}",
                f"- Near-critical remaining: {float_pressure.get('near_critical_count') or command.get('near_critical_remaining_count') or 0}",
                f"- Computed CPM critical remaining: {cpm.get('critical_remaining_count') or command.get('critical_remaining_count') or 0}",
                "",
            ]
        )

        review_items = self._review_items_for_export(summary, workbench)
        if review_items:
            lines.extend(self._review_items_section_lines(review_items, heading="## Review Workbench"))

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

        agenda = self._suggested_agenda_lines(review_items)
        if agenda:
            lines.extend(agenda)

        appendix = self._evidence_appendix_lines(prior)
        if appendix and variant == "executive":
            lines.extend(appendix)

        caveats = story.get("caveats") or []
        if caveats:
            lines.append("## Caveats")
            for caveat in caveats:
                lines.append(f"- {caveat}")
            lines.append("")

        source_basis = (qa or {}).get("source_basis") or {}
        if source_basis:
            lines.extend(["", "## Source Basis", ""])
            for metric, path in sorted(source_basis.items()):
                lines.append(f"- {metric}: `{path}`")

        lines.append(
            "_Sequence cues only — not causation findings. This memo does not determine delay responsibility, entitlement, or compensability._"
        )
        return "\n".join(lines)

    def _review_items_markdown(self, summary: dict[str, Any]) -> str:
        workbench = summary.get("review_workbench") or {}
        review_items = self._review_items_for_export(summary, workbench)
        lines = [
            f"# Schedule Review Items — {summary.get('project_display_name') or summary.get('project_key')}",
            "",
            f"As of {summary.get('as_of_date')}",
            "",
        ]
        lines.extend(self._review_items_section_lines(review_items, heading="## Review Items"))
        lines.extend(self._suggested_agenda_lines(review_items))
        lines.append(
            "_Sequence cues only — not causation findings. This memo does not determine delay responsibility, entitlement, or compensability._"
        )
        return "\n".join(lines)

    def _review_items_for_export(
        self,
        summary: dict[str, Any],
        workbench: dict[str, Any],
    ) -> list[dict[str, Any]]:
        persisted = summary.get("persisted_review_items")
        if isinstance(persisted, list) and persisted:
            return persisted
        if workbench.get("persisted"):
            return list(workbench.get("items") or workbench.get("preview") or [])
        return list(workbench.get("preview") or [])

    @staticmethod
    def _review_items_section_lines(items: list[dict[str, Any]], *, heading: str) -> list[str]:
        if not items:
            return []
        lines = [heading, ""]
        for item in items:
            lineage = item.get("lineage")
            suffix = f" ({lineage})" if lineage else ""
            lines.append(
                f"- [{item.get('review_status')}] P{item.get('priority')} {item.get('item_title')}{suffix}"
            )
            if item.get("pm_notes"):
                lines.append(f"  - Notes: {item['pm_notes']}")
        lines.append("")
        return lines

    @staticmethod
    def _suggested_agenda_lines(items: list[dict[str, Any]]) -> list[str]:
        open_items = [
            item
            for item in items
            if str(item.get("review_status")) in {"open", "watching"}
        ]
        open_items.sort(key=lambda row: (-int(row.get("priority") or 0), str(row.get("item_title") or "")))
        if not open_items:
            return []
        lines = ["## Suggested Review Agenda", ""]
        for index, item in enumerate(open_items[:12], start=1):
            lines.append(f"{index}. {item.get('item_title')} [{item.get('review_status')}]")
        lines.append("")
        return lines

    @staticmethod
    def _evidence_appendix_lines(prior: dict[str, Any]) -> list[str]:
        drilldowns = prior.get("review_drilldowns") or {}
        lines = ["## Evidence Appendix", ""]
        added = False
        for key, preview in drilldowns.items():
            rows = list(preview.get("items") or [])[:8]
            if not rows:
                continue
            added = True
            lines.append(f"### {key.replace('_', ' ').title()}")
            for row in rows:
                label = row.get("activity_name") or row.get("activity_id") or row.get("title") or "—"
                delta = row.get("finish_delta_days")
                detail = f" ({delta:+}d)" if delta is not None else ""
                lines.append(f"- {label}{detail}")
            lines.append("")
        return lines if added else []

    def _html(
        self,
        summary: dict[str, Any],
        *,
        qa: dict[str, Any] | None = None,
        variant: str = "standard",
        scope: str = "full",
    ) -> str:
        md = self._markdown(summary, qa=qa, variant=variant, scope=scope)
        paragraphs = []
        for block in md.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            if block.startswith("# "):
                paragraphs.append(f"<h1>{html.escape(block[2:])}</h1>")
            elif block.startswith("## "):
                paragraphs.append(f"<h2>{html.escape(block[3:])}</h2>")
            elif block.startswith("### "):
                paragraphs.append(f"<h3>{html.escape(block[4:])}</h3>")
            elif block.startswith("- "):
                items = "".join(f"<li>{html.escape(line[2:])}</li>" for line in block.splitlines() if line.startswith("- "))
                paragraphs.append(f"<ul>{items}</ul>")
            elif block.startswith("_") and block.endswith("_"):
                paragraphs.append(f"<p class='disclaimer'><em>{html.escape(block.strip('_'))}</em></p>")
            else:
                paragraphs.append(f"<p>{html.escape(block).replace(chr(10), '<br/>')}</p>")
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
            "<title>Schedule Review Memo</title>"
            f"<style>{_PRINT_CSS}</style></head><body>"
            + "".join(paragraphs)
            + "</body></html>"
        )

    def _executive_html(
        self,
        summary: dict[str, Any],
        *,
        qa: dict[str, Any] | None = None,
        scope: str = "full",
    ) -> str:
        return self._html(summary, qa=qa, variant="executive", scope=scope)