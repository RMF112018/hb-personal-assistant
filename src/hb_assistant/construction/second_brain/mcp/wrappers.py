"""Phase 08D MCP allowed workflow wrappers (Prompt 05; +Phase 09 daily-brief handoff packet).

The ten ``mcp_*_wrapper`` functions are thin adapters over existing, offline-safe,
metadata-only second-brain builders. Each returns a bounded summary dict
``{status, provenance, results, source_count, output_classification}``; the broker adds
``policy_posture`` + ``receipt_id`` and runs the no-raw / bounding gate. Wrappers extract
only safe scalar/count/class fields — never raw bodies, prompts, responses, SQL, tokens,
signed/download URLs, or final determinations — and degrade gracefully (never raise) on
empty/insufficient local state. All are read-only except ``hb_memory_feedback``, which
records a local feedback-log row (local metadata; no external writeback).
"""

from __future__ import annotations

from datetime import date
from functools import partial
from typing import Any, Callable

from ..agents.policy import build_agent_registry_proof
from ..automation_health import run_automation_health
from ..config import load_second_brain_config
from ..daily_brief.triage import ReviewTriageAgent
from ..daily_brief_delivery import evaluate_daily_brief_delivery
from ..daily_brief_open import evaluate_brief_open
from ..data_quality import (
    evaluate_phase_08a_data_quality_gates,
    evaluate_phase_08b_data_quality_gates,
    evaluate_phase_08c_data_quality_gates,
)
from ..freshness import evaluate_source_freshness
from ..memory.preference import record_operator_feedback
from ..memory.store import read_memory_candidates
from ..research.orchestrator import RetrievalOrchestrator
from ..safety import build_second_brain_no_writeback_proof
from ..synthesis.agent import synthesize_answer
from .proof import build_mcp_tool_broker_proof

Wrapper = Callable[[dict[str, Any]], dict[str, Any]]

_MAX_LIST = 50


def _bounded(
    status: str,
    provenance: str,
    results: list[dict[str, Any]],
    *,
    source_count: int | None = None,
    classification: str = "bounded_summary",
) -> dict[str, Any]:
    return {
        "status": status,
        "provenance": provenance,
        "results": results[:_MAX_LIST],
        "source_count": source_count if source_count is not None else len(results),
        "output_classification": classification,
    }


def _degraded(provenance: str, reason: str) -> dict[str, Any]:
    return _bounded(
        "degraded", provenance, [{"reason_code": reason}], source_count=0, classification="degraded"
    )


def mcp_status_wrapper(arguments: dict[str, Any], *, db_path: str | None = None) -> dict[str, Any]:
    """hb_status — runtime + agents + automation health posture (metadata only)."""
    try:
        config = load_second_brain_config()
        agents = build_agent_registry_proof()
        health, _ = run_automation_health(db_path=db_path, emit_receipt=False)
        return _bounded(
            "ok",
            "second-brain status + agents + automation health",
            [
                {
                    "runtime_mode": config.mode,
                    "config_status": config.config_status,
                    "agent_count": agents.get("agent_count"),
                    "agents_enabled": agents.get("enabled_count"),
                    "agents_proof_passed": agents.get("proof_passed"),
                    "automation_status": health.overall_status,
                    "automation_reason": health.reason_code,
                }
            ],
            source_count=3,
        )
    except Exception:  # noqa: BLE001 - degrade, never raise into the broker
        return _degraded("second-brain status", "status_unavailable")


