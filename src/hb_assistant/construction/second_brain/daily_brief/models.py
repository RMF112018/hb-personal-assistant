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


# --- Phase 08B Prompt 01: deterministic render-view contract --------------------------


class RenderViewLine(_SourceLinked):
    """One render-ready line: redacted title, tier, and safe source refs (no raw content)."""

    title_redacted: str
    review_tier: int = 3
    review_tier_reason_code: str | None = None
    source_refs: list[dict[str, str]] = []


class RenderViewSection(BaseModel):
    """A render-ready section: a named, ordered list of lines plus its line count."""

    name: str
    lines: list[RenderViewLine] = []
    line_count: int = 0

    model_config = {"extra": "forbid"}


class DailyBriefRenderView(BaseModel):
    """Deterministic, render-ready view the future HTML renderer consumes.

    Built deterministically from a (persisted or in-memory) delivery handoff. Sections are
    ordered by ``HANDOFF_SECTIONS``; lines preserve handoff order. No raw source content is
    carried and no HTML is produced here — ``rendered`` is always False (a future renderer
    flips it only when it actually emits HTML, which this contract never does).
    """

    brief_date: str
    brief_run_id: str | None = None
    title_redacted: str = ""
    generated_utc: str = ""
    degradation_mode: str = "blocked"
    context_quality_class: str = "insufficient"
    review_tier: int = 3
    sections: list[RenderViewSection] = []
    section_counts: dict[str, int] = {}
    total_line_count: int = 0
    review_required_count: int = 0
    stale_unknown_count: int = 0
    source_ref_count: int = 0
    format: Literal["render_view"] = "render_view"
    rendered: bool = False

    model_config = {"extra": "forbid"}

    @field_validator("rendered")
    @classmethod
    def _never_rendered(cls, value: bool) -> bool:
        if value:
            raise ValueError("render view is a structured contract; no HTML is produced")
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


# --- Prompt 13: launchd scheduling dry-run install preview -----------------------------


class LaunchdSchedulePreview(BaseModel):
    """Dry-run-only launchd install preview for the scheduled daily brief.

    A documentation/preview artifact: no plist is written and ``launchctl`` is never
    invoked. All paths are redacted (``$HOME`` -> ``~``); logs live outside the repo.
    """

    label: str
    hour: int = 0
    minute: int = 0
    day_offset: int = 0
    command_mode: str = "apply"
    program_arguments_redacted: list[str] = []
    plist: dict[str, Any] = {}
    plist_path_redacted: str = ""
    log_out_redacted: str = ""
    log_err_redacted: str = ""
    log_dir_redacted: str = ""
    logs_outside_repo: bool = True
    manual_install_commands: list[str] = []
    readiness: dict[str, Any] = {}
    phase_08b_handoff: str = ""
    dry_run_install_only: bool = True
    external_writeback_performed: bool = False
    preview_id: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("program_arguments_redacted")
    @classmethod
    def _args_have_no_forbidden_tokens(cls, value: list[str]) -> list[str]:
        for token in value:
            if token in FORBIDDEN_REFERENCE_FIELDS:
                raise ValueError(f"forbidden raw token in program arguments: {token!r}")
        return value

    @field_validator("dry_run_install_only")
    @classmethod
    def _must_be_dry_run(cls, value: bool) -> bool:
        if not value:
            raise ValueError("launchd install preview is dry-run only")
        return value

    @field_validator("external_writeback_performed")
    @classmethod
    def _no_external_writeback(cls, value: bool) -> bool:
        if value:
            raise ValueError("schedule preview never performs external writeback")
        return value
