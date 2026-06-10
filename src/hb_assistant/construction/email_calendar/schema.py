"""Email/calendar structured projection DDL, generated from the committed projection
registry (the single source of truth the engine also writes against), plus the static
ingestion-run / coverage / snapshot receipt tables.

Consumed by the V49 migration (mirrors ``procore.projection_registry.build_v47_ddl`` and
``reconcile_column_alters``). ``CREATE TABLE IF NOT EXISTS`` keeps the migration additive
and idempotent; V1-V48 tables are untouched.

Every generated table carries the zero-CHECK guards so a raw body can never be flagged as
emitted to evidence and no external writeback can be recorded at the SQLite layer.
"""

from __future__ import annotations

import sqlite3

from . import projection_registry as reg

PROJECTION_SCHEMA_VERSION = reg.PROJECTION_SCHEMA_VERSION

# Zero-CHECK guards on every structured + receipt table (outbound-leak / writeback fences).
_GUARDS = (
    "raw_body_emitted_to_evidence INTEGER NOT NULL DEFAULT 0 "
    "CHECK(raw_body_emitted_to_evidence = 0)",
    "external_writeback_performed INTEGER NOT NULL DEFAULT 0 "
    "CHECK(external_writeback_performed = 0)",
)

# Columns that must carry INTEGER affinity so flag/count queries (``= 1``) behave.
_INTEGER_NAMES = frozenset(
    {
        "has_attachments",
        "has_join_url",
        "has_recurrence",
        "has_full_body",
        "model_ready",
        "is_inline",
        "recipient_count",
        "attachment_count",
        "attendee_count",
        "message_count",
        "participant_count",
        "number_of_occurrences",
        "pattern_interval",
    }
)
_INTEGER_SUFFIXES = ("_available", "_chars", "_count", "_bytes")


def _col_type(name: str) -> str:
    if name in _INTEGER_NAMES or name.endswith(_INTEGER_SUFFIXES):
        return "INTEGER"
    return "TEXT"


