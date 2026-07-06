"""N8C-8 decision / preference / open-loop extractor — deterministic, source-backed, NO LLM.

Pack-scoped. Turns a context pack's structured records into advisory decision / preference / open-loop
records via two bounded input paths:

  1. **Claims (primary, structured ``claim_type``):** a pack's ``claim_candidate`` items point at N8C-4
     candidate claims whose ``claim_type`` is already one of decision_candidate / preference / commitment
     / task_candidate / risk / assumption / date / fact / unknown. Each maps deterministically onto a
     decision / preference / open-loop record. A conservative, bounded heuristic promotes a
     question-shaped claim to an open-loop ``question`` (low confidence + ``needs_review``). No LLM.
  2. **Memory compilations (secondary, WEAK advisory):** built N8C-7 compilations for nodes referenced by
     the pack's sources contribute their ``preferences_json`` / ``risks_json`` / ``open_questions_json``
     entries — capped confidence, ``needs_review``, and stamped ``compilation_derived`` in metadata.

Preview and dry-run are fully read-only; records are written only by
``apply_decision_memory(..., apply=True)`` and only into the four N8C-8-owned tables. The extractor only
READS claims/packs/memory — candidate claims stay candidate/unreviewed; nothing is executed, scheduled,
or sent. Records default to ``status='candidate'`` / ``review_state='unreviewed'``.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from . import decision_memory_models as M
from .memory_models import bound_text, clamp_confidence, normalize_memory_name


@dataclass
class DecisionMemoryProviders:
    claim_repo: Any
    pack_repo: Any
    enrichment_repo: Any
    source_repo: Any
    memory_repo: Any


# claim_type → how to build a record. Kept explicit (no LLM, no fuzzy inference).
def _strength_from_confidence(conf: float | None) -> str:
    c = clamp_confidence(conf) if conf is not None else 0.0
    if c >= 0.8:
        return "strong"
    if c >= 0.6:
        return "medium"
    return "weak"


def _priority_from_confidence(conf: float | None) -> str:
    c = clamp_confidence(conf) if conf is not None else 0.0
    if c >= 0.75:
        return "high"
    if c >= 0.5:
        return "medium"
    return "low"


def _looks_like_question(text: str | None) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    return t.endswith("?") or t.startswith("question:") or t.startswith("question ")


def _claim_provenance(claim: dict[str, Any], source_repo: Any, pack_id: str,
                      pack_item_id: str | None, *, conn: sqlite3.Connection | None) -> dict[str, Any]:
    source_id = claim.get("source_id")
    detail = source_repo.get_source_detail(source_id, conn=conn) if source_id else None
    return {
        "source_id": source_id,
        "note_rel_path": claim.get("note_rel_path"),
        "claim_id": claim.get("claim_id"),
        "pack_id": pack_id,
        "pack_item_id": pack_item_id,
        "evidence_excerpt": claim.get("evidence_excerpt"),
        "evidence_location": claim.get("evidence_location"),
        "source_digest": detail.get("content_sha256") if detail else None,
        "card_digest": claim.get("card_digest"),
        "observed_at": claim.get("observed_at"),
        "valid_from": claim.get("valid_from"),
        "valid_until": claim.get("valid_until"),
    }


def _action_text(claim: dict[str, Any]) -> tuple[str | None, bool]:
    """Prefer normalized_object/predicate; fall back to bounded claim_text (flag = is_fallback)."""
    for key in ("normalized_object", "normalized_predicate"):
        val = (claim.get(key) or "").strip()
        if val:
            return val, False
    text = (claim.get("claim_text") or "").strip()
    return (bound_text(text, 200) if text else None), True


def _classify_claim(claim: dict[str, Any], providers: DecisionMemoryProviders, pack_id: str,
                    pack_item_id: str | None, *,
                    conn: sqlite3.Connection | None) -> M._BaseRecord | None:
    claim_type = claim.get("claim_type")
    prov = _claim_provenance(claim, providers.source_repo, pack_id, pack_item_id, conn=conn)
    subject = (claim.get("normalized_subject") or "").strip() or None
    action, is_fallback = _action_text(claim)
    conf = clamp_confidence(claim.get("confidence"))
    review = M.REVIEW_NEEDS_REVIEW if is_fallback else M.REVIEW_UNREVIEWED
    common = dict(normalized_subject=subject, review_state=review, confidence=conf, **prov)

    if claim_type == "decision_candidate":
        return M.DecisionRecord(decision_type=M.DECISION_CANDIDATE,
                                decision_text=claim.get("claim_text"), normalized_decision=action,
                                decided_at=claim.get("observed_at"), **common)
    if claim_type == "preference":
        return M.PreferenceRecord(preference_type=M.USER_PREFERENCE,
                                  preference_text=claim.get("claim_text"), normalized_preference=action,
                                  strength=_strength_from_confidence(conf), **common)
    if claim_type == "commitment":
        return M.OpenLoopRecord(open_loop_type=M.OPEN_LOOP_COMMITMENT,
                                open_loop_text=claim.get("claim_text"), normalized_action=action,
                                priority=_priority_from_confidence(conf),
                                stale_after=claim.get("stale_after"), **common)
    if claim_type == "risk":
        return M.OpenLoopRecord(open_loop_type=M.OPEN_LOOP_RISK_FOLLOWUP,
                                open_loop_text=claim.get("claim_text"), normalized_action=action,
                                priority=_priority_from_confidence(conf),
                                stale_after=claim.get("stale_after"), **common)
    if claim_type == "task_candidate":
        if _looks_like_question(claim.get("claim_text")):
            return _question_open_loop(claim, action, prov, subject, conf)
        return M.OpenLoopRecord(open_loop_type=M.OPEN_LOOP_TASK_CANDIDATE,
                                open_loop_text=claim.get("claim_text"), normalized_action=action,
                                priority=_priority_from_confidence(conf),
                                due_at=claim.get("valid_until"), stale_after=claim.get("stale_after"),
                                **common)
    # Conservative question heuristic on other claim types (fact/unknown/assumption): only when the
    # text is clearly a question. Low confidence + needs_review + bounded.
    if _looks_like_question(claim.get("claim_text")):
        return _question_open_loop(claim, action, prov, subject, conf)
    return None  # unsupported → rejected


def _question_open_loop(claim: dict[str, Any], action: str | None, prov: dict[str, Any],
                        subject: str | None, conf: float) -> M.OpenLoopRecord:
    return M.OpenLoopRecord(
        open_loop_type=M.OPEN_LOOP_QUESTION, open_loop_text=claim.get("claim_text"),
        normalized_action=action, normalized_subject=subject,
        review_state=M.REVIEW_NEEDS_REVIEW, priority="low",
        confidence=min(conf, M.QUESTION_CONFIDENCE_CAP), **prov)


# --- compilation-derived (weak advisory) ------------------------------------------------
def _compilation_records(providers: DecisionMemoryProviders, comp: dict[str, Any], *,
                         conn: sqlite3.Connection | None) -> list[M._BaseRecord]:
    node = providers.memory_repo.get_node(comp["node_id"], conn=conn)
    if node is None:
        return []
    # A representative source anchor from the node's mentions (bounded).
    mentions = providers.memory_repo.list_mentions(comp["node_id"], limit=1, conn=conn)
    rep = mentions[0] if mentions else {}
    subject = normalize_memory_name(node.get("canonical_name")) or None
    base = {
        "normalized_subject": subject, "review_state": M.REVIEW_NEEDS_REVIEW,
        "memory_node_id": comp["node_id"], "compilation_id": comp["compilation_id"],
        "source_id": rep.get("source_id"), "note_rel_path": rep.get("note_rel_path"),
        "source_digest": rep.get("source_digest"),
        "metadata": {"compilation_derived": True, "compile_type": comp.get("compile_type")},
    }
    out: list[M._BaseRecord] = []
    for item in _json_list(comp.get("preferences_json")):
        out.append(M.PreferenceRecord(
            preference_type=M.WORKFLOW_PREFERENCE, preference_text=item, normalized_preference=item,
            strength="weak", confidence=M.COMPILATION_CONFIDENCE_CAP,
            evidence_excerpt=item, **base))
    for item in _json_list(comp.get("risks_json")):
        out.append(M.OpenLoopRecord(
            open_loop_type=M.OPEN_LOOP_RISK_FOLLOWUP, open_loop_text=item, normalized_action=item,
            priority="low", confidence=M.COMPILATION_CONFIDENCE_CAP, evidence_excerpt=item, **base))
    for item in _json_list(comp.get("open_questions_json")):
        out.append(M.OpenLoopRecord(
            open_loop_type=M.OPEN_LOOP_QUESTION, open_loop_text=item, normalized_action=item,
            priority="low", confidence=min(M.COMPILATION_CONFIDENCE_CAP, M.QUESTION_CONFIDENCE_CAP),
            evidence_excerpt=item, **base))
    return out


def _json_list(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [str(x).strip() for x in loaded if isinstance(loaded, list) and str(x).strip()][:20]


# --- discovery / preview / apply --------------------------------------------------------
def discover_decision_memory(providers: DecisionMemoryProviders, *, pack_id: str,
                             conn: sqlite3.Connection | None = None) -> list[M._BaseRecord]:
    """Pack-scoped discovery (read-only): returns advisory record drafts from both input paths."""
    items = providers.pack_repo.list_items(pack_id, conn=conn)
    drafts: list[M._BaseRecord] = []
    source_ids: list[str] = []
    for item in items:
        if item.get("source_id"):
            source_ids.append(item["source_id"])
        if not item.get("included", 1):
            continue
        if item.get("item_type") == "claim_candidate" and item.get("claim_id"):
            claim = providers.claim_repo.get_claim(item["claim_id"], conn=conn)
            if claim is None:
                continue
            rec = _classify_claim(claim, providers, pack_id, item.get("pack_item_id"), conn=conn)
            if rec is not None:
                drafts.append(rec)
    # Path 2: compilation-derived weak records for the pack's sources.
    for comp in providers.memory_repo.list_built_compilations_for_sources(source_ids, conn=conn):
        drafts.extend(_compilation_records(providers, comp, conn=conn))
    return drafts


def _to_rows(drafts: list[M._BaseRecord], created_by: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"decisions": [], "preferences": [], "open_loops": []}
    for d in drafts:
        row = {**d.to_row(), "created_by": created_by}
        if isinstance(d, M.DecisionRecord):
            out["decisions"].append(row)
        elif isinstance(d, M.PreferenceRecord):
            out["preferences"].append(row)
        elif isinstance(d, M.OpenLoopRecord):
            out["open_loops"].append(row)
    return out


def preview_decision_memory(providers: DecisionMemoryProviders, *, pack_id: str,
                            created_by: str = "service",
                            conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Discover + build rows for a pack WITHOUT persisting. Fully read-only."""
    drafts = discover_decision_memory(providers, pack_id=pack_id, conn=conn)
    rows = _to_rows(drafts, created_by)
    return {"pack_id": pack_id, **rows,
            "counts": {k: len(v) for k, v in rows.items()}}


