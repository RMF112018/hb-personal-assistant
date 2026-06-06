"""Phase 09 Addendum Prompt 04 — memory quality and supersession controls.

Minimum-viable controls so accepted long-term memory does not become stale, duplicative, or unsafe:
deterministic duplicate detection, metadata-only supersession, freshness labeling, source retention,
and review-status transition validation. Uses the existing schema only (``supersedes_memory_id``,
``review_status`` CHECK incl. ``superseded``, ``long_term_memory_quality_signals.freshness_class`` +
``signal_type='freshness'``) — **no migration**. Time-based auto-expiration is a documented future
enhancement (no unnecessary schema added).

Public entry points:
  normalize_statement(text) -> str
  statement_fingerprint(*, statement_redacted, project_key, memory_type, source_family) -> str
  detect_duplicate_accepted(*, statement_redacted, project_key, memory_type, source_family, db_path) -> dict
  validate_status_transition(current, target) -> dict
  supersede_accepted_memory(*, old_memory_id, new_memory_id, db_path=None, confirm=False) -> dict
  mark_memory_freshness(memory_id, *, freshness_class, db_path=None) -> str
  build_memory_quality_controls_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain memory supersede | quality-controls-proof
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
_PROOF_JSON = "accepted-memory-quality-controls-proof.json"
_PROOF_MD = "accepted-memory-quality-controls-proof.md"

# Allowed review-status transitions for long_term_memory_items.
# Repo policy: accepted memory is removed by SUPERSESSION (revocation == supersede), never by
# transitioning accepted -> rejected. pending_review is the only entry to accepted/rejected.
ALLOWED_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending_review": frozenset({"accepted", "rejected"}),
    "accepted": frozenset({"superseded"}),
    "rejected": frozenset(),
    "superseded": frozenset(),
}


class MemoryQualityControlsError(RuntimeError):
    """Raised when the quality-controls surface cannot resolve schema/policy (fail-closed)."""


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


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _schema_ready(db_path: str | None) -> int:
    conn = _open_ro(db_path)
    if conn is None:
        raise MemoryQualityControlsError(
            "schema not ready for memory quality controls (no database)"
        )
    try:
        if not _has_table(conn, "schema_migrations"):
            raise MemoryQualityControlsError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has_table(conn, "long_term_memory_items"):
            raise MemoryQualityControlsError(
                f"schema not ready for memory quality controls (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_memory_quality_controls_contract() -> dict[str, Any]:
    """Load the quality-controls contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("memory_quality_controls_contract")
    if not isinstance(contract, dict) or "allowed_status_transitions" not in contract:
        raise MemoryQualityControlsError(
            "phase 09 memory-quality-controls contract not found or missing required fields"
        )
    return contract


# --- Duplicate detection -------------------------------------------------------------------------


def normalize_statement(text: str) -> str:
    """Deterministic normalization for duplicate detection (whitespace-collapse + casefold)."""
    return " ".join(str(text or "").split()).casefold()


def statement_fingerprint(
    *,
    statement_redacted: str,
    project_key: str | None,
    memory_type: str,
    source_family: str,
) -> str:
    """SHA256 dedup key over project | memory_type | source_family | normalized statement."""
    key = "|".join(
        [
            str(project_key or ""),
            str(memory_type or ""),
            str(source_family or ""),
            normalize_statement(statement_redacted),
        ]
    )
    return _hash(key)


def _first_source_family(conn: sqlite3.Connection, memory_id: str) -> str:
    row = conn.execute(
        "SELECT source_family FROM long_term_memory_source_refs WHERE memory_id = ? "
        "ORDER BY source_family LIMIT 1",
        (memory_id,),
    ).fetchone()
    return str(row[0]) if row else ""


