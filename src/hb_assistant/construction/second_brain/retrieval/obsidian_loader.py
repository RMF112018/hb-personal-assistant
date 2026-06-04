"""Phase 09 Prompt 16 — approved Obsidian output loader (read-only, fail-closed).

Loads **only approved, source-linked generated Obsidian notes** into safe, metadata-only nodes for the
future embed/index step (Prompts 18-19). "Approved" means the entries of the latest **`mode='apply'`**
Obsidian index manifest — dry-run manifests are never loaded (the "unapproved Obsidian notes indexed"
stop condition cannot be hit). Each candidate node is validated by the Prompt 14 embedding guard
(`validate_embedding_candidate`): it must be in the embeddable allowlist, carry the required
source-linked metadata, be free of forbidden raw fields / raw-content shapes, and not be an unresolved
high-impact (tier-3 / review_required) item.

The loader is **read-only** (opens the DB `?mode=ro`) and persists nothing — node persistence is
Prompts 18-19. The report and evidence are **metadata-only** (counts + per-node hashes); the redacted
excerpt (`text_redacted`, the already-redacted heading/section the index holds) rides only on the
in-memory node objects for the future embedder and is never echoed. No embeddings are computed here.

Public entry points:
  load_approved_obsidian_nodes(db_path=None, *, project_key=None) -> list[dict]
  build_obsidian_loader_report(db_path=None, *, project_key=None) -> dict
  build_obsidian_loader_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval obsidian-loader status|proof --json
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw
from .embedding_policy import (
    load_embedding_vector_policy_contract,
    load_embedding_vector_policy_seed,
    validate_embedding_candidate,
)

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "approved-obsidian-loader-proof.json"
_PROOF_MD = "approved-obsidian-loader-proof.md"

_FAMILY = "approved_obsidian_generated_outputs"
_TEXT_MAX = 280


class ObsidianLoaderError(RuntimeError):
    """Raised when the approved-Obsidian loader cannot resolve policy or schema (fail-closed)."""


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
    import hashlib

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


def _latest_apply_manifest(conn: sqlite3.Connection) -> str | None:
    """Return the latest STRICT apply-mode manifest id (never a dry_run fallback)."""
    row = conn.execute(
        "SELECT manifest_id FROM obsidian_index_manifests "
        "WHERE mode = 'apply' ORDER BY generated_utc DESC, manifest_id DESC LIMIT 1"
    ).fetchone()
    return None if row is None else str(row[0])


def _candidate_from_entry(rec: tuple[Any, ...]) -> dict[str, Any]:
    note_hash, content_hash, conf, status, section, heading, refs_json, modified = rec
    tier = 1
    ref_count = 0
    try:
        meta = json.loads(refs_json) if refs_json else {}
        tier = int(meta.get("review_tier", 1))
        ref_count = int(meta.get("source_ref_count", 0))
    except Exception:
        tier = 1
    text = str(heading or section or "")[:_TEXT_MAX]
    review_status = str(status or ("review_required" if tier == 3 else "auto_advisory"))
    return {
        "node_id": _hash(f"{note_hash}:{content_hash}")[:32],
        "source_family": _FAMILY,
        "source_ref": str(note_hash),
        "content_hash": str(content_hash or ""),
        "confidence_class": str(conf or "high"),
        "review_tier": tier,
        "review_status": review_status,
        "review_required": tier == 3,
        "freshness_label": "current" if modified else "unknown",
        "source_ref_count": ref_count,
        "text_redacted": text,
    }


def load_approved_obsidian_nodes(
    db_path: str | None = None, *, project_key: str | None = None
) -> list[dict[str, Any]]:
    """Load guard-validated approved Obsidian nodes (read-only, fail-closed). Returns full nodes."""
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()

    conn = _open_ro(db_path)
    if conn is None or not _table_exists(conn, "schema_migrations"):
        if conn is not None:
            conn.close()
        raise ObsidianLoaderError(
            "schema not ready for approved-Obsidian loader (no schema_migrations)"
        )
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        schema_version = int(row[0]) if row and row[0] is not None else 0
        if schema_version < 38 or not _table_exists(conn, "obsidian_index_manifests"):
            raise ObsidianLoaderError(
                f"schema not ready for approved-Obsidian loader (version {schema_version}, expected >= 38)"
            )
        manifest_id = _latest_apply_manifest(conn)
        if manifest_id is None:
            return []
        clause = " AND project_key = ?" if project_key is not None else ""
        params: list[Any] = [manifest_id]
        if project_key is not None:
            params.append(project_key)
        rows = conn.execute(
            "SELECT note_path_hash, content_hash, confidence_class, review_status, section_marker, "
            "heading_redacted, source_refs_json, modified_utc FROM obsidian_index_entries "
            "WHERE manifest_id = ?" + clause + " ORDER BY note_path_hash, section_marker LIMIT 500",
            tuple(params),
        ).fetchall()
    finally:
        conn.close()

    nodes: list[dict[str, Any]] = []
    for rec in rows:
        candidate = _candidate_from_entry(rec)
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
        "source_ref_count": node["source_ref_count"],
    }


def build_obsidian_loader_report(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Build the metadata-only approved-Obsidian loader report (read-only, fail-closed)."""
    nodes = load_approved_obsidian_nodes(db_path, project_key=project_key)
    warnings: list[str] = []
    if not nodes:
        warnings.append("no_approved_obsidian_notes")
    return {
        "command": "second-brain retrieval obsidian-loader status",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "source_family": _FAMILY,
        "loaded_count": len(nodes),
        "status": "loaded" if nodes else "empty",
        "nodes": [_node_summary(n) for n in nodes],
        "warnings": warnings,
        "apply_manifests_only": True,
        "read_only": True,
    }


