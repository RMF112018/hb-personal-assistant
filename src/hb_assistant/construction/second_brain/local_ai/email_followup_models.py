"""Phase 10 — Email Follow-Up Raw Enrichment contracts (V45 persistence row + shared enums).

Declarative-only typed contracts for the review-safe ``email_followup_enrichments`` (V45) table.
There is no runtime here: no model call, no DB access, no raw loading. Every model uses
``extra="forbid"`` so an unknown/forbidden raw field (``raw_email_body``, ``body_html``,
``raw_prompt`` …) is rejected at parse time.

The persisted row carries ONLY structured/redacted model-enriched follow-up fields plus
SHA-256[:12] hashes and source references. The bounded sanitized raw email window that fed the
model is never represented here beyond its ``raw_excerpt_hash``. The model *output* schema
(:class:`EmailFollowupEnrichmentOutput`) lives in :mod:`email_followup_route` (Prompt 03); this
module defines the persistence contract and the closed vocabularies both share.

Waiting-state vocabulary follows the package contract
(``waiting_on_me | waiting_on_others | open | possibly_resolved | closed | unknown``) — a superset
of :data:`models.WaitingState` aligned with the deterministic follow-up watch statuses in
:mod:`follow_up_watch` (open / waiting_on_me / waiting_on_others / possibly_resolved / closed).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Closed vocabularies (shared by the model output schema and the persisted row).
# ---------------------------------------------------------------------------
EnrichmentWaitingState = Literal[
    "waiting_on_me", "waiting_on_others", "open", "possibly_resolved", "closed", "unknown"
]
EnrichmentAssigneeType = Literal["me", "other", "mixed", "unknown"]
#: Review lifecycle for an enrichment row (mirrors V45_TABLE_SPEC).
EnrichmentReviewStatus = Literal["pending", "accepted", "rejected", "superseded"]
#: Coarse confidence band used for daily-brief labeling (never replaces the numeric score).
ConfidenceBand = Literal["high", "medium", "low"]
#: Source candidate kinds eligible for enrichment (accepted task/commitment or a watch item).
EnrichmentCandidateType = Literal["task", "commitment", "watch_item"]

#: Default model task family / prompt template version (kept in sync with the route + DB defaults).
MODEL_TASK = "email_followup_raw_enrichment"
PROMPT_TEMPLATE_VERSION = "email_followup_raw_enrichment.v1"

#: Default confidence-band cut points (high >= 0.75, medium >= 0.5, else low). Operators may pass
#: their own thresholds; daily-brief consumption uses these to label / gate low-confidence items.
DEFAULT_HIGH_CONFIDENCE = 0.75
DEFAULT_MEDIUM_CONFIDENCE = 0.5


def confidence_band_for(
    confidence: float,
    *,
    high: float = DEFAULT_HIGH_CONFIDENCE,
    medium: float = DEFAULT_MEDIUM_CONFIDENCE,
) -> ConfidenceBand:
    """Map a 0.0-1.0 confidence to a coarse band (deterministic; no clock/IO)."""
    if confidence >= high:
        return "high"
    if confidence >= medium:
        return "medium"
    return "low"


class EmailFollowupEnrichmentRow(BaseModel):
    """A persisted review-safe V45 ``email_followup_enrichments`` row.

    Holds only structured/redacted enriched fields, hashes, and source references. ``extra="forbid"``
    plus the absence of any body/html/url/token/prompt/response field make raw persistence
    impossible through this contract. ``raw_excerpt_hash`` / ``input_context_hash`` / ``output_hash``
    / ``email_thread_ref_hash`` are opaque SHA-256[:12] hashes.
    """

    enrichment_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    source_candidate_id: str = Field(min_length=1)
    source_candidate_type: EnrichmentCandidateType
    watch_item_id: str | None = None
    email_thread_ref_hash: str | None = None
    email_message_ref_hashes: list[str] = Field(default_factory=list)
    raw_excerpt_hash: str = Field(min_length=1)
    enriched_title: str = Field(min_length=1, max_length=240)
    waiting_state: EnrichmentWaitingState
    assignee_type: EnrichmentAssigneeType
    assignee_display: str | None = Field(default=None, max_length=200)
    suggested_next_action: str | None = Field(default=None, max_length=1000)
    due_at_utc: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_band: ConfidenceBand
    reason_codes: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    review_status: EnrichmentReviewStatus = "pending"
    model_task: str = MODEL_TASK
    model_profile_id: str | None = None
    prompt_template_version: str = PROMPT_TEMPLATE_VERSION
    input_context_hash: str = Field(min_length=1)
    output_hash: str = Field(min_length=1)

    model_config = {"extra": "forbid"}

    @field_validator("source_refs", "email_message_ref_hashes", "reason_codes")
    @classmethod
    def _no_blank_entries(cls, value: list[str]) -> list[str]:
        if any(not isinstance(v, str) or not v.strip() for v in value):
            raise ValueError("list entries must be non-empty strings")
        return value