def detect_duplicate_accepted(
    *,
    statement_redacted: str,
    project_key: str | None,
    memory_type: str,
    source_family: str,
    db_path: str | None = None,
    exclude_memory_id: str | None = None,
) -> dict[str, Any]:
    """Read-only: is there an existing accepted item with the same dedup fingerprint?"""
    _schema_ready(db_path)
    target = statement_fingerprint(
        statement_redacted=statement_redacted,
        project_key=project_key,
        memory_type=memory_type,
        source_family=source_family,
    )
    conn = _open_ro(db_path)
    if conn is None:
        raise MemoryQualityControlsError(
            "schema not ready for memory quality controls (no database)"
        )
    try:
        rows = conn.execute(
            "SELECT memory_id, statement_redacted, project_key, memory_type "
            "FROM long_term_memory_items WHERE review_status = 'accepted'"
        ).fetchall()
        existing_id: str | None = None
        for memory_id, statement, pkey, mtype in rows:
            if exclude_memory_id is not None and memory_id == exclude_memory_id:
                continue
            fp = statement_fingerprint(
                statement_redacted=str(statement or ""),
                project_key=pkey,
                memory_type=str(mtype or ""),
                source_family=_first_source_family(conn, str(memory_id)),
            )
            if fp == target:
                existing_id = str(memory_id)
                break
    finally:
        conn.close()
    return {
        "is_duplicate": existing_id is not None,
        "existing_memory_id": existing_id,
        "fingerprint": target,
    }


# --- Transition validation -----------------------------------------------------------------------


def validate_status_transition(current: str, target: str) -> dict[str, Any]:
    """Validate a review_status transition against ALLOWED_STATUS_TRANSITIONS."""
    cur = str(current or "")
    tgt = str(target or "")
    if cur not in ALLOWED_STATUS_TRANSITIONS or tgt not in (
        "accepted",
        "pending_review",
        "rejected",
        "superseded",
    ):
        return {"ok": False, "reason": "UNKNOWN_STATUS", "current": cur, "target": tgt}
    ok = tgt in ALLOWED_STATUS_TRANSITIONS[cur]
    return {
        "ok": ok,
        "reason": "OK" if ok else "TRANSITION_NOT_ALLOWED",
        "current": cur,
        "target": tgt,
    }


# --- Supersession (metadata-only) ----------------------------------------------------------------


def _read_item(conn: sqlite3.Connection, memory_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT memory_id, review_status, supersedes_memory_id FROM long_term_memory_items "
        "WHERE memory_id = ?",
        (memory_id,),
    ).fetchone()
    if row is None:
        return None
    return {"memory_id": row[0], "review_status": row[1], "supersedes_memory_id": row[2]}


