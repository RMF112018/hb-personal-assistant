"""Phase 09 Prompt 28 — unsupported claim checks + review routing (advisory).

Each retrieved item presented as context is a **claim**. A claim is **supported** iff it carries a
``source_ref`` and an allowlisted (non-excluded) ``source_family``; otherwise it is **unsupported**.
Unsupported claims are detected and **routed to human review** (``review_required``, tier 3, with a reason
code) so they are never presented as fact; a *supported* claim that is tier-3 or carries
``stale_unknown_flags`` / ``conflict_flags`` is routed to ``review_recommended``.

It is **advisory only**: it makes **no** final claim or entitlement determination
(``claim_or_entitlement_decision_performed`` + ``unsupported_claim_performed`` guards stay 0), assembles
no final answer, and persists **metadata-only** (no raw claim text/excerpt/source ref — only hashes,
counts, family names, review vocabulary, and reasons) to the existing V38
``second_brain_retrieval_unsupported_claim_checks`` table. Read-only by default
(``emit_receipt=False`` persists nothing). Fail-closed on missing policy or stale schema.

Public entry points:
  detect_and_route_claims(items, *, unsupported_review_tier=3) -> dict
  build_unsupported_claim_checks(db_path=None, *, project_key=None, families=None, emit_receipt=False) -> dict
  persist_unsupported_claim_check(db_path, result, *, policy_version) -> str
  build_unsupported_claim_checks_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval claim-checks build | proof --json
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
from .broker import RetrievalBroker
from .models import RetrievalItem
from .policy import EXCLUDED_FAMILIES

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "unsupported-claim-checks-proof.json"
_PROOF_MD = "unsupported-claim-checks-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_unsupported_claim_checks.seed.yaml"

_CLAIM_CHECK_TABLE = "second_brain_retrieval_unsupported_claim_checks"

# Canonical review-tier -> review-status mapping (mirrors synthesis/reasoning._review_status_for_tier).
_REVIEW_STATUS_FOR_TIER: dict[int, str] = {
    1: "auto_advisory",
    2: "review_recommended",
    3: "review_required",
}


class UnsupportedClaimCheckError(RuntimeError):
    """Raised when the claim-checks builder cannot resolve policy/schema (fail-closed)."""


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
    """Return the schema version if ready (>=38 with the claim-checks table), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise UnsupportedClaimCheckError("schema not ready for claim checks (no database)")
    try:

        def _has(table: str) -> bool:
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                is not None
            )

        if not _has("schema_migrations"):
            raise UnsupportedClaimCheckError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has(_CLAIM_CHECK_TABLE):
            raise UnsupportedClaimCheckError(
                f"schema not ready for claim checks (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_unsupported_claim_checks_contract() -> dict[str, Any]:
    """Load the unsupported-claim-checks contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("unsupported_claim_checks_contract")
    if not isinstance(contract, dict) or "support_rule" not in contract:
        raise UnsupportedClaimCheckError(
            "phase 09 unsupported-claim-checks contract not found or missing required fields"
        )
    return contract


def load_unsupported_claim_checks_seed() -> dict[str, Any]:
    """Load the resolved unsupported-claim-checks seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise UnsupportedClaimCheckError(f"unsupported-claim-checks seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "unsupported_review_tier" not in data:
        raise UnsupportedClaimCheckError(
            f"{candidate} must define the unsupported-claim-checks policy"
        )
    return data


def detect_and_route_claims(
    items: list[RetrievalItem], *, unsupported_review_tier: int = 3
) -> dict[str, Any]:
    """Detect unsupported claims and route them (and review-flagged supported claims) to review.

    A claim (item) is supported iff it has a ``source_ref`` and an allowlisted non-excluded
    ``source_family``. Unsupported claims route to review_required (tier 3); a supported claim that is
    tier-3 or carries stale/conflict flags routes to review_recommended. Returns metadata-only counts +
    routing breakdown + hashed per-claim routing records — never raw claim text/excerpt/source ref.
    """
    claim_count = len(items)
    unsupported_count = 0
    routing_records: list[dict[str, Any]] = []
    by_review_status: dict[str, int] = {}
    by_reason: dict[str, int] = {}

    for it in items:
        supported = (
            bool(it.source_ref)
            and bool(it.source_family)
            and (it.source_family not in EXCLUDED_FAMILIES)
        )
        flagged = (
            int(it.review_tier) >= 3 or bool(it.stale_unknown_flags) or bool(it.conflict_flags)
        )

        if not supported:
            unsupported_count += 1
            tier = unsupported_review_tier
            review_status = _REVIEW_STATUS_FOR_TIER.get(tier, "review_required")
            reason = (
                "unsupported_excluded_family"
                if it.source_family in EXCLUDED_FAMILIES
                else "unsupported_no_source_link"
            )
        elif flagged:
            tier = max(2, int(it.review_tier))
            review_status = _REVIEW_STATUS_FOR_TIER.get(tier, "review_recommended")
            reason = "supported_review_flagged"
        else:
            continue  # clean, source-supported claim — not routed

        by_review_status[review_status] = by_review_status.get(review_status, 0) + 1
        by_reason[reason] = by_reason.get(reason, 0) + 1
        routing_records.append(
            {
                "source_ref_hash": _hash(it.source_ref)[:48] if it.source_ref else "",
                "source_family": it.source_family,
                "review_tier": tier,
                "review_status": review_status,
                "reason": reason,
            }
        )

    routed_count = len(routing_records)
    if unsupported_count > 0:
        status = "blocked"  # zero tolerance: an unsupported claim must not be presented as fact
    elif routed_count > 0:
        status = "review_routed"
    else:
        status = "clean"

    return {
        "claim_count": claim_count,
        "unsupported_count": unsupported_count,
        "routed_count": routed_count,
        "status": status,
        "by_review_status": by_review_status,
        "by_reason": by_reason,
        "routing_records": routing_records,
    }


def build_unsupported_claim_checks(
    db_path: str | None = None,
    *,
    project_key: str | None = None,
    families: tuple[str, ...] | None = None,
    emit_receipt: bool = False,
) -> dict[str, Any]:
    """Detect unsupported claims over the deterministic corpus and route them to review (read-only).

    Returns a JSON-safe, metadata-only summary (counts, routing breakdown, hashed routing records — never
    raw claim text/source ref); persists nothing unless ``emit_receipt``. Advisory only — makes no claim
    or entitlement determination.
    """
    contract = load_unsupported_claim_checks_contract()
    seed = load_unsupported_claim_checks_seed()
    schema_version = _schema_ready(db_path)
    unsupported_tier = int(seed.get("unsupported_review_tier", 3)) or 3

    env = RetrievalBroker(db_path).retrieve(
        project_key=project_key, families=families, emit_receipt=False
    )
    cc = detect_and_route_claims(env.items, unsupported_review_tier=unsupported_tier)

    run_id = f"uclaim_{_hash(f'{project_key or ""}|{cc["claim_count"]}|{cc["unsupported_count"]}|{cc["status"]}')[:32]}"
    check_id = _hash(f"{run_id}:claim")[:48]

    result = {
        "command": "second-brain retrieval claim-checks build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": cc["status"],
        "run_id": run_id,
        "check_id": check_id,
        "schema_version": schema_version,
        "project_key": project_key,
        "claim_count": cc["claim_count"],
        "unsupported_count": cc["unsupported_count"],
        "routed_count": cc["routed_count"],
        "by_review_status": cc["by_review_status"],
        "by_reason": cc["by_reason"],
        "routing_records": cc["routing_records"],
        "coverage_warnings": list(env.coverage_warnings),
        "advisory_only": True,
        "assembles_final_answer": False,
        "claim_determination_made": False,
        "routes_unsupported_to_review": True,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "receipt_emitted": emit_receipt,
        "read_only": not emit_receipt,
    }

    if emit_receipt:
        persist_unsupported_claim_check(db_path, result, policy_version=str(seed.get("version")))

    return result


def persist_unsupported_claim_check(
    db_path: str | None, result: dict[str, Any], *, policy_version: str
) -> str:
    """Persist a guard-clean metadata-only unsupported-claim-check receipt. Returns check_id."""
    _schema_ready(db_path)
    resolved = db_path or str(PathPolicy().get_db_path())
    check_id = str(result["check_id"])
    conn = sqlite3.connect(resolved)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {_CLAIM_CHECK_TABLE} "
            "(check_id, policy_version, schema_version, run_id, claim_count, unsupported_count, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                check_id,
                policy_version,
                int(result["schema_version"]),
                str(result["run_id"]),
                int(result["claim_count"]),
                int(result["unsupported_count"]),
                str(result["status"]),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return check_id


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
        "# Phase 09 — Unsupported Claim Checks + Review Routing Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- status: {proof['status']}",
        f"- claim_count: {proof['claim_count']}",
        f"- unsupported_count: {proof['unsupported_count']} (must be >= 1)",
        f"- unsupported_routed_to_review_required: {proof['unsupported_routed_to_review_required']}",
        f"- flagged_routed_to_review_recommended: {proof['flagged_routed_to_review_recommended']}",
        f"- claim_determination_made: {proof['claim_determination_made']} (must be false)",
        f"- receipt_guard_clean: {proof['receipt_guard_clean']}",
        f"- claim_or_entitlement_decision_performed: {proof['claim_or_entitlement_decision_performed']} (must be 0)",
        f"- unsupported_claim_performed: {proof['unsupported_claim_performed']} (must be 0)",
        f"- read_only_default_no_persist: {proof['read_only_default_no_persist']}",
        f"- no_raw_emitted: {proof['no_raw_emitted']}",
        "",
    ]
    return "\n".join(lines)


def _synthetic_claims() -> list[RetrievalItem]:
    """A clean supported tier-1 claim (not routed); an unsupported claim (no source_ref -> review_required);
    a supported tier-3 mandatory-review claim (-> review_required); and a supported tier-2 claim carrying a
    conflict flag (-> review_recommended)."""
    return [
        RetrievalItem(
            source_family="approved_obsidian_generated_outputs",
            source_ref="ref-supported",
            record_type="note",
            record_ref="s",
            confidence_class="high",
            review_tier=1,
        ),
        RetrievalItem(
            source_family="accepted_long_term_memory",
            source_ref="",  # no source link -> unsupported
            record_type="memory",
            record_ref="u",
            confidence_class="high",
            review_tier=2,
        ),
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="ref-tier3",
            record_type="issue",
            record_ref="f",
            confidence_class="medium",
            review_tier=3,  # supported but mandatory-review tier -> review_required
        ),
        RetrievalItem(
            source_family="cross_source_relationships",
            source_ref="ref-flagged",
            record_type="relationship",
            record_ref="r",
            confidence_class="medium",
            review_tier=2,  # supported tier-2 + conflict flag -> review_recommended
            conflict_flags=["conflicting_relationship_state"],
        ),
    ]


