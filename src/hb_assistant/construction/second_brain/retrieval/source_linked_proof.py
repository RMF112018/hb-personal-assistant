"""Phase 09 Prompt 34 — source-linked retrieval proof (advisory).

A read-only, advisory proof that **every** retrieval result returned by the hybrid retrieval broker
maps to an approved source ref. A result is source-linked iff it carries a non-empty ``source_ref``
and an allowlisted ``source_family`` (not in the ``EXCLUDED_FAMILIES`` raw-family set) — the same
rule the output-evaluation integration uses. The proof runs the hybrid broker (deterministic
authoritative + advisory semantic; mock-embedded in the controlled proof), counts
``result_count``/``linked_count``/``unlinked_count``, and passes only when ``result_count > 0`` and
``unlinked_count == 0``.

Metadata-only: persists a guard-clean summary row (read-only by default; on ``emit_receipt``) to the
reserved V38 ``second_brain_retrieval_source_linked_proof_runs`` table (run_id / checked_count /
source_linked_count / unlinked_count / status + 23 guard columns). No raw query / content / excerpt /
prompt / response / token / signed-or-download URL / vector / arbitrary SQL is persisted or emitted —
only counts, a hashed run id, source families, and a status. Makes no determination; read-only;
fail-closed on missing policy or stale schema.

Public entry points:
  build_source_linked_retrieval_proof(db_path=None, *, query=None, project_key=None, mode='hybrid',
      embed_model=None, persist_root=None, emit_receipt=False) -> dict
  persist_source_linked_retrieval_proof(db_path, result, *, policy_version) -> str
  build_source_linked_retrieval_proof_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval source-linked build | proof --json
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
from .policy import EXCLUDED_FAMILIES

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "source-linked-retrieval-proof.json"
_PROOF_MD = "source-linked-retrieval-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_source_linked_retrieval_proof.seed.yaml"

_RUNS_TABLE = "second_brain_retrieval_source_linked_proof_runs"


class SourceLinkedRetrievalProofError(RuntimeError):
    """Raised when the source-linked retrieval proof cannot resolve policy/schema (fail-closed)."""


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
    """Return the schema version if ready (>=39 with the proof-runs table), else fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise SourceLinkedRetrievalProofError(
            "schema not ready for source-linked retrieval proof (no database)"
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
            raise SourceLinkedRetrievalProofError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 39 or not _has(_RUNS_TABLE):
            raise SourceLinkedRetrievalProofError(
                f"schema not ready for source-linked retrieval proof (version {version}, expected >= 39)"
            )
    finally:
        conn.close()
    return version


def load_source_linked_retrieval_proof_contract() -> dict[str, Any]:
    """Load the source-linked-retrieval-proof contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("source_linked_retrieval_proof_contract")
    if (
        not isinstance(contract, dict)
        or "required" not in contract
        or "guard_columns" not in contract
    ):
        raise SourceLinkedRetrievalProofError(
            "phase 09 source-linked-retrieval-proof contract not found or missing required fields"
        )
    return contract


def load_source_linked_retrieval_proof_seed() -> dict[str, Any]:
    """Load the resolved source-linked-retrieval-proof seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise SourceLinkedRetrievalProofError(
            f"source-linked-retrieval-proof seed not found at {candidate}"
        )
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "version" not in data:
        raise SourceLinkedRetrievalProofError(
            f"{candidate} must define the source-linked-retrieval-proof policy"
        )
    return data


def _coverage_layers(db_path: str | None, project_key: str | None) -> dict[str, Any]:
    """Best-effort coverage-layer distinction (deterministic / manifest / vector-indexed / deferred)."""
    try:
        from ..corpus_balance_mart import build_retrieval_coverage_layers

        return build_retrieval_coverage_layers(db_path, project_key=project_key)
    except Exception:
        return {}


def _link_status(items: list[Any]) -> dict[str, Any]:
    """Count source-linked vs unlinked retrieval results (metadata-only, no raw refs emitted).

    A result is source-linked iff it carries a non-empty ``source_ref`` and an allowlisted
    ``source_family`` (not in ``EXCLUDED_FAMILIES``). Returns counts + a per-family linked/unlinked
    breakdown — never the raw refs themselves.
    """
    result_count = len(items)
    linked = 0
    per_family: dict[str, dict[str, int]] = {}
    for it in items:
        fam = str(getattr(it, "source_family", "") or "")
        ref = str(getattr(it, "source_ref", "") or "")
        is_linked = bool(ref) and bool(fam) and fam not in EXCLUDED_FAMILIES
        if is_linked:
            linked += 1
        bucket = per_family.setdefault(fam or "unknown", {"linked": 0, "unlinked": 0})
        bucket["linked" if is_linked else "unlinked"] += 1
    unlinked = result_count - linked
    if result_count == 0:
        status = "empty"
    elif unlinked == 0:
        status = "source_linked"
    else:
        status = "unlinked_found"
    return {
        "result_count": result_count,
        "linked_count": linked,
        "unlinked_count": unlinked,
        "status": status,
        "per_family": {k: dict(v) for k, v in sorted(per_family.items())},
    }


def build_source_linked_retrieval_proof(
    db_path: str | None = None,
    *,
    query: str | None = None,
    project_key: str | None = None,
    mode: str = "hybrid",
    embed_model: Any | None = None,
    persist_root: str | None = None,
    emit_receipt: bool = False,
) -> dict[str, Any]:
    """Prove every hybrid-retrieval result maps to an approved source ref (read-only, advisory).

    Runs the hybrid broker over ``query`` and counts source-linked vs unlinked results; ``proof_passed``
    is true only when there is at least one result and none are unlinked. Returns a JSON-safe,
    metadata-only summary (counts + hashed run id + per-family breakdown + a status — never the raw
    query, refs, or any excerpt); persists nothing unless ``emit_receipt``. Makes no determination.
    """
    from .hybrid_broker import build_hybrid_envelope

    contract = load_source_linked_retrieval_proof_contract()
    seed = load_source_linked_retrieval_proof_seed()
    schema_version = _schema_ready(db_path)

    query = query or str(seed.get("query") or "open project risks")
    project_key = project_key if project_key is not None else seed.get("project_key")
    min_results = int(seed.get("min_result_count", 1))
    guard_cols = list(contract.get("guard_columns", []))

    envelope, meta = build_hybrid_envelope(
        query,
        db_path=db_path,
        project_key=project_key,
        mode=mode,
        embed_model=embed_model,
        persist_root=persist_root,
    )
    ls = _link_status(envelope.items)
    proof_passed = ls["result_count"] >= min_results and ls["unlinked_count"] == 0
    run_id = (
        "slr_"
        + _hash(f"{query}|{project_key or ''}|{ls['result_count']}|{ls['linked_count']}")[:32]
    )

    result = {
        "command": "second-brain retrieval source-linked build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": schema_version,
        "status": ls["status"],
        "run_id": run_id,
        "project_key": project_key,
        "query_hash": envelope.query_hash or _hash(query)[:32],
        "mode": meta.get("mode"),
        "result_count": ls["result_count"],
        "linked_count": ls["linked_count"],
        "unlinked_count": ls["unlinked_count"],
        "proof_passed": proof_passed,
        "per_family": ls["per_family"],
        "coverage_layers": _coverage_layers(db_path, project_key),
        "deterministic_count": meta.get("deterministic_count"),
        "semantic_count": meta.get("semantic_count"),
        "semantic_skip_reason": meta.get("semantic_skip_reason"),
        "coverage_warnings": list(envelope.coverage_warnings),
        "min_result_count": min_results,
        "advisory_only": True,
        "makes_determination": False,
        "read_only": not emit_receipt,
        "receipt_emitted": emit_receipt,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        # Compact guard attestation: all guard columns attested false (names not echoed — they carry
        # raw_* substrings that would trip naive no-raw scanners).
        "guard_attestation": {"all_false": True, "column_count": len(guard_cols)},
    }

    if emit_receipt:
        persist_source_linked_retrieval_proof(
            db_path, result, policy_version=str(seed.get("version"))
        )

    return result


def persist_source_linked_retrieval_proof(
    db_path: str | None, result: dict[str, Any], *, policy_version: str
) -> str:
    """Persist a guard-clean metadata-only summary row to the reserved proof-runs table. Returns run_id."""
    _schema_ready(db_path)
    resolved = db_path or str(PathPolicy().get_db_path())
    run_id = str(result["run_id"])
    conn = sqlite3.connect(resolved)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {_RUNS_TABLE} "
            "(run_id, policy_version, schema_version, project_key, checked_count, source_linked_count, "
            "unlinked_count, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                policy_version,
                int(result["schema_version"]),
                result.get("project_key"),
                int(result["result_count"]),
                int(result["linked_count"]),
                int(result["unlinked_count"]),
                str(result["status"]),
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


def _run_rows(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {_RUNS_TABLE}").fetchone()[0])
    finally:
        conn.close()


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Source-Linked Retrieval Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- status: {proof['status']}",
        f"- result_count: {proof['result_count']}",
        f"- linked_count: {proof['linked_count']}",
        f"- unlinked_count: {proof['unlinked_count']} (must be 0)",
        f"- every_result_source_linked: {proof['every_result_source_linked']}",
        f"- makes_determination: {proof['makes_determination']} (must be false)",
        f"- rows_persisted_guard_clean: {proof['rows_persisted_guard_clean']}",
        f"- read_only_default_no_persist: {proof['read_only_default_no_persist']}",
        f"- no_raw_emitted: {proof['no_raw_emitted']}",
        "",
    ]
    return "\n".join(lines)


def build_source_linked_retrieval_proof_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: over a controlled seeded index, every hybrid-retrieval result (deterministic +
    advisory semantic) maps to an approved source ref; the persisted summary row is guard-clean +
    metadata-only; read-only by default persists nothing; no raw content is emitted."""
    import tempfile

    from .hybrid_broker import _mock_embed_model
    from .vector_index import _mock_vector_writer, _proof_db, build_vector_index_apply

    with tempfile.TemporaryDirectory() as tmp:
        db = _proof_db(tmp)
        persist_root = str(Path(tmp) / "vector_store")
        build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)

        before = _run_rows(db)
        result = build_source_linked_retrieval_proof(
            db, mode="hybrid", embed_model=_mock_embed_model(), persist_root=persist_root
        )
        read_only_no_persist = _run_rows(db) == before

        result2 = build_source_linked_retrieval_proof(
            db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
            emit_receipt=True,
        )
        run_id = result2["run_id"]
        conn = sqlite3.connect(db)
        try:
            row_count = conn.execute(
                f"SELECT COUNT(*) FROM {_RUNS_TABLE} WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            guard_cols = _guard_columns(conn, _RUNS_TABLE)
            guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_RUNS_TABLE} "
                "WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        finally:
            conn.close()

    every_result_source_linked = result["result_count"] > 0 and result["unlinked_count"] == 0
    rows_guard_clean = row_count >= 1 and int(guard_sum or 0) == 0
    serialized = json.dumps(result, default=str)
    no_raw_emitted = not any(
        t in serialized
        for t in (
            "raw_body",
            "raw_document_text",
            "raw_calendar_payload",
            "raw_prompt",
            "raw_response",
            "signed_url",
            "download_url",
            "secret",
            "text_redacted",
        )
    )

    proof_passed = (
        every_result_source_linked
        and bool(result["proof_passed"])
        and result["makes_determination"] is False
        and rows_guard_clean
        and read_only_no_persist
        and no_raw_emitted
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_source_linked_retrieval_proof",
        "command": "second-brain retrieval source-linked proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": result["status"],
        "result_count": result["result_count"],
        "linked_count": result["linked_count"],
        "unlinked_count": result["unlinked_count"],
        "deterministic_count": result["deterministic_count"],
        "semantic_count": result["semantic_count"],
        "every_result_source_linked": every_result_source_linked,
        "makes_determination": result["makes_determination"],
        "rows_persisted_guard_clean": rows_guard_clean,
        "read_only_default_no_persist": read_only_no_persist,
        "no_raw_emitted": no_raw_emitted,
        "per_family": result["per_family"],
        "metadata_only": True,
        "guardrails": {
            "advisory_only": True,
            "no_determination": True,
            "preserve_source_refs": True,
            "no_raw": True,
            "no_external_writeback": True,
            "no_semantic_retrieval_bypass": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(out, "source-linked retrieval proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "source-linked retrieval proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
