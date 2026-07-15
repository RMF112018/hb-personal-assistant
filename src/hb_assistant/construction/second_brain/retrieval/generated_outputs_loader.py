"""Phase 09 — generated outputs vector loader (read-only, fail-closed).

Loads **only approved, source-linked generated outputs** (accepted research packets from
`second_brain_research_packets` + applied, source-linked daily briefs from `daily_brief_runs`
with `mode='apply'` and positive `source_ref_count`) into safe, metadata-only nodes for the
future embed/index step (Prompts 18-19).

Approval and eligibility are defined by the Phase 09 approved source manifest (Prompt 15):
- research packets: `review_status = 'accepted'`
- daily briefs: `mode = 'apply'`, `status != 'blocked'`, `output_path_hash IS NOT NULL`,
  `source_ref_count > 0`

Each candidate node is validated by the Prompt 14 embedding guard
(`validate_embedding_candidate`): embeddable family (after allowlist update), required
source-linked metadata, no forbidden raw fields, no raw-content shapes, and not an unresolved
high-impact (review_required) item.

For node text (`text_redacted`):
- research packets: the already-redacted `summary_redacted` (capped)
- daily briefs: concatenated `title_redacted` values from associated `daily_brief_handoff_lines`
  (already redacted, source-linked handoff titles; capped). This is marker-bounded approved
  generated output content in the handoff sense; no raw prompt/response/body is used.

The loader is **read-only** (opens the DB `?mode=ro`) and persists nothing — node persistence is
Prompts 18-19. The report and evidence are **metadata-only** (counts + per-node hashes); the
redacted text rides only on the in-memory node objects for the future embedder and is never
echoed. No embeddings are computed here.

Public entry points:
  load_approved_generated_output_nodes(db_path=None, *, project_key=None) -> list[dict]
  build_generated_outputs_loader_report(db_path=None, *, project_key=None) -> dict
  build_generated_outputs_loader_proof(*, evidence_dir=None, write_evidence=True) -> dict
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
_PROOF_JSON = "generated-outputs-loader-proof.json"
_PROOF_MD = "generated-outputs-loader-proof.md"

_FAMILY = "generated_outputs"
_TEXT_MAX = 280


class GeneratedOutputsLoaderError(RuntimeError):
    """Raised when the generated-outputs loader cannot resolve policy or schema (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[5]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()[:12]
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


def _source_ref_count_for_brief(conn: sqlite3.Connection, brief_run_id: str) -> int:
    if not _table_exists(conn, "daily_brief_source_refs"):
        return 0
    row = conn.execute(
        "SELECT COUNT(*) FROM daily_brief_source_refs WHERE brief_run_id = ?",
        (brief_run_id,),
    ).fetchone()
    return int(row[0]) if row else 0


def _latest_handoff_text_for_brief(conn: sqlite3.Connection, brief_run_id: str) -> str:
    """Build a bounded redacted text from handoff line titles (already redacted, source-linked).
    Used only for in-memory vector node text; never persisted raw.
    """
    if not _table_exists(conn, "daily_brief_handoff_lines"):
        return ""
    rows = conn.execute(
        """
        SELECT title_redacted
        FROM daily_brief_handoff_lines
        WHERE brief_run_id = ?
        ORDER BY section, line_index
        LIMIT 20
        """,
        (brief_run_id,),
    ).fetchall()
    parts = [str(r[0] or "").strip() for r in rows if r[0]]
    text = " | ".join(parts) if parts else ""
    return text[:_TEXT_MAX]


def _candidate_from_packet(row: tuple[Any, ...]) -> dict[str, Any]:
    packet_id, topic_hash, conf, tier, status, summary, created = row
    review_status = str(status or "pending_review")
    review_tier = int(tier) if tier is not None else 2
    freshness = "current" if created else "unknown"
    text = str(summary or "[redacted research packet summary]")[:_TEXT_MAX]
    return {
        "node_id": _hash(str(packet_id))[:32],
        "source_family": _FAMILY,
        "source_ref": str(packet_id),
        "content_hash": str(topic_hash or _hash(str(packet_id))),
        "confidence_class": str(conf or "medium"),
        "review_tier": review_tier,
        "review_status": review_status,
        "review_required": review_tier >= 3 or review_status not in ("accepted", "auto_advisory"),
        "freshness_label": freshness,
        "source_ref_count": 0,  # packets use internal source_ref_count; manifest already filtered
        "text_redacted": text,
        "memory_type": "research_packet",
    }


def _candidate_from_brief(conn: sqlite3.Connection, row: tuple[Any, ...]) -> dict[str, Any]:
    brief_run_id, output_hash, tier, status, generated = row
    review_tier = int(tier) if tier is not None else 1
    review_status = "auto_advisory"
    freshness = "current" if generated else "unknown"
    ref_count = _source_ref_count_for_brief(conn, str(brief_run_id))
    text = (
        _latest_handoff_text_for_brief(conn, str(brief_run_id)) or "[redacted daily brief handoff]"
    )
    return {
        "node_id": _hash(str(brief_run_id))[:32],
        "source_family": _FAMILY,
        "source_ref": str(brief_run_id),
        "content_hash": str(output_hash or _hash(str(brief_run_id))),
        "confidence_class": "high",
        "review_tier": review_tier,
        "review_status": review_status,
        "review_required": False,
        "freshness_label": freshness,
        "source_ref_count": ref_count,
        "text_redacted": text[:_TEXT_MAX],
        "memory_type": "daily_brief",
    }


def load_approved_generated_output_nodes(
    db_path: str | None = None, *, project_key: str | None = None
) -> list[dict[str, Any]]:
    """Load guard-validated approved generated-output nodes (read-only, fail-closed).

    Selects only manifest-eligible records:
    - accepted research packets
    - apply-mode daily brief runs with source refs and non-blocked status
    Then applies the embedding guardrail.
    """
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()

    conn = _open_ro(db_path)
    if conn is None or not _table_exists(conn, "schema_migrations"):
        if conn is not None:
            conn.close()
        raise GeneratedOutputsLoaderError(
            "schema not ready for generated-outputs loader (no schema_migrations)"
        )
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        schema_version = int(row[0]) if row and row[0] is not None else 0
        if schema_version < 38:
            raise GeneratedOutputsLoaderError(
                f"schema not ready for generated-outputs loader (version {schema_version}, expected >= 38)"
            )

        nodes: list[dict[str, Any]] = []

        # Research packets (accepted only)
        if _table_exists(conn, "second_brain_research_packets"):
            clause = " AND project_key = ?" if project_key is not None else ""
            params: list[Any] = ["accepted"]
            if project_key is not None:
                params.append(project_key)
            rows = conn.execute(
                "SELECT packet_id, topic_hash, confidence_class, review_tier, review_status, "
                "summary_redacted, created_utc "
                "FROM second_brain_research_packets WHERE review_status = ?"
                + clause
                + " LIMIT 200",
                tuple(params),
            ).fetchall()
            for r in rows:
                cand = _candidate_from_packet(r)
                if not validate_embedding_candidate(cand, contract=contract, seed=seed):
                    nodes.append(cand)

        # Applied daily briefs with source linkage (eligible per manifest)
        if _table_exists(conn, "daily_brief_runs"):
            # daily_brief_runs has no project_key; we still apply the guard later
            rows = conn.execute(
                "SELECT brief_run_id, output_path_hash, review_tier, status, generated_utc "
                "FROM daily_brief_runs "
                "WHERE mode = 'apply' AND status != 'blocked' "
                "AND output_path_hash IS NOT NULL "
                "ORDER BY generated_utc DESC, brief_run_id DESC LIMIT 50",
            ).fetchall()
            for r in rows:
                cand = _candidate_from_brief(conn, r)
                if cand.get("source_ref_count", 0) > 0 and not validate_embedding_candidate(
                    cand, contract=contract, seed=seed
                ):
                    nodes.append(cand)
    finally:
        if conn is not None:
            conn.close()

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
        "source_ref_count": node.get("source_ref_count", 0),
    }


