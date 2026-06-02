"""Phase 08A interactive-query + answer-synthesis structures (Prompt 08).

`QueryResult` is the source-linked interactive-query output (the eight
`interactive_query_contract.required_output` fields + metadata). `EvaluationPreview` is a
deterministic pre-presentation checklist over the repo `evaluation_criteria_contract`
checklist items (computed, not persisted — full Output Evaluation Agent A05 + persistence
are deferred). No raw bodies/document text/calendar payloads/prompts/responses/URLs/
secrets — ever.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

from ..reasoning import FORBIDDEN_REFERENCE_FIELDS


class EvaluationPreview(BaseModel):
    """Deterministic evaluation checklist preview (mirrors the evaluation contract)."""

    checklist: dict[str, bool] = {}
    checklist_total: int = 0
    checklist_passed: int = 0
    score: float = 0.0
    passed: bool = False
    review_tier: int = 3
    review_status: str = "review_required"

    model_config = {"extra": "forbid"}


class QueryResult(BaseModel):
    """Source-linked interactive-query output (interactive_query_contract.required_output)."""

    answer_redacted: str = ""
    source_refs: list[dict[str, str]] = []
    confidence_labels: dict[str, Any] = {}
    review_tiers: dict[str, Any] = {}
    research_packet_summary: dict[str, Any] = {}
    evaluation_summary: dict[str, Any] = {}
    warnings: list[str] = []
    advisory_vs_actionable_marking: dict[str, Any] = {}
    # Metadata (not part of the required_output set).
    synthesized: bool = False
    mode: str = "mock"
    retrieval_receipt_id: str | None = None
    packet_receipt_id: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("source_refs")
    @classmethod
    def _refs_have_no_forbidden_fields(
        cls, value: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        for ref in value:
            forbidden = set(ref) & FORBIDDEN_REFERENCE_FIELDS
            if forbidden:
                raise ValueError(f"forbidden raw field(s) in source_ref: {sorted(forbidden)}")
        return value
