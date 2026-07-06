"""N8C-7 memory compiler — deterministic, source-backed, no LLM.

Discovers recurring entities/concepts/topics from the N8C substrate (claims, context-pack items,
enrichment summaries, backlink targets), normalizes them into canonical memory nodes, attaches
source-backed mentions, and compiles bounded per-node summaries. Preview and dry-run are fully
read-only; nodes/mentions/compilations are written only by ``apply_memory_compilation(..., apply=True)``
and only into the four memory-owned tables.

Boundaries baked in:
  * SQLite stays the source of truth; compiled memory is ADVISORY — a node status / review tier /
    compilation NEVER implies a claim was accepted. The compiler only READS claims (they stay
    candidate/unreviewed).
  * Discovery prefers claim ``normalized_subject``/``normalized_object``; a raw ``claim_text`` fallback
    is lower-confidence and ``needs_operator_review``.
  * Provenance quality drives the review tier: deterministic source-backed claim mentions are
    ``trusted_source_backed`` (unless stale/ambiguous/low-confidence); Qwen-derived enrichment
    summaries are ``needs_operator_review``; backlink suggestions are ``low_confidence``. A node
    inherits its worst (most-cautious) mention tier.
  * No vault write, no raw source/email body or prompt/response persisted (bounded excerpts only),
    no claim mutation, no startup compiler. Compilation is pack-scoped by default.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from . import enrichment_review as review
from . import memory_models as mm


@dataclass
class MemoryProviders:
    claim_repo: Any
    pack_repo: Any
    enrichment_repo: Any
    source_repo: Any


@dataclass
class _NodeAgg:
    node_type: str
    canonical_name: str
    domain: str | None
    mentions: list[mm.MemoryMention] = field(default_factory=list)
    aliases: set[str] = field(default_factory=set)

    @property
    def node_id(self) -> str:
        return mm.compute_node_id(self.node_type, mm.normalize_memory_name(self.canonical_name),
                                  self.domain)


# --- provenance-quality tier ------------------------------------------------------------
def mention_tier(*, mention_type: str, source_state: str, resolution: str,
                 confidence: float | None, is_fallback: bool) -> str:
    """Advisory review tier from provenance quality (never a claim disposition)."""
    if resolution == "ambiguous":
        return mm.TIER_AMBIGUOUS_SOURCE
    if source_state in (review.SRC_DELETED, review.SRC_MISSING, review.SRC_STALE):
        return mm.TIER_STALE_SOURCE
    if mention_type == mm.MENTION_ENRICHMENT_SUMMARY:
        return mm.TIER_NEEDS_OPERATOR_REVIEW  # Qwen-derived
    if mention_type == mm.MENTION_BACKLINK_TARGET:
        return mm.TIER_LOW_CONFIDENCE
    if is_fallback:
        return mm.TIER_NEEDS_OPERATOR_REVIEW  # raw claim_text fallback
    if confidence is not None and confidence < mm.LOW_CONFIDENCE_THRESHOLD:
        return mm.TIER_LOW_CONFIDENCE
    if mention_type in (mm.MENTION_CLAIM_SUBJECT, mm.MENTION_CLAIM_OBJECT):
        return mm.TIER_TRUSTED_SOURCE_BACKED
    return mm.TIER_CANDIDATE_ONLY


# --- discovery (read-only) --------------------------------------------------------------
def discover_memory_candidates(providers: MemoryProviders, *, pack_id: str,
                               conn: sqlite3.Connection | None = None) -> dict[str, _NodeAgg]:
    """Pack-scoped discovery: turn a context pack's items into candidate nodes + source-backed
    mentions. Returns ``{node_id: _NodeAgg}``. Every returned node has at least one mention."""
    items = providers.pack_repo.list_items(pack_id, conn=conn)
    agg: dict[str, _NodeAgg] = {}
    for item in items:
        if not item.get("included", 1):
            continue
        item_type = item.get("item_type")
        if item_type == "claim_candidate" and item.get("claim_id"):
            _from_claim(providers, agg, item, pack_id, conn=conn)
        elif item_type == "backlink_suggestion":
            _from_backlink(agg, item, pack_id)
        elif item_type == "source_summary":
            _from_summary(providers, agg, item, pack_id, conn=conn)
    return agg


def _add(agg: dict[str, _NodeAgg], node_type: str, canonical_name: str, domain: str | None,
         mention: mm.MemoryMention) -> None:
    name = (canonical_name or "").strip()
    if not name or not mm.normalize_memory_name(name):
        return  # reject unsupported / empty-identity candidates
    node = _NodeAgg(node_type=node_type, canonical_name=mm.bound_text(name, mm.NAME_HARD_CAP),
                    domain=domain)
    nid = node.node_id
    holder = agg.setdefault(nid, node)
    holder.mentions.append(mention)


def _from_claim(providers: MemoryProviders, agg: dict[str, _NodeAgg], item: dict[str, Any],
                pack_id: str, *, conn: sqlite3.Connection | None) -> None:
    claim = providers.claim_repo.get_claim(item["claim_id"], conn=conn)
    if claim is None:
        return
    source_id = claim.get("source_id")
    source_state = review._source_state(providers.source_repo, source_id, conn=conn)
    resolution = review._resolution(providers.source_repo, claim.get("note_rel_path"), conn=conn)
    detail = providers.source_repo.get_source_detail(source_id, conn=conn) if source_id else None
    source_digest = detail.get("content_sha256") if detail else None
    conf = mm.clamp_confidence(claim.get("confidence"))
    subj = (claim.get("normalized_subject") or "").strip()
    obj = (claim.get("normalized_object") or "").strip()
    made = False
    for mtype, name in ((mm.MENTION_CLAIM_SUBJECT, subj), (mm.MENTION_CLAIM_OBJECT, obj)):
        if not name:
            continue
        made = True
        _add(agg, mm.NODE_ENTITY, name, None, mm.MemoryMention(
            mention_type=mtype, mention_text=name, claim_id=claim.get("claim_id"),
            source_id=source_id, note_rel_path=claim.get("note_rel_path"), pack_id=pack_id,
            pack_item_id=item.get("pack_item_id"), evidence_excerpt=claim.get("evidence_excerpt"),
            source_digest=source_digest, confidence=conf, source_state=source_state,
            review_tier=mention_tier(mention_type=mtype, source_state=source_state,
                                     resolution=resolution, confidence=conf, is_fallback=False)))
    if not made:
        # Fallback: raw claim_text → a single concept node, lower-confidence + needs review.
        text = (claim.get("claim_text") or "").strip()
        if text:
            _add(agg, mm.NODE_CONCEPT, text, None, mm.MemoryMention(
                mention_type=mm.MENTION_CLAIM_SUBJECT, mention_text=mm.bound_text(text, 120),
                claim_id=claim.get("claim_id"), source_id=source_id,
                note_rel_path=claim.get("note_rel_path"), pack_id=pack_id,
                pack_item_id=item.get("pack_item_id"), evidence_excerpt=claim.get("evidence_excerpt"),
                source_digest=source_digest, confidence=min(conf, 0.39), source_state=source_state,
                review_tier=mention_tier(mention_type=mm.MENTION_CLAIM_SUBJECT,
                                         source_state=source_state, resolution=resolution,
                                         confidence=conf, is_fallback=True)))


def _from_backlink(agg: dict[str, _NodeAgg], item: dict[str, Any], pack_id: str) -> None:
    target = (item.get("evidence_excerpt") or item.get("title") or "").strip()
    if not target:
        return
    _add(agg, mm.NODE_TOPIC, target, None, mm.MemoryMention(
        mention_type=mm.MENTION_BACKLINK_TARGET, mention_text=mm.bound_text(target, 120),
        source_id=item.get("source_id"), note_rel_path=item.get("note_rel_path"),
        receipt_id=item.get("receipt_id"), job_id=item.get("job_id"), pack_id=pack_id,
        pack_item_id=item.get("pack_item_id"), evidence_excerpt=target,
        confidence=item.get("confidence"),
        review_tier=mention_tier(mention_type=mm.MENTION_BACKLINK_TARGET, source_state="current",
                                 resolution="none", confidence=item.get("confidence"),
                                 is_fallback=False)))


def _from_summary(providers: MemoryProviders, agg: dict[str, _NodeAgg], item: dict[str, Any],
                  pack_id: str, *, conn: sqlite3.Connection | None) -> None:
    # A source_summary item ties a Qwen-derived summary to its source; make a source-topic node.
    source_id = item.get("source_id")
    note_rel_path = item.get("note_rel_path")
    name = _source_topic_name(note_rel_path, source_id)
    if not name:
        return
    source_state = review._source_state(providers.source_repo, source_id, conn=conn)
    resolution = review._resolution(providers.source_repo, note_rel_path, conn=conn)
    _add(agg, mm.NODE_TOPIC, name, None, mm.MemoryMention(
        mention_type=mm.MENTION_ENRICHMENT_SUMMARY, mention_text=name, source_id=source_id,
        note_rel_path=note_rel_path, receipt_id=item.get("receipt_id"), job_id=item.get("job_id"),
        pack_id=pack_id, pack_item_id=item.get("pack_item_id"),
        evidence_excerpt=item.get("content_excerpt"),
        source_digest=item.get("source_digest"), confidence=item.get("confidence"),
        source_state=source_state,
        review_tier=mention_tier(mention_type=mm.MENTION_ENRICHMENT_SUMMARY,
                                 source_state=source_state, resolution=resolution,
                                 confidence=item.get("confidence"), is_fallback=False)))


def _source_topic_name(note_rel_path: str | None, source_id: str | None) -> str:
    if note_rel_path:
        stem = PurePosixPath(str(note_rel_path)).stem
        if stem.strip():
            return stem.strip()
    return f"source:{source_id}" if source_id else ""


# --- compile (deterministic) ------------------------------------------------------------
def _node_input_digest(mentions: list[mm.MemoryMention]) -> str:
    anchors = sorted(
        f"{m.mention_type}|{m.source_id or ''}|{m.claim_id or ''}|{m.pack_item_id or ''}|"
        f"{m.source_digest or ''}|{m.source_state or ''}|{m.review_tier or ''}"
        for m in mentions
    )
    return mm.sha256_hex(json.dumps(anchors, sort_keys=True))


def _compile_node(node: _NodeAgg, *, compile_type: str = mm.COMPILE_NODE_SUMMARY) -> dict[str, Any]:
    mentions = node.mentions
    tiers = [m.review_tier for m in mentions if m.review_tier]
    tier = mm.worst_tier(tiers)
    source_ids = {m.source_id for m in mentions if m.source_id}
    claim_ids = {m.claim_id for m in mentions if m.claim_id}
    pack_ids = {m.pack_id for m in mentions if m.pack_id}
    input_digest = _node_input_digest(mentions)
    node_id = node.node_id
    # Bounded, deterministic key points = distinct mention texts (order-stable).
    seen: set[str] = set()
    key_points: list[str] = []
    for m in mentions:
        t = mm.bound_text(m.mention_text or m.evidence_excerpt or "", mm.KEY_POINT_CAP).strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            key_points.append(t)
    truncated = len(key_points) > mm.KEY_POINTS_MAX
    key_points = key_points[: mm.KEY_POINTS_MAX]
    stale_count = sum(1 for m in mentions
                      if m.review_tier in (mm.TIER_STALE_SOURCE, mm.TIER_AMBIGUOUS_SOURCE,
                                           mm.TIER_NEEDS_OPERATOR_REVIEW))
    open_questions: list[str] = []
    if tier != mm.TIER_TRUSTED_SOURCE_BACKED:
        open_questions.append(f"Operator review advised: node tier is {tier}.")
    summary = mm.bound_text(
        f"{node.canonical_name} ({node.node_type}) — {len(mentions)} mention(s) across "
        f"{len(source_ids)} source(s) and {len(claim_ids)} claim(s); advisory tier {tier}.",
        mm.SUMMARY_HARD_CAP)
    output_digest = mm.sha256_hex(json.dumps({"summary": summary, "key_points": key_points,
                                              "tier": tier}, sort_keys=True))
    compilation_id = mm.compute_compilation_id(node_id, compile_type, input_digest)
    return {
        "compilation_id": compilation_id,
        "node_id": node_id,
        "compile_type": compile_type,
        "summary": summary,
        "key_points_json": json.dumps(key_points, sort_keys=True),
        "open_questions_json": json.dumps(open_questions, sort_keys=True),
        "risks_json": json.dumps([], sort_keys=True),
        "preferences_json": json.dumps([], sort_keys=True),
        "source_count": len(source_ids),
        "claim_count": len(claim_ids),
        "pack_count": len(pack_ids),
        "mention_count": len(mentions),
        "input_digest": input_digest,
        "output_digest": output_digest,
        "stale_count": stale_count,
        "truncated": truncated,
        "review_tier": tier,
    }


def _node_header(node: _NodeAgg, input_digest: str, created_by: str) -> dict[str, Any]:
    tiers = [m.review_tier for m in node.mentions if m.review_tier]
    confs = [m.confidence for m in node.mentions if m.confidence is not None]
    return {
        "node_id": node.node_id,
        "node_type": node.node_type,
        "canonical_name": node.canonical_name,
        "normalized_name": mm.normalize_memory_name(node.canonical_name),
        "domain": node.domain,
        "aliases": sorted(node.aliases),
        "review_tier": mm.worst_tier(tiers),
        "confidence": max(confs) if confs else None,
        "input_digest": input_digest,
        "created_by": created_by,
    }


def preview_memory_compilation(providers: MemoryProviders, *, pack_id: str, created_by: str = "service",
                               conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Discover + compile for a pack WITHOUT persisting. Fully read-only."""
    agg = discover_memory_candidates(providers, pack_id=pack_id, conn=conn)
    nodes: list[dict[str, Any]] = []
    mentions: list[dict[str, Any]] = []
    compilations: list[dict[str, Any]] = []
    for node in agg.values():
        input_digest = _node_input_digest(node.mentions)
        nodes.append(_node_header(node, input_digest, created_by))
        mentions.extend(m.to_row(node.node_id) for m in node.mentions)
        compilations.append(_compile_node(node))
    return {"pack_id": pack_id, "nodes": nodes, "mentions": mentions,
            "compilations": compilations, "node_count": len(nodes),
            "mention_count": len(mentions)}


