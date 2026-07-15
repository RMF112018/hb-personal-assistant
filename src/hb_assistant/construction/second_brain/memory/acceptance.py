"""Phase 09 Addendum Prompt 02 — explicit memory acceptance workflow.

Converts a vetted candidate from the durable safe candidate store (``memory_update_candidates``) into
an accepted ``long_term_memory_items`` row. **Acceptance requires explicit operator action — there is
no automatic acceptance.** The existing curator (`review_memory_candidate`) performs the promotion but
enforces no acceptance blocking, so this module adds a strict, fail-closed **acceptance gate** plus
explicit ``confirm`` semantics, layered on the existing curator/store. Uses the existing
``long_term_memory_items`` table (schema sufficient — no migration); guard columns stay 0.

Rejected / deferred / superseded items never load into retrieval or the vector index — the reviewed
memory loader gates strictly on ``review_status='accepted'``.

Public entry points:
  evaluate_candidate_acceptance(candidate) -> dict
  accept_memory_candidate(candidate_id, *, db_path=None, confirm=False) -> dict
  decide_memory_candidate(candidate_id, *, decision, reason=None, db_path=None, confirm=False) -> dict
  list_accepted_memory(*, db_path=None, status="accepted", limit=200) -> dict
  build_memory_acceptance_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain memory accept | reject | list | proof --json
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
from .candidate_preview import (
    _implies_determination,
    _is_raw_shaped,
    load_memory_candidate_preview_seed,
)
from .models import MemoryCandidate

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "accepted-memory-acceptance-proof.json"
_PROOF_MD = "accepted-memory-acceptance-proof.md"

_DECISIONS = ("rejected", "deferred", "superseded")


class MemoryAcceptanceError(RuntimeError):
    """Raised when the acceptance workflow cannot resolve the candidate/schema (fail-closed)."""


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
        raise MemoryAcceptanceError("schema not ready for memory acceptance (no database)")
    try:
        if not _has_table(conn, "schema_migrations"):
            raise MemoryAcceptanceError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has_table(conn, "long_term_memory_items"):
            raise MemoryAcceptanceError(
                f"schema not ready for memory acceptance (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_memory_acceptance_contract() -> dict[str, Any]:
    """Load the acceptance contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("memory_acceptance_contract")
    if not isinstance(contract, dict) or "acceptance_rules" not in contract:
        raise MemoryAcceptanceError(
            "phase 09 memory-acceptance contract not found or missing required fields"
        )
    return contract


# --- Acceptance gate -----------------------------------------------------------------------------


def _determination_terms() -> list[str]:
    seed = load_memory_candidate_preview_seed()
    return [str(t).lower() for t in seed.get("determination_terms", [])]


def evaluate_candidate_acceptance(
    candidate: MemoryCandidate, *, determination_terms: list[str] | None = None
) -> dict[str, Any]:
    """Strict, fail-closed acceptance gate. Collects all blocks; acceptable iff none apply."""
    terms = determination_terms if determination_terms is not None else _determination_terms()
    statement = str(candidate.statement_redacted or "")
    refs = candidate.source_refs or []
    has_source_ref = any(str(r.get("source_ref") or "").strip() for r in refs)
    raw_in_refs = any(
        _is_raw_shaped(str(r.get("source_ref") or "")) for r in refs if r.get("source_ref")
    )

    blocks: list[str] = []
    if not has_source_ref:
        blocks.append("NO_SOURCE_REF")
    if not statement.strip():
        blocks.append("NO_STATEMENT")
    if not str(candidate.proposed_memory_type or "").strip():
        blocks.append("NO_MEMORY_TYPE")
    conf = str(candidate.confidence_class or "").strip().lower()
    if not conf or conf == "unknown":
        blocks.append("NO_CONFIDENCE_CLASS")
    if candidate.review_tier not in (1, 2, 3):
        blocks.append("INVALID_REVIEW_TIER")
    if (statement.strip() and _is_raw_shaped(statement)) or raw_in_refs:
        blocks.append("RAW_CONTENT_FINDING")
    if int(candidate.review_tier or 3) >= 3:
        blocks.append("UNRESOLVED_HIGH_IMPACT")
    if statement.strip() and _implies_determination(statement, terms):
        blocks.append("FINAL_DETERMINATION")

    return {
        "acceptable": not blocks,
        "blocks": blocks,
        "checks": {
            "has_source_ref": has_source_ref,
            "has_statement": bool(statement.strip()),
            "has_memory_type": bool(str(candidate.proposed_memory_type or "").strip()),
            "has_confidence_class": bool(conf and conf != "unknown"),
            "review_tier": int(candidate.review_tier or 0),
            "no_raw_finding": not (
                (statement.strip() and _is_raw_shaped(statement)) or raw_in_refs
            ),
            "not_unresolved_high_impact": int(candidate.review_tier or 3) < 3,
            "not_final_determination": not (
                statement.strip() and _implies_determination(statement, terms)
            ),
        },
    }