def mcp_validation_status_wrapper(
    arguments: dict[str, Any], *, db_path: str | None = None
) -> dict[str, Any]:
    """hb_validation_status — phase gates + no-writeback proofs (metadata only)."""
    try:
        g8a = evaluate_phase_08a_data_quality_gates(db_path=db_path)
        g8b = evaluate_phase_08b_data_quality_gates(db_path=db_path)
        g8c = evaluate_phase_08c_data_quality_gates(db_path=db_path)
        nw = build_second_brain_no_writeback_proof(db_path=db_path)
        broker = build_mcp_tool_broker_proof(write_evidence=False)
        return _bounded(
            "ok",
            "phase 08A/08B/08C gates + no-writeback proofs + 08D broker proof",
            [
                {
                    "phase_08a_gates_ok": g8a.get("ok"),
                    "phase_08b_gates_ok": g8b.get("ok"),
                    "phase_08c_gates_ok": g8c.get("ok"),
                    "phase_08c_readiness_overstated": g8c.get("readiness_overstated"),
                    "no_writeback_proof_passed": nw.get("proof_passed"),
                    "mcp_broker_proof_passed": broker.get("proof_passed"),
                    "phase_08d_gates": "pending_prompt_12",
                }
            ],
            source_count=5,
        )
    except Exception:  # noqa: BLE001
        return _degraded("validation status", "validation_unavailable")


def mcp_query_wrapper(arguments: dict[str, Any], *, db_path: str | None = None) -> dict[str, Any]:
    """hb_query — research-first interactive query (mock-first; bounded summary only)."""
    question = str(arguments.get("question") or "").strip()
    if not question:
        return _degraded("interactive query", "question_required")
    try:
        project_key = arguments.get("project_key")
        result = synthesize_answer(
            question=question,
            project_key=str(project_key) if project_key else None,
            db_path=db_path,
        )
        packet = result.research_packet_summary or {}
        return _bounded(
            "ok" if result.synthesized else "degraded",
            "retrieval orchestrator + answer synthesis (mock-first)",
            [
                {
                    "synthesized": result.synthesized,
                    "answer_redacted": result.answer_redacted,
                    "source_ref_count": len(result.source_refs),
                    "context_quality_class": packet.get("context_quality_class"),
                    "degradation_mode": packet.get("degradation_mode"),
                    "review_tier": (result.review_tiers or {}).get("max_tier"),
                    "warnings": list(result.warnings)[:_MAX_LIST],
                }
            ],
            source_count=len(result.source_refs),
        )
    except Exception:  # noqa: BLE001
        return _degraded("interactive query", "query_unavailable")


def mcp_research_packet_wrapper(
    arguments: dict[str, Any], *, db_path: str | None = None
) -> dict[str, Any]:
    """hb_research_packet — research packet assessment (counts/classes only)."""
    try:
        packet_type = str(arguments.get("packet_type") or "interactive_query")
        project_key = arguments.get("project_key")
        result = RetrievalOrchestrator(db_path=db_path).orchestrate(
            packet_type=packet_type,
            project_key=str(project_key) if project_key else None,
            emit_receipt=False,
        )
        packet = result.packet
        assessment = result.assessment
        return _bounded(
            "ok" if result.research_packet_ok else "degraded",
            "research packet builder",
            [
                {
                    "context_quality_class": packet.context_quality_class,
                    "degradation_mode": packet.degradation_mode,
                    "source_ref_count": packet.source_ref_count,
                    "review_required_count": packet.review_required_count,
                    "review_tier": packet.review_tier,
                    "families_present": list(assessment.families_present),
                    "families_missing": list(assessment.families_missing),
                    "source_coverage": assessment.source_coverage,
                    "open_questions": list(assessment.open_questions)[:_MAX_LIST],
                }
            ],
            source_count=packet.source_ref_count,
        )
    except Exception:  # noqa: BLE001
        return _degraded("research packet", "research_unavailable")


def mcp_get_daily_brief_wrapper(
    arguments: dict[str, Any], *, db_path: str | None = None
) -> dict[str, Any]:
    """hb_get_daily_brief — delivery-status safe view (metadata only)."""
    try:
        brief_date = arguments.get("brief_date")
        status = evaluate_daily_brief_delivery(
            brief_date=str(brief_date) if brief_date else None, db_path=db_path
        )
        return _bounded(
            "ok",
            "daily-brief delivery status (read-only)",
            [
                {
                    "overall_status": status.overall_status,
                    "reason_code": status.reason_code,
                    "brief_date": status.brief_date,
                    "eligible": status.eligible,
                    "already_delivered": status.already_delivered,
                    "delivery_channel": status.delivery_channel,
                }
            ],
            source_count=1,
        )
    except Exception:  # noqa: BLE001
        return _degraded("daily-brief delivery", "brief_status_unavailable")


