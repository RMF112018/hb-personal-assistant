"""Phase 09 Prompt 31 — memory consolidation preview (review-only proposals).

A read-only, advisory pass over the **accepted** long-term memory corpus (``long_term_memory_items``,
``review_status='accepted'``) that clusters exact-duplicate statements and generates **review-only
consolidation proposals** (keep one canonical member, propose superseding the redundant duplicates) for
human review.

It **never auto-deletes, auto-supersedes, or auto-merges** any memory item — ``long_term_memory_items``
is left byte-for-byte unchanged; only proposals are written (on ``emit_receipt``) to the reserved V38
``second_brain_memory_consolidation_candidates`` (one row per cluster) + ``…_review_items`` (one row per
member, ``advisory_only=1``) tables. Statements and memory refs are SHA256-hashed — no raw statement text
is persisted or emitted. Read-only by default (``emit_receipt=False`` persists nothing). Fail-closed on
missing policy or stale schema; makes no determination.

Public entry points:
  cluster_consolidation_candidates(accepted_items, *, min_cluster_size=2) -> dict
  build_memory_consolidation_preview(db_path=None, *, project_key=None, emit_receipt=False) -> dict
  persist_memory_consolidation_preview(db_path, result, *, policy_version) -> str
  build_memory_consolidation_preview_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain memory consolidation-preview build | proof --json
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "memory-consolidation-preview-proof.json"
_PROOF_MD = "memory-consolidation-preview-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_memory_consolidation_preview.seed.yaml"

_CANDIDATES_TABLE = "second_brain_memory_consolidation_candidates"
_REVIEW_ITEMS_TABLE = "second_brain_memory_consolidation_review_items"
_MEMORY_ITEMS_TABLE = "long_term_memory_items"


class MemoryConsolidationPreviewError(RuntimeError):
    """Raised when the consolidation-preview builder cannot resolve policy/schema (fail-closed)."""


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


def _schema_ready(db_path: str | None) -> int:
    """Return the schema version if ready (>=38 with both consolidation tables), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise MemoryConsolidationPreviewError(
            "schema not ready for memory consolidation preview (no database)"
        )
    try:

        def _has(table: str) -> bool:
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                is not None
            )

        if not _has("schema_migrations"):
            raise MemoryConsolidationPreviewError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has(_CANDIDATES_TABLE) or not _has(_REVIEW_ITEMS_TABLE):
            raise MemoryConsolidationPreviewError(
                f"schema not ready for memory consolidation preview (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_memory_consolidation_preview_contract() -> dict[str, Any]:
    """Load the memory-consolidation-preview contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("memory_consolidation_preview_contract")
    if not isinstance(contract, dict) or "min_cluster_size" not in contract:
        raise MemoryConsolidationPreviewError(
            "phase 09 memory-consolidation-preview contract not found or missing required fields"
        )
    return contract


def load_memory_consolidation_preview_seed() -> dict[str, Any]:
    """Load the resolved memory-consolidation-preview seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise MemoryConsolidationPreviewError(
            f"memory-consolidation-preview seed not found at {candidate}"
        )
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "min_cluster_size" not in data:
        raise MemoryConsolidationPreviewError(
            f"{candidate} must define the memory-consolidation-preview policy"
        )
    return data


def cluster_consolidation_candidates(
    accepted_items: list[dict[str, Any]], *, min_cluster_size: int = 2
) -> dict[str, Any]:
    """Cluster accepted memory items by exact-duplicate statement and build review-only proposals.

    Group items by (project_key, memory_type, statement_hash). A cluster is a group of >= min_cluster_size
    items. For each cluster the deterministically-oldest member (sorted by created_utc then memory_id) is
    the canonical keep; the rest are proposed supersede. Returns metadata-only proposal records — only
    SHA256 hashes of statements / memory ids, never raw text. Generates proposals only; mutates nothing.
    """
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for it in accepted_items:
        statement_hash = _hash(str(it.get("statement_redacted") or ""))
        key = (
            str(it.get("project_key") or ""),
            str(it.get("memory_type") or ""),
            statement_hash,
        )
        groups.setdefault(key, []).append({**it, "_statement_hash": statement_hash})

    proposals: list[dict[str, Any]] = []
    total_members = 0
    for (_pk, _mt, statement_hash), members in groups.items():
        if len(members) < min_cluster_size:
            continue
        ordered = sorted(
            members, key=lambda m: (str(m.get("created_utc") or ""), str(m.get("memory_id") or ""))
        )
        member_id_hashes = sorted(_hash(str(m.get("memory_id") or "")) for m in members)
        cluster_hash = _hash("|".join(member_id_hashes))
        canonical = ordered[0]
        member_records: list[dict[str, Any]] = []
        for m in ordered:
            role = "keep_canonical" if m is canonical else "supersede"
            member_records.append(
                {
                    "memory_id_hash": _hash(str(m.get("memory_id") or ""))[:48],
                    "role": role,
                    "decision_note_hash": _hash(f"{role}:{cluster_hash}")[:48],
                }
            )
        total_members += len(members)
        proposals.append(
            {
                "candidate_id": f"mcc_{cluster_hash[:32]}",
                "cluster_hash": cluster_hash[:48],
                "statement_hash": statement_hash[:48],
                "source_memory_ref_hash": _hash(str(canonical.get("memory_id") or ""))[:48],
                "confidence_class": str(canonical.get("confidence_class") or "unknown"),
                "member_count": len(members),
                "members": member_records,
            }
        )

    return {
        "cluster_count": len(proposals),
        "total_member_count": total_members,
        "proposals": proposals,
    }


def _read_accepted_items(conn: sqlite3.Connection, project_key: str | None) -> list[dict[str, Any]]:
    sql = (
        "SELECT memory_id, memory_type, statement_redacted, project_key, confidence_class, created_utc "
        "FROM long_term_memory_items WHERE review_status = 'accepted'"
    )
    params: tuple[Any, ...] = ()
    if project_key is not None:
        sql += " AND project_key = ?"
        params = (project_key,)
    return [
        {
            "memory_id": r[0],
            "memory_type": r[1],
            "statement_redacted": r[2],
            "project_key": r[3],
            "confidence_class": r[4],
            "created_utc": r[5],
        }
        for r in conn.execute(sql, params).fetchall()
    ]


def build_memory_consolidation_preview(
    db_path: str | None = None,
    *,
    project_key: str | None = None,
    emit_receipt: bool = False,
) -> dict[str, Any]:
    """Generate review-only consolidation proposals over the accepted memory corpus (read-only, advisory).

    Returns a JSON-safe, metadata-only summary (cluster counts + hashed proposal records — never raw
    statement text); persists nothing unless ``emit_receipt``. Never auto-deletes/supersedes/merges
    memory; makes no determination.
    """
    contract = load_memory_consolidation_preview_contract()
    seed = load_memory_consolidation_preview_seed()
    schema_version = _schema_ready(db_path)
    min_size = int(seed.get("min_cluster_size", 2)) or 2

    conn = _open_ro(db_path)
    if conn is None:
        raise MemoryConsolidationPreviewError(
            "schema not ready for memory consolidation preview (no database)"
        )
    try:
        accepted = _read_accepted_items(conn, project_key)
    finally:
        conn.close()

    cl = cluster_consolidation_candidates(accepted, min_cluster_size=min_size)
    run_id = f"mcons_{_hash(f'{project_key or ""}|{cl["cluster_count"]}|{cl["total_member_count"]}')[:32]}"
    status = "built" if cl["cluster_count"] else "empty"

    result = {
        "command": "second-brain memory consolidation-preview build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": status,
        "run_id": run_id,
        "schema_version": schema_version,
        "project_key": project_key,
        "accepted_item_count": len(accepted),
        "cluster_count": cl["cluster_count"],
        "total_member_count": cl["total_member_count"],
        "proposal_review_tier": str(seed.get("proposal_review_tier", "mandatory_review")),
        "proposal_review_status": str(seed.get("proposal_review_status", "pending_review")),
        "proposals": cl["proposals"],
        "advisory_only": True,
        "makes_determination": False,
        "auto_deletes_or_supersedes": False,
        "review_only_proposals": True,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "receipt_emitted": emit_receipt,
        "read_only": not emit_receipt,
    }

    if emit_receipt:
        persist_memory_consolidation_preview(
            db_path, result, policy_version=str(seed.get("version"))
        )

    return result


def persist_memory_consolidation_preview(
    db_path: str | None, result: dict[str, Any], *, policy_version: str
) -> str:
    """Persist guard-clean metadata-only consolidation proposals (candidates + review items). Returns
    run_id. Never touches long_term_memory_items (no auto-delete/supersede)."""
    _schema_ready(db_path)
    resolved = db_path or str(PathPolicy().get_db_path())
    run_id = str(result["run_id"])
    schema_version = int(result["schema_version"])
    review_tier = str(result["proposal_review_tier"])
    review_status = str(result["proposal_review_status"])
    conn = sqlite3.connect(resolved)
    try:
        for prop in result["proposals"]:
            candidate_id = str(prop["candidate_id"])
            conn.execute(
                f"INSERT OR REPLACE INTO {_CANDIDATES_TABLE} "
                "(candidate_id, policy_version, schema_version, run_id, source_memory_ref_hash, "
                "cluster_hash, confidence_class, review_tier, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    candidate_id,
                    policy_version,
                    schema_version,
                    run_id,
                    str(prop["source_memory_ref_hash"]),
                    str(prop["cluster_hash"]),
                    str(prop["confidence_class"]),
                    review_tier,
                    "proposed",
                ),
            )
            for i, member in enumerate(prop["members"]):
                review_item_id = _hash(f"{candidate_id}:{i}:{member['memory_id_hash']}")[:48]
                conn.execute(
                    f"INSERT OR REPLACE INTO {_REVIEW_ITEMS_TABLE} "
                    "(review_item_id, policy_version, schema_version, candidate_id, review_tier, "
                    "review_status, decision_note_hash, advisory_only) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                    (
                        review_item_id,
                        policy_version,
                        schema_version,
                        candidate_id,
                        review_tier,
                        review_status,
                        str(member["decision_note_hash"]),
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


def _memory_items_fingerprint(db_path: str) -> tuple[int, str]:
    """A stable fingerprint of long_term_memory_items (row count + sorted memory_id:review_status set)."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT memory_id, review_status FROM {_MEMORY_ITEMS_TABLE} ORDER BY memory_id"
        ).fetchall()
    finally:
        conn.close()
    fp = ";".join(f"{r[0]}={r[1]}" for r in rows)
    return len(rows), fp


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Memory Consolidation Preview Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- status: {proof['status']}",
        f"- cluster_count: {proof['cluster_count']} (must be 1)",
        f"- total_member_count: {proof['total_member_count']} (must be 2)",
        f"- candidates_persisted: {proof['candidates_persisted']}",
        f"- review_items_persisted: {proof['review_items_persisted']}",
        f"- rows_guard_clean: {proof['rows_guard_clean']}",
        f"- advisory_only_flag_set: {proof['advisory_only_flag_set']}",
        f"- long_term_memory_items_unchanged: {proof['long_term_memory_items_unchanged']} (must be true)",
        f"- singleton_not_proposed: {proof['singleton_not_proposed']}",
        f"- makes_determination: {proof['makes_determination']} (must be false)",
        f"- read_only_default_no_persist: {proof['read_only_default_no_persist']}",
        f"- no_raw_statement_emitted: {proof['no_raw_statement_emitted']}",
        "",
    ]
    return "\n".join(lines)


def _seed_proof_db(db: str) -> None:
    """Seed two accepted items with the SAME statement (a duplicate cluster) + one unique singleton."""
    from .models import MemoryItem
    from .store import write_memory_item

    refs = [{"source_family": "accepted_long_term_memory", "source_ref": "m-x"}]
    for mid in ("dup-1", "dup-2"):
        write_memory_item(
            MemoryItem(
                memory_id=mid,
                memory_type="fact",
                statement_redacted="Project Alpha kickoff is in March.",
                confidence_class="high",
                review_status="accepted",
                source_refs=refs,
            ),
            db_path=db,
        )
    write_memory_item(
        MemoryItem(
            memory_id="uniq-1",
            memory_type="fact",
            statement_redacted="Project Beta has a new site manager.",
            confidence_class="high",
            review_status="accepted",
            source_refs=refs,
        ),
        db_path=db,
    )


def build_memory_consolidation_preview_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: a duplicate cluster yields one review-only proposal (canonical + supersede), the
    candidate + review-item rows are guard-clean + advisory_only=1, long_term_memory_items is UNCHANGED
    (no auto-delete/supersede), the singleton is not proposed, and no raw statement is emitted."""
    import tempfile

    from hb_assistant.store.migrator import ensure_schema_ready

    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "mcons.sqlite")
        ensure_schema_ready(db)
        _seed_proof_db(db)

        before_fp = _memory_items_fingerprint(db)
        cand_before = _table_rows(db, _CANDIDATES_TABLE)

        # read-only default persists nothing
        result = build_memory_consolidation_preview(db)
        read_only_no_persist = _table_rows(db, _CANDIDATES_TABLE) == cand_before

        # emit proposals + verify guard-clean metadata-only persistence
        result2 = build_memory_consolidation_preview(db, emit_receipt=True)
        run_id = result2["run_id"]
        after_fp = _memory_items_fingerprint(db)

        conn = sqlite3.connect(db)
        try:
            cand_rows = conn.execute(
                f"SELECT COUNT(*) FROM {_CANDIDATES_TABLE} WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            cand_ids = [
                str(r[0])
                for r in conn.execute(
                    f"SELECT candidate_id FROM {_CANDIDATES_TABLE} WHERE run_id = ?", (run_id,)
                ).fetchall()
            ]
            ri_rows = (
                conn.execute(
                    f"SELECT COUNT(*) FROM {_REVIEW_ITEMS_TABLE} WHERE candidate_id IN "
                    f"({','.join('?' for _ in cand_ids)})",
                    cand_ids,
                ).fetchone()[0]
                if cand_ids
                else 0
            )
            advisory_sum = (
                conn.execute(
                    f"SELECT COALESCE(SUM(advisory_only), 0) FROM {_REVIEW_ITEMS_TABLE} "
                    f"WHERE candidate_id IN ({','.join('?' for _ in cand_ids)})",
                    cand_ids,
                ).fetchone()[0]
                if cand_ids
                else 0
            )
            cand_guards = _guard_columns(conn, _CANDIDATES_TABLE)
            ri_guards = _guard_columns(conn, _REVIEW_ITEMS_TABLE)
            cand_guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(cand_guards)}), 0) FROM {_CANDIDATES_TABLE} "
                "WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
            ri_guard_sum = (
                conn.execute(
                    f"SELECT COALESCE(SUM({'+'.join(ri_guards)}), 0) FROM {_REVIEW_ITEMS_TABLE} "
                    f"WHERE candidate_id IN ({','.join('?' for _ in cand_ids)})",
                    cand_ids,
                ).fetchone()[0]
                if cand_ids
                else 0
            )
        finally:
            conn.close()

    long_term_unchanged = before_fp == after_fp
    candidates_persisted = cand_rows == 1
    review_items_persisted = ri_rows == 2
    rows_guard_clean = int(cand_guard_sum or 0) == 0 and int(ri_guard_sum or 0) == 0
    advisory_only_flag_set = int(advisory_sum or 0) == ri_rows and ri_rows >= 1
    singleton_not_proposed = (
        result["total_member_count"] == 2
    )  # only the duplicate pair, not the singleton
    serialized = json.dumps(result, default=str)
    no_raw_statement = (
        "statement_redacted" not in serialized
        and "Project Alpha" not in serialized
        and "Project Beta" not in serialized
    )

    proof_passed = (
        result["status"] == "built"
        and result["cluster_count"] == 1
        and result["total_member_count"] == 2
        and candidates_persisted
        and review_items_persisted
        and rows_guard_clean
        and advisory_only_flag_set
        and long_term_unchanged
        and singleton_not_proposed
        and result["makes_determination"] is False
        and read_only_no_persist
        and no_raw_statement
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_memory_consolidation_preview",
        "command": "second-brain memory consolidation-preview proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": result["status"],
        "cluster_count": result["cluster_count"],
        "total_member_count": result["total_member_count"],
        "candidates_persisted": candidates_persisted,
        "review_items_persisted": review_items_persisted,
        "rows_guard_clean": rows_guard_clean,
        "advisory_only_flag_set": advisory_only_flag_set,
        "long_term_memory_items_unchanged": long_term_unchanged,
        "singleton_not_proposed": singleton_not_proposed,
        "makes_determination": result["makes_determination"],
        "read_only_default_no_persist": read_only_no_persist,
        "no_raw_statement_emitted": no_raw_statement,
        "metadata_only": True,
        "guardrails": {
            "advisory_only": True,
            "no_determination": True,
            "never_auto_delete_or_supersede": True,
            "review_only_proposals": True,
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
        _assert_no_raw(out, "memory consolidation preview proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "memory consolidation preview proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof


def _table_rows(db_path: str, table: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()
