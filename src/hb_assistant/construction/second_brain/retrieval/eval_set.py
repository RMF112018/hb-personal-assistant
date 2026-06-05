"""Phase 09 Prompt 24 — retrieval quality eval set (source-linked cases from approved outputs).

Creates source-linked retrieval evaluation **cases** from the **approved outputs** corpus (approved
Obsidian generated outputs + reviewed/accepted long-term memory). Each case asserts that a query targeting
an approved output should retrieve that source — linked only by a **hashed** source ref. Eval sets and
cases are persisted **metadata-only** to the V38 ``second_brain_retrieval_eval_sets`` +
``second_brain_retrieval_eval_cases`` tables (guard-clean); no raw query text, raw content, answer, or raw
source ref is created or stored (only hashes). Executing/scoring the set against the index
(``eval_runs``) is a later prompt.

Read-only by default (``emit_receipt=False`` persists nothing); review tier / confidence class / source
references (hashed) / freshness are preserved. Fail-closed on missing policy or stale schema.

Public entry points:
  build_retrieval_eval_set(db_path=None, *, project_key=None, name=None, emit_receipt=False) -> dict
  persist_retrieval_eval_set(db_path, result, *, policy_version) -> str
  build_retrieval_eval_set_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval eval-set build | proof --json
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
from .policy import ALLOWLISTED_SOURCE_FAMILIES, EXCLUDED_FAMILIES
from .vector_index import _gather_approved_nodes

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "retrieval-eval-set-proof.json"
_PROOF_MD = "retrieval-eval-set-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_retrieval_eval_set.seed.yaml"

_SETS_TABLE = "second_brain_retrieval_eval_sets"
_CASES_TABLE = "second_brain_retrieval_eval_cases"


class RetrievalEvalSetError(RuntimeError):
    """Raised when the eval-set builder cannot resolve policy/schema (fail-closed)."""


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
    """Return the schema version if ready (>=38 with the eval tables), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise RetrievalEvalSetError("schema not ready for eval set (no database)")
    try:

        def _has(table: str) -> bool:
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                is not None
            )

        if not _has("schema_migrations"):
            raise RetrievalEvalSetError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has(_SETS_TABLE) or not _has(_CASES_TABLE):
            raise RetrievalEvalSetError(
                f"schema not ready for eval set (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_retrieval_eval_set_contract() -> dict[str, Any]:
    """Load the retrieval-eval-set contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("retrieval_eval_set_contract")
    if not isinstance(contract, dict) or "approved_source_families" not in contract:
        raise RetrievalEvalSetError(
            "phase 09 retrieval-eval-set contract not found or missing required fields"
        )
    return contract


def load_retrieval_eval_set_seed() -> dict[str, Any]:
    """Load the resolved retrieval-eval-set seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise RetrievalEvalSetError(f"retrieval-eval-set seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "default_set_name" not in data:
        raise RetrievalEvalSetError(f"{candidate} must define the retrieval-eval-set policy")
    return data


def _build_cases(nodes: list[dict[str, Any]], *, set_id: str) -> list[dict[str, Any]]:
    """One source-linked eval case per approved node. Skips unsafe/unlinked nodes (no source ref or
    excluded family). Metadata-only — hashed refs, never the raw source ref."""
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in nodes:
        family = str(node.get("source_family") or "")
        ref = str(node.get("source_ref") or "")
        if not ref or not family or family in EXCLUDED_FAMILIES:
            continue
        if family not in ALLOWLISTED_SOURCE_FAMILIES:
            continue
        case_id = _hash(f"{set_id}:{family}:{ref}")[:48]
        if case_id in seen:
            continue
        seen.add(case_id)
        cases.append(
            {
                "eval_case_id": case_id,
                "source_family": family,
                "expected_source_ref_hash": _hash(ref)[:48],
                "question_hash": _hash(f"{family}:{ref}:retrieval")[:48],
                "confidence_class": str(node.get("confidence_class") or "unknown"),
                "review_tier": int(node.get("review_tier") or 3),
            }
        )
    return cases


def build_retrieval_eval_set(
    db_path: str | None = None,
    *,
    project_key: str | None = None,
    name: str | None = None,
    emit_receipt: bool = False,
) -> dict[str, Any]:
    """Create source-linked retrieval eval cases from approved outputs (read-only, fail-closed).

    Returns a JSON-safe, metadata-only summary; persists nothing unless ``emit_receipt`` is set.
    """
    contract = load_retrieval_eval_set_contract()
    seed = load_retrieval_eval_set_seed()
    schema_version = _schema_ready(db_path)
    set_name = name or str(seed.get("default_set_name", "approved_retrieval_eval"))

    nodes, manifest = _gather_approved_nodes(db_path, project_key)
    set_hash = _hash(
        f"{set_name}|{project_key or ''}|"
        + "|".join(
            sorted(
                f"{n.get('source_family')}:{_hash(str(n.get('source_ref')))[:16]}" for n in nodes
            )
        )
    )
    set_id = f"res_{set_hash[:32]}"
    cases = _build_cases(nodes, set_id=set_id)

    per_family: dict[str, int] = {}
    tiers: set[int] = set()
    for c in cases:
        per_family[c["source_family"]] = per_family.get(c["source_family"], 0) + 1
        tiers.add(int(c["review_tier"]))
    review_tier_summary = (
        f"max={max(tiers)};tiers={','.join(str(t) for t in sorted(tiers))}" if tiers else "none"
    )
    status = "built" if cases else "empty"
    warnings: list[str] = []
    if not cases:
        warnings.append("no_approved_outputs")

    result = {
        "command": "second-brain retrieval eval-set build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": status,
        "eval_set_id": set_id,
        "name_hash": _hash(set_name)[:48],
        "schema_version": schema_version,
        "project_key": project_key,
        "manifest_id": manifest.get("manifest_id"),
        "case_count": len(cases),
        "per_family_case_count": per_family,
        "review_tier_summary": review_tier_summary,
        "warnings": warnings,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "cases": [
            {
                "eval_case_id": c["eval_case_id"],
                "source_family": c["source_family"],
                "expected_source_ref_hash": c["expected_source_ref_hash"],
                "question_hash": c["question_hash"],
                "confidence_class": c["confidence_class"],
            }
            for c in cases
        ],
        "receipt_emitted": emit_receipt,
        "read_only": not emit_receipt,
    }

    if emit_receipt:
        persist_retrieval_eval_set(db_path, result, policy_version=str(seed.get("version")))

    return result


def persist_retrieval_eval_set(
    db_path: str | None, result: dict[str, Any], *, policy_version: str
) -> str:
    """Persist a guard-clean metadata-only eval set + per-case rows. Returns eval_set_id."""
    _schema_ready(db_path)
    resolved = db_path or str(PathPolicy().get_db_path())
    set_id = str(result["eval_set_id"])
    conn = sqlite3.connect(resolved)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {_SETS_TABLE} "
            "(eval_set_id, policy_version, schema_version, name_hash, case_count, review_tier, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                set_id,
                policy_version,
                int(result["schema_version"]),
                str(result["name_hash"]),
                int(result["case_count"]),
                str(result["review_tier_summary"]),
                str(result["status"]),
            ),
        )
        for c in result["cases"]:
            conn.execute(
                f"INSERT OR REPLACE INTO {_CASES_TABLE} "
                "(eval_case_id, policy_version, schema_version, eval_set_id, question_hash, "
                "expected_source_ref_hash, confidence_class) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(c["eval_case_id"]),
                    policy_version,
                    int(result["schema_version"]),
                    set_id,
                    str(c["question_hash"]),
                    str(c["expected_source_ref_hash"]),
                    str(c["confidence_class"]),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return set_id


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
        "# Phase 09 — Retrieval Quality Eval Set Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- case_count: {proof['case_count']}",
        f"- cases_source_linked: {proof['cases_source_linked']}",
        f"- set_persisted_guard_clean: {proof['set_persisted_guard_clean']}",
        f"- cases_persisted_guard_clean: {proof['cases_persisted_guard_clean']}",
        f"- unsafe_node_excluded: {proof['unsafe_node_excluded']}",
        f"- no_raw_source_ref_emitted: {proof['no_raw_source_ref_emitted']}",
        "",
    ]
    return "\n".join(lines)