def _candidate_from_row(row: dict[str, Any]) -> MemoryCandidate:
    """Reconstruct a MemoryCandidate from a stored candidate row (mirrors the `memory review` CLI)."""
    return MemoryCandidate(
        candidate_id=row["candidate_id"],
        proposed_memory_type=row["proposed_memory_type"],
        statement_redacted=row["statement_redacted"],
        project_key=row["project_key"],
        origin_id=row["origin_id"],
        provenance_class=row["provenance_class"],
        confidence_class=row["confidence_class"],
        review_required=bool(row["review_required"]),
        review_tier=row["review_tier"] or 3,
        review_tier_reason_code=row["review_tier_reason_code"] or "T3_MODEL_ONLY",
        sensitivity_class=row["sensitivity_class"],
        source_refs=json.loads(row["source_refs_json"] or "[]"),
        status=row["status"],
    )


def _source_ref_summary(candidate: MemoryCandidate) -> dict[str, Any]:
    refs = candidate.source_refs or []
    first = refs[0] if refs else {}
    family = str(first.get("source_family") or "")
    ref = str(first.get("source_ref") or "")
    return {
        "source_ref_count": len(refs),
        "source_family": family,
        "source_ref_hash": _hash(ref)[:48] if ref else "",
    }


# --- Accept / decide -----------------------------------------------------------------------------


def accept_memory_candidate(
    candidate_id: str, *, db_path: str | None = None, confirm: bool = False
) -> dict[str, Any]:
    """Explicitly accept a candidate into long_term_memory_items (no auto-acceptance).

    Without ``confirm`` this is a dry-run that persists nothing. With ``confirm`` and a passing gate the
    candidate is promoted to an accepted memory item; a failing gate refuses and persists nothing.
    """
    from .store import read_memory_candidate

    contract = load_memory_acceptance_contract()
    _schema_ready(db_path)
    row = read_memory_candidate(candidate_id, db_path=db_path)
    if row is None:
        raise MemoryAcceptanceError(f"candidate not found: {candidate_id}")

    candidate = _candidate_from_row(row)
    gate = evaluate_candidate_acceptance(candidate)
    refs = _source_ref_summary(candidate)

    # Duplicate suppression (db-aware, read-only): refuse an item equivalent to an existing accepted
    # one by (project_key, memory_type, source_family, normalized statement).
    from .quality_controls import detect_duplicate_accepted

    blocks = list(gate["blocks"])
    dup = detect_duplicate_accepted(
        statement_redacted=candidate.statement_redacted,
        project_key=candidate.project_key,
        memory_type=candidate.proposed_memory_type,
        source_family=refs["source_family"],
        db_path=db_path,
    )
    if dup["is_duplicate"]:
        blocks.append("DUPLICATE_ACCEPTED")
    acceptable = not blocks

    result: dict[str, Any] = {
        "command": "second-brain memory accept",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "candidate_id": candidate_id,
        "memory_type": candidate.proposed_memory_type,
        "confidence_class": candidate.confidence_class,
        "review_tier": int(candidate.review_tier or 0),
        "project_key": candidate.project_key,
        "source_family": refs["source_family"],
        "source_ref_hash": refs["source_ref_hash"],
        "source_ref_count": refs["source_ref_count"],
        "acceptable": acceptable,
        "blocks": blocks,
        "checks": gate["checks"],
        "duplicate_of_memory_id": dup["existing_memory_id"],
        "confirm": confirm,
        "requires_confirm": True,
        "writes_external": False,
        "guard_columns_false": True,
        "contract_version": contract.get("version"),
    }

    if not confirm:
        result["accepted"] = False
        result["would_accept"] = acceptable
        result["persisted"] = False
        return result

    if not acceptable:
        result["accepted"] = False
        result["would_accept"] = False
        result["persisted"] = False
        return result

    from .curator import review_memory_candidate

    _review, item, signals = review_memory_candidate(
        candidate=candidate, decision="accepted", emit=True, db_path=db_path
    )
    result["accepted"] = True
    result["would_accept"] = True
    result["persisted"] = True
    result["memory_id"] = item.memory_id if item else None
    result["review_status"] = item.review_status if item else None
    result["quality_signal_types"] = [s.signal_type for s in signals]
    return result


