"""Phase 10 V51 — daily-brief assembly orchestration (deterministic-authoritative, model advisory).

The single entry point that ties the V51 overlay together:

    packet → feedback calibration → (optional bounded model advice) → deterministic ranking
           → (optional advisory similarity) → deterministic section assembly → (optional persist)

The deterministic ranking and section order are authoritative; model output only nudges within a
bounded range and only after deterministic eligibility is established. If the model layer is
unavailable, withheld, or unsafe, the deterministic ranked brief is preserved and the run is marked
``deterministic_fallback_used`` with an honest ``model_layer_status``. ``--no-client`` is a success
path (deterministic ranking still runs); only a fail-closed packet (raw leak) fails the run.

Dry-run performs zero writes. Apply requires ``max_persist`` and caps the number of ranked-candidate
and similarity-edge rows written. Only redacted/hashed metadata is persisted — never raw content,
prompts, or responses.
"""

from __future__ import annotations

from typing import Any, Optional

from hb_assistant.retrieval.embedder import Embedder

from . import candidate_lifecycle as lc
from .candidate_ranking import ALGORITHM_VERSION, POLICY_VERSION, rank_candidates
from .candidate_ranking_models import CandidateRankingResult, DailyBriefAssemblyResult
from .candidate_ranking_packets import build_candidate_ranking_packet
from .candidate_similarity import build_similarity_edges
from .feedback_calibration import build_calibration
from .model_eval_metrics import compute_usefulness
from .models import LocalModelProfile, LocalModelProfiles
from .ollama_candidate_ranking import build_ranking_advice
from .structured_output import GenerationBackend

ASSEMBLY_POLICY_VERSION = "assembly-v1"

#: Number of top-ranked items pulled into the "top priorities" section.
_TOP_N = 5

#: Deterministic section order + display titles (raw-free).
_SECTION_ORDER: list[tuple[str, str]] = [
    ("top_priorities", "Top Priorities"),
    ("waiting_on_me", "Waiting On Me"),
    ("waiting_on_others", "Waiting On Others / Follow-ups"),
    ("meeting_prep", "Meeting Prep"),
    ("project_procore_risk", "Project / Procore Risk"),
    ("review_needs_decision", "Review Queue / Needs Decision"),
    ("accepted_stale", "Accepted Stale Items"),
    ("data_gaps_degraded", "Data Gaps / Degraded Model Status"),
]
_RISK_SECTIONS: frozenset[str] = frozenset({"procore"})
_MEETING_SECTIONS: frozenset[str] = frozenset({"calendar", "meeting_prep"})


def _category_for(item: dict[str, Any]) -> str:
    """Map a ranked item to its primary assembly section (deterministic)."""
    state = str(item.get("lifecycle_state"))
    family = str(item.get("family") or "")
    section = str(item.get("section") or "")
    waiting = str(item.get("waiting_signal"))
    if state == lc.STATE_STALE:
        return "accepted_stale"
    if state in (lc.STATE_NEW, lc.STATE_NEEDS_REVIEW, lc.STATE_PROJECT_REVIEW_REQUIRED):
        return "review_needs_decision"
    # accepted-ish
    if family in _RISK_SECTIONS or section in _RISK_SECTIONS:
        return "project_procore_risk"
    if family in _MEETING_SECTIONS or section in _MEETING_SECTIONS:
        return "meeting_prep"
    if waiting == "waiting_on_me":
        return "waiting_on_me"
    if waiting == "waiting_on_others" or item.get("subject_type") == "follow_up_watch":
        return "waiting_on_others"
    return "top_priorities"