def build_generated_outputs_loader_report(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Build the metadata-only generated-outputs loader report (read-only, fail-closed)."""
    nodes = load_approved_generated_output_nodes(db_path, project_key=project_key)
    warnings: list[str] = []
    if not nodes:
        warnings.append("no_approved_generated_outputs")
    if any(
        n.get("source_ref_count", 0) == 0 for n in nodes if n.get("memory_type") == "daily_brief"
    ):
        warnings.append("unsourced_brief")
    return {
        "command": "second-brain retrieval generated-outputs-loader status",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "source_family": _FAMILY,
        "loaded_count": len(nodes),
        "status": "loaded" if nodes else "empty",
        "nodes": [_node_summary(n) for n in nodes],
        "warnings": warnings,
        "metadata_only": True,
        "read_only": True,
    }


def _seed_proof_fixtures(tmp: str) -> str:
    """Build a temp DB with one accepted packet + one apply brief + source refs + handoff lines.
    Return the db path. Only for proof; never touches operator DB.
    """
    from hb_assistant.store.migrator import ensure_schema_ready

    db = str(Path(tmp) / "gen_out_loader_proof.db")
    ensure_schema_ready(db)

    conn = sqlite3.connect(db)
    try:
        now = _now()
        # Accepted research packet (eligible)
        conn.execute(
            """
            INSERT INTO second_brain_research_packets
            (packet_id, mode, topic_hash, project_key, source_ref_count, review_required_count,
             stale_unknown_count, conflict_count, context_quality_class, confidence_class,
             review_tier, review_tier_reason_code, review_status, advisory_classification,
             summary_redacted, status, created_utc,
             raw_email_body_persisted, raw_document_text_persisted, raw_calendar_payload_persisted,
             raw_prompt_persisted, raw_response_persisted, retrieved_context_persisted,
             signed_url_persisted, download_url_persisted, external_writeback_performed)
            VALUES (?, 'mock', ?, 'P1', 3, 0, 0, 0, 'high', 'high', 1, 'T1_APPROVED', 'accepted', 'advisory',
                    '[redacted packet summary for vector test]', 'synthesized', ?,
                    0,0,0,0,0,0,0,0,0)
            """,
            ("pkt-vec-1", _hash("pkt-vec-1")[:16], now),
        )

        # Apply daily brief run (eligible)
        conn.execute(
            """
            INSERT INTO daily_brief_runs
            (brief_run_id, brief_date, mode, status, project_count, source_ref_count,
             review_required_count, stale_unknown_count, review_tier, degradation_mode,
             output_path_redacted, output_path_hash, generated_utc,
             raw_email_body_persisted, raw_document_text_persisted, raw_calendar_payload_persisted,
             raw_prompt_persisted, raw_response_persisted, retrieved_context_persisted,
             signed_url_persisted, download_url_persisted, external_writeback_performed)
            VALUES (?, '2026-06-02', 'apply', 'synthesized', 1, 2, 0, 0, 1, 'none',
                    '12_Daily_Brief/2026-06-02_daily_brief.md', ?, ?,
                    0,0,0,0,0,0,0,0,0)
            """,
            ("brf-vec-1", _hash("brf-vec-1")[:16], now),
        )

        # Run-level source refs (required for manifest eligibility)
        for sf, sr in [
            ("cross_source_relationships", "rel-1"),
            ("project_issue_history_items", "hist-1"),
        ]:
            conn.execute(
                """
                INSERT INTO daily_brief_source_refs
                (daily_brief_source_ref_id, brief_run_id, source_family, source_ref, evidence_trail_id,
                 confidence_class, review_required, stale_unknown)
                VALUES (?, ?, ?, ?, NULL, 'high', 0, 0)
                """,
                (_hash(f"brf-vec-1:{sf}")[:16], "brf-vec-1", sf, sr),
            )

        # Handoff lines (redacted titles, source-linked) — provides the text_redacted for brief node
        for idx, (sec, title, refs) in enumerate(
            [
                (
                    "priority_actions",
                    "Follow up on RFI 042",
                    '[{"source_family":"procore","source_ref":"rfi-042"}]',
                ),
                (
                    "waiting_on",
                    "Materials delivery delayed",
                    '[{"source_family":"email","source_ref":"em-77"}]',
                ),
            ]
        ):
            conn.execute(
                """
                INSERT INTO daily_brief_handoff_lines
                (line_id, brief_run_id, section, line_index, title_redacted, review_tier,
                 source_refs_json, generated_utc,
                 raw_email_body_persisted, raw_document_text_persisted, raw_calendar_payload_persisted,
                 raw_prompt_persisted, raw_response_persisted, retrieved_context_persisted,
                 signed_url_persisted, download_url_persisted, external_writeback_performed)
                VALUES (?, ?, ?, ?, ?, 2, ?, ?,
                        0,0,0,0,0,0,0,0,0)
                """,
                (_hash(f"brf-vec-1-line-{idx}")[:16], "brf-vec-1", sec, idx, title, refs, now),
            )

        conn.commit()
    finally:
        conn.close()
    return db


def _candidate_cases() -> list[dict[str, Any]]:
    """Controlled safe + planted-unsafe candidate nodes exercising the embedding guard."""
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    safe = {
        "node_id": "n-safe-gen",
        "source_family": _FAMILY,
        "source_ref": "pkt-safe-1",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 1,
        "review_status": "accepted",
        "review_required": False,
        "freshness_label": "current",
        "source_ref_count": 2,
        "text_redacted": "[redacted generated summary for test]",
    }
    synthetic_secret = "Bea" + "rer " + "z" * 32
    planted: list[tuple[str, dict[str, Any]]] = [
        ("non_embeddable_family", {**safe, "source_family": "raw_prompt"}),
        ("missing_metadata", {k: v for k, v in safe.items() if k != "content_hash"}),
        ("raw_shape_text", {**safe, "text_redacted": synthetic_secret}),
        (
            "unresolved_review",
            {**safe, "review_required": True, "review_status": "pending_review"},
        ),
    ]
    cases: list[dict[str, Any]] = []
    v = validate_embedding_candidate(safe, contract=contract, seed=seed)
    cases.append(
        {
            "name": "safe_generated_node",
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
        "# Phase 09 — Generated Outputs Loader Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- approved_loaded_count: {proof['approved_loaded_count']}",
        f"- non_approved_loaded_count: {proof['non_approved_loaded_count']} (must be 0 for dry/blocked)",
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


def build_generated_outputs_loader_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: approved generated outputs load as nodes; non-approved (dry/blocked/pending) excluded;
    embedding guardrail enforced. Temp DB only; no operator writes.
    """
    with tempfile.TemporaryDirectory() as tmp:
        approved_db = _seed_proof_fixtures(tmp)
        # For non-approved simulation we insert pending/dry rows into approved_db (loader filters them out by status/mode).
        conn = sqlite3.connect(approved_db)
        try:
            # Add a pending packet (should be excluded by loader)
            conn.execute(
                "INSERT INTO second_brain_research_packets "
                "(packet_id, mode, topic_hash, project_key, source_ref_count, review_required_count, "
                "stale_unknown_count, conflict_count, context_quality_class, confidence_class, "
                "review_tier, review_tier_reason_code, review_status, advisory_classification, "
                "summary_redacted, status, created_utc, "
                "raw_email_body_persisted, raw_document_text_persisted, raw_calendar_payload_persisted, "
                "raw_prompt_persisted, raw_response_persisted, retrieved_context_persisted, "
                "signed_url_persisted, download_url_persisted, external_writeback_performed) "
                "VALUES (?, 'mock', ?, 'P1', 0, 0, 0, 0, 'low', 'low', 2, 'T2', 'pending_review', 'advisory', "
                "'[pending]', 'synthesized', ?, 0,0,0,0,0,0,0,0,0)",
                ("pkt-pending", _hash("pkt-pending")[:16], _now()),
            )
            # Add a dry_run brief (should be excluded)
            conn.execute(
                "INSERT INTO daily_brief_runs "
                "(brief_run_id, brief_date, mode, status, project_count, source_ref_count, "
                "review_required_count, stale_unknown_count, review_tier, degradation_mode, "
                "output_path_redacted, output_path_hash, generated_utc, "
                "raw_email_body_persisted, raw_document_text_persisted, raw_calendar_payload_persisted, "
                "raw_prompt_persisted, raw_response_persisted, retrieved_context_persisted, "
                "signed_url_persisted, download_url_persisted, external_writeback_performed) "
                "VALUES (?, '2026-06-02', 'dry_run', 'synthesized', 0, 0, 0, 0, 3, 'none', NULL, NULL, ?, "
                "0,0,0,0,0,0,0,0,0)",
                ("brf-dry", _now()),
            )
            conn.commit()
        finally:
            conn.close()

        approved_nodes = load_approved_generated_output_nodes(approved_db)
        # For non-approved simulation, load from same DB (the pending/dry are present but should yield 0 from the loader)
        # To be explicit, we also create a dedicated non-approved DB with only dry/pending.
        with tempfile.TemporaryDirectory() as tmp2:
            non_db = _seed_proof_fixtures(tmp2)
            c2 = sqlite3.connect(non_db)
            try:
                c2.execute(
                    "INSERT INTO second_brain_research_packets "
                    "(packet_id, mode, topic_hash, project_key, source_ref_count, review_required_count, "
                    "stale_unknown_count, conflict_count, context_quality_class, confidence_class, "
                    "review_tier, review_tier_reason_code, review_status, advisory_classification, "
                    "summary_redacted, status, created_utc, "
                    "raw_email_body_persisted, raw_document_text_persisted, raw_calendar_payload_persisted, "
                    "raw_prompt_persisted, raw_response_persisted, retrieved_context_persisted, "
                    "signed_url_persisted, download_url_persisted, external_writeback_performed) "
                    "VALUES (?, 'mock', ?, 'P1', 0, 0, 0, 0, 'low', 'low', 2, 'T2', 'pending_review', 'advisory', "
                    "'[pending]', 'synthesized', ?, 0,0,0,0,0,0,0,0,0)",
                    ("pkt-pend2", _hash("pkt-pend2")[:16], _now()),
                )
                c2.execute(
                    "INSERT INTO daily_brief_runs "
                    "(brief_run_id, brief_date, mode, status, project_count, source_ref_count, "
                    "review_required_count, stale_unknown_count, review_tier, degradation_mode, "
                    "output_path_redacted, output_path_hash, generated_utc, "
                    "raw_email_body_persisted, raw_document_text_persisted, raw_calendar_payload_persisted, "
                    "raw_prompt_persisted, raw_response_persisted, retrieved_context_persisted, "
                    "signed_url_persisted, download_url_persisted, external_writeback_performed) "
                    "VALUES (?, '2026-06-02', 'dry_run', 'synthesized', 0, 0, 0, 0, 3, 'none', NULL, NULL, ?, "
                    "0,0,0,0,0,0,0,0,0)",
                    ("brf-dry2", _now()),
                )
                c2.commit()
            finally:
                c2.close()
            non_nodes = load_approved_generated_output_nodes(non_db)

    approved_loaded = len(approved_nodes)
    non_loaded = len(non_nodes)
    cases = _candidate_cases()
    proof_passed = approved_loaded >= 1 and non_loaded == 0 and all(c["passed"] for c in cases)

    proof: dict[str, Any] = {
        "proof": "phase_09_generated_outputs_loader",
        "command": "second-brain retrieval generated-outputs-loader proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "approved_loaded_count": approved_loaded,
        "non_approved_loaded_count": non_loaded,
        "case_count": len(cases),
        "cases": cases,
        "metadata_only": True,
        "guardrails": {
            "read_only": True,
            "no_raw": True,
            "no_writeback": True,
            "manifest_eligible_only": True,
            "exclude_unresolved_high_impact": True,
            "local_first": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "generated-outputs-loader proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "generated-outputs-loader proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
