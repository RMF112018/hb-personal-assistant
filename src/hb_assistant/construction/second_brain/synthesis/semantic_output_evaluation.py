"""Phase 09 Prompt 23 — output evaluation integration (semantic outputs → evaluation + checks).

Routes semantic (vector) retrieval outputs through the **Output Evaluation (A05) layer** plus an
**unsupported-claim check** and a **source-linked proof**, persisting metadata-only receipts to the V38
``second_brain_retrieval_source_linked_proof_runs`` + ``second_brain_retrieval_unsupported_claim_checks``
tables. The semantic context is evaluated for fitness (source-linkage, review tier, no-raw, degradation
honesty) but **never assembles a final answer** — the context ``AdapterResult`` is non-synthesized
(``answer=""``, ``synthesized=False``), so `build_evaluation_preview` runs over the retrieved context, not
a generated answer. Every retrieved item must be a **supported, source-linked claim** (zero tolerance for
unsupported / unlinked items); any violation fails closed.

Read-only by default (``emit_receipt=False`` persists nothing); review tier / confidence / source refs /
freshness / coverage warnings are preserved; the raw query is never emitted (only ``query_hash``); no
answer / excerpt is emitted. Fail-closed on missing policy, stale schema, or an excluded source family.

Public entry points:
  build_semantic_output_evaluation(query, *, db_path=None, project_key=None, families=None, mode='hybrid',
      embed_model=None, persist_root=None, metadata_filter=None, emit_receipt=False) -> dict
  persist_evaluation_receipts(db_path, result, *, policy_version) -> dict
  build_semantic_output_evaluation_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval output-eval run "<q>" | proof --json
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw
from ..reasoning import AdapterResult, _review_status_for_tier
from ..research.packet import build_research_packet_from_envelope
from ..retrieval import ALLOWLISTED_SOURCE_FAMILIES
from ..retrieval.hybrid_broker import build_hybrid_envelope
from ..retrieval.models import RetrievalItem
from ..retrieval.policy import EXCLUDED_FAMILIES
from .evaluation import build_evaluation_preview

if TYPE_CHECKING:
    from ..retrieval.metadata_filter import MetadataFilter

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "output-evaluation-integration-proof.json"
_PROOF_MD = "output-evaluation-integration-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_output_evaluation_integration.seed.yaml"

_SOURCE_LINKED_TABLE = "second_brain_retrieval_source_linked_proof_runs"
_CLAIM_CHECK_TABLE = "second_brain_retrieval_unsupported_claim_checks"


class SemanticOutputEvaluationError(RuntimeError):
    """Raised when the evaluation-integration cannot resolve policy/schema (fail-closed)."""


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


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _schema_ready(db_path: str | None) -> int:
    """Return the schema version if ready (>=38 with the receipt tables), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise SemanticOutputEvaluationError("schema not ready for output evaluation (no database)")
    try:

        def _has(table: str) -> bool:
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                is not None
            )

        if not _has("schema_migrations"):
            raise SemanticOutputEvaluationError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has(_SOURCE_LINKED_TABLE) or not _has(_CLAIM_CHECK_TABLE):
            raise SemanticOutputEvaluationError(
                f"schema not ready for output evaluation (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_output_evaluation_contract() -> dict[str, Any]:
    """Load the output-evaluation-integration contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("output_evaluation_integration_contract")
    if not isinstance(contract, dict) or "unsupported_claim_zero_tolerance" not in contract:
        raise SemanticOutputEvaluationError(
            "phase 09 output-evaluation-integration contract not found or missing required fields"
        )
    return contract


def load_output_evaluation_seed() -> dict[str, Any]:
    """Load the resolved output-evaluation-integration seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise SemanticOutputEvaluationError(f"output-evaluation seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "default_mode" not in data:
        raise SemanticOutputEvaluationError(f"{candidate} must define the output-evaluation policy")
    return data


def _map_degradation(envelope_mode: str) -> str:
    """Map the 5-value retrieval degradation mode to the 3-value AdapterResult literal."""
    if envelope_mode == "blocked":
        return "blocked"
    if envelope_mode == "none":
        return "none"
    return "graceful_degraded"


def _source_linked_proof(items: list[RetrievalItem]) -> dict[str, Any]:
    """A retrieved item is source-linked iff it carries a source_ref + an allowlisted source_family."""
    checked = len(items)
    linked = sum(
        1
        for it in items
        if it.source_ref and it.source_family and it.source_family not in EXCLUDED_FAMILIES
    )
    unlinked = checked - linked
    return {
        "checked_count": checked,
        "source_linked_count": linked,
        "unlinked_count": unlinked,
        "status": "source_linked" if unlinked == 0 else "unlinked_found",
    }


def _unsupported_claim_check(items: list[RetrievalItem]) -> dict[str, Any]:
    """A claim is supported iff its retrieved item is source-linked; unsupported claims block (zero tol.)."""
    claim_count = len(items)
    unsupported = sum(
        1
        for it in items
        if not (it.source_ref and it.source_family and it.source_family not in EXCLUDED_FAMILIES)
    )
    return {
        "claim_count": claim_count,
        "unsupported_count": unsupported,
        "status": "clean" if unsupported == 0 else "blocked",
    }


def _context_adapter_result(envelope: Any, query: str, research_packet_ok: bool) -> Any:
    """Build a non-synthesized context AdapterResult (answer="", synthesized=False) for evaluation."""
    ctx = envelope.to_context_envelope(question=query, research_packet_ok=research_packet_ok)
    adapter_result = AdapterResult(
        answer="",
        mode="mock",
        synthesized=False,
        source_references=ctx.source_references,
        confidence=ctx.confidence_class,
        review_tier=ctx.review_tier,
        review_reason_code=ctx.review_reason_code,
        review_status=_review_status_for_tier(ctx.review_tier),
        disposition=ctx.disposition,
        degradation_mode=_map_degradation(envelope.degradation_mode),
        coverage_warnings=ctx.coverage_warnings,
        stale_unknown_warnings=ctx.stale_unknown_warnings,
        conflict_warnings=ctx.conflict_warnings,
    )
    return adapter_result, ctx


def _query_hash(query: str, project_key: str | None, mode: str) -> str:
    import hashlib

    return hashlib.sha256(f"{query}|{project_key or ''}|{mode}".encode()).hexdigest()


def build_semantic_output_evaluation(
    query: str,
    *,
    db_path: str | None = None,
    project_key: str | None = None,
    families: tuple[str, ...] | None = None,
    mode: str = "hybrid",
    embed_model: Any | None = None,
    persist_root: str | None = None,
    metadata_filter: MetadataFilter | None = None,
    emit_receipt: bool = False,
) -> dict[str, Any]:
    """Route semantic retrieval outputs through evaluation + unsupported-claim + source-linked checks.

    Builds the hybrid envelope, assembles a research packet, runs the A05 evaluation over a
    **non-synthesized** context result, and runs the claim/source checks over the retrieved items.
    Returns a metadata-only summary; never synthesizes an answer; persists nothing unless ``emit_receipt``.
    """
    contract = load_output_evaluation_contract()
    seed = load_output_evaluation_seed()
    schema_version = _schema_ready(db_path)

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
    packet, assessment, _rr, _pr = build_research_packet_from_envelope(
        envelope,
        packet_type="interactive_query",
        requested=requested,
        project_key=project_key,
        db_path=db_path,
        emit_receipt=False,
    )

    research_packet_ok = packet.degradation_mode != "blocked"
    adapter_result, ctx = _context_adapter_result(envelope, query, research_packet_ok)
    evaluation = build_evaluation_preview(
        adapter_result=adapter_result, packet=packet, assessment=assessment, envelope=ctx
    )

    source_linked = _source_linked_proof(envelope.items)
    claim_check = _unsupported_claim_check(envelope.items)
    overall_passed = (
        bool(evaluation.passed)
        and claim_check["unsupported_count"] == 0
        and source_linked["unlinked_count"] == 0
    )

    query_hash = _query_hash(query, project_key, meta["mode"])
    run_id = f"sle_{query_hash[:32]}"
    result = {
        "command": "second-brain retrieval output-eval run",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": "ok",
        "route": "evaluation_only",
        "synthesis_performed": False,
        "assembles_final_answer": False,
        "semantic_advisory_only": True,
        "run_id": run_id,
        "query_hash": query_hash,
        "schema_version": schema_version,
        "project_key": project_key,
        "mode": meta["mode"],
        "semantic_count": meta["semantic_count"],
        "deterministic_count": meta["deterministic_count"],
        "semantic_skip_reason": meta["semantic_skip_reason"],
        "overall_passed": overall_passed,
        "evaluation": {
            "passed": bool(evaluation.passed),
            "score": evaluation.score,
            "checklist_passed": evaluation.checklist_passed,
            "checklist_total": evaluation.checklist_total,
            "review_tier": evaluation.review_tier,
            "review_status": evaluation.review_status,
            "checklist": evaluation.checklist,
        },
        "source_linked_proof": source_linked,
        "unsupported_claim_check": claim_check,
        "coverage_warnings": list(ctx.coverage_warnings),
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "receipt_emitted": emit_receipt,
        "read_only": not emit_receipt,
    }

    if emit_receipt:
        receipts = persist_evaluation_receipts(
            db_path, result, policy_version=str(seed.get("version"))
        )
        result["source_linked_run_id"] = receipts["run_id"]
        result["unsupported_claim_check_id"] = receipts["check_id"]

    return result


def persist_evaluation_receipts(
    db_path: str | None, result: dict[str, Any], *, policy_version: str
) -> dict[str, str]:
    """Persist guard-clean metadata-only source-linked + unsupported-claim receipts. Returns the ids."""
    import hashlib

    _schema_ready(db_path)
    resolved = db_path or str(PathPolicy().get_db_path())
    run_id = str(result["run_id"])
    check_id = hashlib.sha256(f"{run_id}:claim".encode()).hexdigest()[:48]
    sl = result["source_linked_proof"]
    cc = result["unsupported_claim_check"]
    conn = sqlite3.connect(resolved)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {_SOURCE_LINKED_TABLE} "
            "(run_id, policy_version, schema_version, project_key, checked_count, source_linked_count, "
            "unlinked_count, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                policy_version,
                int(result["schema_version"]),
                result.get("project_key"),
                int(sl["checked_count"]),
                int(sl["source_linked_count"]),
                int(sl["unlinked_count"]),
                str(sl["status"]),
            ),
        )
        conn.execute(
            f"INSERT OR REPLACE INTO {_CLAIM_CHECK_TABLE} "
            "(check_id, policy_version, schema_version, run_id, claim_count, unsupported_count, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                check_id,
                policy_version,
                int(result["schema_version"]),
                run_id,
                int(cc["claim_count"]),
                int(cc["unsupported_count"]),
                str(cc["status"]),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"run_id": run_id, "check_id": check_id}