def _assemble_sections(
    ranked: list[dict[str, Any]], *, withheld_source_missing: int, model_layer_status: str
) -> list[dict[str, Any]]:
    """Build deterministic-ordered sections from the ranked items (top-N first, then by category)."""
    top_ids = {str(r["candidate_id"]) for r in ranked[:_TOP_N]}
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in _SECTION_ORDER}
    for r in ranked:
        cid = str(r["candidate_id"])
        key = "top_priorities" if cid in top_ids else _category_for(r)
        buckets[key].append(r)

    sections: list[dict[str, Any]] = []
    for display_order, (key, title) in enumerate(_SECTION_ORDER):
        members = buckets[key]
        if key == "data_gaps_degraded":
            # Informational only — carries no candidate ids; reports withheld + model status.
            if withheld_source_missing == 0 and model_layer_status in ("ok", "model_enriched"):
                continue
            degraded = (
                f"source_missing_withheld={withheld_source_missing};model_layer={model_layer_status}"
            )
            sections.append(
                {
                    "section_key": key,
                    "display_order": display_order,
                    "title_redacted": title,
                    "candidate_ids": [],
                    "section_score": 0.0,
                    "degraded_reason": degraded,
                }
            )
            continue
        if not members:
            continue
        ids = [str(m["candidate_id"]) for m in members]
        avg = round(sum(float(m["final_score"]) for m in members) / len(members), 4)
        sections.append(
            {
                "section_key": key,
                "display_order": display_order,
                "title_redacted": title,
                "candidate_ids": ids,
                "section_score": avg,
                "degraded_reason": None,
            }
        )
    return sections