def apply_memory_compilation(providers: MemoryProviders, memory_repo: Any, *, pack_id: str,
                             apply: bool = False, created_by: str = "service",
                             conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Discover + compile, and — only when ``apply`` — persist nodes/mentions/compilations into the
    memory-owned tables (nothing else). Idempotent: re-running over unchanged inputs creates no
    duplicates; a changed input digest yields a new compilation that supersedes the prior."""
    preview = preview_memory_compilation(providers, pack_id=pack_id, created_by=created_by, conn=conn)
    if not apply:
        return {"applied": False, **preview}
    agg = discover_memory_candidates(providers, pack_id=pack_id, conn=conn)
    persisted_nodes = 0
    persisted_mentions = 0
    persisted_compilations = 0
    for node in agg.values():
        input_digest = _node_input_digest(node.mentions)
        memory_repo.upsert_node(_node_header(node, input_digest, created_by), conn=conn)
        for m in node.mentions:
            if memory_repo.upsert_mention(m.to_row(node.node_id), conn=conn)["created"]:
                persisted_mentions += 1
        memory_repo.refresh_node_counts(node.node_id, conn=conn)
        comp = _compile_node(node)
        if memory_repo.persist_compilation(comp, conn=conn)["created"]:
            persisted_compilations += 1
        persisted_nodes += 1
    return {"applied": True, "pack_id": pack_id, "nodes": persisted_nodes,
            "new_mentions": persisted_mentions, "new_compilations": persisted_compilations,
            "node_count": preview["node_count"]}


def export_memory_node(node: dict[str, Any], mentions: list[dict[str, Any]],
                       compilations: list[dict[str, Any]], *, fmt: str = "json") -> dict[str, Any]:
    """Bounded export of a persisted node. JSON only; relative paths + ids + digests + bounded
    excerpts; no raw source/email bodies, no raw prompts/responses."""
    if fmt != "json":
        raise mm.MemoryValidationError(f"unsupported_export_format:{fmt}")
    return {
        "format": "json",
        "node": {k: node.get(k) for k in (
            "node_id", "node_type", "canonical_name", "normalized_name", "aliases_json", "domain",
            "status", "review_tier", "confidence", "source_count", "claim_count", "mention_count",
            "compilation_count", "input_digest", "created_at")},
        "mentions": [
            {k: m.get(k) for k in (
                "mention_id", "mention_type", "mention_text", "source_id", "note_rel_path",
                "claim_id", "receipt_id", "pack_id", "pack_item_id", "evidence_excerpt",
                "source_digest", "confidence", "review_tier", "source_state")}
            for m in mentions],
        "compilations": [
            {k: c.get(k) for k in (
                "compilation_id", "compile_type", "summary", "key_points_json", "open_questions_json",
                "source_count", "claim_count", "mention_count", "input_digest", "output_digest",
                "stale_count", "truncated", "review_tier", "status", "created_at")}
            for c in compilations],
    }


def mark_memory_node_stale_if_needed(providers: MemoryProviders, memory_repo: Any, node_id: str, *,
                                     pack_id: str,
                                     conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Explicit live check: re-derive the node's input digest from the pack and compare to the
    stored one. On drift, mark the node stale (explicit). No background scan exists."""
    existing = memory_repo.get_node(node_id, conn=conn)
    if existing is None:
        return {"node_id": node_id, "found": False}
    agg = discover_memory_candidates(providers, pack_id=pack_id, conn=conn)
    node = agg.get(node_id)
    current = _node_input_digest(node.mentions) if node else ""
    stored = existing.get("input_digest")
    drifted = current != stored
    if drifted and existing.get("status") != "stale":
        memory_repo.mark_node_stale(node_id, detail="input_digest_drift", conn=conn)
    return {"node_id": node_id, "found": True, "stale": drifted,
            "stored_input_digest": stored, "current_input_digest": current}