def decide_memory_candidate(
    candidate_id: str,
    *,
    decision: str,
    reason: str | None = None,
    db_path: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Reject / defer / supersede a candidate (never creates an accepted memory item)."""
    from .curator import review_memory_candidate
    from .store import read_memory_candidate

    contract = load_memory_acceptance_contract()
    _schema_ready(db_path)
    if decision not in _DECISIONS:
        raise MemoryAcceptanceError(
            f"decision must be one of {_DECISIONS} (use `accept` for acceptance)"
        )
    row = read_memory_candidate(candidate_id, db_path=db_path)
    if row is None:
        raise MemoryAcceptanceError(f"candidate not found: {candidate_id}")

    candidate = _candidate_from_row(row)
    result: dict[str, Any] = {
        "command": "second-brain memory reject",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "candidate_id": candidate_id,
        "decision": decision,
        "confirm": confirm,
        "requires_confirm": True,
        "writes_external": False,
        "creates_accepted_memory": False,
        "loads_into_retrieval": False,
        "contract_version": contract.get("version"),
    }
    if not confirm:
        result["persisted"] = False
        return result

    review, item, _signals = review_memory_candidate(
        candidate=candidate,
        decision=decision,
        decision_reason_redacted=reason,
        emit=True,
        db_path=db_path,
    )
    result["persisted"] = True
    result["decision"] = review.decision
    result["created_memory_item"] = item is not None
    return result


def list_accepted_memory(
    *, db_path: str | None = None, status: str = "accepted", limit: int = 200
) -> dict[str, Any]:
    """Metadata-only listing of long_term_memory_items by review_status (no statement text)."""
    contract = load_memory_acceptance_contract()
    _schema_ready(db_path)
    conn = _open_ro(db_path)
    if conn is None:
        raise MemoryAcceptanceError("schema not ready for memory acceptance (no database)")
    try:
        rows = conn.execute(
            "SELECT memory_id, memory_type, confidence_class, review_status, project_key, created_utc "
            "FROM long_term_memory_items WHERE review_status = ? ORDER BY memory_id LIMIT ?",
            (status, int(limit)),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for memory_id, mtype, conf, rstatus, pkey, created in rows:
            ref_count = conn.execute(
                "SELECT COUNT(*) FROM long_term_memory_source_refs WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()[0]
            items.append(
                {
                    "memory_id": memory_id,
                    "memory_type": mtype,
                    "confidence_class": conf,
                    "review_status": rstatus,
                    "project_key": pkey,
                    "freshness_label": "current" if created else "unknown",
                    "source_ref_count": int(ref_count),
                }
            )
    finally:
        conn.close()

    return {
        "command": "second-brain memory list",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": status,
        "count": len(items),
        "items": items,
        "metadata_only": True,
        "loadable_into_retrieval": status == "accepted",
        "contract_version": contract.get("version"),
    }


# --- Proof ---------------------------------------------------------------------------------------


def _ltm_count(db_path: str, status: str | None = None) -> int:
    conn = sqlite3.connect(db_path)
    try:
        if status is None:
            return int(conn.execute("SELECT COUNT(*) FROM long_term_memory_items").fetchone()[0])
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM long_term_memory_items WHERE review_status = ?", (status,)
            ).fetchone()[0]
        )
    finally:
        conn.close()


def _guard_sum(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cols = [str(r[1]) for r in conn.execute("PRAGMA table_info(long_term_memory_items)")]
        guards = [c for c in cols if c.endswith("_persisted")]
        if not guards:
            return 0
        row = conn.execute(
            f"SELECT COALESCE(SUM({'+'.join(guards)}), 0) FROM long_term_memory_items"
        ).fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def _seed_proof_db(db: str) -> dict[str, str]:
    """Seed candidates exercising the acceptance gate + a non-accepted item for retrieval exclusion."""
    from .curator import propose_memory_candidate
    from .models import MemoryItem
    from .store import write_memory_item

    refs = [{"source_family": "approved_read_models", "source_ref": "rm-1"}]
    clean = propose_memory_candidate(
        statement_redacted="The project uses metric units for all submittals.",
        proposed_memory_type="project_context",
        origin_id="o-clean",
        source_refs=refs,
        confidence_class="high",
        db_path=db,
        emit=True,
    )
    raw = propose_memory_candidate(
        statement_redacted="reference doc at https://example.com/spec",
        proposed_memory_type="project_context",
        origin_id="o-raw",
        source_refs=refs,
        confidence_class="high",
        db_path=db,
        emit=True,
    )
    unsourced = propose_memory_candidate(
        statement_redacted="an unsourced recollection",
        proposed_memory_type="fact",
        origin_id="o-unsourced",
        source_refs=[],
        confidence_class="high",
        db_path=db,
        emit=True,
    )
    sensitive = propose_memory_candidate(
        statement_redacted="a financial exposure note",
        proposed_memory_type="fact",
        origin_id="o-sensitive",
        source_refs=refs,
        confidence_class="high",
        sensitivity_category="financial",
        db_path=db,
        emit=True,
    )
    determination = propose_memory_candidate(
        statement_redacted="the change order is approved and final",
        proposed_memory_type="fact",
        origin_id="o-determination",
        source_refs=refs,
        confidence_class="high",
        db_path=db,
        emit=True,
    )
    # A non-accepted item that must be excluded from retrieval loading.
    write_memory_item(
        MemoryItem(
            memory_id="sup-excluded-1",
            memory_type="fact",
            statement_redacted="an outdated, superseded fact",
            confidence_class="high",
            review_status="superseded",
            source_refs=refs,
        ),
        db_path=db,
    )
    return {
        "clean": clean.candidate_id,
        "raw": raw.candidate_id,
        "unsourced": unsourced.candidate_id,
        "sensitive": sensitive.candidate_id,
        "determination": determination.candidate_id,
        "superseded_memory_id": "sup-excluded-1",
    }


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 Addendum — Memory Acceptance Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- accepted_persisted_as_accepted: {proof['accepted_persisted_as_accepted']}",
        f"- dry_run_persists_nothing: {proof['dry_run_persists_nothing']}",
        f"- raw_shaped_blocked: {proof['raw_shaped_blocked']}",
        f"- unsourced_blocked: {proof['unsourced_blocked']}",
        f"- high_impact_blocked: {proof['high_impact_blocked']}",
        f"- determination_blocked: {proof['determination_blocked']}",
        f"- rejected_creates_no_item: {proof['rejected_creates_no_item']}",
        f"- non_accepted_excluded_from_retrieval: {proof['non_accepted_excluded_from_retrieval']}",
        f"- guard_columns_all_false: {proof['guard_columns_all_false']}",
        f"- no_external_writeback: {proof['no_external_writeback']}",
        "",
    ]
    return "\n".join(lines)


def build_memory_acceptance_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof of the explicit acceptance workflow over a deterministic fixture."""
    import tempfile

    from hb_assistant.store.migrator import ensure_schema_ready

    from ..retrieval.memory_loader import load_reviewed_memory_nodes
    from .store import read_memory_candidate

    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "acc.sqlite")
        ensure_schema_ready(db)
        ids = _seed_proof_db(db)

        # dry-run (no confirm) persists nothing
        accepted_before = _ltm_count(db, "accepted")
        dry = accept_memory_candidate(ids["clean"], db_path=db, confirm=False)
        dry_run_persists_nothing = (
            dry["accepted"] is False
            and dry["persisted"] is False
            and dry["would_accept"] is True
            and _ltm_count(db, "accepted") == accepted_before
        )

        # explicit confirmed acceptance of the clean candidate
        acc = accept_memory_candidate(ids["clean"], db_path=db, confirm=True)
        accepted_id = acc.get("memory_id")
        accepted_persisted_as_accepted = (
            acc["accepted"] is True
            and acc["review_status"] == "accepted"
            and accepted_id is not None
            and _ltm_count(db, "accepted") == accepted_before + 1
        )

        # unsafe candidates refused (with confirm) and persisted nothing
        before_unsafe = _ltm_count(db, "accepted")
        raw = accept_memory_candidate(ids["raw"], db_path=db, confirm=True)
        uns = accept_memory_candidate(ids["unsourced"], db_path=db, confirm=True)
        hi = accept_memory_candidate(ids["sensitive"], db_path=db, confirm=True)
        det = accept_memory_candidate(ids["determination"], db_path=db, confirm=True)
        raw_shaped_blocked = raw["accepted"] is False and "RAW_CONTENT_FINDING" in raw["blocks"]
        unsourced_blocked = uns["accepted"] is False and "NO_SOURCE_REF" in uns["blocks"]
        high_impact_blocked = hi["accepted"] is False and "UNRESOLVED_HIGH_IMPACT" in hi["blocks"]
        determination_blocked = det["accepted"] is False and "FINAL_DETERMINATION" in det["blocks"]
        no_unsafe_persisted = _ltm_count(db, "accepted") == before_unsafe

        # reject decision creates no accepted memory item
        rej = decide_memory_candidate(
            ids["determination"],
            decision="rejected",
            reason="not durable",
            db_path=db,
            confirm=True,
        )
        rejected_row = read_memory_candidate(ids["determination"], db_path=db)
        rejected_creates_no_item = (
            rej["created_memory_item"] is False
            and rejected_row is not None
            and rejected_row["status"] == "rejected"
        )

        # non-accepted items excluded from retrieval loading
        nodes = load_reviewed_memory_nodes(db)
        loaded_refs = {str(n.get("source_ref")) for n in nodes}
        non_accepted_excluded = (
            accepted_id in loaded_refs and ids["superseded_memory_id"] not in loaded_refs
        )

        guard_columns_all_false = _guard_sum(db) == 0

    proof_passed = (
        dry_run_persists_nothing
        and accepted_persisted_as_accepted
        and raw_shaped_blocked
        and unsourced_blocked
        and high_impact_blocked
        and determination_blocked
        and no_unsafe_persisted
        and rejected_creates_no_item
        and non_accepted_excluded
        and guard_columns_all_false
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_memory_acceptance",
        "command": "second-brain memory proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "accepted_persisted_as_accepted": accepted_persisted_as_accepted,
        "dry_run_persists_nothing": dry_run_persists_nothing,
        "raw_shaped_blocked": raw_shaped_blocked,
        "unsourced_blocked": unsourced_blocked,
        "high_impact_blocked": high_impact_blocked,
        "determination_blocked": determination_blocked,
        "no_unsafe_persisted": no_unsafe_persisted,
        "rejected_creates_no_item": rejected_creates_no_item,
        "non_accepted_excluded_from_retrieval": non_accepted_excluded,
        "guard_columns_all_false": guard_columns_all_false,
        "no_external_writeback": True,
        "requires_explicit_confirmation": True,
        "no_auto_acceptance": True,
        "metadata_only": True,
        "guardrails": {
            "explicit_confirmation_required": True,
            "no_auto_acceptance": True,
            "no_external_writeback": True,
            "no_raw": True,
            "guard_columns_false": True,
            "non_accepted_never_loads": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(out, "memory acceptance proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "memory acceptance proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