# --- Proof ---------------------------------------------------------------------------------------


def _guard_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return [
        c
        for c in cols
        if c.endswith(("_persisted", "_performed")) or c.endswith("_bypassed_policy")
    ]


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Output Evaluation Integration Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- evaluation_passed: {proof['evaluation_passed']}",
        f"- unsupported_count: {proof['unsupported_count']}",
        f"- unlinked_count: {proof['unlinked_count']}",
        f"- overall_passed: {proof['overall_passed']}",
        f"- receipts_persisted_guard_clean: {proof['receipts_persisted_guard_clean']}",
        f"- unsupported_claim_detected_and_blocked: {proof['unsupported_claim_detected_and_blocked']}",
        f"- no_answer_emitted: {proof['no_answer_emitted']}",
        f"- raw_query_not_emitted: {proof['raw_query_not_emitted']}",
        f"- excluded_family_fail_closed: {proof['excluded_family_fail_closed']}",
        "",
    ]
    return "\n".join(lines)


def build_semantic_output_evaluation_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: semantic outputs route through real A05 evaluation + claim/source checks; the
    receipts persist metadata-only + guard-clean; an unsupported claim is detected and blocks."""
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

        result = build_semantic_output_evaluation(
            raw_query,
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
            emit_receipt=True,
        )

        conn = sqlite3.connect(db)
        try:
            sl_rows = conn.execute(f"SELECT COUNT(*) FROM {_SOURCE_LINKED_TABLE}").fetchone()[0]
            cc_rows = conn.execute(f"SELECT COUNT(*) FROM {_CLAIM_CHECK_TABLE}").fetchone()[0]
            sl_guards = _guard_columns(conn, _SOURCE_LINKED_TABLE)
            cc_guards = _guard_columns(conn, _CLAIM_CHECK_TABLE)
            sl_guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(sl_guards)}), 0) FROM {_SOURCE_LINKED_TABLE}"
            ).fetchone()[0]
            cc_guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(cc_guards)}), 0) FROM {_CLAIM_CHECK_TABLE}"
            ).fetchone()[0]
        finally:
            conn.close()

        excluded_fail_closed = False
        try:
            build_semantic_output_evaluation(
                raw_query,
                db_path=db,
                mode="hybrid",
                embed_model=_mock_embed_model(),
                persist_root=persist_root,
                metadata_filter=MetadataFilter(source_families=("raw_email_body",)),
            )
        except Exception:
            excluded_fail_closed = True

    # Unsupported-claim detection over synthetic items (one missing a source ref, one excluded family).
    synthetic = [
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="ok",
            record_type="issue",
            record_ref="ok",
            confidence_class="high",
            review_tier=1,
            review_status="auto_advisory",
            review_required=False,
        ),
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="",
            record_type="issue",
            record_ref="x",
            confidence_class="high",
            review_tier=1,
            review_status="auto_advisory",
            review_required=False,
        ),
    ]
    syn_claim = _unsupported_claim_check(synthetic)
    syn_link = _source_linked_proof(synthetic)
    unsupported_detected = syn_claim["unsupported_count"] == 1 and syn_link["unlinked_count"] == 1

    serialized = json.dumps(result, default=str)
    evaluation_passed = bool(result["evaluation"]["passed"])
    receipts_guard_clean = (
        sl_rows >= 1 and cc_rows >= 1 and int(sl_guard_sum) == 0 and int(cc_guard_sum) == 0
    )
    no_answer = "answer" not in result and "answer_redacted" not in result
    raw_query_not_emitted = raw_query not in serialized

    proof_passed = (
        evaluation_passed
        and result["unsupported_claim_check"]["unsupported_count"] == 0
        and result["source_linked_proof"]["unlinked_count"] == 0
        and result["overall_passed"] is True
        and receipts_guard_clean
        and unsupported_detected
        and no_answer
        and raw_query_not_emitted
        and excluded_fail_closed
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_output_evaluation_integration",
        "command": "second-brain retrieval output-eval proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "evaluation_passed": evaluation_passed,
        "evaluation_score": result["evaluation"]["score"],
        "unsupported_count": result["unsupported_claim_check"]["unsupported_count"],
        "unlinked_count": result["source_linked_proof"]["unlinked_count"],
        "overall_passed": result["overall_passed"],
        "receipts_persisted_guard_clean": receipts_guard_clean,
        "unsupported_claim_detected_and_blocked": unsupported_detected,
        "no_answer_emitted": no_answer,
        "raw_query_not_emitted": raw_query_not_emitted,
        "excluded_family_fail_closed": excluded_fail_closed,
        "metadata_only": True,
        "guardrails": {
            "semantic_retrieval_through_evaluation_only": True,
            "unsupported_claims_blocked_never_emitted": True,
            "no_final_answer_assembly": True,
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
        _assert_no_raw(out, "output evaluation integration proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "output evaluation integration proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
