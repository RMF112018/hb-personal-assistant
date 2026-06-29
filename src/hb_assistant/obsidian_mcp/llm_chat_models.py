"""Structured models for LLM chat memory tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

LlmChatDomain = str
LlmChatKnowledgeType = str
LlmChatSensitivity = str


@dataclass
class LlmChatSource:
    kind: str = "inline"
    platform: str = "unknown"
    model: str = "unknown"
    path: str | None = None
    hash: str | None = None
    char_count: int = 0
    truncated: bool = False
    redaction_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LlmChatClassification:
    primary_domain: LlmChatDomain
    secondary_domains: list[str]
    knowledge_type: LlmChatKnowledgeType
    sensitivity: LlmChatSensitivity
    confidence: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LlmChatExtraction:
    conversation_title: str
    executive_summary: str
    why_this_matters: str
    key_takeaways: str
    durable_knowledge: str
    decisions_or_conclusions: str
    action_items: str
    open_questions: str
    risks_or_caveats: str
    useful_details: str
    tags: list[str]
    domain_fields: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LlmChatTemplateSelection:
    template_path: str
    template_name: str
    target_folder: str
    confidence: float
    fallback_used: bool
    source_tier: str = "internal"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LlmChatPlannedNote:
    action_id: str
    action: Literal["create_session_note"]
    target_path: str
    preview: str
    op: Literal["create"] = "create"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LlmChatPlannedUpdate:
    action_id: str
    action: Literal["update_topic_memory"]
    target_path: str
    expected_sha256: str | None
    preview: str
    op: Literal["patch"] = "patch"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LlmChatPlan:
    plan_id: str
    plan_kind: Literal["session_note", "topic_memory"]
    created_at: str
    source: LlmChatSource
    classification: LlmChatClassification
    extraction: LlmChatExtraction
    template_selection: LlmChatTemplateSelection | None
    allowed_actions: list[str]
    actions: list[dict[str, Any]]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.template_selection is not None:
            data["template_selection"] = self.template_selection.to_dict()
        return data


@dataclass
class LlmChatApplyResult:
    plan_id: str
    applied: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    failed: list[dict[str, Any]]
    counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
