"""Phase 08A daily-brief context + review-triage structures (Prompt 11).

The Daily Brief Context Builder (daily_brief_agent) turns broker-retrieved, packet-assessed
context into bounded, source-linked **cards** (attention items, meetings, projects, warnings,
review-required) plus a structured **delivery handoff input** — never HTML, never a
notification. The Review Triage Agent (review_triage_agent) summarizes the review load
grouped by tier, source, project, and urgency. Every structure is metadata-only: no raw
bodies/document text/calendar payloads/prompts/responses/URLs/secrets — enforced by a
field validator that rejects the forbidden raw reference fields.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, field_validator

from ..reasoning import FORBIDDEN_REFERENCE_FIELDS

CardKind = Literal[
    "attention_item",
    "meeting",
    "project",
    "warning",
    "review_required",
]
HANDOFF_SECTIONS: tuple[str, ...] = (
    "priority_actions",
    "waiting_on",
    "meeting_prep",
    "file_review_queue",
    "project_signals",
)


def _reject_forbidden_refs(value: list[dict[str, str]]) -> list[dict[str, str]]:
    """Reject any source-ref dict that names a forbidden raw field (no leakage)."""
    for ref in value:
        forbidden = set(ref) & FORBIDDEN_REFERENCE_FIELDS
        if forbidden:
            raise ValueError(f"forbidden raw field(s) in source_ref: {sorted(forbidden)}")
    return value


class _SourceLinked(BaseModel):
    """Mixin base: a metadata-only structure carrying redacted source references."""

    model_config = {"extra": "forbid"}

    @field_validator("source_refs", check_fields=False)
    @classmethod
    def _no_forbidden_fields(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        return _reject_forbidden_refs(value)


class AttentionItemCard(_SourceLinked):
    """A priority, advisory action surfaced for attention (tier 1/2 actionable item)."""

    title_redacted: str
    project_key: str | None = None
    review_tier: int = 2
    review_tier_reason_code: str = "T2_REVIEW_RECOMMENDED"
    confidence_class: str = "unknown"
    urgency: str = "low"
    source_refs: list[dict[str, str]] = []


class MeetingCard(_SourceLinked):
    """A meeting-prep card. Empty when no meeting read model is available (degrades)."""

    title_redacted: str
    project_key: str | None = None
    review_tier: int = 3
    review_tier_reason_code: str = "T3_MANDATORY_REVIEW"
    source_refs: list[dict[str, str]] = []


class ProjectCard(_SourceLinked):
    """A per-project rollup: item counts, review load, and aggregated source refs."""

    project_key: str
    item_count: int = 0
    review_required_count: int = 0
    stale_unknown_count: int = 0
    max_review_tier: int = 3
    source_refs: list[dict[str, str]] = []


class WarningCard(_SourceLinked):
    """A degradation signal: a stale/unknown or conflicting source needing attention."""

    warning_class: str  # "stale_unknown" | "conflict"
    summary_redacted: str
    project_key: str | None = None
    review_tier: int = 3
    source_refs: list[dict[str, str]] = []


class ReviewRequiredCard(_SourceLinked):
    """A Tier-3 item that must be reviewed before it can be treated as fact/actioned."""

    title_redacted: str
    project_key: str | None = None
    review_tier: int = 3
    review_tier_reason_code: str = "T3_MANDATORY_REVIEW"
    source_refs: list[dict[str, str]] = []

    @field_validator("review_tier")
    @classmethod
    def _must_be_tier_3(cls, value: int) -> int:
        if value != 3:
            raise ValueError("review_required cards are Tier 3 by definition")
        return value


class ReviewLoadStatus(BaseModel):
    """Review Triage Agent output: review load grouped by tier/source/project/urgency."""

    total_review_items: int = 0
    by_tier: dict[str, int] = {}
    by_source_family: dict[str, int] = {}
    by_project: dict[str, int] = {}
    by_urgency: dict[str, int] = {}
    tier_3_count: int = 0
    mandatory_review_count: int = 0
    degradation_mode: str = "none"
    warnings: list[str] = []

    model_config = {"extra": "forbid"}


class HandoffLine(_SourceLinked):
    """One structured, source-linked delivery line (no rendered prose, no HTML)."""

    title_redacted: str
    review_tier: int = 3
    source_refs: list[dict[str, str]] = []


class DeliveryHandoffInput(BaseModel):
    """Structured, source-linked handoff input. Never HTML; never emits a notification."""

    sections: dict[str, list[HandoffLine]] = {}
    source_refs: list[dict[str, str]] = []
    review_tier: int = 3
    degradation_mode: str = "none"
    output_format: Literal["structured_data"] = "structured_data"
    notification_emitted: bool = False

    model_config = {"extra": "forbid"}

    @field_validator("source_refs")
    @classmethod
    def _no_forbidden_fields(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        return _reject_forbidden_refs(value)

    @field_validator("notification_emitted")
    @classmethod
    def _never_notifies(cls, value: bool) -> bool:
        if value:
            raise ValueError("daily brief never emits notifications (handoff input only)")
        return value


class DailyBriefContext(BaseModel):
    """Bounded, source-linked daily-brief context package (assembled, never rendered)."""

    brief_date: str
    brief_run_id: str | None = None
    project_count: int = 0
    source_ref_count: int = 0
    review_required_count: int = 0
    stale_unknown_count: int = 0
    source_coverage: float = 0.0
    review_tier_counts: dict[str, int] = {}
    context_quality_class: str = "insufficient"
    degradation_mode: str = "blocked"
    review_tier: int = 3
    review_tier_reason_code: str = "T3_MANDATORY_REVIEW"
    research_packet_id: str | None = None
    attention_cards: list[AttentionItemCard] = []
    meeting_cards: list[MeetingCard] = []
    project_cards: list[ProjectCard] = []
    warning_cards: list[WarningCard] = []
    review_required_cards: list[ReviewRequiredCard] = []
    review_load: ReviewLoadStatus = ReviewLoadStatus()
    delivery_handoff: DeliveryHandoffInput = DeliveryHandoffInput()
    source_refs: list[dict[str, str]] = []
    warnings: list[str] = []
    status: str = "blocked"

    model_config = {"extra": "forbid"}

    @field_validator("source_refs")
    @classmethod
    def _no_forbidden_fields(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        return _reject_forbidden_refs(value)


# --- Prompt 12: generation / evaluation / delivery-handoff payloads -------------------


class NotificationSummary(BaseModel):
    """Data-only notification summary (NEVER emitted here; no macOS notification)."""

    title_redacted: str = ""
    attention_count: int = 0
    review_required_count: int = 0
    warning_count: int = 0
    project_count: int = 0
    eligible: bool = False
    channel: Literal["local_only"] = "local_only"
    emitted: bool = False

    model_config = {"extra": "forbid"}

    @field_validator("emitted")
    @classmethod
    def _never_emitted(cls, value: bool) -> bool:
        if value:
            raise ValueError("notification summary is data-only; never emitted")
        return value


class HtmlRenderingData(BaseModel):
    """Structured render-data for a future HTML renderer. No HTML is produced here."""

    title_redacted: str = ""
    sections: dict[str, list[HandoffLine]] = {}
    source_refs: list[dict[str, str]] = []
    format: Literal["render_data"] = "render_data"
    rendered: bool = False

    model_config = {"extra": "forbid"}

    @field_validator("source_refs")
    @classmethod
    def _no_forbidden_fields(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        return _reject_forbidden_refs(value)

    @field_validator("rendered")
    @classmethod
    def _never_rendered(cls, value: bool) -> bool:
        if value:
            raise ValueError("HTML rendering data is structured-only; no HTML is produced")
        return value


class DeliveryHandoffPayload(BaseModel):
    """Phase 08B delivery-handoff payload — local-only, source-linked, never delivered."""

    phase: Literal["08B"] = "08B"
    brief_run_id: str | None = None
    brief_date: str
    evaluation_run_id: str | None = None
    eligible_for_delivery: bool = False
    review_tier: int = 3
    degradation_mode: str = "blocked"
    sections: dict[str, list[HandoffLine]] = {}
    source_refs: list[dict[str, str]] = []
    notification_summary: NotificationSummary = NotificationSummary()
    html_rendering: HtmlRenderingData = HtmlRenderingData()
    local_only: bool = True
    external_delivery_performed: bool = False

    model_config = {"extra": "forbid"}

    @field_validator("source_refs")
    @classmethod
    def _no_forbidden_fields(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        return _reject_forbidden_refs(value)

    @field_validator("local_only")
    @classmethod
    def _must_be_local_only(cls, value: bool) -> bool:
        if not value:
            raise ValueError("delivery handoff payload is local-only")
        return value

    @field_validator("external_delivery_performed")
    @classmethod
    def _no_external_delivery(cls, value: bool) -> bool:
        if value:
            raise ValueError("no external delivery is ever performed")
        return value


class DailyBriefResult(BaseModel):
    """Daily Brief Agent (daily_brief_agent) generate/evaluate/apply outcome."""

    brief_date: str
    brief_run_id: str | None = None
    mode: str = "dry_run"
    status: str = "blocked"
    applied: bool = False
    apply_blocked_reason: str | None = None
    evaluation: dict[str, Any] = {}
    evaluation_run_id: str | None = None
    eligible_for_delivery: bool = False
    output_written: bool = False
    output_path_redacted: str | None = None
    output_path_hash: str | None = None
    delivery_handoff: DeliveryHandoffPayload
    source_ref_count: int = 0
    source_coverage: float = 0.0
    review_tier_counts: dict[str, int] = {}
    review_tier: int = 3
    degradation_mode: str = "blocked"
    warnings: list[str] = []

    model_config = {"extra": "forbid"}
