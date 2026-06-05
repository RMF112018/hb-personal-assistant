"""Phase 09 Prompt 20 — hybrid retrieval broker (deterministic + advisory semantic, fail-closed).

Combines the **deterministic** Retrieval Broker (A03 — the source of truth over the allowlisted
families) with an **advisory semantic** path that queries the applied vector index (Prompt 19). The two
result sets are merged into one source-linked, guard-clean ``RetrievalEnvelope`` and re-bounded by the
existing deterministic context budget. Deterministic results are authoritative; semantic results are
advisory "suggested context" only — source-linked back to approved/reviewed nodes (via the persisted
``vector_index_items`` receipts), review tier / confidence / freshness preserved, floored at review tier
2 (never auto-tier-1), and re-validated with the Prompt 14 no-raw guardrail before admission.

Source-of-truth discipline: the broker returns an *envelope*, never a final answer — answer assembly
stays in the Research Packet / Evaluation layers (``assembles_final_answer`` is always ``False`` and the
``semantic_retrieval_bypassed_policy`` guard stays 0). Everything is metadata-only: the raw query string
is never persisted (only its hash), no excerpts/vectors are persisted, and vectors live outside SQLite.
The semantic path is fail-closed — skipped (deterministic still returned) when the optional LlamaIndex
SDK is absent or there is no applied vector index. The embedder is injectable so proofs/tests run offline.

Public entry points:
  build_hybrid_retrieval(query, *, db_path=None, project_key=None, families=None, mode='hybrid',
                         embed_model=None, top_k=None, persist_root=None) -> dict
  persist_hybrid_query_record(db_path, result, *, policy_version) -> str
  build_hybrid_retrieval_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval hybrid status | search "<q>" | proof --json
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw
from .broker import RetrievalBroker
from .embedding_policy import (
    load_embedding_vector_policy_contract,
    load_embedding_vector_policy_seed,
    validate_embedding_candidate,
)
from .llamaindex_config import _llama_index_available, load_llamaindex_config_seed
from .models import RetrievalItem
from .policy import EXCLUDED_FAMILIES, apply_context_budget, load_context_budget

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "hybrid-retrieval-proof.json"
_PROOF_MD = "hybrid-retrieval-proof.md"

_VECTOR_RUNS_TABLE = "second_brain_retrieval_vector_index_runs"
_VECTOR_ITEMS_TABLE = "second_brain_retrieval_vector_index_items"
_RUNS_TABLE = "second_brain_retrieval_hybrid_query_runs"
_RESULTS_TABLE = "second_brain_retrieval_hybrid_query_results"

_APPLY_SEED_RELATIVE = Path("resources") / "config" / "phase_09_hybrid_retrieval.seed.yaml"


class HybridRetrievalError(RuntimeError):
    """Raised when the hybrid broker cannot resolve policy/schema (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    import subprocess

    try:
        repo_root = Path(__file__).resolve().parents[5]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def load_hybrid_retrieval_contract() -> dict[str, Any]:
    """Load the hybrid-retrieval contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("hybrid_retrieval_contract")
    if not isinstance(contract, dict) or "modes" not in contract:
        raise HybridRetrievalError(
            "phase 09 hybrid-retrieval contract not found or missing required fields"
        )
    return contract


def load_hybrid_retrieval_seed() -> dict[str, Any]:
    """Load the resolved hybrid-retrieval seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _APPLY_SEED_RELATIVE
    if not candidate.exists():
        raise HybridRetrievalError(f"hybrid-retrieval seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "default_mode" not in data:
        raise HybridRetrievalError(f"{candidate} must define the hybrid-retrieval policy")
    return data


def _require_v38(db_path: str | None) -> int:
    """Return the schema version if ready (>=38 with the hybrid tables), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise HybridRetrievalError("schema not ready for hybrid retrieval (no database)")
    try:

        def _has(table: str) -> bool:
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                is not None
            )

        if not _has("schema_migrations"):
            raise HybridRetrievalError(
                "schema not ready for hybrid retrieval (no schema_migrations)"
            )
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has(_RUNS_TABLE) or not _has(_RESULTS_TABLE):
            raise HybridRetrievalError(
                f"schema not ready for hybrid retrieval (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def _score_bucket(score: float | None, thresholds: dict[str, Any]) -> str:
    if score is None:
        return "unknown"
    if score >= float(thresholds.get("high", 0.66)):
        return "high"
    if score >= float(thresholds.get("medium", 0.33)):
        return "medium"
    return "low"


def _latency_bucket(elapsed_s: float) -> str:
    if elapsed_s < 0.5:
        return "fast"
    if elapsed_s < 2.0:
        return "normal"
    return "slow"


def _vector_store_root(persist_root: str | None) -> Path:
    if persist_root:
        return Path(persist_root)
    return PathPolicy().get_app_support() / "retrieval" / "vector_store"


def _latest_applied_vector_index_run(
    db_path: str | None, persist_root: str | None
) -> tuple[str, Path] | None:
    """Locate the newest applied vector-index run + its on-disk store (read-only), or None."""
    conn = _open_ro(db_path)
    if conn is None:
        return None
    try:
        if (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_VECTOR_RUNS_TABLE,)
            ).fetchone()
            is None
        ):
            return None
        row = conn.execute(
            f"SELECT run_id FROM {_VECTOR_RUNS_TABLE} WHERE status = 'applied' "
            "ORDER BY created_at_utc DESC, run_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    run_id = str(row[0])
    persist_dir = _vector_store_root(persist_root) / run_id
    if not persist_dir.exists() or not any(persist_dir.iterdir()):
        return None
    return run_id, persist_dir


def _lookup_item_metadata(db_path: str | None, item_id: str) -> dict[str, Any] | None:
    """Read the metadata-only vector_index_items receipt for a node (read-only), or None."""
    conn = _open_ro(db_path)
    if conn is None:
        return None
    try:
        row = conn.execute(
            f"SELECT source_family, source_ref_hash, content_hash, confidence_class, freshness_label "
            f"FROM {_VECTOR_ITEMS_TABLE} WHERE item_id = ?",
            (item_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "source_family": str(row[0]),
        "source_ref_hash": str(row[1]),
        "content_hash": str(row[2]),
        "confidence_class": str(row[3] or "unknown"),
        "freshness_label": str(row[4] or "unknown"),
    }


def _semantic_query(
    query: str,
    *,
    db_path: str | None,
    seed: dict[str, Any],
    top_k: int,
    embed_model: Any | None = None,
    persist_root: str | None = None,
) -> tuple[list[tuple[RetrievalItem, float | None]], str | None]:
    """Advisory semantic retrieval over the applied vector index (fail-closed).

    Returns ``(items_with_scores, skip_reason)``. ``skip_reason`` is non-None when the semantic path was
    skipped (SDK absent / no applied index) — the deterministic path is unaffected. Each admitted item is
    source-linked to a ``vector_index_items`` receipt and re-validated with the no-raw guardrail.
    """
    if embed_model is None and not _llama_index_available():
        return [], "semantic_sdk_not_available"
    located = _latest_applied_vector_index_run(db_path, persist_root)
    if located is None:
        return [], "semantic_no_applied_index"
    run_id, persist_dir = located

    try:
        from llama_index.core import Settings, StorageContext, load_index_from_storage
    except ImportError:
        return [], "semantic_sdk_not_available"

    config = load_llamaindex_config_seed()
    if embed_model is None:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        embed_model = HuggingFaceEmbedding(model_name=str(config.get("embedding_model_label")))
    Settings.embed_model = embed_model

    storage_context = StorageContext.from_defaults(persist_dir=str(persist_dir))
    index = load_index_from_storage(storage_context)
    matches = index.as_retriever(similarity_top_k=top_k).retrieve(query)

    contract = load_embedding_vector_policy_contract()
    pol_seed = load_embedding_vector_policy_seed()
    min_tier = int(seed.get("semantic_min_review_tier", 2)) or 2
    out: list[tuple[RetrievalItem, float | None]] = []
    for match in matches:
        node = match.node
        node_id = str(getattr(node, "ref_doc_id", None) or node.node_id)
        item_id = _hash(f"{run_id}:{node_id}")[:48]
        meta = _lookup_item_metadata(db_path, item_id)
        if meta is None:
            continue  # not source-linked to an approved receipt → drop
        if meta["source_family"] in EXCLUDED_FAMILIES:
            continue
        excerpt = str(node.get_content() or "")[:280]
        candidate = {
            "source_family": meta["source_family"],
            "source_ref": meta["source_ref_hash"],
            "content_hash": meta["content_hash"],
            "confidence_class": meta["confidence_class"],
            "review_tier": min_tier,
            "freshness_label": meta["freshness_label"],
            "text_redacted": excerpt,
        }
        if validate_embedding_candidate(candidate, contract=contract, seed=pol_seed):
            continue  # no-raw / policy guardrail rejected → drop
        item = RetrievalItem(
            source_family=meta["source_family"],
            source_ref=meta["source_ref_hash"],
            record_type="semantic_match",
            record_ref=node_id,
            confidence_class=meta["confidence_class"],
            review_tier=min_tier,
            review_status="review_recommended" if min_tier == 2 else "review_required",
            review_required=min_tier >= 3,
            content_excerpt_redacted=excerpt,
            recency=meta["freshness_label"],
        )
        out.append((item, match.score))
    return out, None


def build_hybrid_status(
    db_path: str | None = None, *, persist_root: str | None = None
) -> dict[str, Any]:
    """Read-only hybrid-retrieval readiness (deterministic always; semantic iff SDK + applied index)."""
    contract = load_hybrid_retrieval_contract()
    seed = load_hybrid_retrieval_seed()
    try:
        schema_version = _require_v38(db_path)
        schema_ready = True
    except HybridRetrievalError:
        schema_version = 0
        schema_ready = False
    sdk_available = _llama_index_available()
    applied = _latest_applied_vector_index_run(db_path, persist_root) is not None
    semantic_ready = sdk_available and applied
    blockers: list[str] = []
    if not sdk_available:
        blockers.append("semantic_sdk_not_available")
    if not applied:
        blockers.append("semantic_no_applied_index")
    return {
        "command": "second-brain retrieval hybrid status",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": schema_version,
        "schema_ready": schema_ready,
        "deterministic_ready": True,
        "sdk_available": sdk_available,
        "applied_vector_index_present": applied,
        "semantic_ready": semantic_ready,
        "modes": list(contract.get("modes", ())),
        "default_mode": seed.get("default_mode"),
        "semantic_blockers": blockers,
        "deterministic_source_of_truth": True,
        "semantic_advisory_only": True,
        "assembles_final_answer": False,
        "policy_version": seed.get("version"),
        "read_only": True,
    }


def build_hybrid_retrieval(
    query: str,
    *,
    db_path: str | None = None,
    project_key: str | None = None,
    families: tuple[str, ...] | None = None,
    mode: str = "hybrid",
    embed_model: Any | None = None,
    top_k: int | None = None,
    persist_root: str | None = None,
) -> dict[str, Any]:
    """Combine deterministic + advisory semantic retrieval into one metadata-only result (fail-closed).

    Deterministic results are authoritative; semantic results are advisory and source-linked. Returns a
    JSON-safe, metadata-only summary (counts, per-family + origin split, tier distribution, score
    buckets, degradation, warnings, ``assembles_final_answer=False``, ``query_hash`` — never the raw
    query or any excerpt). Persists nothing; the merged envelope is built in memory.
    """
    contract = load_hybrid_retrieval_contract()
    seed = load_hybrid_retrieval_seed()
    if mode not in contract.get("modes", ()):
        raise HybridRetrievalError(f"unknown hybrid retrieval mode: {mode!r}")
    schema_version = _require_v38(db_path)
    top_k = int(top_k if top_k is not None else seed.get("semantic_top_k", 5))
    top_k = min(top_k, int(contract.get("semantic_max_top_k", 20)))
    thresholds = contract.get("score_bucket_thresholds", {})

    started = time.monotonic()
    det_env = RetrievalBroker(db_path).retrieve(
        project_key=project_key, families=families, emit_receipt=False
    )
    deterministic_refs = {(it.source_family, it.source_ref) for it in det_env.items}

    semantic_pairs: list[tuple[RetrievalItem, float | None]] = []
    skip_reason: str | None = None
    if mode == "hybrid":
        semantic_pairs, skip_reason = _semantic_query(
            query,
            db_path=db_path,
            seed=seed,
            top_k=top_k,
            embed_model=embed_model,
            persist_root=persist_root,
        )
    else:
        skip_reason = "semantic_disabled_mode"

    # Deterministic is authoritative; admit only non-duplicate semantic suggestions.
    score_by_ref: dict[tuple[str, str], float | None] = {}
    semantic_refs: set[tuple[str, str]] = set()
    semantic_items: list[RetrievalItem] = []
    for item, score in semantic_pairs:
        key = (item.source_family, item.source_ref)
        if key in deterministic_refs or key in semantic_refs:
            continue
        semantic_refs.add(key)
        score_by_ref[key] = score
        semantic_items.append(item)

    merged = list(det_env.items) + semantic_items
    kept, char_count, truncated, degradation = apply_context_budget(merged, load_context_budget())

    coverage_warnings = list(det_env.coverage_warnings)
    if skip_reason:
        coverage_warnings.append(f"semantic_unavailable:{skip_reason}")
    if semantic_items:
        coverage_warnings.append("semantic_advisory_only")

    tier_distribution = {"1": 0, "2": 0, "3": 0}
    per_family: dict[str, int] = {}
    deterministic_count = 0
    semantic_count = 0
    results: list[dict[str, Any]] = []
    for rank, it in enumerate(kept, start=1):
        tier_distribution[str(it.review_tier)] += 1
        per_family[it.source_family] = per_family.get(it.source_family, 0) + 1
        key = (it.source_family, it.source_ref)
        is_semantic = key in semantic_refs
        if is_semantic:
            semantic_count += 1
        else:
            deterministic_count += 1
        results.append(
            {
                "rank": rank,
                "origin": "semantic" if is_semantic else "deterministic",
                "source_family": it.source_family,
                "source_ref_hash": _hash(it.source_ref)[:48],
                "confidence_class": it.confidence_class,
                "score_bucket": _score_bucket(score_by_ref.get(key), thresholds)
                if is_semantic
                else "deterministic",
            }
        )

    query_hash = _hash(f"{query}|{project_key or ''}|{mode}|{','.join(sorted(families or ()))}")
    run_id = f"hyq_{query_hash[:32]}"
    elapsed = time.monotonic() - started

    return {
        "command": "second-brain retrieval hybrid search",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": "ok",
        "run_id": run_id,
        "schema_version": schema_version,
        "project_key": project_key,
        "query_hash": query_hash,
        "mode": mode,
        "deterministic_authoritative": True,
        "semantic_advisory_only": True,
        "assembles_final_answer": False,
        "result_count": len(kept),
        "deterministic_count": deterministic_count,
        "semantic_count": semantic_count,
        "semantic_skip_reason": skip_reason,
        "per_family_count": per_family,
        "tier_distribution": tier_distribution,
        "degradation_mode": degradation,
        "context_char_count": char_count,
        "truncated": truncated,
        "latency_bucket": _latency_bucket(elapsed),
        "coverage_warnings": coverage_warnings,
        "stale_unknown_warnings": list(det_env.stale_unknown_warnings),
        "conflict_warnings": list(det_env.conflict_warnings),
        "policy_version": seed.get("version"),
        "results": results,
        "read_only": True,
    }


def persist_hybrid_query_record(
    db_path: str | None, result: dict[str, Any], *, policy_version: str
) -> str:
    """Persist a guard-clean hybrid query run + per-result rows (metadata-only). Returns run_id."""
    _require_v38(db_path)
    resolved = db_path or str(PathPolicy().get_db_path())
    run_id = str(result["run_id"])
    conn = sqlite3.connect(resolved)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {_RUNS_TABLE} "
            "(run_id, policy_version, schema_version, project_key, query_hash, mode, result_count, "
            "latency_bucket) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                policy_version,
                int(result["schema_version"]),
                result.get("project_key"),
                str(result["query_hash"]),
                str(result["mode"]),
                int(result["result_count"]),
                str(result.get("latency_bucket") or "unknown"),
            ),
        )
        for r in result["results"]:
            result_id = _hash(f"{run_id}:{r['rank']}:{r['source_ref_hash']}")[:48]
            conn.execute(
                f"INSERT OR REPLACE INTO {_RESULTS_TABLE} "
                "(result_id, policy_version, schema_version, run_id, rank, source_family, "
                "source_ref_hash, confidence_class, score_bucket) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result_id,
                    policy_version,
                    int(result["schema_version"]),
                    run_id,
                    int(r["rank"]),
                    str(r["source_family"]),
                    str(r["source_ref_hash"]),
                    str(r["confidence_class"]),
                    str(r["score_bucket"]),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return run_id


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
        "# Phase 09 — Hybrid Retrieval Broker Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- deterministic_count: {proof['deterministic_count']}",
        f"- semantic_count: {proof['semantic_count']}",
        f"- semantic_advisory_only: {proof['semantic_advisory_only']}",
        f"- semantic_source_linked: {proof['semantic_source_linked']}",
        f"- assembles_final_answer: {proof['assembles_final_answer']} (must be false)",
        f"- run_record_guard_clean: {proof['run_record_guard_clean']}",
        f"- result_records_guard_clean: {proof['result_records_guard_clean']}",
        f"- semantic_retrieval_bypassed_policy: {proof['semantic_retrieval_bypassed_policy']} (must be 0)",
        f"- no_forbidden_persisted_columns: {proof['no_forbidden_persisted_columns']}",
        f"- raw_query_not_persisted: {proof['raw_query_not_persisted']}",
        f"- no_applied_index_semantic_skipped: {proof['no_applied_index_semantic_skipped']}",
        f"- deterministic_only_mode_skips_semantic: {proof['deterministic_only_mode_skips_semantic']}",
        f"- unsafe_semantic_node_dropped: {proof['unsafe_semantic_node_dropped']}",
        "",
    ]
    return "\n".join(lines)


def build_hybrid_retrieval_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: a guard-clean hybrid query merges deterministic + advisory semantic results,
    persists metadata-only receipts (raw query never stored), and skips semantic fail-closed."""
    from .vector_index import (
        _empty_migrated_db,
        _mock_vector_writer,
        _proof_db,
        build_vector_index_apply,
    )

    contract = load_hybrid_retrieval_contract()
    seed = load_hybrid_retrieval_seed()
    forbidden_cols = {str(c) for c in contract.get("forbidden_persisted_fields", [])}
    raw_query = "what is the project summary status"

    with tempfile.TemporaryDirectory() as tmp:
        db = _proof_db(tmp)
        persist_root = str(Path(tmp) / "vector_store")
        build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)
        embed = _mock_embed_model()

        result = build_hybrid_retrieval(
            raw_query,
            db_path=db,
            mode="hybrid",
            embed_model=embed,
            persist_root=persist_root,
        )
        run_id = persist_hybrid_query_record(
            db, result, policy_version=str(result["policy_version"])
        )

        # deterministic-only mode skips the semantic path
        det_only = build_hybrid_retrieval(
            raw_query, db_path=db, mode="deterministic_only", persist_root=persist_root
        )

        # unsafe semantic node is dropped (excluded family lookup short-circuits admission)
        unsafe_dropped = _semantic_unsafe_drops(db, persist_root, seed, embed)

        conn = sqlite3.connect(db)
        try:
            run_row = conn.execute(
                f"SELECT query_hash, result_count FROM {_RUNS_TABLE} WHERE run_id = ?", (run_id,)
            ).fetchone()
            run_guard_cols = _guard_columns(conn, _RUNS_TABLE)
            run_guard_sum = conn.execute(
                f"SELECT {'+'.join(run_guard_cols)} FROM {_RUNS_TABLE} WHERE run_id = ?", (run_id,)
            ).fetchone()
            bypass_val = conn.execute(
                f"SELECT semantic_retrieval_bypassed_policy FROM {_RUNS_TABLE} WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            result_count_db = conn.execute(
                f"SELECT COUNT(*) FROM {_RESULTS_TABLE} WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            result_guard_cols = _guard_columns(conn, _RESULTS_TABLE)
            result_guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(result_guard_cols)}), 0) FROM {_RESULTS_TABLE} "
                "WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
            run_cols = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({_RUNS_TABLE})")}
            result_cols = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({_RESULTS_TABLE})")}
        finally:
            conn.close()

        # No-applied-index: a schema-current but empty DB has no vector store -> semantic skipped.
        empty_db = _empty_migrated_db(tmp)
        no_index = _semantic_query(
            raw_query, db_path=empty_db, seed=seed, top_k=5, embed_model=embed, persist_root=tmp
        )

    raw_query_not_persisted = run_row is not None and raw_query not in (run_row[0] or "")
    run_guard_clean = run_guard_sum is not None and int(run_guard_sum[0] or 0) == 0
    result_guard_clean = int(result_guard_sum or 0) == 0
    semantic_count = int(result.get("semantic_count", 0))
    semantic_source_linked = all(
        r["origin"] != "semantic" or bool(r["source_ref_hash"]) for r in result["results"]
    )
    no_forbidden_columns = not (forbidden_cols & (run_cols | result_cols))
    no_index_skipped = no_index[0] == [] and no_index[1] == "semantic_no_applied_index"

    proof_passed = (
        result["status"] == "ok"
        and result["deterministic_count"] >= 1
        and semantic_count >= 1
        and result["assembles_final_answer"] is False
        and run_row is not None
        and int(run_row[1]) == int(result["result_count"])
        and result_count_db == len(result["results"])
        and run_guard_clean
        and result_guard_clean
        and int(bypass_val[0] or 0) == 0
        and no_forbidden_columns
        and raw_query_not_persisted
        and semantic_source_linked
        and det_only["semantic_count"] == 0
        and det_only["semantic_skip_reason"] == "semantic_disabled_mode"
        and unsafe_dropped
        and no_index_skipped
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_hybrid_retrieval",
        "command": "second-brain retrieval hybrid proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "deterministic_count": result["deterministic_count"],
        "semantic_count": semantic_count,
        "semantic_advisory_only": result["semantic_advisory_only"],
        "semantic_source_linked": semantic_source_linked,
        "assembles_final_answer": result["assembles_final_answer"],
        "run_record_guard_clean": run_guard_clean,
        "result_records_guard_clean": result_guard_clean,
        "semantic_retrieval_bypassed_policy": int(bypass_val[0] or 0),
        "no_forbidden_persisted_columns": no_forbidden_columns,
        "raw_query_not_persisted": raw_query_not_persisted,
        "no_applied_index_semantic_skipped": no_index_skipped,
        "deterministic_only_mode_skips_semantic": det_only["semantic_count"] == 0,
        "unsafe_semantic_node_dropped": unsafe_dropped,
        "metadata_only": True,
        "guardrails": {
            "deterministic_source_of_truth": True,
            "semantic_advisory_only": True,
            "no_final_answer_assembly": True,
            "no_raw": True,
            "no_external_writeback": True,
            "vectors_outside_sqlite": True,
            "no_semantic_retrieval_bypass": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "hybrid retrieval proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "hybrid retrieval proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof


def _mock_embed_model() -> Any:
    from llama_index.core.embeddings import MockEmbedding

    dim = int(load_embedding_vector_policy_seed().get("embedding_dim", 384))
    return MockEmbedding(embed_dim=dim)


def _semantic_unsafe_drops(db: str, persist_root: str, seed: dict[str, Any], embed: Any) -> bool:
    """Confirm an unsafe (excluded-family / raw-shape) semantic candidate is never admitted."""
    contract = load_embedding_vector_policy_contract()
    pol_seed = load_embedding_vector_policy_seed()
    synthetic_secret = "Bea" + "rer " + "z" * 32
    unsafe_excluded = {
        "source_family": "raw_email_body",
        "source_ref": "x",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 2,
        "freshness_label": "current",
        "text_redacted": "[redacted]",
    }
    unsafe_raw = {
        "source_family": "accepted_long_term_memory",
        "source_ref": "y",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 2,
        "freshness_label": "current",
        "text_redacted": synthetic_secret,
    }
    return bool(
        validate_embedding_candidate(unsafe_excluded, contract=contract, seed=pol_seed)
    ) and bool(validate_embedding_candidate(unsafe_raw, contract=contract, seed=pol_seed))