def build_unsupported_claim_checks_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: unsupported claims are detected + routed to review_required, review-flagged
    supported claims route to review_recommended, no claim/entitlement determination is made, the receipt
    is guard-clean + metadata-only, and no raw claim text is emitted."""
    import tempfile

    from .vector_index import _proof_db

    claims = _synthetic_claims()
    cc = detect_and_route_claims(claims, unsupported_review_tier=3)

    unsupported_routed = any(
        r["reason"].startswith("unsupported") and r["review_status"] == "review_required"
        for r in cc["routing_records"]
    )
    flagged_routed = any(
        r["reason"] == "supported_review_flagged" and r["review_status"] == "review_recommended"
        for r in cc["routing_records"]
    )

    with tempfile.TemporaryDirectory() as tmp:
        db = _proof_db(tmp)
        before = _row_count(db)
        # read-only default persists nothing
        build_unsupported_claim_checks(db)
        read_only_no_persist = _row_count(db) == before

        # emit a receipt on synthetic claims and verify guard-clean metadata-only persistence
        seed = load_unsupported_claim_checks_seed()
        run_id = "uclaim_proof"
        check_id = _hash(f"{run_id}:claim")[:48]
        synth_result = {
            "run_id": run_id,
            "check_id": check_id,
            "schema_version": _schema_ready(db),
            "claim_count": cc["claim_count"],
            "unsupported_count": cc["unsupported_count"],
            "status": cc["status"],
        }
        persist_unsupported_claim_check(db, synth_result, policy_version=str(seed.get("version")))

        conn = sqlite3.connect(db)
        try:
            row_present = (
                conn.execute(
                    f"SELECT COUNT(*) FROM {_CLAIM_CHECK_TABLE} WHERE check_id = ?", (check_id,)
                ).fetchone()[0]
                == 1
            )
            guard_cols = _guard_columns(conn, _CLAIM_CHECK_TABLE)
            guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_CLAIM_CHECK_TABLE} "
                "WHERE check_id = ?",
                (check_id,),
            ).fetchone()[0]
            claim_decision = conn.execute(
                f"SELECT COALESCE(SUM(claim_or_entitlement_decision_performed), 0) FROM "
                f"{_CLAIM_CHECK_TABLE} WHERE check_id = ?",
                (check_id,),
            ).fetchone()[0]
            unsupported_perf = conn.execute(
                f"SELECT COALESCE(SUM(unsupported_claim_performed), 0) FROM {_CLAIM_CHECK_TABLE} "
                "WHERE check_id = ?",
                (check_id,),
            ).fetchone()[0]
        finally:
            conn.close()

    serialized_cc = json.dumps(cc, default=str)
    # The routing records carry only hashed refs — no raw synthetic source_ref ("ref-*") must appear.
    no_raw_emitted = "ref-" not in serialized_cc

    receipt_guard_clean = row_present and int(guard_sum or 0) == 0

    proof_passed = (
        cc["unsupported_count"] >= 1
        and cc["status"] == "blocked"
        and unsupported_routed
        and flagged_routed
        and receipt_guard_clean
        and int(claim_decision or 0) == 0
        and int(unsupported_perf or 0) == 0
        and read_only_no_persist
        and no_raw_emitted
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_unsupported_claim_checks",
        "command": "second-brain retrieval claim-checks proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": cc["status"],
        "claim_count": cc["claim_count"],
        "unsupported_count": cc["unsupported_count"],
        "unsupported_routed_to_review_required": unsupported_routed,
        "flagged_routed_to_review_recommended": flagged_routed,
        "claim_determination_made": False,
        "receipt_guard_clean": receipt_guard_clean,
        "claim_or_entitlement_decision_performed": int(claim_decision or 0),
        "unsupported_claim_performed": int(unsupported_perf or 0),
        "read_only_default_no_persist": read_only_no_persist,
        "no_raw_emitted": no_raw_emitted,
        "by_review_status": cc["by_review_status"],
        "by_reason": cc["by_reason"],
        "metadata_only": True,
        "guardrails": {
            "advisory_only": True,
            "no_final_answer": True,
            "no_claim_or_entitlement_determination": True,
            "route_unsupported_to_review": True,
            "no_raw": True,
            "no_external_writeback": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "unsupported claim checks proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "unsupported claim checks proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof


def _row_count(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {_CLAIM_CHECK_TABLE}").fetchone()[0])
    finally:
        conn.close()