def apply_decision_memory(providers: DecisionMemoryProviders, repo: Any, *, pack_id: str,
                          apply: bool = False, created_by: str = "service",
                          conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Discover + build, and — only when ``apply`` — persist into the four N8C-8 tables (nothing else).
    Idempotent: unchanged inputs create no duplicates; a changed evidence digest supersedes the prior
    record of the SAME lineage."""
    preview = preview_decision_memory(providers, pack_id=pack_id, created_by=created_by, conn=conn)
    if not apply:
        return {"applied": False, **preview}
    created = {"decisions": 0, "preferences": 0, "open_loops": 0}
    superseded = 0
    for row in preview["decisions"]:
        res = repo.upsert_decision(row, conn=conn)
        created["decisions"] += 1 if res["created"] else 0
        superseded += len(res.get("superseded", []))
    for row in preview["preferences"]:
        res = repo.upsert_preference(row, conn=conn)
        created["preferences"] += 1 if res["created"] else 0
        superseded += len(res.get("superseded", []))
    for row in preview["open_loops"]:
        res = repo.upsert_open_loop(row, conn=conn)
        created["open_loops"] += 1 if res["created"] else 0
        superseded += len(res.get("superseded", []))
    return {"applied": True, "pack_id": pack_id, "created": created, "superseded": superseded,
            "counts": preview["counts"]}


def export_decision_memory(repo: Any, *, kind: str, status: str | None = None,
                           limit: int = 50, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Bounded JSON export of persisted records. JSON only; relative paths + ids + digests + bounded
    excerpts; no raw source/email bodies, no raw prompts/responses."""
    if kind == "decisions":
        records = repo.list_decisions(status=status, limit=limit, conn=conn)
    elif kind == "preferences":
        records = repo.list_preferences(status=status, limit=limit, conn=conn)
    elif kind == "open-loops":
        records = repo.list_open_loops(status=status, limit=limit, conn=conn)
    else:
        raise M.DecisionMemoryValidationError(f"unknown_export_kind:{kind}")
    return {"format": "json", "kind": kind, "count": len(records), "records": records}


def mark_open_loop_stale_if_needed(providers: DecisionMemoryProviders, repo: Any, open_loop_id: str, *,
                                   pack_id: str,
                                   conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Explicit live check: re-derive the pack's current open-loop ids; if this record is no longer
    produced (its evidence drifted) mark it stale. No background scan exists."""
    existing = repo.get_open_loop(open_loop_id, conn=conn)
    if existing is None:
        return {"open_loop_id": open_loop_id, "found": False}
    preview = preview_decision_memory(providers, pack_id=pack_id, conn=conn)
    current_ids = {r["open_loop_id"] for r in preview["open_loops"]}
    drifted = open_loop_id not in current_ids
    if drifted and existing.get("status") != M.STATUS_STALE:
        repo.mark_open_loop_stale(open_loop_id, detail="evidence_drift", conn=conn)
    return {"open_loop_id": open_loop_id, "found": True, "stale": drifted}
