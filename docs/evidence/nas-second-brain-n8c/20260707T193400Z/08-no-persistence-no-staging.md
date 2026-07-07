# 08 — No Persistence / No Action Staging

Routing and context assembly write NOTHING. See `07-boundaries.md` for the policy block and advisory-only
proof; this note isolates the persistence/staging evidence.

- **No table created / no row written.** After several routes over a migrated DB the `sqlite_master` table
  set is identical, and no table name contains "workflow"
  (`test_nas_mcp_workflows.py::test_no_workflow_persistence_tables_written`). The router opens read-only
  connections; the MCP handler additionally serves from the `mode=ro&immutable=1` snapshot with
  `PRAGMA query_only=ON` (`test_handler_uses_query_only_and_ro_uri`, `test_snapshot_is_read_only`).
- **No workflow run/event/receipt table in the migrator.** `LATEST_SCHEMA_VERSION == 108`;
  `store/migrator.py` defines no `assistant_workflow*` / `workflow_run` / `workflow_event`
  (`test_no_schema_bump`, `test_no_workflow_persistence_table_in_migrator`).
- **`workflow_id` is ephemeral.** A deterministic response id folded from the bounded request; never
  persisted.
- **No action staged.** No task/reminder/email/calendar/agenda/invite/disposition object is created; open
  loops are never closed/reopened/deferred/accepted/rejected. Action staging is the honest N8C-18 deferral
  (`stage_*` capabilities in the registry). AST guards confirm no `record_disposition` / writer call in the
  handlers or broker views.
