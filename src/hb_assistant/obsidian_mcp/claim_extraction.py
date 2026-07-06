"""Deterministic, rule-based claim extraction (N8C-4).

No LLM: bounded regex/keyword rules turn note/card text into :class:`ClaimCandidate`s (dates,
deadlines, preferences, risks, assumptions, commitments, decisions). Qwen/Ollama extraction is
explicitly out of scope here — the ``ingest_claim_candidates`` seam lets a future model write through
the same validated path (``extracted_by="future_qwen"``) with no schema change.

The card-aware orchestrator ties in N8C-2 identity + N8C-3 navigation: it refuses to extract from an
**ambiguous** or **deleted** source/card, labels extraction from a **stale** source, and pulls content
only through the approved bounded :func:`source_navigation.get_vault_note`.
"""

from __future__ import annotations

import re
from typing import Any

from . import source_card_identity as identity
from . import source_navigation as nav
from .claim_models import (
    ASSUMPTION,
    COMMITMENT,
    DATE,
    DECISION_CANDIDATE,
    PREFERENCE,
    RISK,
    SOURCE_STATE_CURRENT,
    SOURCE_STATE_DELETED,
    SOURCE_STATE_STALE,
    TASK_CANDIDATE,
    ClaimCandidate,
)
from .claim_repository import ClaimRepository
from .config import ObsidianMcpConfig
from .source_index_repository import SourceIndexRepository

EXTRACTOR_VERSION = "rule_based-v1"

# Longest reasonable segment to treat as one claim's evidence (bounds runaway lines).
_MAX_SEGMENT = 400

# (claim_type, compiled pattern, confidence). Order = priority; at most one claim per type per segment.
_RULES: tuple[tuple[str, re.Pattern[str], float], ...] = (
    (DECISION_CANDIDATE, re.compile(r"\b(?:we|i)\s+decided\b|\bdecision\s*:|\bdecided to\b|\bagreed to\b", re.I), 0.8),
    (COMMITMENT, re.compile(r"\bi\s+will\b|\bi['’]ll\b|\bi\s+commit\b|\bi['’]?m going to\b|\bwe will\b", re.I), 0.7),
    (RISK, re.compile(r"\brisk\s*:|\brisk that\b|\bat risk\b|\bmay slip\b|\bcould (?:delay|slip)\b|\bmight slip\b", re.I), 0.7),
    (ASSUMPTION, re.compile(r"\bassumption\s*:|\bassumes?\b|\bassumed\b|\bassuming\b", re.I), 0.7),
    (PREFERENCE, re.compile(r"\bi\s+prefer\b|\bwe\s+prefer\b|\bi['’]d rather\b|\bpreference\s*(?:is|:)", re.I), 0.7),
    (TASK_CANDIDATE, re.compile(r"\bdue (?:by|on)\b|\bdeadline\b|\bneed to\b|\baction\s*:|\bto-?do\b|\bfollow up\b", re.I), 0.6),
)

# Hard-date patterns (month-name D, YYYY / ISO / slashed).
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE_RE = re.compile(
    rf"\b(?:{_MONTHS})\w*\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    re.I,
)


class ClaimExtractionBlocked(ValueError):
    """Extraction refused because the source/card state is unsafe (ambiguous or deleted)."""


def _segments(text: str) -> list[str]:
    """Split text into bounded claim-sized segments (lines, then sentence-ish), order-preserving."""
    out: list[str] = []
    for line in (text or "").replace("\r", "\n").split("\n"):
        line = line.strip().lstrip("#>-*• \t")
        if not line:
            continue
        # further split long prose lines on sentence boundaries
        parts = re.split(r"(?<=[.!?])\s+", line) if len(line) > _MAX_SEGMENT else [line]
        for p in parts:
            p = p.strip()
            if p:
                out.append(p[:_MAX_SEGMENT])
    return out


