"""Phase 10 V51 — bounded local-Ollama advisory ranking layer (fails closed to deterministic).

Wraps the existing schema-enforced :class:`StructuredOutputClient` (local-only, hash-only receipts,
bounded retry/self-repair, single-hop fallback) with a strict post-validation pass so the model can
*advise* but never *decide*:

* The model receives only the redacted structured packet and is told the deterministic score,
  lifecycle state, and source-ref gates are authoritative.
* Output is validated against :class:`CandidateRankingAdvice` (``extra="forbid"``, clamped strings).
* Any advice citing an unknown alias is dropped; any leaky narrative withholds the whole model
  layer (raw safety beats partial advice).
* Surviving advice becomes a bounded ``model_advisory_score`` per candidate; the ranking engine
  caps how far that can move an item.

Fail-closed to deterministic ranking on: daemon unavailable, model missing, timeout, invalid JSON or
schema, leaky output, unknown aliases, or no usable advice. Only hash-only receipts + ranking
metadata are persisted — never prompts or responses.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .candidate_ranking_models import CandidateRankingAdvice
from .model_eval_metrics import scan_text_for_forbidden
from .models import LocalModelProfile, LocalModelProfiles
from .structured_output import GenerationBackend, StructuredOutputClient

TASK_TYPE = "candidate_ranking_brief_assembly"

_SYSTEM = (
    "You re-order an ALREADY-DECIDED daily brief. The deterministic score, lifecycle state, and "
    "source-ref gates are authoritative and you cannot override them. You may only: suggest relative "
    "priority within a bounded range, assign short grouping labels, flag possible duplicates, and "
    "write one short 'why this matters' per item. You may reference ONLY the candidate aliases given. "
    "Never invent source refs, names, dates, amounts, URLs, emails, claims, or project facts. Never "
    "change lifecycle state, accept/reject/snooze/merge/suppress, or recommend external actions. "
    "Return JSON only, matching the schema."
)


def _packet_prompt(packet: dict[str, Any]) -> str:
    """Build the redacted prompt body (aliases + bounded redacted signals only — never raw text)."""
    rows = []
    for it in packet.get("items", []):
        rows.append(
            {
                "alias": it["alias"],
                "family": it["family"],
                "section": it["section"],
                "lifecycle_state": it["lifecycle_state"],
                "due_bucket": it["due_bucket"],
                "waiting_signal": it["waiting_signal"],
                "project_key": it.get("project_key"),
                "title_redacted": it.get("title_redacted"),
                "reason_redacted": it.get("reason_redacted"),
            }
        )
    return json.dumps({"candidates": rows}, sort_keys=True, separators=(",", ":"))


def _advisory_score(priority_hint: Optional[int], total: int) -> Optional[float]:
    """Map a 1..N priority hint (1 = highest) to a bounded 0..100 advisory score."""
    if priority_hint is None or total <= 0:
        return None
    hint = max(1, min(priority_hint, total))
    return round(100.0 * (total - (hint - 1)) / total, 4)


def build_ranking_advice(
    packet: dict[str, Any],
    *,
    profile: LocalModelProfile,
    profiles: LocalModelProfiles,
    backend: Optional[GenerationBackend] = None,
    store: Optional[Any] = None,
    dry_run: bool = True,
    heavy_enabled: bool = False,
) -> dict[str, Any]:
    """Run the bounded advisory model over a ranking packet and post-validate its output.

    Returns a dict with: ``status`` (``ok`` | ``withheld`` | ``degraded``), ``model_scores``
    (candidate_id → 0..100), ``why`` / ``reason_codes`` per candidate_id, advisory ``groups`` /
    ``duplicates`` (alias-based), the hash-only receipt fields, and honest drop/withhold reasons.
    """
    alias_map: dict[str, str] = dict(packet.get("alias_map") or {})
    items = packet.get("packet", packet).get("items", []) if "packet" in packet else packet.get(
        "items", []
    )
    known_aliases = {str(it["alias"]) for it in items}
    total = len(items)

    result = StructuredOutputClient().run(
        schema=CandidateRankingAdvice,
        profile=profile,
        profiles=profiles,
        system=_SYSTEM,
        prompt=_packet_prompt({"items": items}),
        input_context=str(packet.get("packet", packet).get("candidate_set_hash", "")),
        task_type=TASK_TYPE,
        backend=backend,
        store=store,
        dry_run=dry_run,
        heavy_enabled=heavy_enabled,
    )

    receipt = {
        "model_status": result.status,
        "model_profile_id": result.profile_id,
        "model_name": result.model_name,
        "model_receipt_id": result.receipt_id,
        "output_hash": result.output_hash,
        "input_context_hash": result.input_context_hash,
        "fallback_used": result.fallback_used,
        "would_write_receipt": result.would_write_receipt,
    }

    if result.status != "ok" or not result.validated:
        return {
            "status": "degraded",
            "degraded_reason": f"model_{result.status}",
            "model_scores": {},
            "why": {},
            "reason_codes": {},
            "groups": [],
            "duplicates": [],
            "dropped_unknown_alias": 0,
            **receipt,
        }

    advice = CandidateRankingAdvice.model_validate(result.validated)

    # Raw safety beats partial advice: any leaky narrative withholds the whole model layer.
    for ai in advice.items:
        if scan_text_for_forbidden(ai.why_this_matters) or scan_text_for_forbidden(ai.group_label):
            return {
                "status": "withheld",
                "degraded_reason": "raw_leak_in_model_output",
                "model_scores": {},
                "why": {},
                "reason_codes": {},
                "groups": [],
                "duplicates": [],
                "dropped_unknown_alias": 0,
                **receipt,
            }
    for g in advice.groups:
        if scan_text_for_forbidden(g.group_label):
            return {
                "status": "withheld",
                "degraded_reason": "raw_leak_in_model_output",
                "model_scores": {},
                "why": {},
                "reason_codes": {},
                "groups": [],
                "duplicates": [],
                "dropped_unknown_alias": 0,
                **receipt,
            }

    model_scores: dict[str, float] = {}
    why: dict[str, str] = {}
    reason_codes: dict[str, list[str]] = {}
    dropped = 0
    for ai in advice.items:
        if ai.alias not in known_aliases:
            dropped += 1
            continue
        cid = alias_map[ai.alias]
        score = _advisory_score(ai.priority_hint, total)
        if score is not None:
            model_scores[cid] = score
        if ai.why_this_matters:
            why[cid] = ai.why_this_matters
        if ai.reason_codes:
            reason_codes[cid] = ai.reason_codes

    # Advisory groups/duplicates referencing only known aliases (raw-free, review-only).
    groups = [
        {"group_label": g.group_label, "aliases": [a for a in g.aliases if a in known_aliases]}
        for g in advice.groups
    ]
    duplicates = [
        {
            "alias_a": d.alias_a,
            "alias_b": d.alias_b,
            "candidate_a_id": alias_map.get(d.alias_a),
            "candidate_b_id": alias_map.get(d.alias_b),
            "similarity_label": d.similarity_label,
        }
        for d in advice.duplicates
        if d.alias_a in known_aliases and d.alias_b in known_aliases and d.alias_a != d.alias_b
    ]

    usable = bool(model_scores or why or groups or duplicates)
    return {
        "status": "ok" if usable else "degraded",
        "degraded_reason": None if usable else "all_model_advice_dropped",
        "model_scores": model_scores,
        "why": why,
        "reason_codes": reason_codes,
        "groups": groups,
        "duplicates": duplicates,
        "dropped_unknown_alias": dropped,
        **receipt,
    }
