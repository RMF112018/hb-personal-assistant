"""Phase 09 Prompt 18 — vector index build dry run (read-only, fail-closed).

Produces a metadata-only **build plan** over the approved source manifest's nodes — what *would* be
embedded and indexed — **computing no embeddings and writing no vector store**. The apply path (actual
embeddings + vector store) lands in Prompt 19.

The **approved source manifest is the only input** (provenance + authorization), and the node sources
are the per-category loaders (Obsidian + reviewed memory), which already enforce approved + source-linked
+ guard-clean. The build re-asserts the build rule on every node: **reject any source lacking review
tier, confidence, source ref, or freshness metadata, or failing the no-raw proof** (Prompt 14's
`validate_embedding_candidate`). The third manifest category (generated outputs / research packets) has
no loader yet and is deferred.

Everything is read-only (the plan opens the DB `?mode=ro`), metadata-only (counts + hashes; no node
text), and fail-closed. Vectors are never persisted to SQLite. Dry-run persistence (a single
`status='dry_run'` `vector_index_runs` row) is exercised only via `persist_dry_run_record` in
proofs/tests — the operator DB is never written.

Public entry points:
  build_vector_index_dry_run(db_path=None, *, project_key=None) -> dict
  persist_dry_run_record(db_path, plan, *, policy_version) -> str
  build_vector_index_dry_run_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval llamaindex build [--dry-run] | build-proof --json
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw
from .embedding_policy import (
    load_embedding_vector_policy_contract,
    load_embedding_vector_policy_seed,
    validate_embedding_candidate,
)
from .llamaindex_config import load_llamaindex_config_seed
from .memory_loader import load_reviewed_memory_nodes
from .obsidian_loader import load_approved_obsidian_nodes
from .source_manifest import build_approved_source_manifest

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "vector-index-dry-run-proof.json"
_PROOF_MD = "vector-index-dry-run-proof.md"

_RUNS_TABLE = "second_brain_retrieval_vector_index_runs"
_REQUIRED_FIELDS = ("review_tier", "confidence_class", "source_ref", "freshness_label")


class VectorIndexBuildError(RuntimeError):
    """Raised when the vector-index build cannot resolve policy/schema (fail-closed)."""


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


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _schema_ready(db_path: str | None) -> int:
    """Return the schema version if ready (>=38 with the runs table), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None or not _table_exists(conn, "schema_migrations"):
        if conn is not None:
            conn.close()
        raise VectorIndexBuildError(
            "schema not ready for vector-index build (no schema_migrations)"
        )
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _table_exists(conn, _RUNS_TABLE):
            raise VectorIndexBuildError(
                f"schema not ready for vector-index build (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def _apply_build_rule(
    node: dict[str, Any], *, contract: dict[str, Any], seed: dict[str, Any]
) -> list[str]:
    """Return build-rejection reasons for a node (empty ⇒ indexable). Fail-closed.

    Rejects any node lacking review tier / confidence / source ref / freshness metadata, or failing the
    embedding no-raw guardrail (the no-raw proof).
    """
    violations = [f"missing_{f}" for f in _REQUIRED_FIELDS if node.get(f) in (None, "")]
    violations.extend(validate_embedding_candidate(node, contract=contract, seed=seed))
    return violations