def mcp_daily_brief_packet_wrapper(
    arguments: dict[str, Any], *, db_path: str | None = None
) -> dict[str, Any]:
    """hb_daily_brief_packet — application-generated daily brief handoff packet.

    Returns the metadata-only ``DailyBriefHandoffPacketV2`` (render_payload / governance_metadata
    split) for the requested date/project scope, for Claude scheduled rendering only. Claude renders
    only ``render_payload``; ``governance_metadata`` is never rendered. Read-only, source-linked, no
    raw, no writeback, no final determination; reuses the existing daily-brief assembly (no retrieval
    logic here). Fails closed to a safe degraded metadata error on any failure. The full packet rides
    in ``results[0]``.
    """
    try:
        from ..daily_brief.packet import build_daily_brief_packet_v2

        date_arg = arguments.get("date")
        scope = arguments.get("project_scope")
        include_rendering = arguments.get("include_rendering_instructions", True)
        brief_date = str(date_arg) if date_arg else date.today().isoformat()
        project_key = None if (scope is None or str(scope) == "all") else str(scope)

        packet = build_daily_brief_packet_v2(
            brief_date=brief_date, project_key=project_key, mode="dry_run", db_path=db_path
        )
        if include_rendering is False:
            governance = {
                k: v
                for k, v in packet.get("governance_metadata", {}).items()
                if k != "rendering_instructions"
            }
            packet = {**packet, "governance_metadata": governance}

        source_count = int(
            packet.get("governance_metadata", {})
            .get("source_coverage_summary", {})
            .get("source_ref_count", 0)
            or 0
        )
        return _bounded(
            "ok",
            "daily brief handoff packet (DailyBriefHandoffPacketV2; render_payload only; read-only)",
            [packet],
            source_count=source_count,
            classification="daily_brief_handoff_packet",
        )
    except Exception:  # noqa: BLE001 - fail closed to a safe metadata error
        return _degraded("daily brief handoff packet", "packet_unavailable")


def mcp_open_daily_brief_wrapper(
    arguments: dict[str, Any], *, db_path: str | None = None
) -> dict[str, Any]:
    """hb_open_daily_brief — local-only open POLICY/STATUS (never opens anything)."""
    try:
        brief_date = arguments.get("brief_date")
        target = str(arguments.get("target") or "vault")
        status = evaluate_brief_open(
            brief_date=str(brief_date) if brief_date else None, target=target, db_path=db_path
        )
        return _bounded(
            "ok",
            "automation open-brief local-only policy (read-only; never opens)",
            [
                {
                    "overall_status": status.overall_status,
                    "reason_code": status.reason_code,
                    "open_target": status.open_target,
                    "policy_open_enabled": status.policy_open_enabled,
                    "eligible": status.eligible,
                    "already_opened": status.already_opened,
                    "opened": status.opened,  # always False here — wrapper never applies
                    "path_hash": status.path_hash,
                }
            ],
            source_count=1,
        )
    except Exception:  # noqa: BLE001
        return _degraded("open-brief policy", "open_status_unavailable")


def mcp_review_load_status_wrapper(
    arguments: dict[str, Any], *, db_path: str | None = None
) -> dict[str, Any]:
    """hb_review_load_status — review triage + source freshness (counts only)."""
    try:
        project_key = arguments.get("project_key")
        load = ReviewTriageAgent(db_path=db_path).summarize(
            project_key=str(project_key) if project_key else None
        )
        fresh = evaluate_source_freshness(db_path=db_path)
        return _bounded(
            "ok",
            "review triage + source freshness observability",
            [
                {
                    "total_review_items": load.total_review_items,
                    "tier_3_count": load.tier_3_count,
                    "mandatory_review_count": load.mandatory_review_count,
                    "by_tier": dict(load.by_tier),
                    "by_urgency": dict(load.by_urgency),
                    "degradation_mode": load.degradation_mode,
                    "freshness_status": fresh.overall_status,
                    "stale_count": fresh.stale_count,
                    "unknown_count": fresh.unknown_count,
                }
            ],
            source_count=load.total_review_items,
        )
    except Exception:  # noqa: BLE001
        return _degraded("review load", "review_load_unavailable")


