"""V120 — expand manifest entry classification CHECK for gateway proxy classes.

SQLite cannot widen CHECK constraints in place; rebuild ``pa_tool_manifest_entries``.
"""

from __future__ import annotations

from .pa_client_tool_manifest_tables import (
    READ_WRITE_CLASS_VALUES,
    SAFETY_CLASS_VALUES,
    TOOL_CLASS_VALUES,
    _csv,
)

V120_MANIFEST_ENTRY_CLASSIFICATION_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE pa_tool_manifest_entries_v120 (
      manifest_entry_id TEXT PRIMARY KEY,
      manifest_id TEXT NOT NULL,
      tool_name TEXT NOT NULL,
      tool_group TEXT,
      tool_class TEXT NOT NULL CHECK(tool_class IN ({_csv(TOOL_CLASS_VALUES)})),
      safety_class TEXT NOT NULL CHECK(safety_class IN ({_csv(SAFETY_CLASS_VALUES)})),
      read_write_class TEXT NOT NULL CHECK(read_write_class IN ({_csv(READ_WRITE_CLASS_VALUES)})),
      preferred_for_json TEXT,
      avoid_when_json TEXT,
      required_args_json TEXT,
      optional_args_json TEXT,
      limits_json TEXT,
      workflow_roles_json TEXT,
      replacement_tools_json TEXT,
      common_failure_modes_json TEXT,
      examples_json TEXT,
      last_verified_at TEXT,
      freshness_state TEXT
    )
    """,
    """
    INSERT INTO pa_tool_manifest_entries_v120
    SELECT * FROM pa_tool_manifest_entries
    """,
    "DROP TABLE pa_tool_manifest_entries",
    "ALTER TABLE pa_tool_manifest_entries_v120 RENAME TO pa_tool_manifest_entries",
    "CREATE INDEX IF NOT EXISTS idx_pa_tool_manifest_entries_manifest "
    "ON pa_tool_manifest_entries(manifest_id, tool_name)",
]