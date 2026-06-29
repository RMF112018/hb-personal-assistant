"""Deterministic extraction from LLM chat transcripts."""

from __future__ import annotations

import re
from typing import Any

from .llm_chat_classify import LlmChatClassification
from .llm_chat_models import LlmChatExtraction

_MAX_TAGS = 12
_TITLE_MAX = 80
_BULLET_RE = re.compile(r"^[\-\*\d+\.]\s+", re.MULTILINE)
_DECISION_MARKERS = ("decided", "decision:", "conclusion:", "we'll go with", "chosen")
_ACTION_MARKERS = ("action item", "todo", "next step", "follow up", "follow-up", "task:")
_QUESTION_RE = re.compile(r"\?\s*$", re.MULTILINE)


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and len(stripped) > 3:
            return stripped[:_TITLE_MAX]
    return "LLM Session"


def _sentences(text: str, limit: int = 3) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return [p.strip() for p in parts if p.strip()][:limit]


def _bullet_lines(text: str, markers: tuple[str, ...], limit: int = 8) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        lower = line.lower().strip()
        if not lower:
            continue
        if any(m in lower for m in markers) or _BULLET_RE.match(line.strip()):
            cleaned = _BULLET_RE.sub("", line.strip())
            if cleaned and cleaned not in items:
                items.append(cleaned[:240])
        if len(items) >= limit:
            break
    return items


def _format_bullets(items: list[str]) -> str:
    if not items:
        return "- (none extracted)"
    return "\n".join(f"- {item}" for item in items)


def _normalize_tag(tag: str) -> str:
    norm = re.sub(r"[\s_]+", "-", tag.strip().lower())
    norm = re.sub(r"[^a-z0-9/-]", "", norm)
    return norm.strip("-/")


def _extract_tags(text: str, classification: LlmChatClassification) -> list[str]:
    tags = {"llm-session", f"domain/{classification.primary_domain.replace('_', '-')}"}
    tags.add(f"type/{classification.knowledge_type.replace('_', '-')}")
    for word in re.findall(r"\b[A-Za-z]{5,}\b", text.lower()):
        if word in {"about", "there", "would", "could", "should", "their", "which"}:
            continue
        norm = _normalize_tag(word)
        if norm:
            tags.add(norm)
        if len(tags) >= _MAX_TAGS:
            break
    return sorted(tags)[:_MAX_TAGS]


def _domain_fields(text: str, classification: LlmChatClassification) -> dict[str, str]:
    domain = classification.primary_domain
    fields: dict[str, str] = {}
    if domain == "software_dev":
        fields["technical_context"] = _format_bullets(_sentences(text, 2))
        fields["symptoms_or_errors"] = _format_bullets(_bullet_lines(text, ("error", "exception", "failed", "traceback")))
        fields["commands_that_worked"] = _format_bullets(_bullet_lines(text, ("$ ", "npm ", "pytest", "python ", "git ")))
        fields["commands_that_failed"] = "- (none extracted)"
        fields["root_cause_analysis"] = _format_bullets(_bullet_lines(text, ("root cause", "because", "caused by")))
        fields["files_or_modules_discussed"] = _format_bullets(_bullet_lines(text, (".py", ".ts", ".tsx", "src/", "module")))
        fields["patch_plan"] = _format_bullets(_bullet_lines(text, ("fix", "patch", "change", "update")))
        fields["validation_steps"] = _format_bullets(_bullet_lines(text, ("test", "verify", "validate", "pytest")))
        fields["follow_up_work"] = _format_bullets(_bullet_lines(text, _ACTION_MARKERS))
        fields["repo_hint"] = ""
        fields["module_hint"] = ""
    elif domain in ("fatherhood_parenting", "child_development"):
        fields["summary"] = _format_bullets(_sentences(text, 2))
        fields["parenting_context"] = _format_bullets(_bullet_lines(text, ("parent", "child", "bedtime", "routine")))
        fields["child_development_takeaways"] = _format_bullets(_bullet_lines(text, ("development", "milestone", "learn")))
        fields["approaches_discussed"] = _format_bullets(_bullet_lines(text, ("try", "approach", "strategy")))
        fields["what_to_try_next"] = _format_bullets(_bullet_lines(text, _ACTION_MARKERS))
    elif domain in ("personal_health", "mental_wellness"):
        fields["summary"] = _format_bullets(_sentences(text, 2))
        fields["health_context"] = _format_bullets(_bullet_lines(text, ("symptom", "sleep", "exercise", "stress")))
        fields["research_findings"] = _format_bullets(_sentences(text, 4))
        fields["options_discussed"] = _format_bullets(_bullet_lines(text, ("option", "consider", "might")))
        fields["questions_for_professional"] = _format_bullets(_bullet_lines(text, ("ask doctor", "provider", "?")))
    elif domain in ("random_research", "general_curiosity", "personal_learning"):
        fields["research_question"] = _first_nonempty_line(text)
        fields["summary"] = _format_bullets(_sentences(text, 3))
        fields["key_findings"] = _format_bullets(_sentences(text, 5))
        fields["sources_or_references"] = "- (conversation-derived; verify independently)"
        fields["open_threads"] = _format_bullets(_bullet_lines(text, ("?", "unclear", "more research")))
    return fields


def extract_memory(text: str, classification: LlmChatClassification) -> LlmChatExtraction:
    title = _first_nonempty_line(text)
    summary_sents = _sentences(text, 3)
    decisions = _bullet_lines(text, _DECISION_MARKERS)
    actions = _bullet_lines(text, _ACTION_MARKERS)
    questions = [line.strip() for line in _QUESTION_RE.findall(text)][:5]
    if not questions:
        questions = _bullet_lines(text, ("?", "unclear", "open question"))

    return LlmChatExtraction(
        conversation_title=title,
        executive_summary=_format_bullets(summary_sents),
        why_this_matters=_format_bullets(_sentences(text, 2)),
        key_takeaways=_format_bullets(summary_sents),
        durable_knowledge=_format_bullets(_sentences(text, 5)),
        decisions_or_conclusions=_format_bullets(decisions),
        action_items=_format_bullets(actions),
        open_questions=_format_bullets(questions),
        risks_or_caveats="- Verify independently; not professional advice.",
        useful_details=_format_bullets(_sentences(text, 4)),
        tags=_extract_tags(text, classification),
        domain_fields=_domain_fields(text, classification),
    )


def summarize_text(text: str, *, max_bullets: int = 5) -> str:
    return _format_bullets(_sentences(text, max_bullets))


def extract_decisions(text: str) -> list[str]:
    return _bullet_lines(text, _DECISION_MARKERS)


def extract_action_items(text: str) -> list[str]:
    return _bullet_lines(text, _ACTION_MARKERS)
