"""Phase 10 V51 — advisory candidate similarity / duplicate layer (review-only, never auto-merge).

Produces raw-free ``candidate_similarity_edges`` so the operator can *review* possible duplicates.
It NEVER merges, suppresses, or hides a candidate — the V50 lifecycle merge/suppression service
remains the only authority for that.

Three deterministic-first signals, in precedence order:

1. **Deterministic exact clusters** — subjects sharing a V50 ``duplicate_group_key`` (which already
   folds in canonical source id + normalized title/reason) are exact duplicates (score 1.0).
2. **Normalized title/reason match** — a cheap deterministic fallback for items without a shared
   group key (score 0.95).
3. **Semantic similarity** — optional cosine over a redacted title+reason embedding, using the
   hermetic :class:`DeterministicEmbedder` in tests or a local Ollama embedder when safe. Transient
   vectors only; never persisted. Skipped (and reported) above a bounded candidate count.

Model-advised duplicate pairs are recorded as advisory edges too, but only as additional review
evidence — they carry a ``model_advisory`` method and never change scoring.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Optional

from hb_assistant.retrieval.embedder import Embedder

from .candidate_lifecycle import scrub_note

#: Above this candidate count the O(n^2) semantic pass is skipped and reported (kept bounded).
_MAX_SEMANTIC_ITEMS = 200
_DEFAULT_SEMANTIC_THRESHOLD = 0.85
_REVIEW_RECOMMENDATION = "review_duplicate_candidate"


def _normalized_text(item: dict[str, Any]) -> str:
    parts = [str(item.get("title_redacted") or ""), str(item.get("reason_redacted") or "")]
    scrubbed = scrub_note(" ".join(parts), max_chars=240) or ""
    return scrubbed.strip().lower()


def _cluster_id(member_ids: list[str]) -> str:
    blob = "|".join(sorted(member_ids))
    return "cl:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def build_similarity_edges(
    items: list[dict[str, Any]],
    *,
    brief_date: str,
    embedder: Optional[Embedder] = None,
    semantic_threshold: float = _DEFAULT_SEMANTIC_THRESHOLD,
    model_duplicates: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Build advisory similarity edges for a packet's items. Pure; returns edges + cluster map.

    Each edge is a raw-free dict ready for ``ConstructionStore.upsert_similarity_edge``. Returns
    ``edges``, the deterministic ``clusters`` (cluster_id → member candidate ids), and whether the
    semantic pass ran.
    """
    edges: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    clusters: dict[str, list[str]] = {}

    def _add_edge(a: str, b: str, score: float, method: str, cluster_id: Optional[str],
                  features: dict[str, Any], model_label: Optional[str] = None) -> None:
        lo, hi = sorted((a, b))
        key: tuple[str, str] = (lo, hi)
        if key in seen_pairs or a == b:
            return
        seen_pairs.add(key)
        edges.append(
            {
                "brief_date": brief_date,
                "candidate_a_id": key[0],
                "candidate_b_id": key[1],
                "similarity_score": round(score, 4),
                "similarity_method": method,
                "cluster_id": cluster_id,
                "deterministic_features_json": json.dumps(features, sort_keys=True),
                "model_label": model_label,
                "review_recommendation": _REVIEW_RECOMMENDATION,
            }
        )

    # 1. Deterministic exact clusters by V50 duplicate_group_key.
    by_group: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        gk = it.get("duplicate_group_key")
        if gk:
            by_group.setdefault(str(gk), []).append(it)
    for gk, members in by_group.items():
        if len(members) < 2:
            continue
        member_ids = sorted(str(m["candidate_id"]) for m in members)
        cid = _cluster_id(member_ids)
        clusters[cid] = member_ids
        for i in range(len(member_ids)):
            for j in range(i + 1, len(member_ids)):
                _add_edge(member_ids[i], member_ids[j], 1.0, "deterministic_group_key", cid,
                          {"duplicate_group_key": gk})

    # 2. Normalized title/reason match for items without a shared group key.
    by_norm: dict[str, list[str]] = {}
    for it in items:
        norm = _normalized_text(it)
        if norm:
            by_norm.setdefault(norm, []).append(str(it["candidate_id"]))
    for member_ids in by_norm.values():
        uniq = sorted(set(member_ids))
        if len(uniq) < 2:
            continue
        cid = _cluster_id(uniq)
        clusters.setdefault(cid, uniq)
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                _add_edge(uniq[i], uniq[j], 0.95, "normalized_text", cid,
                          {"normalized_text_match": True})

    # 3. Optional semantic pass (transient vectors only; bounded; never persists vectors).
    semantic_ran = False
    if embedder is not None and 1 < len(items) <= _MAX_SEMANTIC_ITEMS:
        semantic_ran = True
        vectors: list[tuple[str, list[float]]] = []
        for it in items:
            text = _normalized_text(it)
            if text:
                vectors.append((str(it["candidate_id"]), embedder.embed(text)))
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                a_id, a_vec = vectors[i]
                b_id, b_vec = vectors[j]
                score = _cosine(a_vec, b_vec)
                if score >= semantic_threshold:
                    _add_edge(a_id, b_id, score, "semantic_embedding", None,
                              {"cosine": round(score, 4)})

    # 4. Model-advised duplicates (review evidence only; never affects scoring or lifecycle).
    for d in model_duplicates or []:
        ma_id = d.get("candidate_a_id")
        mb_id = d.get("candidate_b_id")
        if ma_id and mb_id:
            _add_edge(str(ma_id), str(mb_id), 0.5, "model_advisory", None,
                      {"model": True}, model_label=d.get("similarity_label"))

    return {
        "edges": edges,
        "clusters": clusters,
        "semantic_ran": semantic_ran,
        "edge_count": len(edges),
    }
