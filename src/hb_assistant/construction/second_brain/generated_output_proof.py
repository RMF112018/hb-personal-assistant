"""Phase 09 Prompt 03 — generated-output population proof (read-only).

Verifies that the second-brain generated-output tables (research packets, daily-brief
runs + source refs + handoff lines, evaluation runs) hold controlled, source-linked,
guard-clean rows: every no-raw / no-writeback ``CHECK(... = 0)`` guard column sums to
zero, the outputs carry source references and confidence / review-tier labels, and no
forbidden raw-content pattern (PEM, bearer token, JWT, signed/tokenized URL) appears in
the safe text columns.

The function is **read-only** — it opens the database read-only and never writes. It is
deliberately database-path agnostic so it can run over the operator DB, a controlled
proof DB, or a temporary test DB. ``parser_outputs`` is intentionally excluded: it is a
Phase 06A file-extraction artifact, not a second-brain generation surface.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

# Generated-output tables owned by gap G-01 (second-brain generation surfaces).
GENERATED_OUTPUT_TABLES: tuple[str, ...] = (
    "second_brain_research_packets",
    "daily_brief_runs",
    "daily_brief_source_refs",
    "daily_brief_handoff_lines",
    "second_brain_evaluation_runs",
)

# Safe (redacted / structured) text columns scanned for forbidden raw-content shapes.
_SCAN_COLUMNS: dict[str, tuple[str, ...]] = {
    "second_brain_research_packets": ("summary_redacted", "coverage_warnings_json"),
    "daily_brief_runs": ("output_path_redacted",),
    "daily_brief_source_refs": ("source_ref", "source_family"),
    "daily_brief_handoff_lines": ("title_redacted", "source_refs_json"),
    "second_brain_evaluation_runs": ("checklist_json",),
}

# Tables/columns expected to carry source references and confidence/review-tier labels.
_SOURCE_REF_COLUMNS: dict[str, tuple[str, ...]] = {
    "second_brain_research_packets": ("source_ref_count", "retrieval_receipt_id"),
    "daily_brief_runs": ("research_packet_id",),
    "daily_brief_source_refs": ("source_family", "source_ref"),
    "daily_brief_handoff_lines": ("source_refs_json",),
    "second_brain_evaluation_runs": ("research_packet_id",),
}
# Gate on confidence_class (reliably present); review_tier is reported but not gated
# because the evaluation-run review_tier is legitimately nullable.
_CONFIDENCE_COLUMNS: dict[str, tuple[str, ...]] = {
    "second_brain_research_packets": ("confidence_class",),
    "second_brain_evaluation_runs": ("confidence_class",),
}

# Forbidden raw-content value shapes (never echo a match — only the table.column).
_FORBIDDEN = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY"
    r"|Bearer [A-Za-z0-9._-]{20,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"
    r"|[?&](sig|sv|se|token|sig=)=[A-Za-z0-9%._-]{16,}"
    r"|https?://[^\s\"']*[?&](sig|token)=",
)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _guard_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    return [
        c
        for c in cols
        if c.endswith("_persisted") or c.endswith("_performed") or c.endswith("_allowed")
    ]


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _schema_version(conn: sqlite3.Connection) -> int | None:
    if not _table_exists(conn, "schema_migrations"):
        return None
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0]) if row and row[0] is not None else None


def build_generated_output_population_proof(db_path: str | None = None) -> dict[str, Any]:
    """Build the read-only generated-output population proof.

    Returns a structured dict with per-table counts, guard-column sums (all must be 0),
    source-linkage and confidence/review-tier coverage, a forbidden-pattern scan result,
    and the overall ``proof_passed`` / ``populated`` verdicts. Never writes.
    """
    resolved = db_path or str(PathPolicy().get_db_path())
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        schema_version = _schema_version(conn)
        tables: dict[str, Any] = {}
        total_rows = 0
        guard_violation = False
        missing_tables: list[str] = []
        raw_findings: list[str] = []
        source_linked = True
        confidence_present = True

        for table in GENERATED_OUTPUT_TABLES:
            if not _table_exists(conn, table):
                missing_tables.append(table)
                tables[table] = {"present": False}
                continue
            count = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            total_rows += count
            guards = _guard_columns(conn, table)
            guard_sum = 0
            if guards and count:
                expr = "+".join(f"COALESCE(SUM({c}),0)" for c in guards)
                guard_sum = int(conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0])
            if guard_sum != 0:
                guard_violation = True

            # Source-linkage: at least one source-ref column is non-empty on populated rows.
            cols = _columns(conn, table)
            src_cols = [c for c in _SOURCE_REF_COLUMNS.get(table, ()) if c in cols]
            linked_rows = 0
            if count and src_cols:
                where = " OR ".join(
                    f"(IFNULL({c}, '') <> '' AND IFNULL({c}, 0) <> 0)" for c in src_cols
                )
                linked_rows = int(
                    conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
                )
                if linked_rows == 0:
                    source_linked = False

            # Confidence / review-tier presence on populated rows.
            conf_cols = [c for c in _CONFIDENCE_COLUMNS.get(table, ()) if c in cols]
            labelled_rows = 0
            if count and conf_cols:
                where = " AND ".join(f"{c} IS NOT NULL" for c in conf_cols)
                labelled_rows = int(
                    conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
                )
                if labelled_rows == 0:
                    confidence_present = False

            # Forbidden raw-content scan over safe text columns (never echo a match value).
            for col in _SCAN_COLUMNS.get(table, ()):
                if col not in cols:
                    continue
                for (val,) in conn.execute(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL"):
                    if isinstance(val, str) and _FORBIDDEN.search(val):
                        raw_findings.append(f"{table}.{col}")
                        break

            tables[table] = {
                "present": True,
                "row_count": count,
                "guard_columns": len(guards),
                "guard_sum": guard_sum,
                "source_ref_columns": src_cols,
                "source_linked_rows": linked_rows,
                "confidence_columns": conf_cols,
                "confidence_labelled_rows": labelled_rows,
            }

        populated = total_rows > 0 and not missing_tables
        proof_passed = (
            populated
            and not guard_violation
            and not raw_findings
            and source_linked
            and confidence_present
            and schema_version == LATEST_SCHEMA_VERSION
        )
        return {
            "proof": "phase_09_generated_output_population",
            "schema_version": schema_version,
            "schema_version_expected": LATEST_SCHEMA_VERSION,
            "populated": populated,
            "proof_passed": proof_passed,
            "total_rows": total_rows,
            "missing_tables": missing_tables,
            "guard_violation": guard_violation,
            "raw_content_findings": raw_findings,
            "source_linked": source_linked,
            "confidence_present": confidence_present,
            "tables": tables,
            "excluded": {
                "parser_outputs": "Phase 06A file-extraction artifact; not a second-brain "
                "generation surface (classified out of scope)."
            },
            "guardrails": {
                "read_only": True,
                "no_raw_content": not raw_findings,
                "no_external_writeback": True,
                "advisory_only": True,
            },
        }
    finally:
        conn.close()
