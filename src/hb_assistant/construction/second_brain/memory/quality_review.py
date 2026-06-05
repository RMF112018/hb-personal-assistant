"""Phase 09 Prompt 30 — memory quality review (advisory).

A read-only, advisory evaluation of **proposed** long-term memory candidates
(``memory_update_candidates`` status ``proposed``) for **duplicate / stale / conflicting** status against
the accepted memory corpus (``long_term_memory_items``). Flagged candidates are surfaced for human review
— the surface **never merges, deletes, or accepts** memory and makes **no determination**.

Detection (deterministic, metadata-only):
  - duplicate  — the candidate's statement (SHA256-hashed) matches an accepted memory item (or another
    proposed candidate).
  - stale      — it matches a *superseded* memory item (restates outdated memory).
  - conflicting — it carries the deterministic conflict reason code ``T3_CONFLICT_DETECTED`` (stamped by
    the memory curator's ``classify_memory_tier``).

Read-only by default (``emit_receipt=False`` persists nothing); on ``emit_receipt`` a guard-clean
metadata-only run row is written to the reserved V38 ``second_brain_memory_quality_review_runs`` table.
**No raw memory statement text** is persisted or emitted — only SHA256 statement hashes, counts, and
review vocabulary. Fail-closed on missing policy or stale schema.

Public entry points:
  evaluate_memory_candidates(candidates, accepted_items, superseded_items) -> dict
  build_memory_quality_review(db_path=None, *, project_key=None, emit_receipt=False) -> dict
  persist_memory_quality_review_run(db_path, result, *, policy_version) -> str
  build_memory_quality_review_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain memory quality-review build | proof --json
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
_PROOF_JSON = "memory-quality-review-proof.json"
_PROOF_MD = "memory-quality-review-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_memory_quality_review.seed.yaml"

_RUNS_TABLE = "second_brain_memory_quality_review_runs"
_CONFLICT_REASON = "T3_CONFLICT_DETECTED"


class MemoryQualityReviewError(RuntimeError):
    """Raised when the memory quality-review builder cannot resolve policy/schema (fail-closed)."""


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
    """Return the schema version if ready (>=38 with the review-runs table), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise MemoryQualityReviewError("schema not ready for memory quality review (no database)")
    try:

        def _has(table: str) -> bool:
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                is not None
            )

        if not _has("schema_migrations"):
            raise MemoryQualityReviewError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has(_RUNS_TABLE):
            raise MemoryQualityReviewError(
                f"schema not ready for memory quality review (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_memory_quality_review_contract() -> dict[str, Any]:
    """Load the memory-quality-review contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("memory_quality_review_contract")
    if not isinstance(contract, dict) or "flag_categories" not in contract:
        raise MemoryQualityReviewError(
            "phase 09 memory-quality-review contract not found or missing required fields"
        )
    return contract


def load_memory_quality_review_seed() -> dict[str, Any]:
    """Load the resolved memory-quality-review seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise MemoryQualityReviewError(f"memory-quality-review seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "candidate_status_reviewed" not in data:
        raise MemoryQualityReviewError(f"{candidate} must define the memory-quality-review policy")
    return data


def evaluate_memory_candidates(
    candidates: list[dict[str, Any]],
    accepted_items: list[dict[str, Any]],
    superseded_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate proposed candidates for duplicate / stale / conflicting (metadata-only).

    A candidate is duplicate if its statement-hash matches an accepted item (or another candidate), stale
    if it matches a superseded item, conflicting if its review_tier_reason_code is the conflict code. A
    candidate may carry multiple flags. Returns counts + per-category counts + hashed per-candidate flag
    records — never raw statement text. Flags for review; makes no determination.
    """
    accepted_hashes = {_hash(str(it.get("statement_redacted") or "")) for it in accepted_items}
    superseded_hashes = {_hash(str(it.get("statement_redacted") or "")) for it in superseded_items}

    seen_candidate_hashes: dict[str, int] = {}
    for c in candidates:
        h = _hash(str(c.get("statement_redacted") or ""))
        seen_candidate_hashes[h] = seen_candidate_hashes.get(h, 0) + 1

    flag_records: list[dict[str, Any]] = []
    per_category = {"duplicate": 0, "stale": 0, "conflicting": 0}
    flagged_tiers: list[int] = []

    for c in candidates:
        statement_hash = _hash(str(c.get("statement_redacted") or ""))
        flags: list[str] = []
        if statement_hash in accepted_hashes or seen_candidate_hashes.get(statement_hash, 0) > 1:
            flags.append("duplicate")
        if statement_hash in superseded_hashes:
            flags.append("stale")
        if str(c.get("review_tier_reason_code") or "") == _CONFLICT_REASON:
            flags.append("conflicting")
        if not flags:
            continue
        for f in flags:
            per_category[f] += 1
        tier = int(c.get("review_tier") or 3)
        flagged_tiers.append(tier)
        flag_records.append(
            {
                "candidate_id_hash": _hash(str(c.get("candidate_id") or ""))[:48],
                "statement_hash": statement_hash[:48],
                "flags": flags,
                "review_tier": tier,
                "confidence_class": str(c.get("confidence_class") or "unknown"),
            }
        )

    reviewed_count = len(candidates)
    flagged_count = len(flag_records)
    review_tier_summary = (
        f"max={max(flagged_tiers)};tiers={','.join(str(t) for t in sorted(set(flagged_tiers)))}"
        if flagged_tiers
        else "none"
    )
    if not candidates:
        status = "empty"
    elif flagged_count:
        status = "flagged"
    else:
        status = "clean"

    return {
        "reviewed_count": reviewed_count,
        "flagged_count": flagged_count,
        "per_category": per_category,
        "review_tier_summary": review_tier_summary,
        "status": status,
        "flag_records": flag_records,
    }


def _read_proposed_candidates(
    conn: sqlite3.Connection, project_key: str | None
) -> list[dict[str, Any]]:
    sql = (
        "SELECT candidate_id, statement_redacted, project_key, review_tier, review_tier_reason_code, "
        "confidence_class FROM memory_update_candidates WHERE status = 'proposed'"
    )
    params: tuple[Any, ...] = ()
    if project_key is not None:
        sql += " AND project_key = ?"
        params = (project_key,)
    return [
        {
            "candidate_id": r[0],
            "statement_redacted": r[1],
            "project_key": r[2],
            "review_tier": r[3],
            "review_tier_reason_code": r[4],
            "confidence_class": r[5],
        }
        for r in conn.execute(sql, params).fetchall()
    ]


def _read_items_by_status(
    conn: sqlite3.Connection, review_status: str, project_key: str | None
) -> list[dict[str, Any]]:
    sql = (
        "SELECT statement_redacted, project_key FROM long_term_memory_items WHERE review_status = ?"
    )
    params: tuple[Any, ...] = (review_status,)
    if project_key is not None:
        sql += " AND project_key = ?"
        params = (review_status, project_key)
    return [{"statement_redacted": r[0], "project_key": r[1]} for r in conn.execute(sql, params)]


def build_memory_quality_review(
    db_path: str | None = None,
    *,
    project_key: str | None = None,
    emit_receipt: bool = False,
) -> dict[str, Any]:
    """Evaluate proposed memory candidates for duplicate/stale/conflicting (read-only, advisory).

    Returns a JSON-safe, metadata-only summary (counts, per-category counts, hashed flag records — never
    raw statement text); persists nothing unless ``emit_receipt``. Flags for review; makes no
    determination, never merges/deletes/accepts memory.
    """
    contract = load_memory_quality_review_contract()
    seed = load_memory_quality_review_seed()
    schema_version = _schema_ready(db_path)

    conn = _open_ro(db_path)
    if conn is None:
        raise MemoryQualityReviewError("schema not ready for memory quality review (no database)")
    try:
        candidates = _read_proposed_candidates(conn, project_key)
        accepted = _read_items_by_status(conn, "accepted", project_key)
        superseded = _read_items_by_status(conn, "superseded", project_key)
    finally:
        conn.close()

    ev = evaluate_memory_candidates(candidates, accepted, superseded)
    run_id = f"mqr_{_hash(f'{project_key or ""}|{ev["reviewed_count"]}|{ev["flagged_count"]}|{ev["status"]}')[:32]}"

    result = {
        "command": "second-brain memory quality-review build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": ev["status"],
        "run_id": run_id,
        "schema_version": schema_version,
        "project_key": project_key,
        "reviewed_count": ev["reviewed_count"],
        "flagged_count": ev["flagged_count"],
        "per_category": ev["per_category"],
        "review_tier_summary": ev["review_tier_summary"],
        "flag_records": ev["flag_records"],
        "advisory_only": True,
        "makes_determination": False,
        "merges_or_deletes_or_accepts": False,
        "routes_flagged_to_review": True,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "receipt_emitted": emit_receipt,
        "read_only": not emit_receipt,
    }

    if emit_receipt:
        persist_memory_quality_review_run(db_path, result, policy_version=str(seed.get("version")))

    return result


def persist_memory_quality_review_run(
    db_path: str | None, result: dict[str, Any], *, policy_version: str
) -> str:
    """Persist a guard-clean metadata-only memory quality-review run row. Returns run_id."""
    _schema_ready(db_path)
    resolved = db_path or str(PathPolicy().get_db_path())
    run_id = str(result["run_id"])
    conn = sqlite3.connect(resolved)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {_RUNS_TABLE} "
            "(run_id, policy_version, schema_version, project_key, reviewed_count, flagged_count, "
            "review_tier, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                policy_version,
                int(result["schema_version"]),
                result.get("project_key"),
                int(result["reviewed_count"]),
                int(result["flagged_count"]),
                str(result["review_tier_summary"]),
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


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Memory Quality Review Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- status: {proof['status']}",
        f"- reviewed_count: {proof['reviewed_count']}",
        f"- flagged_count: {proof['flagged_count']} (must be 3)",
        f"- duplicate_detected: {proof['duplicate_detected']}",
        f"- stale_detected: {proof['stale_detected']}",
        f"- conflicting_detected: {proof['conflicting_detected']}",
        f"- makes_determination: {proof['makes_determination']} (must be false)",
        f"- run_row_guard_clean: {proof['run_row_guard_clean']}",
        f"- read_only_default_no_persist: {proof['read_only_default_no_persist']}",
        f"- no_raw_statement_emitted: {proof['no_raw_statement_emitted']}",
        "",
    ]
    return "\n".join(lines)


def _seed_proof_db(db: str) -> None:
    """Seed a temp DB with accepted/superseded items + proposed candidates (duplicate/stale/conflicting/
    clean) using the real memory store + curator."""
    from .curator import propose_memory_candidate
    from .models import MemoryItem
    from .store import write_memory_item

    refs = [{"source_family": "accepted_long_term_memory", "source_ref": "m-acc"}]
    write_memory_item(
        MemoryItem(
            memory_id="acc-1",
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
            memory_id="sup-1",
            memory_type="fact",
            statement_redacted="Project Alpha used the old budget code.",
            confidence_class="high",
            review_status="superseded",
            source_refs=refs,
        ),
        db_path=db,
    )
    # duplicate of the accepted item
    propose_memory_candidate(
        statement_redacted="Project Alpha kickoff is in March.",
        proposed_memory_type="fact",
        origin_id="o-dup",
        source_refs=refs,
        confidence_class="high",
        db_path=db,
        emit=True,
    )
    # restates a superseded item -> stale
    propose_memory_candidate(
        statement_redacted="Project Alpha used the old budget code.",
        proposed_memory_type="fact",
        origin_id="o-stale",
        source_refs=refs,
        confidence_class="high",
        db_path=db,
        emit=True,
    )
    # conflicting (source-linked, conflict=True -> T3_CONFLICT_DETECTED)
    propose_memory_candidate(
        statement_redacted="Project Alpha kickoff is in May.",
        proposed_memory_type="fact",
        origin_id="o-conflict",
        source_refs=refs,
        confidence_class="high",
        conflict=True,
        db_path=db,
        emit=True,
    )
    # clean (novel, source-linked)
    propose_memory_candidate(
        statement_redacted="Project Beta has a new site manager.",
        proposed_memory_type="fact",
        origin_id="o-clean",
        source_refs=refs,
        confidence_class="high",
        db_path=db,
        emit=True,
    )


def build_memory_quality_review_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: duplicate/stale/conflicting candidates are detected + flagged for review, the
    run row is guard-clean + metadata-only, no determination is made, and no raw statement is emitted."""
    import tempfile

    from hb_assistant.store.migrator import SQLiteMigrator

    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "mqr.sqlite")
        SQLiteMigrator(db_path=db).apply()
        _seed_proof_db(db)

        # read-only default persists nothing
        before = _run_rows(db)
        result = build_memory_quality_review(db)
        read_only_no_persist = _run_rows(db) == before

        # emit a receipt + verify guard-clean metadata-only persistence
        result2 = build_memory_quality_review(db, emit_receipt=True)
        run_id = result2["run_id"]
        conn = sqlite3.connect(db)
        try:
            row_present = (
                conn.execute(
                    f"SELECT COUNT(*) FROM {_RUNS_TABLE} WHERE run_id = ?", (run_id,)
                ).fetchone()[0]
                == 1
            )
            guard_cols = _guard_columns(conn, _RUNS_TABLE)
            guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_RUNS_TABLE} WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        finally:
            conn.close()

    per = result["per_category"]
    duplicate_detected = per["duplicate"] >= 1
    stale_detected = per["stale"] >= 1
    conflicting_detected = per["conflicting"] >= 1
    run_row_guard_clean = row_present and int(guard_sum or 0) == 0
    serialized = json.dumps(result, default=str)
    no_raw_statement = (
        "statement_redacted" not in serialized
        and "Project Alpha" not in serialized
        and "Project Beta" not in serialized
    )

    proof_passed = (
        result["status"] == "flagged"
        and result["flagged_count"] == 3
        and duplicate_detected
        and stale_detected
        and conflicting_detected
        and result["makes_determination"] is False
        and run_row_guard_clean
        and read_only_no_persist
        and no_raw_statement
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_memory_quality_review",
        "command": "second-brain memory quality-review proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": result["status"],
        "reviewed_count": result["reviewed_count"],
        "flagged_count": result["flagged_count"],
        "per_category": per,
        "duplicate_detected": duplicate_detected,
        "stale_detected": stale_detected,
        "conflicting_detected": conflicting_detected,
        "makes_determination": result["makes_determination"],
        "run_row_guard_clean": run_row_guard_clean,
        "read_only_default_no_persist": read_only_no_persist,
        "no_raw_statement_emitted": no_raw_statement,
        "metadata_only": True,
        "guardrails": {
            "advisory_only": True,
            "no_determination": True,
            "no_merge_or_delete_or_accept": True,
            "route_flagged_to_review": True,
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
        _assert_no_raw(out, "memory quality review proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "memory quality review proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof


def _run_rows(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {_RUNS_TABLE}").fetchone()[0])
    finally:
        conn.close()
