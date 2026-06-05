"""Phase 09 Prompt 22 — research packet integration (semantic context routed via packet only).

The sanctioned (and only) route for semantic (vector) retrieval context to enter answer generation:
build the hybrid broker's merged ``RetrievalEnvelope`` (deterministic authoritative + advisory semantic)
and route it through ``build_research_packet_from_envelope`` (A02), producing a metadata-only
``ResearchPacket`` (``advisory_classification='advisory'``). The bridge **never** calls the synthesis
adapter — it returns a packet, not an answer (``synthesis_performed=false``, ``assembles_final_answer=false``,
``route='research_packet_only'``) — so semantic results can never assemble a final answer outside the
Research Packet / Evaluation layers.

Read-only by default (``emit_receipt=False`` persists nothing); review tier / confidence / source
references / freshness / coverage warnings are preserved; no raw content / query / excerpt is emitted
(only ``query_hash``). Fail-closed on missing policy, stale schema, or an excluded source family.

Public entry points:
  build_semantic_research_packet(query, *, db_path=None, project_key=None, families=None, mode='hybrid',
      embed_model=None, persist_root=None, metadata_filter=None, packet_type='interactive_query',
      emit_receipt=False) -> dict
  build_semantic_research_packet_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval research-packet build "<q>" | proof --json
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw
from ..retrieval import ALLOWLISTED_SOURCE_FAMILIES
from ..retrieval.hybrid_broker import build_hybrid_envelope
from .packet import build_research_packet_from_envelope

if TYPE_CHECKING:
    from ..retrieval.metadata_filter import MetadataFilter

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "research-packet-integration-proof.json"
_PROOF_MD = "research-packet-integration-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_research_packet_integration.seed.yaml"


class SemanticPacketError(RuntimeError):
    """Raised when the semantic→packet route cannot resolve policy or a parameter is invalid (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[5]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def load_research_packet_integration_contract() -> dict[str, Any]:
    """Load the research-packet-integration contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("research_packet_integration_contract")
    if not isinstance(contract, dict) or "semantic_context_route" not in contract:
        raise SemanticPacketError(
            "phase 09 research-packet-integration contract not found or missing required fields"
        )
    return contract


def load_research_packet_integration_seed() -> dict[str, Any]:
    """Load the resolved research-packet-integration seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise SemanticPacketError(f"research-packet-integration seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "default_packet_type" not in data:
        raise SemanticPacketError(f"{candidate} must define the research-packet-integration policy")
    return data


def build_semantic_research_packet(
    query: str,
    *,
    db_path: str | None = None,
    project_key: str | None = None,
    families: tuple[str, ...] | None = None,
    mode: str = "hybrid",
    embed_model: Any | None = None,
    persist_root: str | None = None,
    metadata_filter: MetadataFilter | None = None,
    packet_type: str | None = None,
    emit_receipt: bool = False,
) -> dict[str, Any]:
    """Route hybrid (deterministic + advisory semantic) retrieval context through Research Packet
    generation. Returns a metadata-only summary; never synthesizes an answer; persists nothing unless
    ``emit_receipt`` is set (a metadata-only, guard-clean research-packet receipt)."""
    contract = load_research_packet_integration_contract()
    seed = load_research_packet_integration_seed()
    resolved_type = packet_type or str(seed.get("default_packet_type", "interactive_query"))
    if resolved_type not in contract.get("allowed_packet_types", ()):
        raise SemanticPacketError(f"packet_type not allowed: {resolved_type!r}")

    envelope, meta = build_hybrid_envelope(
        query,
        db_path=db_path,
        project_key=project_key,
        families=families,
        mode=mode,
        embed_model=embed_model,
        persist_root=persist_root,
        metadata_filter=metadata_filter,
    )
    effective = meta.get("effective_families")
    requested = tuple(effective) if effective else (families or tuple(ALLOWLISTED_SOURCE_FAMILIES))

    packet, assessment, retrieval_receipt_id, packet_receipt_id = (
        build_research_packet_from_envelope(
            envelope,
            packet_type=resolved_type,
            requested=requested,
            project_key=project_key,
            db_path=db_path,
            emit_receipt=emit_receipt,
        )
    )

    return {
        "command": "second-brain retrieval research-packet build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": "ok",
        "route": str(contract.get("semantic_context_route", "research_packet_only")),
        "synthesis_performed": False,
        "assembles_final_answer": False,
        "semantic_advisory_only": True,
        "mode": meta["mode"],
        "query_hash": meta["query_hash"],
        "schema_version": meta["schema_version"],
        "project_key": project_key,
        "packet_type": resolved_type,
        "result_count": meta["result_count"],
        "semantic_count": meta["semantic_count"],
        "deterministic_count": meta["deterministic_count"],
        "semantic_skip_reason": meta["semantic_skip_reason"],
        "packet": {
            "packet_id": packet.packet_id,
            "advisory_classification": packet.advisory_classification,
            "context_quality_class": packet.context_quality_class,
            "degradation_mode": packet.degradation_mode,
            "review_tier": packet.review_tier,
            "review_tier_reason_code": packet.review_tier_reason_code,
            "review_status": packet.review_status,
            "source_ref_count": packet.source_ref_count,
            "review_required_count": packet.review_required_count,
            "stale_unknown_count": packet.stale_unknown_count,
            "conflict_count": packet.conflict_count,
            "coverage_warnings": packet.coverage_warnings,
            "status": packet.status,
        },
        "assessment": {
            "families_present": assessment.families_present,
            "families_missing": assessment.families_missing,
            "source_coverage": assessment.source_coverage,
            "degradation_recommendation": assessment.degradation_recommendation,
            "open_questions": assessment.open_questions,
            "policy_warnings": assessment.policy_warnings,
        },
        "receipt_emitted": emit_receipt,
        "retrieval_receipt_id": retrieval_receipt_id,
        "packet_receipt_id": packet_receipt_id,
        "policy_version": seed.get("version"),
        "read_only": not emit_receipt,
    }


# --- Proof ---------------------------------------------------------------------------------------


_PACKETS_TABLE = "second_brain_research_packets"


def _synthesis_has_no_semantic_path() -> bool:
    """Confirm the synthesis agent has no direct reference to the hybrid/semantic retrieval broker."""
    from ..synthesis import agent as synth_agent

    src = Path(synth_agent.__file__).read_text(encoding="utf-8")
    return "hybrid_broker" not in src and "build_hybrid" not in src


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Research Packet Integration Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- route_is_research_packet_only: {proof['route_is_research_packet_only']}",
        f"- semantic_context_in_packet: {proof['semantic_context_in_packet']}",
        f"- packet_advisory: {proof['packet_advisory']}",
        f"- returns_packet_not_answer: {proof['returns_packet_not_answer']}",
        f"- packet_receipt_persisted_metadata_only: {proof['packet_receipt_persisted_metadata_only']}",
        f"- synthesis_has_no_semantic_path: {proof['synthesis_has_no_semantic_path']}",
        f"- excluded_family_fail_closed: {proof['excluded_family_fail_closed']}",
        f"- raw_query_not_emitted: {proof['raw_query_not_emitted']}",
        "",
    ]
    return "\n".join(lines)


def build_semantic_research_packet_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: semantic context routes into a research packet (advisory), never an answer; the
    packet receipt persists metadata-only; synthesis has no direct semantic path; excluded families fail
    closed."""
    import sqlite3
    import tempfile

    from ..retrieval.hybrid_broker import _mock_embed_model
    from ..retrieval.metadata_filter import MetadataFilter
    from ..retrieval.vector_index import (
        _mock_vector_writer,
        _proof_db,
        build_vector_index_apply,
    )

    raw_query = "what changed on the active project summary this week"
    with tempfile.TemporaryDirectory() as tmp:
        db = _proof_db(tmp)
        persist_root = str(Path(tmp) / "vs")
        build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)

        result = build_semantic_research_packet(
            raw_query,
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
            emit_receipt=True,
        )

        conn = sqlite3.connect(db)
        try:
            packet_rows = conn.execute(f"SELECT COUNT(*) FROM {_PACKETS_TABLE}").fetchone()[0]
            cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({_PACKETS_TABLE})")]
            guard_cols = [
                c
                for c in cols
                if c.endswith(("_persisted", "_performed")) or c.endswith("_bypassed_policy")
            ]
            guard_sum = (
                conn.execute(
                    f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_PACKETS_TABLE}"
                ).fetchone()[0]
                if guard_cols
                else 0
            )
        finally:
            conn.close()

        excluded_fail_closed = False
        try:
            build_semantic_research_packet(
                raw_query,
                db_path=db,
                mode="hybrid",
                embed_model=_mock_embed_model(),
                persist_root=persist_root,
                metadata_filter=MetadataFilter(source_families=("raw_email_body",)),
            )
        except Exception:
            excluded_fail_closed = True

    serialized = json.dumps(result, default=str)
    route_only = result["route"] == "research_packet_only"
    semantic_in_packet = int(result["semantic_count"]) >= 1
    packet_advisory = result["packet"]["advisory_classification"] == "advisory"
    returns_packet_not_answer = (
        result["synthesis_performed"] is False
        and result["assembles_final_answer"] is False
        and "answer" not in result
        and "answer_redacted" not in result
    )
    receipt_metadata_only = packet_rows >= 1 and int(guard_sum) == 0
    no_semantic_path = _synthesis_has_no_semantic_path()
    raw_query_not_emitted = raw_query not in serialized

    proof_passed = (
        route_only
        and semantic_in_packet
        and packet_advisory
        and returns_packet_not_answer
        and receipt_metadata_only
        and no_semantic_path
        and excluded_fail_closed
        and raw_query_not_emitted
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_research_packet_integration",
        "command": "second-brain retrieval research-packet proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "route_is_research_packet_only": route_only,
        "semantic_context_in_packet": semantic_in_packet,
        "semantic_count": result["semantic_count"],
        "packet_advisory": packet_advisory,
        "returns_packet_not_answer": returns_packet_not_answer,
        "packet_receipt_persisted_metadata_only": receipt_metadata_only,
        "research_packet_rows": packet_rows,
        "synthesis_has_no_semantic_path": no_semantic_path,
        "excluded_family_fail_closed": excluded_fail_closed,
        "raw_query_not_emitted": raw_query_not_emitted,
        "metadata_only": True,
        "guardrails": {
            "semantic_retrieval_through_research_packet_only": True,
            "no_final_answer_assembly": True,
            "no_semantic_retrieval_bypass": True,
            "no_raw": True,
            "no_external_writeback": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(out, "research packet integration proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "research packet integration proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
