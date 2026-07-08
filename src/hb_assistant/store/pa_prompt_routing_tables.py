"""V114 — Prompt Preflight & Tool Routing durable manifest.

Durable snapshot of the routing source: tool families, prompt workflow recipes, and per-tool routing
entries. These tables let ``hb_mcp_status`` and the freshness guard read the routing manifest durably
rather than only recomputing it from the static seed. All tables are additive and ship EMPTY; rows are
written only by the explicit routing-manifest snapshot path (read-only routing tools never write). There
is deliberately NO route-audit table — route calls are audited by the existing broker audit envelope, so
the preflight surface stays fully read-only.
"""

from __future__ import annotations

# pa_tool_families — one row per routing family (24 seeded).
# pa_prompt_workflow_recipes — one row per workflow recipe (richer than the legacy
#   pa_workflow_route_recipes table; new/additive so back-compat is preserved).
# pa_tool_routing_entries — one row per live tool with its family + read/write + safety class.
V114_PROMPT_ROUTING_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS pa_tool_families (
        family_id TEXT PRIMARY KEY,
        purpose TEXT NOT NULL,
        read_write_class TEXT NOT NULL,
        safety_class TEXT NOT NULL,
        record_json TEXT NOT NULL,
        manifest_version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pa_prompt_workflow_recipes (
        workflow_id TEXT PRIMARY KEY,
        family_id TEXT NOT NULL,
        write_risk TEXT NOT NULL,
        operator_authorization_policy TEXT NOT NULL,
        default_retrieval_layer TEXT NOT NULL,
        record_json TEXT NOT NULL,
        manifest_version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pa_tool_routing_entries (
        tool_name TEXT PRIMARY KEY,
        tool_group TEXT,
        tool_family TEXT NOT NULL,
        read_write_class TEXT NOT NULL,
        safety_class TEXT NOT NULL,
        deprecated INTEGER NOT NULL DEFAULT 0,
        record_json TEXT NOT NULL,
        manifest_version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_prompt_workflow_recipes_family ON pa_prompt_workflow_recipes (family_id)",
    "CREATE INDEX IF NOT EXISTS idx_pa_tool_routing_entries_family ON pa_tool_routing_entries (tool_family)",
]

PROMPT_ROUTING_TABLES: tuple[str, ...] = (
    "pa_tool_families",
    "pa_prompt_workflow_recipes",
    "pa_tool_routing_entries",
)