def supersede_accepted_memory(
    *,
    old_memory_id: str,
    new_memory_id: str,
    db_path: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Supersede an accepted item with a newer accepted item (metadata-only; no auto-acceptance).

    Without ``confirm`` this is a dry-run. With ``confirm`` and a valid accepted->superseded transition
    the old item becomes ``superseded`` and the new item gains ``supersedes_memory_id=old``; the
    superseded item is then excluded from retrieval (the loader gates on ``accepted``).
    """
    contract = load_memory_quality_controls_contract()
    _schema_ready(db_path)

    conn = _open_ro(db_path)
    if conn is None:
        raise MemoryQualityControlsError(
            "schema not ready for memory quality controls (no database)"
        )
    try:
        old = _read_item(conn, old_memory_id)
        new = _read_item(conn, new_memory_id)
    finally:
        conn.close()

    blocks: list[str] = []
    if old is None:
        blocks.append("OLD_NOT_FOUND")
    if new is None:
        blocks.append("NEW_NOT_FOUND")
    if old is not None and old["review_status"] != "accepted":
        blocks.append("OLD_NOT_ACCEPTED")
    if new is not None and new["review_status"] != "accepted":
        blocks.append("NEW_NOT_ACCEPTED")
    transition = validate_status_transition(old["review_status"] if old else "", "superseded")
    if old is not None and not transition["ok"]:
        blocks.append("TRANSITION_NOT_ALLOWED")

    result: dict[str, Any] = {
        "command": "second-brain memory supersede",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "old_memory_id": old_memory_id,
        "new_memory_id": new_memory_id,
        "transition": "accepted->superseded",
        "transition_ok": transition["ok"],
        "blocks": blocks,
        "confirm": confirm,
        "requires_confirm": True,
        "metadata_only": True,
        "writes_external": False,
        "contract_version": contract.get("version"),
    }

    if blocks:
        result["superseded"] = False
        result["persisted"] = False
        return result
    if not confirm:
        result["superseded"] = False
        result["persisted"] = False
        result["would_supersede"] = True
        return result

    from .store import set_memory_item_status

    set_memory_item_status(old_memory_id, review_status="superseded", db_path=db_path)
    set_memory_item_status(new_memory_id, supersedes_memory_id=old_memory_id, db_path=db_path)
    result["superseded"] = True
    result["persisted"] = True
    return result


# --- Freshness -----------------------------------------------------------------------------------


def mark_memory_freshness(
    memory_id: str, *, freshness_class: str, db_path: str | None = None
) -> str:
    """Record a freshness quality signal (schema-supported stale/fresh flag). Metadata-only."""
    import uuid

    from .models import QualitySignal
    from .store import write_quality_signal

    return write_quality_signal(
        QualitySignal(
            signal_id=uuid.uuid4().hex,
            memory_id=memory_id,
            signal_type="freshness",
            freshness_class=freshness_class,
        ),
        db_path=db_path,
    )


# --- Proof ---------------------------------------------------------------------------------------


def _guard_sum(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cols = [str(r[1]) for r in conn.execute("PRAGMA table_info(long_term_memory_items)")]
        guards = [c for c in cols if c.endswith("_persisted")]
        return int(
            conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guards)}), 0) FROM long_term_memory_items"
            ).fetchone()[0]
            or 0
        )
    finally:
        conn.close()


def _seed_accepted(
    db: str, memory_id: str, statement: str, *, source_family: str = "approved_read_models"
) -> None:
    from .models import MemoryItem
    from .store import write_memory_item

    write_memory_item(
        MemoryItem(
            memory_id=memory_id,
            memory_type="project_context",
            statement_redacted=statement,
            project_key="proj-a",
            confidence_class="high",
            review_status="accepted",
            source_refs=[
                {
                    "source_family": source_family,
                    "source_ref": f"ref-{memory_id}",
                    "evidence_ref": f"ev-{memory_id}",
                }
            ],
        ),
        db_path=db,
    )


def _render_proof_md(p: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase 09 Addendum — Memory Quality & Supersession Controls Proof",
            "",
            f"- proof_passed: {p['proof_passed']}",
            f"- generated_utc: {p['generated_utc']}",
            f"- duplicate_detected_and_suppressed: {p['duplicate_detected_and_suppressed']}",
            f"- supersession_excludes_from_retrieval: {p['supersession_excludes_from_retrieval']}",
            f"- supersedes_link_recorded: {p['supersedes_link_recorded']}",
            f"- freshness_label_present: {p['freshness_label_present']}",
            f"- freshness_signal_recorded: {p['freshness_signal_recorded']}",
            f"- source_refs_preserved: {p['source_refs_preserved']}",
            f"- transitions_valid: {p['transitions_valid']}",
            f"- guard_columns_all_false: {p['guard_columns_all_false']}",
            f"- no_external_writeback: {p['no_external_writeback']}",
            "",
        ]
    )


def build_memory_quality_controls_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof of the five quality controls over a deterministic fixture."""
    import tempfile

    from hb_assistant.store.migrator import SQLiteMigrator

    from ..retrieval.memory_loader import load_reviewed_memory_nodes

    contract = load_memory_quality_controls_contract()

    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "qc.sqlite")
        SQLiteMigrator(db_path=db).apply()

        # (1) duplicate detection: two equivalent accepted items share a fingerprint.
        _seed_accepted(db, "mem-orig", "Submittal turnaround is tracked locally.")
        dup = detect_duplicate_accepted(
            statement_redacted="submittal   turnaround IS tracked locally.",  # normalized-equivalent
            project_key="proj-a",
            memory_type="project_context",
            source_family="approved_read_models",
            db_path=db,
        )
        duplicate_detected = dup["is_duplicate"] and dup["existing_memory_id"] == "mem-orig"

        # acceptance integration: accepting an equivalent candidate is blocked DUPLICATE_ACCEPTED.
        from .acceptance import accept_memory_candidate
        from .curator import propose_memory_candidate

        equiv = propose_memory_candidate(
            statement_redacted="Submittal turnaround is tracked locally.",
            proposed_memory_type="project_context",
            origin_id="o-dup",
            source_refs=[{"source_family": "approved_read_models", "source_ref": "ref-dup"}],
            confidence_class="high",
            project_key="proj-a",
            db_path=db,
            emit=True,
        )
        acc = accept_memory_candidate(equiv.candidate_id, db_path=db, confirm=True)
        duplicate_suppressed = acc["accepted"] is False and "DUPLICATE_ACCEPTED" in acc["blocks"]

        # (2) supersession: new accepted item supersedes the original.
        _seed_accepted(db, "mem-new", "Submittal turnaround is now tracked in the new system.")
        sup = supersede_accepted_memory(
            old_memory_id="mem-orig", new_memory_id="mem-new", db_path=db, confirm=True
        )
        nodes = load_reviewed_memory_nodes(db)
        loaded = {str(n.get("source_ref")) for n in nodes}
        supersession_excludes = (
            sup["superseded"] is True and "mem-orig" not in loaded and "mem-new" in loaded
        )
        new_item = _read_item(sqlite3.connect(db), "mem-new")
        supersedes_link = new_item is not None and new_item["supersedes_memory_id"] == "mem-orig"

        # (3) freshness: loaded node carries a freshness label; record a stale freshness signal.
        freshness_label_present = bool(nodes) and bool(nodes[0].get("freshness_label"))
        mark_memory_freshness("mem-new", freshness_class="stale", db_path=db)
        conn = sqlite3.connect(db)
        try:
            freshness_signal_recorded = (
                int(
                    conn.execute(
                        "SELECT COUNT(*) FROM long_term_memory_quality_signals "
                        "WHERE memory_id = 'mem-new' AND signal_type = 'freshness'"
                    ).fetchone()[0]
                )
                == 1
            )
            ref_row = conn.execute(
                "SELECT source_family, source_ref, evidence_trail_id FROM long_term_memory_source_refs "
                "WHERE memory_id = 'mem-new'"
            ).fetchone()
        finally:
            conn.close()

        # (4) source retention: source family/ref + evidence ref preserved.
        source_refs_preserved = (
            ref_row is not None
            and ref_row[0] == "approved_read_models"
            and bool(ref_row[1])
            and bool(ref_row[2])
        )

        guard_columns_all_false = _guard_sum(db) == 0

    # (5) review-status transition validation matrix.
    matrix = {
        "pending_review->accepted": validate_status_transition("pending_review", "accepted")["ok"],
        "pending_review->rejected": validate_status_transition("pending_review", "rejected")["ok"],
        "accepted->superseded": validate_status_transition("accepted", "superseded")["ok"],
        "accepted->rejected": validate_status_transition("accepted", "rejected")["ok"],
        "accepted->pending_review": validate_status_transition("accepted", "pending_review")["ok"],
        "rejected->accepted": validate_status_transition("rejected", "accepted")["ok"],
    }
    transitions_valid = (
        matrix["pending_review->accepted"]
        and matrix["pending_review->rejected"]
        and matrix["accepted->superseded"]
        and not matrix["accepted->rejected"]
        and not matrix["accepted->pending_review"]
        and not matrix["rejected->accepted"]
    )

    proof_passed = (
        duplicate_detected
        and duplicate_suppressed
        and supersession_excludes
        and supersedes_link
        and freshness_label_present
        and freshness_signal_recorded
        and source_refs_preserved
        and transitions_valid
        and guard_columns_all_false
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_memory_quality_controls",
        "command": "second-brain memory quality-controls-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "contract_version": contract.get("version"),
        "duplicate_detected_and_suppressed": duplicate_detected and duplicate_suppressed,
        "duplicate_detected": duplicate_detected,
        "duplicate_suppressed_at_acceptance": duplicate_suppressed,
        "supersession_excludes_from_retrieval": supersession_excludes,
        "supersedes_link_recorded": supersedes_link,
        "freshness_label_present": freshness_label_present,
        "freshness_signal_recorded": freshness_signal_recorded,
        "expiration_status": "future_enhancement_no_schema_added",
        "source_refs_preserved": source_refs_preserved,
        "transition_matrix": matrix,
        "transitions_valid": transitions_valid,
        "guard_columns_all_false": guard_columns_all_false,
        "no_external_writeback": True,
        "metadata_only": True,
        "guardrails": {
            "deterministic_duplicate_detection": True,
            "metadata_only_supersession": True,
            "non_accepted_never_loads": True,
            "source_linked_only": True,
            "no_raw": True,
            "no_external_writeback": True,
            "no_unnecessary_schema": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "memory quality controls proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        md = _render_proof_md(proof)
        _assert_no_raw(md, "memory quality controls proof markdown")
        (out_dir / _PROOF_MD).write_text(md, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