def mcp_memory_review_list_wrapper(
    arguments: dict[str, Any], *, db_path: str | None = None
) -> dict[str, Any]:
    """hb_memory_review_list — memory curator review candidates (metadata only)."""
    try:
        candidates = read_memory_candidates(db_path=db_path, status="proposed", limit=_MAX_LIST)
        bounded = [
            {
                "candidate_id": c.get("candidate_id"),
                "proposed_memory_type": c.get("proposed_memory_type"),
                "confidence_class": c.get("confidence_class"),
                "review_required": c.get("review_required"),
                "review_tier": c.get("review_tier"),
                "sensitivity_class": c.get("sensitivity_class"),
                "status": c.get("status"),
            }
            for c in candidates
        ]
        return _bounded(
            "ok", "memory curator review candidates (read-only)", bounded, source_count=len(bounded)
        )
    except Exception:  # noqa: BLE001
        return _degraded("memory review list", "memory_list_unavailable")


def mcp_memory_feedback_wrapper(
    arguments: dict[str, Any], *, db_path: str | None = None
) -> dict[str, Any]:
    """hb_memory_feedback — record a local feedback-log row (local metadata; no writeback)."""
    target_id = str(arguments.get("target_id") or "").strip()
    if not target_id:
        return _degraded("memory feedback", "target_id_required")
    try:
        rating = arguments.get("rating")
        feedback = record_operator_feedback(
            target_kind=str(arguments.get("target_kind") or "memory_candidate"),
            target_id=target_id,
            feedback_class=str(arguments.get("feedback_class") or "accept"),
            rating=rating if isinstance(rating, int) else None,
            reason_redacted=(
                str(arguments["reason_redacted"]) if arguments.get("reason_redacted") else None
            ),
            db_path=db_path,
            emit=True,
        )
        return _bounded(
            "ok",
            "memory candidate feedback workflow (local feedback log only)",
            [
                {
                    "feedback_id": feedback.feedback_id,
                    "target_kind": feedback.target_kind,
                    "target_id": feedback.target_id,
                    "feedback_class": feedback.feedback_class,
                    "recorded": True,
                }
            ],
            source_count=1,
        )
    except Exception:  # noqa: BLE001
        return _degraded("memory feedback", "feedback_unavailable")


def build_wrapper_registry(*, db_path: str | None = None) -> dict[str, Wrapper]:
    """Return the ten tool-name → wrapper bindings (db_path bound for the broker seam)."""
    return {
        "hb_status": partial(mcp_status_wrapper, db_path=db_path),
        "hb_query": partial(mcp_query_wrapper, db_path=db_path),
        "hb_research_packet": partial(mcp_research_packet_wrapper, db_path=db_path),
        "hb_get_daily_brief": partial(mcp_get_daily_brief_wrapper, db_path=db_path),
        "hb_daily_brief_packet": partial(mcp_daily_brief_packet_wrapper, db_path=db_path),
        "hb_open_daily_brief": partial(mcp_open_daily_brief_wrapper, db_path=db_path),
        "hb_review_load_status": partial(mcp_review_load_status_wrapper, db_path=db_path),
        "hb_memory_review_list": partial(mcp_memory_review_list_wrapper, db_path=db_path),
        "hb_memory_feedback": partial(mcp_memory_feedback_wrapper, db_path=db_path),
        "hb_validation_status": partial(mcp_validation_status_wrapper, db_path=db_path),
    }