def run_candidate_ranking_and_assembly(
    *,
    store: Any,
    brief_date: str,
    now_utc: Optional[str] = None,
    profile: Optional[LocalModelProfile] = None,
    profiles: Optional[LocalModelProfiles] = None,
    backend: Optional[GenerationBackend] = None,
    use_model: bool = True,
    include_similarity: bool = True,
    embedder: Optional[Embedder] = None,
    dry_run: bool = True,
    max_persist: Optional[int] = None,
    heavy_enabled: bool = False,
) -> dict[str, Any]:
    """Run the full V51 ranking + assembly overlay for ``brief_date``.

    Returns a dict carrying ``status``, the ``ranking`` (:class:`CandidateRankingResult` dump), the
    ``assembly`` (:class:`DailyBriefAssemblyResult` dump), advisory ``similarity`` summary, a
    hash-only model ``receipt`` block, and a ``persistence`` summary. The deterministic ranked brief
    is always present; the model layer is clearly labeled advisory.
    """
    if not dry_run and max_persist is None:
        raise ValueError("apply requires max_persist (cap on actual persisted rows)")

    now = now_utc or lc.utc_now()
    packet_result = build_candidate_ranking_packet(store, brief_date=brief_date, now_utc=now)
    packet = packet_result["packet"]
    items = packet["items"]
    withheld = int(packet_result["withheld_source_missing_count"])

    # Fail closed on a raw leak — never render a leaky packet.
    if packet_result["status"] == "fail_closed":
        return {
            "command": "second-brain daily-brief rank-candidates",
            "status": "fail_closed",
            "ok": False,
            "brief_date": brief_date,
            "reason": "packet_guard_unclean",
            "leak_categories": packet_result["leak_categories"],
            "guardrails": _guardrails(),
        }

    calibration = build_calibration(packet_result["feedback_summary"])

    # Bounded advisory model (optional). ``use_model=False`` / no client = clean deterministic run.
    advice: dict[str, Any] = {
        "status": "withheld",
        "degraded_reason": "no_client",
        "model_scores": {},
        "why": {},
        "reason_codes": {},
        "groups": [],
        "duplicates": [],
        "model_status": "no_client",
        "model_profile_id": None,
        "model_name": None,
        "model_receipt_id": None,
        "output_hash": None,
        "input_context_hash": None,
        "would_write_receipt": None,
    }
    if use_model and profile is not None and profiles is not None and items:
        advice = build_ranking_advice(
            {"packet": packet, "alias_map": packet_result["alias_map"]},
            profile=profile,
            profiles=profiles,
            backend=backend,
            store=store if not dry_run else None,
            dry_run=dry_run,
            heavy_enabled=heavy_enabled,
        )

    model_ok = advice["status"] == "ok"
    model_scores = advice["model_scores"] if model_ok else {}
    ranked = rank_candidates(items, calibration=calibration, model_scores=model_scores)

    # Merge advisory narrative/codes onto ranked rows (raw-free; deterministic order preserved).
    for r in ranked:
        cid = str(r["candidate_id"])
        r["why_this_matters_redacted"] = advice["why"].get(cid) if model_ok else None
        r["model_reason_codes"] = advice["reason_codes"].get(cid) if model_ok else None

    # Model layer status: ok/enriched, withheld (no client), or degraded (failed/unsafe).
    if model_ok:
        model_layer_status = "model_enriched"
        deterministic_fallback_used = False
        degraded_reason = None
    elif advice["status"] == "withheld" and advice.get("degraded_reason") == "no_client":
        model_layer_status = "withheld"
        deterministic_fallback_used = True
        degraded_reason = "no_client"
    else:
        model_layer_status = advice["status"]  # withheld | degraded
        deterministic_fallback_used = True
        degraded_reason = advice.get("degraded_reason")

    coverage = float(packet["source_ref_coverage"])
    usefulness = _usefulness_score(ranked, coverage)

    # Similarity (advisory; deterministic-first, never auto-merges).
    similarity: dict[str, Any] = {"edges": [], "clusters": {}, "semantic_ran": False, "edge_count": 0}
    if include_similarity and items:
        similarity = build_similarity_edges(
            items,
            brief_date=brief_date,
            embedder=embedder,
            model_duplicates=advice["duplicates"] if model_ok else None,
        )

    sections = _assemble_sections(
        ranked, withheld_source_missing=withheld, model_layer_status=model_layer_status
    )

    # Deterministic ids (idempotent) — computed even in dry-run so the result is stable.
    ranking_run_id = store.ranking_run_id_for(
        brief_date,
        packet["candidate_set_hash"],
        packet["feedback_digest_hash"],
        POLICY_VERSION,
        ALGORITHM_VERSION,
        model_layer_status,
        advice.get("model_receipt_id"),
    )
    assembly_run_id = store.assembly_run_id_for(brief_date, ranking_run_id, ASSEMBLY_POLICY_VERSION)

    persistence: dict[str, Any] = {
        "persisted_ranked": 0,
        "would_persist_ranked": len(ranked),
        "persisted_edges": 0,
        "would_persist_edges": len(similarity["edges"]),
    }
    if not dry_run:
        persistence = _persist(
            store,
            brief_date=brief_date,
            ranking_run_id=ranking_run_id,
            assembly_run_id=assembly_run_id,
            packet=packet,
            ranked=ranked,
            sections=sections,
            similarity=similarity,
            model_layer_status=model_layer_status,
            deterministic_fallback_used=deterministic_fallback_used,
            degraded_reason=degraded_reason,
            coverage=coverage,
            usefulness=usefulness,
            withheld=withheld,
            max_persist=int(max_persist or 0),
        )

    ranking = CandidateRankingResult(
        brief_date=brief_date,
        ranking_run_id=ranking_run_id,
        policy_version=POLICY_VERSION,
        algorithm_version=ALGORITHM_VERSION,
        candidate_set_hash=packet["candidate_set_hash"],
        feedback_digest_hash=packet["feedback_digest_hash"],
        model_status=model_layer_status,
        model_profile_id=advice.get("model_profile_id"),
        model_name=advice.get("model_name"),
        model_receipt_id=advice.get("model_receipt_id"),
        deterministic_fallback_used=deterministic_fallback_used,
        degraded_reason=degraded_reason,
        candidate_count=len(items),
        ranked_count=len(ranked),
        withheld_source_missing_count=withheld,
        source_ref_coverage=round(coverage, 4),
        usefulness_score=usefulness,
        guard_clean=bool(packet["packet_guard_clean"]),
        ranked=[_ranked_public(r) for r in ranked],
    )
    assembly = DailyBriefAssemblyResult(
        brief_date=brief_date,
        assembly_run_id=assembly_run_id,
        ranking_run_id=ranking_run_id,
        assembly_policy_version=ASSEMBLY_POLICY_VERSION,
        model_layer_status=model_layer_status,
        deterministic_fallback_used=deterministic_fallback_used,
        withheld_reason=(f"source_missing_withheld={withheld}" if withheld else None),
        section_count=len(sections),
        candidate_count=len(ranked),
        sections=sections,
    )

    status = "ok" if packet_result["status"] in ("ok", "no_eligible_candidates") else "degraded"
    return {
        "command": "second-brain daily-brief rank-candidates",
        "status": status,
        "ok": True,
        "brief_date": brief_date,
        "applied": not dry_run,
        "packet_status": packet_result["status"],
        "ranking": ranking.model_dump(),
        "assembly": assembly.model_dump(),
        "similarity": {
            "edge_count": similarity["edge_count"],
            "cluster_count": len(similarity["clusters"]),
            "semantic_ran": similarity["semantic_ran"],
            "review_only": True,
        },
        "receipt": {
            "model_status": advice.get("model_status"),
            "model_receipt_id": advice.get("model_receipt_id"),
            "output_hash": advice.get("output_hash"),
            "input_context_hash": advice.get("input_context_hash"),
            "would_write_receipt": advice.get("would_write_receipt"),
            "dropped_unknown_alias": advice.get("dropped_unknown_alias", 0),
        },
        "persistence": persistence,
        "guardrails": _guardrails(),
    }


