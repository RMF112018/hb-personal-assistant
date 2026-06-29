"""Vault template loading and rendering for LLM chat memory notes."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ObsidianMcpConfig
from .llm_chat_classify import LlmChatClassification
from .llm_chat_models import LlmChatExtraction, LlmChatTemplateSelection
from .tools import ObsidianMcpToolError, resolve_safe_path

_TIER1_DIR = "Templates/LLM Chat"
_TIER2_DIR = "Templates"
_UNIVERSAL_FILENAME = "Template - LLM Session.md"
CONFIDENCE_THRESHOLD = 0.55

_DOMAIN_TEMPLATE: dict[str, str] = {
    "fatherhood_parenting": "Template - LLM Session - Fatherhood Parenting.md",
    "child_development": "Template - LLM Session - Fatherhood Parenting.md",
    "personal_health": "Template - LLM Session - Health Wellness.md",
    "mental_wellness": "Template - LLM Session - Health Wellness.md",
    "random_research": "Template - LLM Session - Research Curiosity.md",
    "general_curiosity": "Template - LLM Session - Research Curiosity.md",
    "personal_learning": "Template - LLM Session - Research Curiosity.md",
    "software_dev": "Template - LLM Session - Software Troubleshooting.md",
    "construction_project_management": "Template - LLM Session - Construction PM.md",
    "business_strategy": "Template - LLM Session - Business Strategy.md",
    "writing_content": "Template - LLM Session - Writing Content Resume.md",
    "career_resume": "Template - LLM Session - Writing Content Resume.md",
    "family_life": "Template - LLM Session - Family Home Life.md",
    "home_life": "Template - LLM Session - Family Home Life.md",
    "household_operations": "Template - LLM Session - Family Home Life.md",
    "relationship_communication": "Template - LLM Session - Communication.md",
    "shopping_products": "Template - LLM Session - Purchase Decision.md",
    "travel": "Template - LLM Session - Travel.md",
    "creative_ideation": "Template - LLM Session - Creative Ideation.md",
    "legal_admin": "Template - LLM Session - Legal Financial Admin.md",
    "personal_finance_admin": "Template - LLM Session - Legal Financial Admin.md",
}

_DOMAIN_FOLDER: dict[str, str] = {
    "fatherhood_parenting": "LLM Sessions/Fatherhood",
    "child_development": "LLM Sessions/Fatherhood",
    "personal_health": "LLM Sessions/Health",
    "mental_wellness": "LLM Sessions/Health",
    "random_research": "LLM Sessions/Research",
    "general_curiosity": "LLM Sessions/Research",
    "personal_learning": "LLM Sessions/Research",
    "software_dev": "LLM Sessions/Dev",
    "construction_project_management": "LLM Sessions/Construction",
    "business_strategy": "LLM Sessions/Business",
    "family_life": "LLM Sessions/Family",
    "home_life": "LLM Sessions/Family",
    "household_operations": "LLM Sessions/Family",
    "relationship_communication": "LLM Sessions/Communication",
    "shopping_products": "LLM Sessions/Purchases",
    "travel": "LLM Sessions/Travel",
    "creative_ideation": "LLM Sessions/Creative",
    "writing_content": "LLM Sessions/Writing",
    "career_resume": "LLM Sessions/Writing",
    "legal_admin": "LLM Sessions/Admin",
    "personal_finance_admin": "LLM Sessions/Admin",
}

_DEV_ONLY_SECTIONS = (
    "Commands That Worked",
    "Commands That Failed",
    "Root Cause Analysis",
    "Files / Modules Discussed",
    "Patch Plan",
    "Validation Steps",
)

_UNIVERSAL_TEMPLATE = """---
title: "{{conversation_title}}"
type: "llm-session"
primary_domain: "{{primary_domain}}"
knowledge_type: "{{knowledge_type}}"
sensitivity: "{{sensitivity}}"
raw_transcript_stored: false
plan_id: "{{plan_id}}"
---

# {{conversation_title}}

## Executive Summary

