"""Phase 09 Prompt 17 — reviewed memory loader (read-only, fail-closed).

Loads **only reviewed (accepted) long-term memory** into safe, metadata-only nodes for the future
embed/index step (Prompts 18-19). "Reviewed" means `long_term_memory_items.review_status='accepted'` —
`pending_review` / `rejected` / `superseded` memory is never loaded (the strict `WHERE
review_status='accepted'` SQL gate makes the "unreviewed memory entering a manifest" stop condition
unreachable). Each candidate node is validated by the Prompt 14 embedding guard
(`validate_embedding_candidate`): embeddable family, source-linked metadata, no forbidden raw fields,
no raw-content shapes.

The loader is **read-only** (opens the DB `?mode=ro`) and persists nothing — node persistence is
Prompts 18-19. The report and evidence are **metadata-only** (counts + per-node hashes); the redacted
memory statement (`text_redacted`) rides only on the in-memory node objects for the future embedder and
is never echoed. No embeddings are computed here.

Public entry points:
  load_reviewed_memory_nodes(db_path=None, *, project_key=None) -> list[dict]
  build_reviewed_memory_loader_report(db_path=None, *, project_key=None) -> dict
  build_reviewed_memory_loader_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval memory-loader status|proof --json
"""

from __future__ import annotations

import hashlib
import json
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

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "reviewed-memory-loader-proof.json"
_PROOF_MD = "reviewed-memory-loader-proof.md"

_FAMILY = "accepted_long_term_memory"
_TEXT_MAX = 280


class MemoryLoaderError(RuntimeError):
    """Raised when the reviewed-memory loader cannot resolve policy or schema (fail-closed)."""


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


def _source_ref_count(conn: sqlite3.Connection, memory_id: str) -> int:
    if not _table_exists(conn, "long_term_memory_source_refs"):
        return 0
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM long_term_memory_source_refs WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()[0]
    )


def load_reviewed_memory_nodes(
    db_path: str | None = None, *, project_key: str | None = None
) -> list[dict[str, Any]]:
    """Load guard-validated reviewed (accepted) memory nodes (read-only, fail-closed)."""
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()

    conn = _open_ro(db_path)
    if conn is None or not _table_exists(conn, "schema_migrations"):
        if conn is not None:
            conn.close()
        raise MemoryLoaderError(
            "schema not ready for reviewed-memory loader (no schema_migrations)"
        )
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        schema_version = int(row[0]) if row and row[0] is not None else 0
        if schema_version < 38 or not _table_exists(conn, "long_term_memory_items"):
            raise MemoryLoaderError(
                f"schema not ready for reviewed-memory loader (version {schema_version}, expected >= 38)"
            )
        clause = " AND project_key = ?" if project_key is not None else ""
        params: list[Any] = ["accepted"]
        if project_key is not None:
            params.append(project_key)
        rows = conn.execute(
            "SELECT memory_id, memory_type, statement_redacted, confidence_class, created_utc "
            "FROM long_term_memory_items WHERE review_status = ?"
            + clause
            + " ORDER BY memory_id LIMIT 500",
            tuple(params),
        ).fetchall()
        counts = {r[0]: _source_ref_count(conn, str(r[0])) for r in rows}
    finally:
        conn.close()

    nodes: list[dict[str, Any]] = []
    for memory_id, memory_type, statement, conf, created in rows:
        candidate = {
            "node_id": _hash(str(memory_id))[:32],
            "source_family": _FAMILY,
            "source_ref": str(memory_id),
            "content_hash": _hash(str(memory_id)),
            "confidence_class": str(conf or "unknown"),
            "review_tier": 1,
            "review_status": "accepted",
            "review_required": False,
            "freshness_label": "current" if created else "unknown",
            "memory_type": str(memory_type or "fact"),
            "source_ref_count": counts.get(memory_id, 0),
            "text_redacted": str(statement or "")[:_TEXT_MAX],
        }
        if not validate_embedding_candidate(candidate, contract=contract, seed=seed):
            nodes.append(candidate)
    return nodes


def _node_summary(node: dict[str, Any]) -> dict[str, Any]:
    """Metadata-only projection (no text) for the report/evidence."""
    return {
        "node_id": node["node_id"],
        "source_family": node["source_family"],
        "source_ref_hash": _hash(node["source_ref"])[:32],
        "content_hash": node["content_hash"],
        "review_tier": node["review_tier"],
        "confidence_class": node["confidence_class"],
        "freshness_label": node["freshness_label"],
        "memory_type": node["memory_type"],
        "source_ref_count": node["source_ref_count"],
    }