def _proof_db_with_obsidian(tmp: str, mode: Literal["dry_run", "apply"]) -> str:
    """Build a fixture-vault Obsidian index in a temp DB at the given mode; return the db path."""
    from ..obsidian_index.indexer import build_index
    from ..obsidian_linkage_proof import write_linkage_fixture_vault

    vault = Path(tmp) / f"vault_{mode}"
    write_linkage_fixture_vault(vault)
    db = str(Path(tmp) / f"idx_{mode}.sqlite")
    build_index(mode=mode, vault_root=vault, db_path=db)
    return db


def _candidate_cases() -> list[dict[str, Any]]:
    """Controlled safe + planted-unsafe candidate nodes exercising the embedding guard."""
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    safe = {
        "node_id": "n-safe",
        "source_family": _FAMILY,
        "source_ref": "note-hash-1",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 1,
        "review_status": "auto_advisory",
        "review_required": False,
        "freshness_label": "current",
        "source_ref_count": 2,
        "text_redacted": "Project Alpha Data Quality Summary",
    }
    synthetic_secret = "Bea" + "rer " + "z" * 32
    planted: list[tuple[str, dict[str, Any]]] = [
        (
            "tier3_review_required",
            {**safe, "review_tier": 3, "review_required": True, "review_status": "review_required"},
        ),
        ("non_embeddable_family", {**safe, "source_family": "raw_email_body"}),
        ("missing_metadata", {k: v for k, v in safe.items() if k != "content_hash"}),
        ("raw_shape_text", {**safe, "text_redacted": synthetic_secret}),
    ]
    cases: list[dict[str, Any]] = []
    v = validate_embedding_candidate(safe, contract=contract, seed=seed)
    cases.append(
        {
            "name": "safe_obsidian_node",
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
        "# Phase 09 — Approved Obsidian Output Loader Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- apply_loaded_count: {proof['apply_loaded_count']}",
        f"- dry_run_loaded_count: {proof['dry_run_loaded_count']} (must be 0)",
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


def build_obsidian_loader_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: apply-only gating + the embedding guardrail (in-memory; no operator writes)."""
    with tempfile.TemporaryDirectory() as tmp:
        apply_db = _proof_db_with_obsidian(tmp, "apply")
        dry_db = _proof_db_with_obsidian(tmp, "dry_run")
        apply_nodes = load_approved_obsidian_nodes(apply_db)
        dry_nodes = load_approved_obsidian_nodes(dry_db)
    cases = _candidate_cases()
    apply_loaded = len(apply_nodes)
    dry_loaded = len(dry_nodes)
    proof_passed = apply_loaded >= 1 and dry_loaded == 0 and all(c["passed"] for c in cases)

    proof: dict[str, Any] = {
        "proof": "phase_09_approved_obsidian_loader",
        "command": "second-brain retrieval obsidian-loader proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "apply_loaded_count": apply_loaded,
        "dry_run_loaded_count": dry_loaded,
        "case_count": len(cases),
        "cases": cases,
        "metadata_only": True,
        "guardrails": {
            "read_only": True,
            "no_raw": True,
            "no_writeback": True,
            "apply_manifests_only": True,
            "exclude_unresolved_high_impact": True,
            "local_first": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "approved-obsidian-loader proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "approved-obsidian-loader proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