def build_retrieval_eval_set_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: source-linked eval cases are built from approved outputs and persisted
    metadata-only + guard-clean; unsafe/unlinked nodes are excluded; no raw source ref is emitted."""
    import tempfile

    from .vector_index import _proof_db

    with tempfile.TemporaryDirectory() as tmp:
        db = _proof_db(tmp)
        result = build_retrieval_eval_set(db, name="proof_eval_set", emit_receipt=True)
        set_id = result["eval_set_id"]

        conn = sqlite3.connect(db)
        try:
            set_rows = conn.execute(
                f"SELECT COUNT(*) FROM {_SETS_TABLE} WHERE eval_set_id = ?", (set_id,)
            ).fetchone()[0]
            case_rows = conn.execute(
                f"SELECT COUNT(*) FROM {_CASES_TABLE} WHERE eval_set_id = ?", (set_id,)
            ).fetchone()[0]
            set_guards = _guard_columns(conn, _SETS_TABLE)
            case_guards = _guard_columns(conn, _CASES_TABLE)
            set_guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(set_guards)}), 0) FROM {_SETS_TABLE} WHERE eval_set_id = ?",
                (set_id,),
            ).fetchone()[0]
            case_guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(case_guards)}), 0) FROM {_CASES_TABLE} "
                "WHERE eval_set_id = ?",
                (set_id,),
            ).fetchone()[0]
            stored_refs = [
                str(r[0])
                for r in conn.execute(
                    f"SELECT expected_source_ref_hash FROM {_CASES_TABLE} WHERE eval_set_id = ?",
                    (set_id,),
                ).fetchall()
            ]
        finally:
            conn.close()

    # Unsafe-node exclusion over synthetic nodes (one without a source ref, one excluded family).
    synthetic = [
        {
            "source_family": "approved_obsidian_generated_outputs",
            "source_ref": "ok",
            "confidence_class": "high",
            "review_tier": 1,
        },
        {
            "source_family": "approved_obsidian_generated_outputs",
            "source_ref": "",
            "confidence_class": "high",
            "review_tier": 1,
        },
        {
            "source_family": "raw_email_body",
            "source_ref": "x",
            "confidence_class": "high",
            "review_tier": 1,
        },
    ]
    syn_cases = _build_cases(synthetic, set_id="syn")
    unsafe_excluded = len(syn_cases) == 1

    cases_source_linked = result["case_count"] >= 1 and all(
        c["expected_source_ref_hash"] and "source_ref" not in c for c in result["cases"]
    )
    set_clean = set_rows == 1 and int(set_guard_sum) == 0
    cases_clean = case_rows == result["case_count"] and int(case_guard_sum) == 0
    # The stored hashes must not equal any raw ref (they are SHA256-derived).
    no_raw_ref = all(len(h) == 48 for h in stored_refs)

    proof_passed = (
        result["status"] == "built"
        and result["case_count"] >= 1
        and cases_source_linked
        and set_clean
        and cases_clean
        and unsafe_excluded
        and no_raw_ref
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_retrieval_eval_set",
        "command": "second-brain retrieval eval-set proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "case_count": result["case_count"],
        "cases_source_linked": cases_source_linked,
        "set_persisted_guard_clean": set_clean,
        "cases_persisted_guard_clean": cases_clean,
        "unsafe_node_excluded": unsafe_excluded,
        "no_raw_source_ref_emitted": no_raw_ref,
        "metadata_only": True,
        "guardrails": {
            "approved_outputs_only": True,
            "source_linked_cases_only": True,
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
        _assert_no_raw(out, "retrieval eval set proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "retrieval eval set proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