{{executive_summary}}

## Key Takeaways

{{key_takeaways}}

## Decisions / Conclusions

{{decisions_or_conclusions}}

## Action Items

{{action_items}}

## Related Notes

{{related_notes}}
"""

_PLACEHOLDER_RE = re.compile(r"\{\{([a-z0-9_]+)\}\}", re.IGNORECASE)
_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_FILENAME_UNSAFE = re.compile(r'[<>:"/\\|?*]')


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _resolve_template(
    config: ObsidianMcpConfig,
    filename: str,
) -> tuple[str, str, str]:
    """Return (body, vault_relative_path, source_tier)."""
    tier1_rel = f"{_TIER1_DIR}/{filename}"
    try:
        tier1 = resolve_safe_path(config, tier1_rel, must_exist=False)
        if tier1.path.is_file():
            return tier1.path.read_text(encoding="utf-8", errors="replace"), tier1.relative, "llm_chat_subdir"
    except ObsidianMcpToolError:
        pass

    tier2_rel = f"{_TIER2_DIR}/{filename}"
    try:
        tier2 = resolve_safe_path(config, tier2_rel, must_exist=False)
        if tier2.path.is_file():
            return tier2.path.read_text(encoding="utf-8", errors="replace"), tier2.relative, "templates_root"
    except ObsidianMcpToolError:
        pass

    if filename != _UNIVERSAL_FILENAME:
        return _resolve_template(config, _UNIVERSAL_FILENAME)

    return _UNIVERSAL_TEMPLATE, _UNIVERSAL_FILENAME, "internal"


def _load_template_body(config: ObsidianMcpConfig, filename: str) -> tuple[str, str, str]:
    return _resolve_template(config, filename)


def select_template(
    config: ObsidianMcpConfig,
    classification: LlmChatClassification,
    *,
    template_mode: str = "auto",
    target_folder: str | None = None,
) -> LlmChatTemplateSelection:
    domain = classification.primary_domain
    mode = (template_mode or "auto").strip().lower()
    if mode == "universal":
        fallback = True
        filename = _UNIVERSAL_FILENAME
    elif mode == "domain":
        fallback = domain not in _DOMAIN_TEMPLATE
        filename = _DOMAIN_TEMPLATE.get(domain, _UNIVERSAL_FILENAME)
    else:
        fallback = classification.confidence < CONFIDENCE_THRESHOLD or domain not in _DOMAIN_TEMPLATE
        filename = _UNIVERSAL_FILENAME if fallback else _DOMAIN_TEMPLATE[domain]

    folder = target_folder or _DOMAIN_FOLDER.get(domain, config.llm_chat_default_target_folder)
    _body, resolved_rel, source_tier = _resolve_template(config, filename)
    return LlmChatTemplateSelection(
        template_path=resolved_rel,
        template_name=filename,
        target_folder=folder,
        confidence=classification.confidence,
        fallback_used=fallback or source_tier == "internal",
        source_tier=source_tier,
    )


def _strip_dev_sections(body: str) -> str:
    sections = list(_SECTION_RE.finditer(body))
    if not sections:
        return body
    remove_ranges: list[tuple[int, int]] = []
    for idx, match in enumerate(sections):
        title = match.group(1).strip()
        if title not in _DEV_ONLY_SECTIONS:
            continue
        start = match.start()
        end = sections[idx + 1].start() if idx + 1 < len(sections) else len(body)
        remove_ranges.append((start, end))
    if not remove_ranges:
        return body
    out = body
    for start, end in reversed(remove_ranges):
        out = out[:start] + out[end:]
    return out.strip() + "\n"


def _build_context(
    *,
    plan_id: str,
    classification: LlmChatClassification,
    extraction: LlmChatExtraction,
    source: dict[str, Any],
    related_notes: list[str],
    redaction_summary: str,
    classification_summary: str,
    conversation_date: str | None = None,
    hints: dict[str, str] | None = None,
) -> dict[str, str]:
    ctx: dict[str, str] = {
        "conversation_title": extraction.conversation_title,
        "source_platform": str(source.get("platform", "unknown")),
        "source_model": str(source.get("model", "unknown")),
        "source_platform_slug": _slug(str(source.get("platform", "unknown"))),
        "conversation_date": conversation_date or _today(),
        "processed_at": _now_iso(),
        "primary_domain": classification.primary_domain,
        "primary_domain_slug": _slug(classification.primary_domain),
        "knowledge_type": classification.knowledge_type,
        "knowledge_type_slug": _slug(classification.knowledge_type),
        "sensitivity": classification.sensitivity,
        "plan_id": plan_id,
        "source_path": str(source.get("path") or ""),
        "source_hash": str(source.get("hash") or ""),
        "executive_summary": extraction.executive_summary,
        "why_this_matters": extraction.why_this_matters,
        "key_takeaways": extraction.key_takeaways,
        "durable_knowledge": extraction.durable_knowledge,
        "decisions_or_conclusions": extraction.decisions_or_conclusions,
        "action_items": extraction.action_items,
        "open_questions": extraction.open_questions,
        "risks_or_caveats": extraction.risks_or_caveats,
        "useful_details": extraction.useful_details,
        "related_notes": "\n".join(f"- [[{n}]]" for n in related_notes) if related_notes else "- (none)",
        "classification_summary": classification_summary,
        "redaction_summary": redaction_summary,
        "classification_confidence": str(classification.confidence),
        "summary": extraction.executive_summary,
        "topic_title": extraction.conversation_title,
        "created": _today(),
        "updated": _today(),
    }
    if hints:
        for key, value in hints.items():
            if value:
                ctx[key] = value
    ctx.update(extraction.domain_fields)
    return ctx


def render_template(
    template_body: str,
    context: dict[str, str],
    *,
    strip_dev_sections: bool = False,
) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return context.get(key, "")

    rendered = _PLACEHOLDER_RE.sub(repl, template_body)
    if strip_dev_sections:
        rendered = _strip_dev_sections(rendered)
    return rendered


def render_session_note(
    config: ObsidianMcpConfig,
    *,
    plan_id: str,
    classification: LlmChatClassification,
    extraction: LlmChatExtraction,
    selection: LlmChatTemplateSelection,
    source: dict[str, Any],
    related_notes: list[str],
    redaction_summary: str,
    classification_summary: str,
    conversation_date: str | None = None,
    hints: dict[str, str] | None = None,
    include_domain_specific_sections: bool | None = None,
) -> str:
    body, _resolved, _tier = _load_template_body(config, selection.template_name)
    context = _build_context(
        plan_id=plan_id,
        classification=classification,
        extraction=extraction,
        source=source,
        related_notes=related_notes,
        redaction_summary=redaction_summary,
        classification_summary=classification_summary,
        conversation_date=conversation_date,
        hints=hints,
    )
    dev_domains = ("software_dev", "construction_project_management")
    if include_domain_specific_sections is False:
        strip_dev = True
    elif include_domain_specific_sections is True:
        strip_dev = False
    else:
        strip_dev = classification.primary_domain not in dev_domains
    return render_template(body, context, strip_dev_sections=strip_dev)


def sanitize_filename_title(title: str) -> str:
    cleaned = _FILENAME_UNSAFE.sub("", title.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:80] or "LLM Session"


def session_note_path(selection: LlmChatTemplateSelection, title: str) -> str:
    safe = sanitize_filename_title(title)
    return f"{selection.target_folder}/{_today()} - {safe}.md"


def list_available_templates(config: ObsidianMcpConfig) -> list[str]:
    names: set[str] = set()
    for rel_dir in (_TIER1_DIR, _TIER2_DIR):
        try:
            resolved = resolve_safe_path(config, rel_dir, must_exist=False)
        except ObsidianMcpToolError:
            continue
        if resolved.path.is_dir():
            names.update(p.name for p in resolved.path.glob("Template - LLM*.md"))
    return sorted(names)
