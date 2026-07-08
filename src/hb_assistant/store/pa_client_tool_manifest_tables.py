"""V112 (part 2) — Client Tool Operating Manifest (N8C-23).

A first-class, versioned control-plane artifact that tells connected clients which tool to use, when, in
what sequence, what NOT to do, and how fresh the routing map is. The manifest is a read/advisory surface;
regenerating and WRITING it to the vault follows the same staged-review pattern as artifact promotion
(``pa_tool_manifest_refresh_proposals`` stages a diff; a server-minted operator approval + receipt is
required to materialize). Silent manifest rewrite is prohibited. All tables ship EMPTY.
"""

from __future__ import annotations


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# Manifest staleness posture (Part 11.9).
STALENESS_STATE_VALUES: tuple[str, ...] = (
    "fresh",
    "review_due",
    "stale",
    "tool_surface_changed",
    "routing_conflict",
    "requires_operator_review",
)

MANIFEST_STATUS_VALUES: tuple[str, ...] = (
    "draft",
    "active",
    "superseded",
)

# Tool classification (Part 11.2).
TOOL_CLASS_VALUES: tuple[str, ...] = (
    "read_only_retrieval",
    "read_only_status",
    "read_only_review",
    "advisory_routing",
    "staged_write",
    "canonical_promotion",
    "system_receipt",
    "manifest_lookup",
    "legacy_low_level",
    "blocked_or_deprecated",
)

# Read/write classification (Part 11.3).
READ_WRITE_CLASS_VALUES: tuple[str, ...] = (
    "read_only",
    "staged_write",
    "canonical_write",
    "system_write",
    "blocked",
)

# Safety class (Part 11.4).
SAFETY_CLASS_VALUES: tuple[str, ...] = (
    "safe_read",
    "bounded_read",
    "advisory_only",
    "staged_write_requires_review",
    "canonical_promotion_requires_explicit_approval",
    "system_manifest_write",
    "blocked",
)

MANIFEST_REFRESH_STATUS_VALUES: tuple[str, ...] = (
    "staged",
    "approved",
    "promoted",
    "rejected",
)


V112_CLIENT_TOOL_MANIFEST_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS pa_client_tool_manifests (
      manifest_id TEXT PRIMARY KEY,
      manifest_version INTEGER NOT NULL,
      manifest_status TEXT NOT NULL DEFAULT 'active' CHECK(manifest_status IN ({_csv(MANIFEST_STATUS_VALUES)})),
      generated_at TEXT NOT NULL,
      generated_from_runtime_commit TEXT,
      tool_count INTEGER NOT NULL DEFAULT 0,
      workflow_count INTEGER NOT NULL DEFAULT 0,
      mapping_count INTEGER NOT NULL DEFAULT 0,
      staleness_state TEXT NOT NULL DEFAULT 'fresh' CHECK(staleness_state IN ({_csv(STALENESS_STATE_VALUES)})),
      freshness_checked_at TEXT,
      next_review_due_at TEXT,
      review_cadence TEXT,
      checksum TEXT NOT NULL,
      manifest_vault_path TEXT,
      manifest_json_path TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_tool_manifests_version "
    "ON pa_client_tool_manifests(manifest_version, manifest_status)",
    f"""
    CREATE TABLE IF NOT EXISTS pa_tool_manifest_entries (
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
    "CREATE INDEX IF NOT EXISTS idx_pa_tool_manifest_entries_manifest "
    "ON pa_tool_manifest_entries(manifest_id, tool_name)",
    """
    CREATE TABLE IF NOT EXISTS pa_workflow_route_recipes (
      workflow_recipe_id TEXT PRIMARY KEY,
      manifest_id TEXT NOT NULL,
      workflow_name TEXT NOT NULL,
      trigger_phrases_json TEXT,
      description TEXT,
      tool_sequence_json TEXT,
      required_operator_approval_points_json TEXT,
      negative_instructions_json TEXT,
      expected_outputs_json TEXT,
      failure_recovery_json TEXT,
      last_reviewed_at TEXT,
      next_review_due_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_workflow_recipes_manifest "
    "ON pa_workflow_route_recipes(manifest_id, workflow_name)",
    # --- staged manifest refresh proposals (no silent rewrite) ---
    f"""
    CREATE TABLE IF NOT EXISTS pa_tool_manifest_refresh_proposals (
      refresh_proposal_id TEXT PRIMARY KEY,
      base_manifest_id TEXT,
      proposed_manifest_version INTEGER NOT NULL,
      freshness_diff_json TEXT,
      checksum TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'staged'
        CHECK(status IN ({_csv(MANIFEST_REFRESH_STATUS_VALUES)})),
      operator_approval_id TEXT,
      receipt_path TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      promoted_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_manifest_refresh_status "
    "ON pa_tool_manifest_refresh_proposals(status, proposed_manifest_version)",
]