def _dedup(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


# Fixed columns present on every structured PARENT table.
_PARENT_FIXED_HEAD = [
    "projection_id TEXT PRIMARY KEY",
    "raw_row_id TEXT",
    "source_family TEXT NOT NULL",
]
_PARENT_FIXED_TAIL = [
    f"projection_schema_version TEXT NOT NULL DEFAULT '{PROJECTION_SCHEMA_VERSION}'",
    "idempotency_key TEXT",
    "security_scrub_status TEXT NOT NULL DEFAULT 'scrubbed'",
    "is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0, 1))",
    "created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    *_GUARDS,
]

# Fixed columns present on every structured CHILD table.
_CHILD_FIXED_HEAD = [
    "projection_id TEXT PRIMARY KEY",
    "parent_projection_id TEXT NOT NULL",
    "raw_row_id TEXT",
    "source_family TEXT",
    "project_key TEXT",
    "role TEXT",
    "domain TEXT",
    "child_index INTEGER",
    "array_path TEXT",
]
_CHILD_FIXED_TAIL = [
    "source_quality TEXT NOT NULL DEFAULT 'metadata_only'",
    "payload_sidecar_json TEXT",
    "is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0, 1))",
    "created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    *_GUARDS,
]

_PARENT_FIXED_NAMES = frozenset(
    {
        "projection_id",
        "raw_row_id",
        "source_family",
        "projection_schema_version",
        "idempotency_key",
        "security_scrub_status",
        "is_current",
        "created_utc",
        "updated_utc",
        "raw_body_emitted_to_evidence",
        "external_writeback_performed",
    }
)
_CHILD_FIXED_NAMES = frozenset(
    {
        "projection_id",
        "parent_projection_id",
        "raw_row_id",
        "source_family",
        "project_key",
        "role",
        "domain",
        "child_index",
        "array_path",
        "source_quality",
        "payload_sidecar_json",
        "is_current",
        "created_utc",
        "updated_utc",
        "raw_body_emitted_to_evidence",
        "external_writeback_performed",
    }
)


def _primary_ddl(plan: reg.SourceFamilyPlan) -> str:
    curated = _dedup(
        [c for c in plan.required_structured_columns() if c not in _PARENT_FIXED_NAMES]
    )
    lines = list(_PARENT_FIXED_HEAD)
    lines += [f"{c} {_col_type(c)}" for c in curated]
    lines += list(_PARENT_FIXED_TAIL)
    body = ",\n  ".join(lines)
    return f"CREATE TABLE IF NOT EXISTS {plan.structured_table} (\n  {body}\n);"


def _child_ddl(table: str, curated: list[str]) -> str:
    cols = _dedup([c for c in curated if c not in _CHILD_FIXED_NAMES])
    lines = list(_CHILD_FIXED_HEAD)
    lines += [f"{c} {_col_type(c)}" for c in cols]
    lines += list(_CHILD_FIXED_TAIL)
    body = ",\n  ".join(lines)
    return f"CREATE TABLE IF NOT EXISTS {table} (\n  {body}\n);"


def _indexes(table: str, columns: tuple[str, ...]) -> list[str]:
    return [f"CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON {table}({col});" for col in columns]


def build_structured_ddl() -> list[str]:
    """CREATE TABLE/INDEX statements for every structured projection table."""
    statements: list[str] = []
    for plan in reg.PLANS.values():
        statements.append(_primary_ddl(plan))
        statements += _indexes(
            plan.structured_table, ("raw_row_id", "project_key", "source_quality")
        )
        child_cols = plan.required_child_columns()
        # one CREATE per distinct child table (recipients table is shared across to/cc/bcc)
        emitted: set[str] = set()
        for child in plan.child_arrays:
            if child.child_table in emitted:
                continue
            emitted.add(child.child_table)
            statements.append(_child_ddl(child.child_table, child_cols.get(child.child_table, [])))
            statements += _indexes(child.child_table, ("parent_projection_id", "raw_row_id"))
    return statements


# --- static receipt / diagnostic tables -------------------------------------------

_RECEIPT_STATEMENTS = [
    # Bounded raw-ingestion run receipt (counts + source-quality distribution; no bodies).
    """
    CREATE TABLE IF NOT EXISTS email_calendar_raw_ingestion_runs (
      run_id TEXT PRIMARY KEY,
      source_family TEXT NOT NULL CHECK(source_family IN ('email', 'calendar')),
      mode TEXT NOT NULL CHECK(mode IN ('dry_run', 'apply')),
      started_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      completed_utc TEXT,
      items_seen INTEGER NOT NULL DEFAULT 0,
      items_attempted_raw INTEGER NOT NULL DEFAULT 0,
      items_raw_persisted INTEGER NOT NULL DEFAULT 0,
      source_quality_distribution_json TEXT NOT NULL DEFAULT '{}',
      status TEXT NOT NULL DEFAULT 'ok',
      error_redacted TEXT,
      raw_body_emitted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_emitted = 0),
      external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
    );
    """,
    # Source-quality distribution snapshots for diagnostics.
    """
    CREATE TABLE IF NOT EXISTS raw_content_source_quality_snapshots (
      snapshot_id TEXT PRIMARY KEY,
      source_family TEXT NOT NULL,
      raw_table TEXT NOT NULL,
      source_quality TEXT NOT NULL,
      row_count INTEGER NOT NULL DEFAULT 0,
      captured_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    # Projection run receipt (counts + status only).
    """
    CREATE TABLE IF NOT EXISTS email_calendar_projection_runs (
      run_id TEXT PRIMARY KEY,
      source_family TEXT NOT NULL,
      mode TEXT NOT NULL CHECK(mode IN ('dry_run', 'apply')),
      started_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      completed_utc TEXT,
      raw_parent_rows INTEGER NOT NULL DEFAULT 0,
      projected_parent_rows INTEGER NOT NULL DEFAULT 0,
      child_rows_written INTEGER NOT NULL DEFAULT 0,
      skipped_higher_quality INTEGER NOT NULL DEFAULT 0,
      degraded_unmapped INTEGER NOT NULL DEFAULT 0,
      source_quality_distribution_json TEXT NOT NULL DEFAULT '{}',
      status TEXT NOT NULL DEFAULT 'ok',
      error_redacted TEXT,
      raw_body_emitted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_emitted = 0),
      external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
    );
    """,
    # Projection coverage receipt (the completeness proof, counts only).
    """
    CREATE TABLE IF NOT EXISTS email_calendar_projection_coverage (
      coverage_id TEXT PRIMARY KEY,
      run_id TEXT,
      source_family TEXT NOT NULL,
      raw_table TEXT NOT NULL,
      structured_table TEXT NOT NULL,
      raw_parent_rows INTEGER NOT NULL DEFAULT 0,
      projected_parent_rows INTEGER NOT NULL DEFAULT 0,
      unmapped_primary_business_fields INTEGER NOT NULL DEFAULT 0,
      unmapped_nested_business_fields INTEGER NOT NULL DEFAULT 0,
      observed_nested_arrays_without_dest INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL,
      computed_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
]


def build_v49_ddl() -> list[str]:
    """All V49 CREATE TABLE/INDEX statements (structured projection + receipt tables)."""
    return build_structured_ddl() + _RECEIPT_STATEMENTS


# --- additive column reconciliation (mirrors V48) ---------------------------------


def required_columns_by_table() -> dict[str, list[str]]:
    """Map each structured table -> its registry-required curated column set (the columns the
    engine writes that are not fixed standard columns)."""
    out: dict[str, list[str]] = {}
    for plan in reg.PLANS.values():
        out[plan.structured_table] = _dedup(
            [c for c in plan.required_structured_columns() if c not in _PARENT_FIXED_NAMES]
        )
        for table, cols in plan.required_child_columns().items():
            existing = out.setdefault(table, [])
            for c in cols:
                if c not in _CHILD_FIXED_NAMES and c not in existing:
                    existing.append(c)
    return out


def reconcile_column_alters(existing_cols_by_table: dict[str, set[str]]) -> list[str]:
    """``ALTER TABLE … ADD COLUMN`` statements for registry curated columns missing from the
    physical structured tables. Additive + idempotent; only missing columns are added."""
    alters: list[str] = []
    for table, cols in sorted(required_columns_by_table().items()):
        existing = existing_cols_by_table.get(table)
        if existing is None:
            continue
        for col in cols:
            if col not in existing:
                alters.append(f"ALTER TABLE {table} ADD COLUMN {col} {_col_type(col)};")
    return alters


def reconcile_structured_columns(conn: sqlite3.Connection) -> None:
    existing: dict[str, set[str]] = {}
    for table in reg.all_structured_tables():
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if rows:
            existing[table] = {r[1] for r in rows}
    for stmt in reconcile_column_alters(existing):
        conn.execute(stmt)


# --- additive columns on the existing V42 raw tables ------------------------------

# Per-column ALTERs (guarded by PRAGMA table_info in the migrator, like V22/V24).
RAW_TABLE_ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "email_message_raw_content": [
        ("source_quality", "TEXT NOT NULL DEFAULT 'metadata_only'"),
        ("raw_capture_run_id", "TEXT"),
        ("source_record_ref", "TEXT"),
        ("source_record_id", "INTEGER"),
        ("source_updated_at_utc", "TEXT"),
        ("payload_hash", "TEXT"),
        ("raw_content_schema_version", "TEXT NOT NULL DEFAULT 'email_raw_v1'"),
        ("raw_sidecar_json", "TEXT"),
    ],
    "email_thread_raw_context": [
        ("source_quality", "TEXT NOT NULL DEFAULT 'metadata_only'"),
        ("raw_capture_run_id", "TEXT"),
        ("payload_hash", "TEXT"),
        ("raw_content_schema_version", "TEXT NOT NULL DEFAULT 'email_thread_raw_v1'"),
    ],
    "calendar_event_raw_content": [
        ("source_quality", "TEXT NOT NULL DEFAULT 'metadata_only'"),
        ("raw_capture_run_id", "TEXT"),
        ("source_record_ref", "TEXT"),
        ("source_record_id", "INTEGER"),
        ("source_updated_at_utc", "TEXT"),
        ("payload_hash", "TEXT"),
        ("raw_content_schema_version", "TEXT NOT NULL DEFAULT 'calendar_raw_v1'"),
        ("join_url_policy", "TEXT NOT NULL DEFAULT 'local_db_only'"),
        ("raw_sidecar_json", "TEXT"),
    ],
}


def raw_table_column_alters(conn: sqlite3.Connection) -> list[str]:
    """Return guarded ALTER statements for missing provenance/source-quality columns on the
    three V42 raw tables. Only columns absent from the physical table are returned."""
    out: list[str] = []
    for table, cols in RAW_TABLE_ADDED_COLUMNS.items():
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if not rows:
            continue
        existing = {r[1] for r in rows}
        for name, decl in cols:
            if name not in existing:
                out.append(f"ALTER TABLE {table} ADD COLUMN {name} {decl};")
    return out


__all__ = [
    "PROJECTION_SCHEMA_VERSION",
    "RAW_TABLE_ADDED_COLUMNS",
    "build_structured_ddl",
    "build_v49_ddl",
    "raw_table_column_alters",
    "reconcile_column_alters",
    "reconcile_structured_columns",
    "required_columns_by_table",
]