def extract_claims_from_text(text: str) -> list[ClaimCandidate]:
    """Deterministic rule-based extraction. Pure — no DB, no I/O. Stable order."""
    candidates: list[ClaimCandidate] = []
    for idx, seg in enumerate(_segments(text)):
        location = f"segment:{idx}"
        seen_types: set[str] = set()
        for claim_type, pattern, conf in _RULES:
            if claim_type in seen_types:
                continue
            if pattern.search(seg):
                seen_types.add(claim_type)
                date_hit = _DATE_RE.search(seg)
                candidates.append(ClaimCandidate(
                    claim_type=claim_type, claim_text=seg, evidence_excerpt=seg,
                    confidence=conf, evidence_location=location,
                    normalized_object=date_hit.group(0) if date_hit else None,
                ))
        # A hard date not already claimed as a deadline/task is a date claim.
        if TASK_CANDIDATE not in seen_types:
            m = _DATE_RE.search(seg)
            if m:
                candidates.append(ClaimCandidate(
                    claim_type=DATE, claim_text=seg, evidence_excerpt=seg, confidence=0.7,
                    evidence_location=location, normalized_object=m.group(0)))
    return candidates


def ingest_claim_candidates(repo: ClaimRepository, source_id: str | None,
                            candidates: list[ClaimCandidate], *, note_rel_path: str | None = None,
                            extractor: str = "manual", extractor_version: str | None = None,
                            model_name: str | None = None, source_state: str | None = None,
                            conn=None, **anchors: Any) -> dict[str, Any]:
    """Validated ingestion seam (rule_based | manual | future_qwen). Internal callers only —
    there is NO remote claim-write tool. Enforces source/card linkage via the repository."""
    return repo.ingest_candidates(
        candidates, source_id=source_id, note_rel_path=note_rel_path, extracted_by=extractor,
        extractor_version=extractor_version, model_name=model_name, source_state=source_state,
        conn=conn, **anchors,
    )


def extract_claims_for_card(
    claim_repo: ClaimRepository,
    source_repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    source_id: str,
    note_rel_path: str,
    *,
    allow_stale_source: bool = False,
    conn=None,
) -> dict[str, Any]:
    """Extract + ingest claims from a source card/note, gated by N8C-2/N8C-3 state.

    Blocks (raises :class:`ClaimExtractionBlocked`) on an ambiguous card→source link or a deleted
    source. A stale source blocks unless ``allow_stale_source`` — then the claims are labeled
    ``source_state="stale"``. Content is the source's bounded, redaction-safe indexed text, retrieved
    only via the approved :func:`source_navigation.get_source` service (the graph-safe summary card
    embeds no raw text, so it is not the extraction input).
    """
    reverse = identity.get_source_for_card(source_repo, note_rel_path, conn=conn)
    if reverse.resolution == "ambiguous":
        raise ClaimExtractionBlocked(f"ambiguous_source_card_link:{note_rel_path}")

    state = identity.classify_card_state(source_repo, config.vault_root, source_id, conn=conn)
    if state.state == identity.STATE_SOURCE_DELETED:
        raise ClaimExtractionBlocked(f"source_deleted:{source_id}")
    if state.state in (identity.STATE_STALE, identity.STATE_MISSING):
        if not allow_stale_source:
            raise ClaimExtractionBlocked(f"stale_source:{source_id}:{state.reason}")
        source_state = SOURCE_STATE_STALE
    else:
        source_state = SOURCE_STATE_CURRENT

    # Extract from the SOURCE's indexed content (the bounded, redaction-safe text_excerpt served by
    # the N8C-3 navigation service) — NOT the graph-safe summary card, which embeds no raw text.
    detail = nav.get_source(source_repo, source_id, conn=conn)
    if detail is None:
        raise ClaimExtractionBlocked(f"source_not_found:{source_id}")
    src = detail.get("source") or {}
    card = identity.get_card_for_source(source_repo, source_id, conn=conn)
    candidates = extract_claims_from_text(src.get("text_excerpt") or "")
    result = claim_repo.ingest_candidates(
        candidates, source_id=source_id, note_rel_path=note_rel_path,
        card_id=(card or {}).get("card_id"), source_kind=src.get("source_kind"),
        source_root_key=src.get("source_root_key"), source_rel_path=src.get("rel_path"),
        source_state=source_state, extracted_by="rule_based", extractor_version=EXTRACTOR_VERSION,
        conn=conn,
    )
    result["source_state"] = source_state
    result["blocked"] = False
    return result


# Re-export for callers/tests.
__all__ = [
    "EXTRACTOR_VERSION",
    "ClaimExtractionBlocked",
    "extract_claims_from_text",
    "ingest_claim_candidates",
    "extract_claims_for_card",
    "SOURCE_STATE_DELETED",
]