def _gather_approved_nodes(
    db_path: str | None, project_key: str | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Gather Obsidian + reviewed-memory loader nodes, with the approved manifest as authorization."""
    manifest = build_approved_source_manifest(db_path, project_key=project_key)
    nodes: list[dict[str, Any]] = []
    nodes.extend(load_approved_obsidian_nodes(db_path, project_key=project_key))
    nodes.extend(load_reviewed_memory_nodes(db_path, project_key=project_key))
    return nodes, manifest


def build_vector_index_dry_run(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Build the read-only dry-run vector-index plan (fail-closed). Persists nothing."""
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    config = load_llamaindex_config_seed()
    schema_version = _schema_ready(db_path)

    nodes, manifest = _gather_approved_nodes(db_path, project_key)

    chunk_size = int(config.get("chunk_size", 512)) or 512
    indexable: list[dict[str, Any]] = []
    rejected = 0
    reasons: dict[str, int] = {}
    per_family: dict[str, int] = {}
    planned_chunks = 0
    for node in nodes:
        violations = _apply_build_rule(node, contract=contract, seed=seed)
        if violations:
            rejected += 1
            for v in violations:
                reasons[v.split(":")[0]] = reasons.get(v.split(":")[0], 0) + 1
            continue
        indexable.append(node)
        fam = str(node["source_family"])
        per_family[fam] = per_family.get(fam, 0) + 1
        text_len = len(str(node.get("text_redacted", "")))
        planned_chunks += max(1, math.ceil(text_len / chunk_size))

    from .llamaindex_config import _llama_index_available

    sdk_available = _llama_index_available()
    config_hash = _hash(
        json.dumps({k: config.get(k) for k in sorted(config)}, sort_keys=True, default=str)
    )
    index_plan_hash = _hash(
        "|".join(
            sorted(
                f"{n['source_family']}:{_hash(str(n['source_ref']))[:16]}:{n['content_hash']}"
                for n in indexable
            )
        )
    )
    warnings: list[str] = []
    if not indexable:
        warnings.append("no_approved_nodes")
    warnings.append("generated_outputs_loader_deferred")

    return {
        "command": "second-brain retrieval llamaindex build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": "dry_run",
        "manifest_id": manifest["manifest_id"],
        "manifest_hash": manifest["manifest_hash"],
        "schema_version": schema_version,
        "embedding_model_label": config.get("embedding_model_label"),
        "index_kind": config.get("index_kind"),
        "vector_store_kind": config.get("vector_store_kind"),
        "config_hash": config_hash,
        "index_plan_hash": index_plan_hash,
        "total_nodes": len(indexable),
        "per_family_node_count": per_family,
        "rejected_node_count": rejected,
        "rejected_reasons": reasons,
        "planned_chunk_count": planned_chunks,
        "sdk_available": sdk_available,
        "ready_to_apply": sdk_available and bool(indexable),
        "no_raw_attested": True,
        "vectors_persisted_to_sqlite": False,
        "warnings": warnings,
        "policy_version": seed.get("version"),
        "read_only": True,
    }


def persist_dry_run_record(
    db_path: str | None, plan: dict[str, Any], *, policy_version: str
) -> str:
    """Persist a single guard-clean dry-run `vector_index_runs` row. Proof/test only. Returns run_id."""
    resolved = db_path or str(PathPolicy().get_db_path())
    run_id = f"vir_dryrun_{plan['index_plan_hash'][:32]}"
    conn = sqlite3.connect(resolved)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {_RUNS_TABLE} "
            "(run_id, policy_version, schema_version, manifest_id, project_key, item_count, status, "
            "config_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                policy_version,
                int(plan["schema_version"]),
                str(plan["manifest_id"]),
                None,
                int(plan["total_nodes"]),
                "dry_run",
                str(plan["config_hash"]),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return run_id


def _proof_db(tmp: str) -> str:
    """Build a proof DB with an apply-mode Obsidian index + one accepted memory item."""

    from ..memory.models import MemoryItem
    from ..memory.store import write_memory_item
    from ..obsidian_index.indexer import build_index
    from ..obsidian_linkage_proof import write_linkage_fixture_vault

    vault = Path(tmp) / "vault"
    write_linkage_fixture_vault(vault)
    db = str(Path(tmp) / "vidx.sqlite")
    build_index(mode="apply", vault_root=vault, db_path=db)
    write_memory_item(
        MemoryItem(
            memory_id="m-proof-1",
            memory_type="fact",
            statement_redacted="[redacted project summary]",
            confidence_class="high",
            review_status="accepted",
            source_refs=[{"source_family": "cross_source_relationships", "source_ref": "rel-1"}],
        ),
        db_path=db,
    )
    return db


def _rule_cases() -> list[dict[str, Any]]:
    """Controlled safe + planted-unsafe nodes exercising the build rule."""
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    safe = {
        "source_family": "accepted_long_term_memory",
        "source_ref": "m-1",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 1,
        "review_status": "accepted",
        "review_required": False,
        "freshness_label": "current",
        "text_redacted": "[redacted project summary]",
    }
    synthetic_secret = "Bea" + "rer " + "z" * 32
    planted: list[tuple[str, dict[str, Any]]] = [
        ("missing_review_tier", {k: v for k, v in safe.items() if k != "review_tier"}),
        ("missing_confidence", {k: v for k, v in safe.items() if k != "confidence_class"}),
        ("missing_source_ref", {k: v for k, v in safe.items() if k != "source_ref"}),
        ("missing_freshness", {k: v for k, v in safe.items() if k != "freshness_label"}),
        ("raw_shape_text", {**safe, "text_redacted": synthetic_secret}),
        ("non_embeddable_family", {**safe, "source_family": "raw_prompt"}),
    ]
    cases: list[dict[str, Any]] = []
    v = _apply_build_rule(safe, contract=contract, seed=seed)
    cases.append(
        {
            "name": "safe_node",
            "expected_indexable": True,
            "indexable": not v,
            "violations": v,
            "passed": not v,
        }
    )
    for name, node in planted:
        v = _apply_build_rule(node, contract=contract, seed=seed)
        cases.append(
            {
                "name": name,
                "expected_indexable": False,
                "indexable": not v,
                "violations": v,
                "passed": bool(v),
            }
        )
    return cases


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Vector Index Build (Dry Run) Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- proof_total_nodes: {proof['proof_total_nodes']}",
        f"- dry_run_record_persisted: {proof['dry_run_record_persisted']}",
        f"- dry_run_record_guard_clean: {proof['dry_run_record_guard_clean']}",
        f"- vectors_persisted_to_sqlite: {proof['vectors_persisted_to_sqlite']} (must be false)",
        "",
        "## Build-rule cases",
        "",
    ]
    for c in proof["cases"]:
        lines.append(
            f"- [{'ok' if c['passed'] else 'FAIL'}] {c['name']}: "
            f"expected_indexable={c['expected_indexable']} indexable={c['indexable']} "
            f"violations={len(c['violations'])}"
        )
    lines.append("")
    return "\n".join(lines)