_MUST_HAVE_REFS: frozenset[str] = frozenset(
    {
        "task_candidate",
        "commitment_candidate",
        "daily_brief_action",
        "accepted_task",
        "accepted_commitment",
    }
)


def ranking_stage_context(result: dict[str, Any]) -> dict[str, Any]:
    """Ranking contradiction flags for the usefulness gate (mirrors ``lifecycle_stage_context``).

    Verifies — never trusts — that the advisory model never became authority: model-scored items
    must be source-linked and lifecycle-eligible, an "enriched" claim must carry receipt/status
    metadata and real advice, fallback must not coexist with a clean-success claim, and surfaced
    source-ref coverage must be 1.0. The gate appends these to a would-be ``success``.
    """
    ranking = result.get("ranking", {})
    receipt = result.get("receipt", {})
    ranked = ranking.get("ranked", [])
    contradictions: list[str] = []

    for r in ranked:
        if r.get("model_advisory_score") is not None:
            if str(r.get("subject_type")) in _MUST_HAVE_REFS and int(r.get("source_ref_count") or 0) == 0:
                contradictions.append("model_ranked_item_missing_source_refs")
            if str(r.get("lifecycle_state")) in lc.HIDDEN_FROM_BRIEF_STATES:
                contradictions.append("model_ranked_item_lifecycle_excluded")

    if ranking.get("model_status") == "model_enriched":
        if not (
            receipt.get("output_hash")
            or receipt.get("would_write_receipt")
            or receipt.get("model_receipt_id")
        ):
            contradictions.append("model_enriched_without_receipt")
        if all(r.get("model_advisory_score") is None for r in ranked):
            contradictions.append("model_enriched_but_all_advice_dropped")
        if ranking.get("deterministic_fallback_used"):
            contradictions.append("fallback_used_but_claims_model_success")

    if float(ranking.get("source_ref_coverage", 1.0)) < 1.0:
        contradictions.append("ranking_source_ref_coverage_below_100")
    if not ranking.get("guard_clean", True):
        contradictions.append("ranking_packet_guard_unclean")

    return {
        "contradictions": sorted(set(contradictions)),
        "model_status": ranking.get("model_status"),
        "source_ref_coverage": ranking.get("source_ref_coverage"),
        "deterministic_fallback_used": ranking.get("deterministic_fallback_used"),
    }


def _ranked_public(r: dict[str, Any]) -> dict[str, Any]:
    """Project a ranked row to the raw-free public fields surfaced in JSON/evidence."""
    return {
        "rank_position": r["rank_position"],
        "candidate_id": r["candidate_id"],
        "subject_type": r["subject_type"],
        "section": r.get("section"),
        "lifecycle_state": r["lifecycle_state"],
        "project_key": r.get("project_key"),
        "due_bucket": r.get("due_bucket"),
        "source_ref_count": r.get("source_ref_count"),
        "deterministic_score": r["deterministic_score"],
        "feedback_score": r["feedback_score"],
        "model_advisory_score": r["model_advisory_score"],
        "final_score": r["final_score"],
        "why_this_matters_redacted": r.get("why_this_matters_redacted"),
        "model_reason_codes": r.get("model_reason_codes"),
        "duplicate_group_key": r.get("duplicate_group_key"),
    }


