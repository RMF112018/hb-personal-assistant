"""Phase 09 Addendum Prompt 01 — memory candidate preview (advisory, read-only).

A read-only preview surface that *surfaces possible* long-term memory candidates from
already-redacted, already-source-linked, guard-clean local records — **without accepting or
persisting any accepted memory**. It never writes to ``long_term_memory_items`` (or anything else):
the preview is metadata-only and fail-closed.

Candidate sources (already-redacted, never raw records):
  - ``system_config_fact`` — durable system/config facts enumerated from live constants.
  - ``operator_preference`` / ``workflow_preference`` / ``retrieval_preference`` / ``team_context`` —
    *repeated* operator preferences (``signal_count >= min_signal_count``) from
    ``second_brain_operator_preference_profiles`` (redacted values only).
  - ``project_context`` — stable redacted project read-model items (``project_risk_digest_items``).

Each surfaced candidate is bounded, source-linked, ``review_status='pending_review'`` and never
auto-accepted. Inputs are rejected when they are unsourced, raw-content-shaped, imply a final
determination, or (in a future acceptance-mode caller) are review tier 3. Because this is an explicit
**non-acceptance preview**, tier-3 inputs are surfaced marked ``non_acceptance_preview_only`` rather
than rejected.

Deterministic: candidate identity/content is hash-derived and input-derived; ``generated_utc`` is the
only wall-clock field and is not part of the candidate set.

Public entry points:
  build_memory_candidate_preview(db_path=None, *, project_key=None, evidence_dir=None,
      write_evidence=False) -> dict
  build_memory_candidate_preview_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain memory candidates build | proof --json
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PREVIEW_JSON = "accepted-memory-candidate-preview.json"
_PREVIEW_MD = "accepted-memory-candidate-preview.md"
_PROOF_JSON = "accepted-memory-candidate-preview-proof.json"
_PROOF_MD = "accepted-memory-candidate-preview-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_memory_candidate_preview.seed.yaml"

_PREF_TABLE = "second_brain_operator_preference_profiles"
_RISK_TABLE = "project_risk_digest_items"

_ALLOWED_MEMORY_TYPES = (
    "system_config_fact",
    "operator_preference",
    "project_context",
    "team_context",
    "workflow_preference",
    "retrieval_preference",
)


class MemoryCandidatePreviewError(RuntimeError):
    """Raised when the candidate-preview builder cannot resolve policy/schema (fail-closed)."""


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
    """Return the schema version if ready (>=38 with long_term_memory_items), else fail closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise MemoryCandidatePreviewError(
            "schema not ready for memory candidate preview (no database)"
        )
    try:
        if not _has_table(conn, "schema_migrations"):
            raise MemoryCandidatePreviewError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has_table(conn, "long_term_memory_items"):
            raise MemoryCandidatePreviewError(
                f"schema not ready for memory candidate preview (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_memory_candidate_preview_contract() -> dict[str, Any]:
    """Load the candidate-preview contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("memory_candidate_preview_contract")
    if not isinstance(contract, dict) or "required_candidate_fields" not in contract:
        raise MemoryCandidatePreviewError(
            "phase 09 memory-candidate-preview contract not found or missing required fields"
        )
    return contract


def load_memory_candidate_preview_seed() -> dict[str, Any]:
    """Load the resolved candidate-preview seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise MemoryCandidatePreviewError(f"memory-candidate-preview seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "candidate_types" not in data:
        raise MemoryCandidatePreviewError(f"{candidate} must define the candidate-preview policy")
    return data


# --- Candidate construction & validation ---------------------------------------------------------


def _bound_statement(text: str, max_chars: int) -> str:
    return text.strip()[:max_chars]


def _is_raw_shaped(text: str) -> bool:
    """True if the statement carries a raw-content-shaped value (token/PEM/JWT/URL/email)."""
    try:
        _assert_no_raw(text, "candidate statement")
    except ValueError:
        return True
    return False


def _implies_determination(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(term in low for term in terms)


def _conf_tier(confidence_class: str | None) -> int:
    c = (confidence_class or "").lower()
    if c in ("high", "deterministic"):
        return 1
    if c in ("medium", "strong_heuristic"):
        return 2
    return 3


def _evaluate_input(
    inp: dict[str, Any],
    *,
    determination_terms: list[str],
    max_chars: int,
    preview_only: bool = True,
) -> dict[str, Any]:
    """Validate one candidate input; return a surfaced candidate or a rejection (with reason_code)."""
    source_family = str(inp.get("source_family") or "")
    source_ref = str(inp.get("source_ref") or "").strip()
    source_ref_hash = _hash(source_ref)[:48] if source_ref else _hash(source_family)[:48]

    def _reject(reason: str) -> dict[str, Any]:
        return {
            "surfaced": False,
            "reason_code": reason,
            "source_family": source_family,
            "source_ref_hash": source_ref_hash,
            "memory_type": inp.get("memory_type"),
        }

    if not source_ref:
        return _reject("REJECTED_UNSOURCED")

    statement = _bound_statement(str(inp.get("statement_redacted") or ""), max_chars)
    if not statement:
        return _reject("REJECTED_EMPTY_STATEMENT")
    if _is_raw_shaped(statement):
        return _reject("REJECTED_RAW_SHAPED")
    if _implies_determination(statement, determination_terms):
        return _reject("REJECTED_DETERMINATION")

    tier = int(inp.get("review_tier") or 3)
    if tier >= 3 and not preview_only:
        return _reject("REJECTED_REVIEW_TIER_3")

    statement_hash = _hash(statement)
    candidate_id = "mcp_" + _hash(f"{source_family}:{source_ref}:{statement_hash}")[:32]
    created_utc = str(inp.get("created_utc") or "")
    candidate = {
        "candidate_id": candidate_id,
        "memory_type": str(inp["memory_type"]),
        "statement_redacted": statement,
        "source_family": source_family,
        "source_ref": source_ref,
        "source_ref_hash": _hash(source_ref)[:48],
        "project_key": inp.get("project_key"),
        "confidence_class": str(inp.get("confidence_class") or "unknown"),
        "review_tier": tier,
        "review_status": "pending_review",
        "reason_code": str(inp.get("reason_code") or "CANDIDATE_PREVIEW"),
        "durability_class": str(inp.get("durability_class") or "durable"),
        "freshness_label": "current" if created_utc else "unknown",
        "created_utc": created_utc,
        "non_acceptance_preview_only": tier >= 3,
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "retrieved_context_persisted": False,
    }
    return {"surfaced": True, "candidate": candidate}


def _candidate_summary(c: dict[str, Any]) -> dict[str, Any]:
    """Metadata-only projection (no statement text, no source_ref) for evidence."""
    statement = str(c.get("statement_redacted") or "")
    return {
        "candidate_id": c["candidate_id"],
        "memory_type": c["memory_type"],
        "source_family": c["source_family"],
        "source_ref_hash": c["source_ref_hash"],
        "project_key": c.get("project_key"),
        "confidence_class": c["confidence_class"],
        "review_tier": c["review_tier"],
        "review_status": c["review_status"],
        "reason_code": c["reason_code"],
        "durability_class": c["durability_class"],
        "freshness_label": c["freshness_label"],
        "statement_hash": _hash(statement)[:48],
        "statement_len": len(statement),
        "non_acceptance_preview_only": c["non_acceptance_preview_only"],
        "raw_prompt_persisted": c["raw_prompt_persisted"],
        "raw_response_persisted": c["raw_response_persisted"],
        "retrieved_context_persisted": c["retrieved_context_persisted"],
    }


# --- Candidate source adapters (read-only, already-redacted inputs) -------------------------------


def _system_config_fact_inputs() -> list[dict[str, Any]]:
    """Durable, non-sensitive system/config facts enumerated from live constants (deterministic)."""
    from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

    facts = [
        (
            "system:schema_version",
            f"The local-first retrieval store schema is at version {LATEST_SCHEMA_VERSION}.",
        ),
        (
            "system:memory_guard_columns",
            "Long-term memory items enforce fail-closed no-raw guard columns.",
        ),
        (
            "system:local_first_posture",
            "The assistant runs local-first with no Microsoft 365 write-back.",
        ),
    ]
    return [
        {
            "memory_type": "system_config_fact",
            "source_family": "system_config_facts",
            "source_ref": ref,
            "statement_redacted": statement,
            "project_key": None,
            "confidence_class": "high",
            "review_tier": 1,
            "durability_class": "stable",
            "created_utc": f"schema-v{LATEST_SCHEMA_VERSION}",
            "reason_code": "SYSTEM_CONFIG_FACT_STABLE",
        }
        for ref, statement in facts
    ]


def _classify_preference(scope: str | None, preference_key: str | None) -> tuple[str, str]:
    s = (scope or "").lower()
    k = (preference_key or "").lower()
    if s == "entity":
        return "team_context", "TEAM_CONTEXT_PREFERENCE"
    if k.startswith("workflow"):
        return "workflow_preference", "REPEATED_WORKFLOW_PREFERENCE"
    if k.startswith("retrieval"):
        return "retrieval_preference", "REPEATED_RETRIEVAL_PREFERENCE"
    return "operator_preference", "REPEATED_OPERATOR_PREFERENCE"


def _operator_preference_inputs(
    conn: sqlite3.Connection, project_key: str | None, min_signal: int
) -> list[dict[str, Any]]:
    if not _has_table(conn, _PREF_TABLE):
        return []
    rows = conn.execute(
        f"SELECT preference_id, scope, scope_key, preference_key, preference_value_redacted, "
        f"confidence_class, signal_count, updated_utc FROM {_PREF_TABLE} "
        f"WHERE signal_count >= ? ORDER BY preference_id",
        (int(min_signal),),
    ).fetchall()
    inputs: list[dict[str, Any]] = []
    for r in rows:
        pref_id, scope, scope_key, key, value, confidence, _signal, updated = r
        memory_type, reason = _classify_preference(scope, key)
        pkey = scope_key if (scope or "") == "project" else None
        if project_key is not None and pkey != project_key:
            continue
        statement = f"{key}: {value}" if value else str(key or "")
        inputs.append(
            {
                "memory_type": memory_type,
                "source_family": "operator_preference_profiles",
                "source_ref": str(pref_id or ""),
                "statement_redacted": statement,
                "project_key": pkey,
                "confidence_class": str(confidence or "unknown"),
                "review_tier": _conf_tier(confidence),
                "durability_class": "durable",
                "created_utc": str(updated or ""),
                "reason_code": reason,
            }
        )
    return inputs


def _project_context_inputs(
    conn: sqlite3.Connection, project_key: str | None
) -> list[dict[str, Any]]:
    if not _has_table(conn, _RISK_TABLE):
        return []
    from ..retrieval.readers import read_risk_digest

    try:
        items = read_risk_digest(None, None, project_key, conn=conn)
    except Exception:
        return []
    inputs: list[dict[str, Any]] = []
    for it in items:
        if it.review_required or it.review_tier >= 3:  # stable project context only
            continue
        inputs.append(
            {
                "memory_type": "project_context",
                "source_family": it.source_family,
                "source_ref": it.source_ref,
                "statement_redacted": it.content_excerpt_redacted,
                "project_key": it.project_key,
                "confidence_class": it.confidence_class,
                "review_tier": it.review_tier,
                "durability_class": "durable",
                "created_utc": it.recency,
                "reason_code": "STABLE_PROJECT_CONTEXT",
            }
        )
    return inputs


def gather_candidate_inputs(
    conn: sqlite3.Connection, *, project_key: str | None, min_signal: int
) -> list[dict[str, Any]]:
    """Gather already-redacted candidate inputs from the safe source adapters (read-only)."""
    inputs: list[dict[str, Any]] = []
    inputs.extend(_system_config_fact_inputs())
    inputs.extend(_operator_preference_inputs(conn, project_key, min_signal))
    inputs.extend(_project_context_inputs(conn, project_key))
    return inputs


# --- Builder -------------------------------------------------------------------------------------


def build_memory_candidate_preview(
    db_path: str | None = None,
    *,
    project_key: str | None = None,
    evidence_dir: str | None = None,
    write_evidence: bool = False,
) -> dict[str, Any]:
    """Build a read-only memory candidate preview (advisory; never accepts/persists memory)."""
    contract = load_memory_candidate_preview_contract()
    seed = load_memory_candidate_preview_seed()
    schema_version = _schema_ready(db_path)

    min_signal = int(seed.get("min_signal_count", 2))
    max_chars = int(seed.get("statement_max_chars", 280))
    determination_terms = [str(t).lower() for t in seed.get("determination_terms", [])]
    preview_only = bool(seed.get("preview_only", True))

    conn = _open_ro(db_path)
    if conn is None:
        raise MemoryCandidatePreviewError(
            "schema not ready for memory candidate preview (no database)"
        )
    conn.row_factory = sqlite3.Row
    try:
        inputs = gather_candidate_inputs(conn, project_key=project_key, min_signal=min_signal)
    finally:
        conn.close()

    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for inp in inputs:
        outcome = _evaluate_input(
            inp,
            determination_terms=determination_terms,
            max_chars=max_chars,
            preview_only=preview_only,
        )
        if outcome["surfaced"]:
            candidates.append(outcome["candidate"])
        else:
            rejected.append(
                {
                    "source_family": outcome["source_family"],
                    "source_ref_hash": outcome["source_ref_hash"],
                    "memory_type": outcome.get("memory_type"),
                    "reason_code": outcome["reason_code"],
                }
            )

    candidates.sort(key=lambda c: c["candidate_id"])
    rejected.sort(key=lambda r: (r["reason_code"], r["source_ref_hash"]))
    per_type = dict(Counter(c["memory_type"] for c in candidates))
    per_durability = dict(Counter(c["durability_class"] for c in candidates))

    result = {
        "command": "second-brain memory candidates build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": "built" if candidates else "empty",
        "schema_version": schema_version,
        "project_key": project_key,
        "candidate_count": len(candidates),
        "rejected_count": len(rejected),
        "per_type": per_type,
        "per_durability": per_durability,
        "candidates": candidates,
        "rejected": rejected,
        "read_only": True,
        "writes_accepted_memory": False,
        "accepted_memory_written": 0,
        "deterministic": True,
        "preview_only": preview_only,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
    }

    if write_evidence:
        _write_preview_evidence(result, evidence_dir)

    return result


def _render_preview_md(result: dict[str, Any], summaries: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase 09 Addendum — Memory Candidate Preview",
        "",
        f"- generated_utc: {result['generated_utc']}",
        f"- repo_sha: {result['repo_sha']}",
        f"- status: {result['status']}",
        f"- schema_version: {result['schema_version']}",
        f"- candidate_count: {result['candidate_count']}",
        f"- rejected_count: {result['rejected_count']}",
        f"- per_type: {result['per_type']}",
        f"- per_durability: {result['per_durability']}",
        f"- read_only: {result['read_only']} | writes_accepted_memory: "
        f"{result['writes_accepted_memory']} | deterministic: {result['deterministic']}",
        "",
        "## Candidate summaries (metadata-only)",
        "",
    ]
    for s in summaries:
        lines.append(
            f"- {s['candidate_id']} | {s['memory_type']} | tier {s['review_tier']}"
            f" | {s['review_status']} | {s['durability_class']} | {s['reason_code']}"
            f" | stmt_hash {s['statement_hash']}"
        )
    if not summaries:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def _write_preview_evidence(result: dict[str, Any], evidence_dir: str | None) -> None:
    summaries = [_candidate_summary(c) for c in result["candidates"]]
    evidence = {
        "command": result["command"],
        "phase": result["phase"],
        "generated_utc": result["generated_utc"],
        "repo_sha": result["repo_sha"],
        "status": result["status"],
        "schema_version": result["schema_version"],
        "project_key": result["project_key"],
        "candidate_count": result["candidate_count"],
        "rejected_count": result["rejected_count"],
        "per_type": result["per_type"],
        "per_durability": result["per_durability"],
        "candidate_summaries": summaries,
        "rejected": result["rejected"],
        "read_only": result["read_only"],
        "writes_accepted_memory": result["writes_accepted_memory"],
        "accepted_memory_written": result["accepted_memory_written"],
        "deterministic": result["deterministic"],
        "preview_only": result["preview_only"],
        "metadata_only": True,
        "policy_version": result["policy_version"],
        "contract_version": result["contract_version"],
    }
    out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = json.dumps(evidence, indent=2, default=str)
    _assert_no_raw(out, "memory candidate preview json")
    (out_dir / _PREVIEW_JSON).write_text(out + "\n", encoding="utf-8")
    markdown = _render_preview_md(result, summaries)
    _assert_no_raw(markdown, "memory candidate preview markdown")
    (out_dir / _PREVIEW_MD).write_text(markdown, encoding="utf-8")


# --- Proof ---------------------------------------------------------------------------------------


def _seed_proof_db(db: str) -> None:
    """Seed repeated operator preferences exercising safe surfacing + every rejection path."""
    from .models import OperatorPreference
    from .store import upsert_operator_preference

    prefs = [
        # safe, repeated workflow preference -> workflow_preference (tier 1)
        OperatorPreference(
            preference_id="pref-wf-brief",
            scope="global",
            preference_key="workflow.daily_brief_time",
            preference_value_redacted="prefers the morning brief early",
            confidence_class="high",
            signal_count=3,
            review_status="accepted",
        ),
        # safe, repeated retrieval preference -> retrieval_preference (tier 2)
        OperatorPreference(
            preference_id="pref-rt-context",
            scope="global",
            preference_key="retrieval.context_size",
            preference_value_redacted="keep retrieved context tight",
            confidence_class="medium",
            signal_count=2,
            review_status="pending_review",
        ),
        # safe team-scoped preference -> team_context (tier 1)
        OperatorPreference(
            preference_id="pref-team-lead",
            scope="entity",
            scope_key="team-pm",
            preference_key="team.ownership",
            preference_value_redacted="the PM team owns submittal turnaround",
            confidence_class="high",
            signal_count=2,
            review_status="accepted",
        ),
        # raw-content-shaped value -> REJECTED_RAW_SHAPED
        OperatorPreference(
            preference_id="pref-raw",
            scope="global",
            preference_key="workflow.reference_link",
            preference_value_redacted="see https://example.com/internal/doc",
            confidence_class="high",
            signal_count=2,
            review_status="pending_review",
        ),
        # determination-implying value -> REJECTED_DETERMINATION
        OperatorPreference(
            preference_id="pref-determination",
            scope="global",
            preference_key="workflow.invoice_policy",
            preference_value_redacted="the change order is approved and final",
            confidence_class="high",
            signal_count=2,
            review_status="pending_review",
        ),
        # low-confidence repeated preference -> surfaced tier 3 (non-acceptance preview only)
        OperatorPreference(
            preference_id="pref-low-conf",
            scope="global",
            preference_key="workflow.step_order_guess",
            preference_value_redacted="maybe reorder the closeout steps",
            confidence_class="low",
            signal_count=2,
            review_status="pending_review",
        ),
        # not repeated (signal_count 1) -> filtered out before validation
        OperatorPreference(
            preference_id="pref-single",
            scope="global",
            preference_key="workflow.one_off",
            preference_value_redacted="a one-off preference",
            confidence_class="high",
            signal_count=1,
            review_status="pending_review",
        ),
    ]
    for pref in prefs:
        upsert_operator_preference(pref, db_path=db)


def _ltm_count(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM long_term_memory_items").fetchone()[0])
    finally:
        conn.close()


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 Addendum — Memory Candidate Preview Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- candidate_count: {proof['candidate_count']}",
        f"- per_type: {proof['per_type']}",
        f"- safe_candidates_surfaced: {proof['safe_candidates_surfaced']}",
        f"- raw_shaped_rejected: {proof['raw_shaped_rejected']}",
        f"- unsourced_rejected: {proof['unsourced_rejected']}",
        f"- determination_rejected: {proof['determination_rejected']}",
        f"- tier3_surfaced_preview_only: {proof['tier3_surfaced_preview_only']}",
        f"- tier3_not_accepted: {proof['tier3_not_accepted']}",
        f"- not_repeated_excluded: {proof['not_repeated_excluded']}",
        f"- accepted_memory_unchanged: {proof['accepted_memory_unchanged']} "
        f"(before={proof['ltm_before']}, after={proof['ltm_after']})",
        f"- evidence_metadata_only: {proof['evidence_metadata_only']}",
        f"- no_raw_emitted: {proof['no_raw_emitted']}",
        "",
    ]
    return "\n".join(lines)


def build_memory_candidate_preview_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: safe candidates surface, unsafe inputs are rejected, tier-3 is surfaced
    preview-only and never accepted, no accepted memory is written, and evidence is metadata-only."""
    import tempfile

    from hb_assistant.store.migrator import SQLiteMigrator

    seed = load_memory_candidate_preview_seed()
    determination_terms = [str(t).lower() for t in seed.get("determination_terms", [])]
    max_chars = int(seed.get("statement_max_chars", 280))

    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "mcp.sqlite")
        SQLiteMigrator(db_path=db).apply()
        _seed_proof_db(db)

        ltm_before = _ltm_count(db)
        result = build_memory_candidate_preview(db, write_evidence=False)
        # Emit the committed preview evidence from this deterministic fixture (synthetic,
        # reproducible) rather than from the operator's live DB.
        if write_evidence:
            build_memory_candidate_preview(db, evidence_dir=evidence_dir, write_evidence=True)
        ltm_after = _ltm_count(db)

    candidates = result["candidates"]
    rejected = result["rejected"]
    reason_codes = {r["reason_code"] for r in rejected}
    surfaced_types = {c["memory_type"] for c in candidates}
    surfaced_ids = {c["source_ref"] for c in candidates}  # source_ref present in full result
    tier3 = [c for c in candidates if c["review_tier"] >= 3]

    # unsourced rejection is proven directly on the validator (preferences always carry an id)
    unsourced_outcome = _evaluate_input(
        {
            "memory_type": "operator_preference",
            "source_family": "operator_preference_profiles",
            "source_ref": "",
            "statement_redacted": "a preference with no source",
        },
        determination_terms=determination_terms,
        max_chars=max_chars,
    )

    safe_candidates_surfaced = {
        "system_config_fact",
        "workflow_preference",
        "retrieval_preference",
        "team_context",
    }.issubset(surfaced_types)
    raw_shaped_rejected = "REJECTED_RAW_SHAPED" in reason_codes
    determination_rejected = "REJECTED_DETERMINATION" in reason_codes
    unsourced_rejected = (
        unsourced_outcome["surfaced"] is False
        and unsourced_outcome["reason_code"] == "REJECTED_UNSOURCED"
    )
    tier3_surfaced_preview_only = bool(tier3) and all(
        c["non_acceptance_preview_only"] and c["review_status"] == "pending_review" for c in tier3
    )
    tier3_not_accepted = all(c["review_status"] == "pending_review" for c in candidates)
    not_repeated_excluded = "pref-single" not in surfaced_ids
    accepted_memory_unchanged = ltm_before == 0 and ltm_after == 0
    serialized = json.dumps({"per_type": result["per_type"], "rejected": rejected}, default=str)
    no_raw_emitted = "https://" not in serialized and "approved and final" not in serialized

    # evidence metadata-only: summaries carry no statement text / source_ref
    summaries = [_candidate_summary(c) for c in candidates]
    evidence_metadata_only = all(
        "statement_redacted" not in s and "source_ref" not in s for s in summaries
    )

    proof_passed = (
        result["status"] == "built"
        and safe_candidates_surfaced
        and raw_shaped_rejected
        and determination_rejected
        and unsourced_rejected
        and tier3_surfaced_preview_only
        and tier3_not_accepted
        and not_repeated_excluded
        and accepted_memory_unchanged
        and evidence_metadata_only
        and no_raw_emitted
        and result["writes_accepted_memory"] is False
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_memory_candidate_preview",
        "command": "second-brain memory candidates proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": result["status"],
        "candidate_count": result["candidate_count"],
        "per_type": result["per_type"],
        "rejected_reason_codes": sorted(reason_codes),
        "safe_candidates_surfaced": safe_candidates_surfaced,
        "raw_shaped_rejected": raw_shaped_rejected,
        "unsourced_rejected": unsourced_rejected,
        "determination_rejected": determination_rejected,
        "tier3_surfaced_preview_only": tier3_surfaced_preview_only,
        "tier3_not_accepted": tier3_not_accepted,
        "not_repeated_excluded": not_repeated_excluded,
        "accepted_memory_unchanged": accepted_memory_unchanged,
        "ltm_before": ltm_before,
        "ltm_after": ltm_after,
        "evidence_metadata_only": evidence_metadata_only,
        "no_raw_emitted": no_raw_emitted,
        "metadata_only": True,
        "guardrails": {
            "read_only_by_default": True,
            "no_acceptance": True,
            "no_external_writeback": True,
            "no_raw": True,
            "source_linked_only": True,
            "deterministic": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(out, "memory candidate preview proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "memory candidate preview proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