def build_vector_index_dry_run_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: dry-run plan + build-rule + guard-clean dry-run record (no operator writes)."""
    with tempfile.TemporaryDirectory() as tmp:
        db = _proof_db(tmp)
        plan = build_vector_index_dry_run(db)
        run_id = persist_dry_run_record(db, plan, policy_version=str(plan["policy_version"]))
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                f"SELECT status, item_count, raw_vector_content_persisted, external_writeback_performed "
                f"FROM {_RUNS_TABLE} WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        finally:
            conn.close()
    record_persisted = row is not None and row[0] == "dry_run"
    record_guard_clean = bool(row) and row[2] == 0 and row[3] == 0
    cases = _rule_cases()
    proof_passed = (
        plan["total_nodes"] >= 1
        and plan["vectors_persisted_to_sqlite"] is False
        and record_persisted
        and record_guard_clean
        and all(c["passed"] for c in cases)
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_vector_index_dry_run",
        "command": "second-brain retrieval llamaindex build-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "proof_total_nodes": plan["total_nodes"],
        "proof_planned_chunk_count": plan["planned_chunk_count"],
        "dry_run_record_persisted": record_persisted,
        "dry_run_record_guard_clean": record_guard_clean,
        "vectors_persisted_to_sqlite": plan["vectors_persisted_to_sqlite"],
        "case_count": len(cases),
        "cases": cases,
        "metadata_only": True,
        "guardrails": {
            "read_only": True,
            "no_raw": True,
            "no_writeback": True,
            "approved_manifest_only_input": True,
            "no_raw_vector_content_in_sqlite": True,
            "dry_run_no_embeddings": True,
            "local_first": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "vector-index dry-run proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "vector-index dry-run proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