def build_reviewed_memory_loader_report(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Build the metadata-only reviewed-memory loader report (read-only, fail-closed)."""
    nodes = load_reviewed_memory_nodes(db_path, project_key=project_key)
    warnings: list[str] = []
    if not nodes:
        warnings.append("no_reviewed_memory")
    if any(n["source_ref_count"] == 0 for n in nodes):
        warnings.append("unsourced_memory")
    return {
        "command": "second-brain retrieval memory-loader status",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "source_family": _FAMILY,
        "loaded_count": len(nodes),
        "status": "loaded" if nodes else "empty",
        "nodes": [_node_summary(n) for n in nodes],
        "warnings": warnings,
        "reviewed_only": True,
        "read_only": True,
    }


def _seed_proof_db(tmp: str, accepted: bool) -> str:
    """Build a temp DB with one accepted (or one pending) memory; return the db path."""
    from hb_assistant.store.migrator import SQLiteMigrator

    from ..memory.models import MemoryItem
    from ..memory.store import write_memory_item

    db = str(Path(tmp) / ("accepted.db" if accepted else "pending.db"))
    SQLiteMigrator(db_path=db).apply()
    write_memory_item(
        MemoryItem(
            memory_id="m-proof-1",
            memory_type="fact",
            statement_redacted="[redacted project summary]",
            confidence_class="high",
            review_status="accepted" if accepted else "pending_review",
            source_refs=[{"source_family": "cross_source_relationships", "source_ref": "rel-1"}],
        ),
        db_path=db,
    )
    return db


def _candidate_cases() -> list[dict[str, Any]]:
    """Controlled safe + planted-unsafe candidate nodes exercising the embedding guard."""
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    safe = {
        "node_id": "n-safe",
        "source_family": _FAMILY,
        "source_ref": "m-1",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 1,
        "review_status": "accepted",
        "review_required": False,
        "freshness_label": "current",
        "source_ref_count": 1,
        "text_redacted": "[redacted project summary]",
    }
    synthetic_secret = "Bea" + "rer " + "z" * 32
    planted: list[tuple[str, dict[str, Any]]] = [
        ("non_embeddable_family", {**safe, "source_family": "raw_prompt"}),
        ("missing_metadata", {k: v for k, v in safe.items() if k != "content_hash"}),
        ("raw_shape_statement", {**safe, "text_redacted": synthetic_secret}),
        (
            "unresolved_review",
            {**safe, "review_required": True, "review_status": "pending_review"},
        ),
    ]
    cases: list[dict[str, Any]] = []
    v = validate_embedding_candidate(safe, contract=contract, seed=seed)
    cases.append(
        {
            "name": "safe_memory_node",
            "expected_loaded": True,
            "loaded": not v,
            "violations": v,
            "passed": not v,
        }
    )
    for name, cand in planted:
        v = validate_embedding_candidate(cand, contract=contract, seed=seed)
        cases.append(
            {
                "name": name,
                "expected_loaded": False,
                "loaded": not v,
                "violations": v,
                "passed": bool(v),
            }
        )
    return cases


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Reviewed Memory Loader Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- accepted_loaded_count: {proof['accepted_loaded_count']}",
        f"- pending_loaded_count: {proof['pending_loaded_count']} (must be 0)",
        "",
        "## Candidate guardrail cases",
        "",
    ]
    for c in proof["cases"]:
        lines.append(
            f"- [{'ok' if c['passed'] else 'FAIL'}] {c['name']}: "
            f"expected_loaded={c['expected_loaded']} loaded={c['loaded']} violations={len(c['violations'])}"
        )
    lines.append("")
    return "\n".join(lines)


def build_reviewed_memory_loader_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: reviewed-only gating + the embedding guardrail (no operator writes)."""
    with tempfile.TemporaryDirectory() as tmp:
        accepted_db = _seed_proof_db(tmp, accepted=True)
        pending_db = _seed_proof_db(tmp, accepted=False)
        accepted_nodes = load_reviewed_memory_nodes(accepted_db)
        pending_nodes = load_reviewed_memory_nodes(pending_db)
    cases = _candidate_cases()
    accepted_loaded = len(accepted_nodes)
    pending_loaded = len(pending_nodes)
    proof_passed = accepted_loaded >= 1 and pending_loaded == 0 and all(c["passed"] for c in cases)

    proof: dict[str, Any] = {
        "proof": "phase_09_reviewed_memory_loader",
        "command": "second-brain retrieval memory-loader proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "accepted_loaded_count": accepted_loaded,
        "pending_loaded_count": pending_loaded,
        "case_count": len(cases),
        "cases": cases,
        "metadata_only": True,
        "guardrails": {
            "read_only": True,
            "no_raw": True,
            "no_writeback": True,
            "reviewed_only_accepted": True,
            "exclude_unresolved_high_impact": True,
            "local_first": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "reviewed-memory-loader proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "reviewed-memory-loader proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
