# 05 — Route-only / read-only proof

- `_invoke_assistant_workflows` opens the RO snapshot byte-for-byte like the N8C-14 handler:
  `sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)` then
  `conn.execute("PRAGMA query_only=ON")`, threaded via `conn=` into `WorkflowRouter.route`, closed in a
  `finally:`. `_ro_uri` yields `mode=ro&immutable=1`.
- `test_snapshot_is_read_only` — a write on that snapshot raises `sqlite3.OperationalError`.
- `test_handler_uses_query_only_and_ro_uri` — AST-scoped to the handler node: asserts `_ro_uri(...)`,
  `PRAGMA query_only=ON`, and `conn.close()` present.
- `test_handler_calls_no_writer_or_source_read` — AST-scoped to the handler + 4 view helpers: none
  references `upsert_*`, `persist_pack`, `read_source_file`, `reindex`, `build_answer_draft`,
  `record_disposition`, `SourceContentProvider`, or `scan`.
- `assistant_list_workflows` needs no DB at all (returns the static catalog).
