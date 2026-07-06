"""Enrichment job/receipt model + typed result contracts (N8C-5).

Shared enums (re-exported from the V101 schema module so the DB CHECKs and the Python layer never
drift), the deterministic ``job_id``, hard size caps, and the pure per-job-type result validators.

Nothing here writes to the DB, runs a model, or enqueues — see ``enrichment_repository`` (store),
``enrichment_model_provider`` (model), and ``qwen_worker`` (orchestration). Result validation is
pure and total: it never trusts model output — oversized or malformed output fails with a clean
error rather than being silently truncated and ingested.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_enrichment_tables import (
    ENRICHMENT_APPLIED_STATUS_VALUES,
    ENRICHMENT_JOB_TYPE_VALUES,
    ENRICHMENT_STATUS_VALUES,
    ENRICHMENT_SUBJECT_TYPE_VALUES,
)

from .claim_models import CLAIM_TYPES, ClaimCandidate, bound_evidence, clamp_confidence

# Re-export enum tuples as frozensets (single source of truth is the schema module).
ENRICHMENT_JOB_TYPES = frozenset(ENRICHMENT_JOB_TYPE_VALUES)
ENRICHMENT_SUBJECT_TYPES = frozenset(ENRICHMENT_SUBJECT_TYPE_VALUES)
ENRICHMENT_STATUSES = frozenset(ENRICHMENT_STATUS_VALUES)
ENRICHMENT_APPLIED_STATUSES = frozenset(ENRICHMENT_APPLIED_STATUS_VALUES)

# Named job types (avoid magic strings).
JOB_SOURCE_SUMMARY = "source_summary"
JOB_CLAIM_EXTRACTION = "claim_extraction"
JOB_BACKLINK_SUGGESTIONS = "backlink_suggestions"
JOB_CLAIM_VALIDATION = "claim_validation"  # reserved in the schema; NOT implemented in N8C-5.

# Only these are executable by the N8C-5 worker; claim_validation is refused until implemented.
IMPLEMENTED_JOB_TYPES = frozenset({JOB_SOURCE_SUMMARY, JOB_CLAIM_EXTRACTION, JOB_BACKLINK_SUGGESTIONS})

# Named statuses.
STATUS_QUEUED = "queued"
STATUS_CLAIMED = "claimed"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_STALE = "stale"
STATUS_SKIPPED = "skipped"
STATUS_CANCELLED = "cancelled"

# Named applied statuses (receipt disposition).
APPLIED_STORED_ONLY = "stored_only"
APPLIED_CANDIDATE_CLAIMS_INGESTED = "candidate_claims_ingested"
APPLIED_REJECTED = "rejected"
APPLIED_STALE_REJECTED = "stale_rejected"
APPLIED_FAILED = "failed"

# Named subject types.
SUBJECT_SOURCE = "source"
SUBJECT_CARD = "card"
SUBJECT_NOTE = "note"
SUBJECT_CLAIM = "claim"

RUNTIME_OLLAMA = "ollama"
DEFAULT_MODEL_NAME = "qwen2.5:14b"

# ----- hard size caps (revision: fail safely on oversized model output, never silent truncate) -----
PAYLOAD_MAX_CHARS = 8_000        # queue-time payload_json ceiling (raises on enqueue if exceeded)
RESULT_MAX_CHARS = 16_000        # raw model output ceiling (checked BEFORE parse; oversized => fail)
ERROR_MAX_CHARS = 2_000          # last_error / error_message storage cap (diagnostic; truncated)
SAFETY_FLAGS_MAX_CHARS = 2_000   # safety_flags_json storage cap
SUMMARY_MAX_CHARS = 4_000        # per-field caps inside a parsed source_summary result
KEY_POINTS_MAX = 20
KEY_POINT_MAX_CHARS = 500
CLAIMS_MAX = 50                  # max claim candidates accepted from one claim_extraction result
SUGGESTIONS_MAX = 50
SUGGESTION_FIELD_MAX_CHARS = 500

_TRUNC_MARK = "…[truncated]"


class EnrichmentValidationError(ValueError):
    """A job spec or model result failed field / size / structure validation (not written)."""


class OversizedModelOutput(EnrichmentValidationError):
    """Raw model output exceeded RESULT_MAX_CHARS — refused wholesale (no truncate-and-ingest)."""


@dataclass(frozen=True)
class ParsedResult:
    """The validated, normalized outcome of one model generation for a job type.

    ``result`` is the stored receipt payload; ``claim_candidates`` are ingest-ready N8C-4 candidates
    (only for claim_extraction); ``safety_flags`` records any bounded/dropped-field notes.
    """

    result: dict[str, Any]
    claim_candidates: list[ClaimCandidate] = field(default_factory=list)
    safety_flags: list[str] = field(default_factory=list)


def compute_job_id(job_type: str, source_id: str | None, note_rel_path: str | None,
                   payload_key: str = "") -> str:
    """Deterministic 24-hex id over (type, subject anchor, payload key) so re-queue is idempotent.

    Same (job_type, source_id, note_rel_path, payload_key) => same job_id => the repository upserts
    rather than creating an uncontrolled duplicate.
    """
    key = f"{job_type}|{source_id or ''}|{note_rel_path or ''}|{payload_key}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def sha256_hex(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def bound_text(text: Any, cap: int) -> str:
    """Truncate a DIAGNOSTIC string to ``cap`` (for our own error/flag storage — safe to truncate)."""
    s = "" if text is None else str(text)
    if len(s) <= cap:
        return s
    return s[: max(0, cap - len(_TRUNC_MARK))] + _TRUNC_MARK


def dumps_capped(obj: Any, cap: int) -> str:
    """Serialize to JSON, raising if the (already field-bounded) payload still exceeds ``cap``."""
    s = json.dumps(obj, sort_keys=True)
    if len(s) > cap:
        raise EnrichmentValidationError(f"payload_exceeds_cap:{len(s)}>{cap}")
    return s


def _load_json_object(raw: str) -> dict[str, Any]:
    if len(raw or "") > RESULT_MAX_CHARS:
        raise OversizedModelOutput(f"model_output_exceeds_cap:{len(raw)}>{RESULT_MAX_CHARS}")
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise EnrichmentValidationError("invalid_model_json") from exc
    if not isinstance(obj, dict):
        raise EnrichmentValidationError("model_result_not_object")
    return obj


def parse_result(job_type: str, raw: str) -> ParsedResult:
    """Validate + normalize raw model output for ``job_type``. Total: raises on any structural or
    size problem; never returns silently truncated model claims."""
    if job_type == JOB_SOURCE_SUMMARY:
        return _parse_source_summary(raw)
    if job_type == JOB_CLAIM_EXTRACTION:
        return _parse_claim_extraction(raw)
    if job_type == JOB_BACKLINK_SUGGESTIONS:
        return _parse_backlink_suggestions(raw)
    raise EnrichmentValidationError(f"unsupported_job_type:{job_type}")


def _parse_source_summary(raw: str) -> ParsedResult:
    obj = _load_json_object(raw)
    flags: list[str] = []
    summary = str(obj.get("summary") or "").strip()
    if not summary:
        raise EnrichmentValidationError("summary_missing")
    if len(summary) > SUMMARY_MAX_CHARS:
        summary = summary[:SUMMARY_MAX_CHARS]
        flags.append("summary_bounded")
    points_in = obj.get("key_points") or []
    if not isinstance(points_in, list):
        raise EnrichmentValidationError("key_points_not_list")
    key_points: list[str] = []
    for p in points_in[:KEY_POINTS_MAX]:
        t = str(p).strip()
        if t:
            key_points.append(t[:KEY_POINT_MAX_CHARS])
    if len(points_in) > KEY_POINTS_MAX:
        flags.append("key_points_bounded")
    result = {"summary": summary, "key_points": key_points,
              "confidence": clamp_confidence(obj.get("confidence"))}
    return ParsedResult(result=result, safety_flags=flags)


def _parse_claim_extraction(raw: str) -> ParsedResult:
    obj = _load_json_object(raw)
    flags: list[str] = []
    claims_in = obj.get("claims") or []
    if not isinstance(claims_in, list):
        raise EnrichmentValidationError("claims_not_list")
    candidates: list[ClaimCandidate] = []
    kept: list[dict[str, Any]] = []
    dropped = 0
    for item in claims_in[:CLAIMS_MAX]:
        if not isinstance(item, dict):
            dropped += 1
            continue
        claim_type = str(item.get("claim_type") or "").strip()
        claim_text = str(item.get("claim_text") or "").strip()
        evidence = bound_evidence(str(item.get("evidence_excerpt") or ""))
        # Refuse unsupported claims: unknown type, empty text, or missing evidence (no provenance).
        if claim_type not in CLAIM_TYPES or not claim_text or not evidence:
            dropped += 1
            continue
        conf = clamp_confidence(item.get("confidence"))
        candidates.append(ClaimCandidate(
            claim_type=claim_type, claim_text=claim_text, evidence_excerpt=evidence, confidence=conf))
        kept.append({"claim_type": claim_type, "claim_text": claim_text[:KEY_POINT_MAX_CHARS],
                     "confidence": conf})
    if len(claims_in) > CLAIMS_MAX:
        flags.append("claims_bounded")
    if dropped:
        flags.append(f"claims_rejected:{dropped}")
    return ParsedResult(result={"claims": kept, "count": len(kept)},
                        claim_candidates=candidates, safety_flags=flags)


def _parse_backlink_suggestions(raw: str) -> ParsedResult:
    obj = _load_json_object(raw)
    flags: list[str] = []
    sugg_in = obj.get("suggestions") or []
    if not isinstance(sugg_in, list):
        raise EnrichmentValidationError("suggestions_not_list")
    suggestions: list[dict[str, Any]] = []
    for item in sugg_in[:SUGGESTIONS_MAX]:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target") or "").strip()[:SUGGESTION_FIELD_MAX_CHARS]
        if not target:
            continue
        suggestions.append({
            "target": target,
            "reason": str(item.get("reason") or "").strip()[:SUGGESTION_FIELD_MAX_CHARS],
            "confidence": clamp_confidence(item.get("confidence")),
        })
    if len(sugg_in) > SUGGESTIONS_MAX:
        flags.append("suggestions_bounded")
    # Store-only: N8C-5 never mutates vault links from suggestions.
    return ParsedResult(result={"suggestions": suggestions, "count": len(suggestions)},
                        safety_flags=flags)
