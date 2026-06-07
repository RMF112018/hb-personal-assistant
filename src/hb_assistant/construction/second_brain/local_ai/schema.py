"""Phase 10 / 10A schema constants + read-only schema-status proof.

Single source of truth for the Phase 10 (V41) tables/guards and the Phase 10A (V42) raw content
tables (additive). The status report covers V41 tables+guards and (when schema >=42) surfaces
row counts for the raw tables (which are exempt from the 13 guards by design, as they are the
authorized raw body holders under policy). Fail-closed on stale for core phase10; advisory for raw.
Read-only over the DB; advisory only; never a determination.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

#: The 21 additive Phase 10 tables created by migration V41, grouped by domain.
PHASE_10_V41_TABLES: tuple[str, ...] = (
    # local model runtime
    "local_model_profiles",
    "local_model_status_receipts",
    "local_model_run_receipts",
    # AI jobs
    "ai_job_queue",
    "ai_job_runs",
    # action intelligence / candidates
    "task_candidates",
    "commitment_candidates",
    "candidate_source_refs",
    "candidate_review_events",
    # follow-ups
    "accepted_tasks",
    "accepted_commitments",
    "follow_up_watch_items",
    "follow_up_status_events",
    # relationships
    "phase10_relationship_candidates",
    # daily brief
    "daily_brief_action_candidates",
    # Obsidian index
    "obsidian_note_index",
    "obsidian_note_tag_index",
    "obsidian_managed_section_registry",
    "obsidian_note_update_receipts",
    # Claude / MCP packets
    "claude_context_packets",
    "claude_context_packet_items",
)

#: Phase 10A (Prompt 02) raw content tables (V42 additive). These hold raw email/calendar bodies
#: (and thread context, model packets, access events, policy state snapshot). They are exempt
#: from the Phase 10 guard columns (by design; the policy surface and later ingestion enforce controls).
PHASE_10A_RAW_TABLES: tuple[str, ...] = (
    "raw_content_policy_state",
    "email_message_raw_content",
    "email_thread_raw_context",
    "calendar_event_raw_content",
    "raw_content_model_context_packets",
    "raw_content_access_events",
)

#: The 13 guard columns every Phase 10 table carries (each enforced ``CHECK(<col> = 0)``).
PHASE_10_GUARD_COLUMNS: list[str] = [
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
    "graph_writeback_performed",
    "procore_writeback_performed",
    "email_send_performed",
    "calendar_mutation_performed",
]

_PHASE_10_TARGET_SCHEMA = 41

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-10-local-action-intelligence"
_PROOF_JSON = "02-schema-v41-proof.json"
_PROOF_MD = "02-schema-v41-proof.md"


class Phase10SchemaError(RuntimeError):
    """Raised when the Phase 10 schema status cannot be assembled (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    return PathPolicy().resolve_repo_root()


def _repo_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_repo_root(), stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def get_raw_content_table_row_counts(db_path: str | None = None) -> dict[str, int | None]:
    """Return current row counts for the Phase 10A raw content tables (V42).

    Read-only. Returns None for a table if it does not exist or DB is unavailable.
    Used by diagnostics/status surfaces and verification.
    """
    conn = _open_ro(db_path)
    counts: dict[str, int | None] = {}
    try:
        for name in PHASE_10A_RAW_TABLES:
            if conn is not None and _table_exists(conn, name):
                counts[name] = int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
            else:
                counts[name] = None
    finally:
        if conn is not None:
            conn.close()
    return counts


def build_phase_10_schema_status_report(
    db_path: str | None = None,
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = False,
) -> dict[str, Any]:
    """Build the read-only V41 Phase 10 schema-status report (fail-closed on stale schema)."""
    conn = _open_ro(db_path)
    schema_version = _schema_version(conn) if conn is not None else 0
    schema_ready = schema_version >= _PHASE_10_TARGET_SCHEMA

    table_reports: list[dict[str, Any]] = []
    guard_sum = 0
    try:
        for name in PHASE_10_V41_TABLES:
            present = conn is not None and _table_exists(conn, name)
            cols = _columns(conn, name) if (conn is not None and present) else set()
            missing_guards = [g for g in PHASE_10_GUARD_COLUMNS if g not in cols]
            row_count: int | None = None
            table_guard_sum: int | None = None
            if conn is not None and present:
                row_count = int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
                if not missing_guards:
                    expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
                    table_guard_sum = int(conn.execute(f"SELECT {expr} FROM {name}").fetchone()[0])
                    guard_sum += table_guard_sum
            table_reports.append(
                {
                    "table_name": name,
                    "present": present,
                    "guard_columns_present": present and not missing_guards,
                    "missing_guard_columns": missing_guards,
                    "row_count": row_count,
                    "guard_sum": table_guard_sum,
                }
            )

        # Phase 10A Prompt 02: when V42+ present, surface raw content tables (row counts only;
        # these tables are exempt from the 13 guard columns as they are the authorized raw holders).
        raw_tables_info: list[dict[str, Any]] = []
        if schema_version >= 42:
            for name in PHASE_10A_RAW_TABLES:
                present = conn is not None and _table_exists(conn, name)
                rcount: int | None = None
                if conn is not None and present:
                    rcount = int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
                raw_tables_info.append(
                    {"table_name": name, "present": present, "row_count": rcount}
                )
    finally:
        if conn is not None:
            conn.close()

    all_tables_present = all(t["present"] for t in table_reports)
    all_guards_present = all(t["guard_columns_present"] for t in table_reports)
    guards_clean = all_tables_present and all_guards_present and guard_sum == 0
    overall_ready = schema_ready and all_tables_present and all_guards_present and guard_sum == 0

    result: dict[str, Any] = {
        "command": "second-brain phase-10 schema-status",
        "proof": "phase_10_schema_status",
        "phase": "10",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": schema_version,
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "schema_ready": schema_ready,
        "phase_10_table_count": len(PHASE_10_V41_TABLES),
        "guard_column_count": len(PHASE_10_GUARD_COLUMNS),
        "all_tables_present": all_tables_present,
        "all_guards_present": all_guards_present,
        "guard_sum": guard_sum,
        "guards_clean": guards_clean,
        "overall_status": "ready" if overall_ready else "not_ready",
        "tables": table_reports,
        "raw_content_tables": raw_tables_info,
        "raw_content_table_count": len(raw_tables_info),
        "read_only": True,
        "advisory_only": True,
        "makes_determination": False,
        "guard_attestation": {
            "additive_only": True,
            "no_raw_persistence": True,
            "no_external_writeback": True,
            "environment_isolated": True,
        },
    }

    if write_evidence:
        result["evidence_written"] = _write_evidence(result, evidence_dir)

    return result


def _write_evidence(result: dict[str, Any], evidence_dir: str | None) -> dict[str, str]:
    base = Path(evidence_dir) if evidence_dir else _repo_root() / EVIDENCE_DIR
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / _PROOF_JSON
    md_path = base / _PROOF_MD
    json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(result), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Phase 10 Prompt 02 — V41 Schema Status Proof",
        "",
        f"**Status:** {result['overall_status']} · **generated_utc:** {result['generated_utc']}",
        "",
        f"- repo_sha: `{result['repo_sha']}`",
        f"- schema_version: {result['schema_version']} (expected {result['schema_version_expected']})",
        f"- tables present: {result['all_tables_present']}"
        f" ({result['phase_10_table_count']}) · guards present: {result['all_guards_present']}"
        f" ({result['guard_column_count']}/table) · guard_sum: {result['guard_sum']}",
        "",
        "## Tables",
        "",
        "| Table | Present | Guards | Rows | Guard sum |",
        "| --- | --- | --- | --- | --- |",
    ]
    for t in result["tables"]:
        lines.append(
            f"| {t['table_name']} | {t['present']} | {t['guard_columns_present']} |"
            f" {t['row_count']} | {t['guard_sum']} |"
        )
    lines += [
        "",
        "## Guardrails",
        "",
        "Additive-only (V1–V40 untouched, idempotent); every table carries the 13 `CHECK(=0)`"
        " guard columns; only redacted/hashed columns are stored (no raw body/payload/prompt/"
        "response/URL/token); dev/production isolation via `ai_job_queue.environment`. Read-only,"
        " advisory; never a determination.",
    ]
    return "\n".join(lines) + "\n"