def _usefulness_score(ranked: list[dict[str, Any]], coverage: float) -> float:
    """Operator usefulness for the ranking run (source coverage weighted; raw-free)."""
    if not ranked:
        return 0.0
    # Reuse the shared rubric over a small redacted projection, then weight by source coverage.
    projection = {
        "ranked": [
            {"source_refs": ["x"] if int(r.get("source_ref_count") or 0) > 0 else []}
            for r in ranked
        ]
    }
    base = compute_usefulness(projection, expected_sections=["ranked"])
    return round(0.5 * base + 0.5 * coverage, 4)


def _persist(
    store: Any,
    *,
    brief_date: str,
    ranking_run_id: str,
    assembly_run_id: str,
    packet: dict[str, Any],
    ranked: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    similarity: dict[str, Any],
    model_layer_status: str,
    deterministic_fallback_used: bool,
    degraded_reason: Optional[str],
    coverage: float,
    usefulness: float,
    withheld: int,
    max_persist: int,
) -> dict[str, Any]:
    """Persist the run/overlay idempotently, capping ranked + edge rows at ``max_persist``."""
    import json as _json

    store.insert_ranking_run(
        brief_date=brief_date,
        policy_version=POLICY_VERSION,
        algorithm_version=ALGORITHM_VERSION,
        candidate_set_hash=packet["candidate_set_hash"],
        feedback_digest_hash=packet["feedback_digest_hash"],
        model_status=model_layer_status,
        deterministic_fallback_used=deterministic_fallback_used,
        degraded_reason=degraded_reason,
        candidate_count=len(packet["items"]),
        ranked_count=len(ranked),
        source_ref_coverage=round(coverage, 4),
        usefulness_score=usefulness,
        ranking_run_id=ranking_run_id,
    )

    persisted_ranked = 0
    for r in ranked:
        if persisted_ranked >= max_persist:
            break
        codes = r.get("model_reason_codes")
        store.insert_ranked_candidate(
            ranking_run_id=ranking_run_id,
            daily_brief_action_candidate_id=str(r["candidate_id"]),
            rank_position=int(r["rank_position"]),
            section_key=_category_for(r),
            deterministic_score=float(r["deterministic_score"]),
            feedback_score=float(r["feedback_score"]),
            final_score=float(r["final_score"]),
            group_key=r.get("duplicate_group_key"),
            model_advisory_score=r.get("model_advisory_score"),
            why_this_matters_redacted=r.get("why_this_matters_redacted"),
            model_reason_codes_json=(_json.dumps(codes) if codes else None),
            source_ref_count=int(r.get("source_ref_count") or 0),
            lifecycle_state_snapshot=str(r["lifecycle_state"]),
        )
        persisted_ranked += 1

    store.insert_assembly_run(
        brief_date=brief_date,
        assembly_policy_version=ASSEMBLY_POLICY_VERSION,
        model_layer_status=model_layer_status,
        ranking_run_id=ranking_run_id,
        deterministic_fallback_used=deterministic_fallback_used,
        section_count=len(sections),
        candidate_count=len(ranked),
        withheld_reason=(f"source_missing_withheld={withheld}" if withheld else None),
        assembly_run_id=assembly_run_id,
    )
    for s in sections:
        store.insert_assembly_section(
            assembly_run_id=assembly_run_id,
            section_key=s["section_key"],
            display_order=int(s["display_order"]),
            title_redacted=s["title_redacted"],
            candidate_ids_json=_json.dumps(s["candidate_ids"]),
            section_score=float(s["section_score"]),
            degraded_reason=s["degraded_reason"],
        )

    persisted_edges = 0
    for edge in similarity["edges"]:
        if persisted_edges >= max_persist:
            break
        store.upsert_similarity_edge(**edge)
        persisted_edges += 1

    return {
        "persisted_ranked": persisted_ranked,
        "would_persist_ranked": len(ranked),
        "persisted_edges": persisted_edges,
        "would_persist_edges": len(similarity["edges"]),
    }


def _guardrails() -> dict[str, bool]:
    return {
        "deterministic_authoritative": True,
        "model_advisory_only": True,
        "model_bounded_influence": True,
        "source_ref_gate": True,
        "similarity_review_only": True,
        "no_auto_merge_or_suppress": True,
        "dry_run_default": True,
        "apply_requires_max_persist": True,
        "receipt_hash_only": True,
        "no_raw_persistence": True,
        "no_writeback": True,
        "local_only": True,
    }
