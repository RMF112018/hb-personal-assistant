"""Phase 10 V51 — Pydantic contracts for candidate ranking + daily-brief assembly.

Strict, declarative schemas for the advisory ranking overlay. The **model-facing** schemas
(:class:`CandidateRankingAdvice` and its items) use ``extra="forbid"`` and clamp every string so
a local model cannot smuggle raw content, unknown fields, or unbounded text into the pipeline. The
model may only reference candidate *aliases* (``c1``, ``c2`` …) supplied in the packet — it never
invents source refs, ids, names, dates, amounts, or URLs. Aliases map back to canonical candidate
ids in :mod:`candidate_ranking_packets`.

The packet/result schemas describe the deterministic, raw-free data that flows between the packet
builder, the ranking engine, the advisory layer, and the assembly layer. Nothing here makes a
network call, touches the DB, or persists anything.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

# Bounds shared with the deterministic redaction posture (kept small — advice is terse).
_ALIAS_MAX = 16
_LABEL_MAX = 64
_WHY_MAX = 240
_CODE_MAX = 48
_MAX_REASON_CODES = 6
_MAX_GROUP_MEMBERS = 64
_MAX_ADVICE_ITEMS = 500


def _clamp(value: Any, limit: int) -> str:
    """Coerce to a single-line bounded string (model strings are never trusted unbounded)."""
    return " ".join(str(value).split())[:limit]


# ---------------------------------------------------------------------------
# Packet schemas (deterministic, raw-free input to ranking + the model).
# ---------------------------------------------------------------------------
class CandidateRankingPacketItem(BaseModel):
    """One raw-free candidate row offered to the ranking engine and (redacted) to the model."""

    alias: str = Field(min_length=1, max_length=_ALIAS_MAX)
    candidate_id: str = Field(min_length=1)
    subject_type: str
    family: str
    section: str
    title_redacted: Optional[str] = None
    reason_redacted: Optional[str] = None
    project_key: Optional[str] = None
    lifecycle_state: str
    due_bucket: str = "none"
    age_bucket: str = "unknown"
    waiting_signal: str = "unknown"
    confidence: Optional[float] = None
    source_ref_count: int = 0
    source_ref_coverage_status: str = "not_applicable"
    duplicate_group_key: Optional[str] = None
    actionable: bool = False

    model_config = {"extra": "forbid"}


class CandidateRankingPacket(BaseModel):
    """The full deterministic packet for one brief date (advisory model sees the redacted items)."""

    brief_date: str
    items: list[CandidateRankingPacketItem] = Field(default_factory=list)
    candidate_set_hash: str
    feedback_digest_hash: str
    packet_char_count: int = 0
    source_ref_coverage: float = 1.0
    packet_guard_clean: bool = True

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Model-facing advisory schemas (strict; the model can only cite known aliases).
# ---------------------------------------------------------------------------
class CandidateRankingAdviceItem(BaseModel):
    """Per-candidate advisory hint. ``alias`` must map to a packet item or the item is dropped."""

    alias: str = Field(min_length=1, max_length=_ALIAS_MAX)
    priority_hint: Optional[int] = Field(default=None, ge=1, le=_MAX_ADVICE_ITEMS)
    group_label: Optional[str] = None
    why_this_matters: Optional[str] = None
    reason_codes: list[str] = Field(default_factory=list, max_length=_MAX_REASON_CODES)

    model_config = {"extra": "forbid"}

    @field_validator("alias", mode="before")
    @classmethod
    def _clamp_alias(cls, v: Any) -> str:
        return _clamp(v, _ALIAS_MAX)

    @field_validator("group_label", "why_this_matters", mode="before")
    @classmethod
    def _clamp_text(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return _clamp(v, _WHY_MAX) or None

    @field_validator("reason_codes", mode="before")
    @classmethod
    def _clamp_codes(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [_clamp(c, _CODE_MAX) for c in v[:_MAX_REASON_CODES] if str(c).strip()]


class CandidateBriefGroupAdvice(BaseModel):
    """Advisory grouping label over a set of candidate aliases (bounded, deterministic-ordered)."""

    group_label: str = Field(min_length=1, max_length=_LABEL_MAX)
    aliases: list[str] = Field(default_factory=list, max_length=_MAX_GROUP_MEMBERS)

    model_config = {"extra": "forbid"}

    @field_validator("group_label", mode="before")
    @classmethod
    def _clamp_label(cls, v: Any) -> str:
        return _clamp(v, _LABEL_MAX)

    @field_validator("aliases", mode="before")
    @classmethod
    def _clamp_aliases(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [_clamp(a, _ALIAS_MAX) for a in v[:_MAX_GROUP_MEMBERS] if str(a).strip()]


class CandidateSimilarityAdvice(BaseModel):
    """Advisory possible-duplicate edge between two aliases. Review-only; never auto-merges."""

    alias_a: str = Field(min_length=1, max_length=_ALIAS_MAX)
    alias_b: str = Field(min_length=1, max_length=_ALIAS_MAX)
    similarity_label: Optional[str] = None

    model_config = {"extra": "forbid"}

    @field_validator("alias_a", "alias_b", mode="before")
    @classmethod
    def _clamp_alias(cls, v: Any) -> str:
        return _clamp(v, _ALIAS_MAX)

    @field_validator("similarity_label", mode="before")
    @classmethod
    def _clamp_label(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return _clamp(v, _LABEL_MAX) or None


class CandidateRankingAdvice(BaseModel):
    """The complete advisory model output. Strict: unknown fields/raw content fail validation."""

    items: list[CandidateRankingAdviceItem] = Field(
        default_factory=list, max_length=_MAX_ADVICE_ITEMS
    )
    groups: list[CandidateBriefGroupAdvice] = Field(default_factory=list, max_length=64)
    duplicates: list[CandidateSimilarityAdvice] = Field(default_factory=list, max_length=256)

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Result schemas (in-memory orchestration outputs; raw-free).
# ---------------------------------------------------------------------------
class CandidateRankingResult(BaseModel):
    """In-memory result of a ranking run (advisory; persisted overlay is hash/metadata only)."""

    brief_date: str
    ranking_run_id: Optional[str] = None
    policy_version: str
    algorithm_version: str
    candidate_set_hash: str
    feedback_digest_hash: str
    model_status: str
    model_profile_id: Optional[str] = None
    model_name: Optional[str] = None
    model_receipt_id: Optional[str] = None
    deterministic_fallback_used: bool = True
    degraded_reason: Optional[str] = None
    candidate_count: int = 0
    ranked_count: int = 0
    withheld_source_missing_count: int = 0
    source_ref_coverage: float = 1.0
    usefulness_score: float = 0.0
    guard_clean: bool = True
    ranked: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class DailyBriefAssemblyResult(BaseModel):
    """In-memory result of an assembled daily brief (deterministic order, advisory grouping)."""

    brief_date: str
    assembly_run_id: Optional[str] = None
    ranking_run_id: Optional[str] = None
    assembly_policy_version: str
    model_layer_status: str
    deterministic_fallback_used: bool = True
    withheld_reason: Optional[str] = None
    section_count: int = 0
    candidate_count: int = 0
    sections: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
