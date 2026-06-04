"""Phase 09 Prompt 04 — MCP runtime receipt & denial smoke proof (read-only).

Verifies that an allowed/denied MCP smoke run has persisted **metadata-only** receipts to a
chosen database with no raw payloads: at least one allowed tool-call receipt and one denial
receipt exist, every no-raw / no-writeback ``CHECK(... = 0)`` guard column on both receipt
tables sums to zero, the receipt ``decision`` values are well-formed (allowed / denied),
every denial carries a reason code, and the safe text columns hold no forbidden raw-content
shape. The structural no-raw / no-writeback attestations of the receipt schema are reused
from :mod:`.proof`.

Read-only — opens the database read-only and never writes. Database-path agnostic so it can
run over a controlled proof DB, the operator DB, or a temporary test DB.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from .proof import (
    _GUARD_COLUMNS,
    _guards_all_zero,
    _receipts_no_raw,
    _receipts_no_writeback,
)
from .registry import load_allowed_tools

_TOOL_CALL_TABLE = "second_brain_mcp_tool_call_receipts"
_DENIAL_TABLE = "second_brain_mcp_denial_receipts"

# Safe (enum / name / hash) columns scanned for forbidden raw-content shapes.
_SCAN_COLUMNS: dict[str, tuple[str, ...]] = {
    _TOOL_CALL_TABLE: ("tool_name", "workflow_wrapper", "output_classification"),
    _DENIAL_TABLE: ("requested_action", "denial_reason_code"),
}

# Forbidden raw-content value shapes (never echo a match — only the table.column).
_FORBIDDEN = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY"
    r"|Bearer [A-Za-z0-9._-]{20,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"
    r"|[?&](sig|sv|se|token)=[A-Za-z0-9%._-]{16,}"
)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _schema_version(conn: sqlite3.Connection) -> int | None:
    if not _table_exists(conn, "schema_migrations"):
        return None
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0]) if row and row[0] is not None else None


def build_mcp_receipt_smoke_proof(db_path: str | None = None) -> dict[str, Any]:
    """Build the read-only MCP receipt-smoke proof.

    Returns a structured dict with allowed / denial receipt counts, per-table guard-column
    results (all must be 0), decision and reason-code checks, a forbidden-pattern scan, the
    reused structural no-raw / no-writeback attestations, and the ``populated`` /
    ``proof_passed`` verdicts. Never writes.
    """
    resolved = db_path or str(PathPolicy().get_db_path())
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        schema_version = _schema_version(conn)
        allowed_names = set(load_allowed_tools())

        missing_tables = [
            t for t in (_TOOL_CALL_TABLE, _DENIAL_TABLE) if not _table_exists(conn, t)
        ]
        if missing_tables:
            return {
                "proof": "phase_09_mcp_receipt_smoke",
                "schema_version": schema_version,
                "schema_version_expected": LATEST_SCHEMA_VERSION,
                "populated": False,
                "proof_passed": False,
                "missing_tables": missing_tables,
                "allowed_receipt_count": 0,
                "denial_receipt_count": 0,
            }

        allowed_count = int(conn.execute(f"SELECT COUNT(*) FROM {_TOOL_CALL_TABLE}").fetchone()[0])
        denial_count = int(conn.execute(f"SELECT COUNT(*) FROM {_DENIAL_TABLE}").fetchone()[0])

        guards_tool_call = _guards_all_zero(conn, _TOOL_CALL_TABLE)
        guards_denial = _guards_all_zero(conn, _DENIAL_TABLE)
        guard_violation = not (guards_tool_call and guards_denial)

        # Decision well-formedness.
        tool_call_decisions = {
            r[0] for r in conn.execute(f"SELECT DISTINCT decision FROM {_TOOL_CALL_TABLE}")
        }
        denial_decisions = {
            r[0] for r in conn.execute(f"SELECT DISTINCT decision FROM {_DENIAL_TABLE}")
        }
        tool_call_decisions_ok = tool_call_decisions <= {"allowed"}
        denial_decisions_ok = denial_decisions <= {"denied"}

        # Every allowed receipt names a tool in the allowed registry.
        tool_names = {
            r[0] for r in conn.execute(f"SELECT DISTINCT tool_name FROM {_TOOL_CALL_TABLE}")
        }
        allowed_tools_valid = tool_names <= allowed_names

        # Every denial carries a non-empty reason code.
        denials_missing_reason = int(
            conn.execute(
                f"SELECT COUNT(*) FROM {_DENIAL_TABLE} "
                "WHERE denial_reason_code IS NULL OR denial_reason_code = ''"
            ).fetchone()[0]
        )
        reason_codes = sorted(
            r[0] for r in conn.execute(f"SELECT DISTINCT denial_reason_code FROM {_DENIAL_TABLE}")
        )

        # Forbidden raw-content scan over safe text columns (never echo a match value).
        raw_findings: list[str] = []
        for table, scan_cols in _SCAN_COLUMNS.items():
            cols = _columns(conn, table)
            for col in scan_cols:
                if col not in cols:
                    continue
                for (val,) in conn.execute(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL"):
                    if isinstance(val, str) and _FORBIDDEN.search(val):
                        raw_findings.append(f"{table}.{col}")
                        break

        # Reused structural attestations of the receipt schema (database-independent).
        structural_no_raw = _receipts_no_raw()
        structural_no_writeback = _receipts_no_writeback()

        populated = allowed_count >= 1 and denial_count >= 1
        proof_passed = (
            populated
            and not guard_violation
            and tool_call_decisions_ok
            and denial_decisions_ok
            and allowed_tools_valid
            and denials_missing_reason == 0
            and not raw_findings
            and bool(structural_no_raw.get("passed"))
            and bool(structural_no_writeback.get("passed"))
            and schema_version == LATEST_SCHEMA_VERSION
        )

        return {
            "proof": "phase_09_mcp_receipt_smoke",
            "schema_version": schema_version,
            "schema_version_expected": LATEST_SCHEMA_VERSION,
            "populated": populated,
            "proof_passed": proof_passed,
            "missing_tables": [],
            "allowed_receipt_count": allowed_count,
            "denial_receipt_count": denial_count,
            "guard_columns_checked": len(_GUARD_COLUMNS),
            "guard_columns_zero": {
                _TOOL_CALL_TABLE: guards_tool_call,
                _DENIAL_TABLE: guards_denial,
            },
            "tool_call_decisions": sorted(tool_call_decisions),
            "denial_decisions": sorted(denial_decisions),
            "tool_call_decisions_ok": tool_call_decisions_ok,
            "denial_decisions_ok": denial_decisions_ok,
            "allowed_tools_valid": allowed_tools_valid,
            "denial_reason_codes": reason_codes,
            "denials_missing_reason": denials_missing_reason,
            "raw_content_findings": raw_findings,
            "structural_no_raw": structural_no_raw,
            "structural_no_writeback": structural_no_writeback,
            "guardrails": {
                "read_only": True,
                "metadata_only": True,
                "no_raw_content": not raw_findings,
                "no_external_writeback": True,
                "deny_first": True,
                "advisory_only": True,
            },
        }
    finally:
        conn.close()
