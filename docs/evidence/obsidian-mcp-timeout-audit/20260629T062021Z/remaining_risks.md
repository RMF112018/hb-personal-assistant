# Remaining Risks / Watch Items

- **Abandoned worker thread on timeout.** `abandon_on_cancel=True` frees the event loop immediately but
  cannot kill the stuck thread; it runs to completion in the background. Acceptable: the server is
  `stateless_http` (each request gets fresh threads) and writes are atomic (`tempfile`+`os.replace`), so
  a timed-out write cannot corrupt the target. If stalls became frequent, abandoned threads could
  accumulate — watch thread count if `tool_timeout` recurs; the real fix in that case is to address the
  underlying stalled I/O, not the guard.
- **`to_thread` + request contextvar.** ctx/scope/principal resolution must stay on the event loop; the
  offloaded lambda never touches `ctx`. Guarded by `test_insufficient_scope_rejected_before_offload`
  (enforcement happens before any thread is spawned).
- **Exact environmental stall trigger not pinned.** The guard fixes the failure mode regardless of
  trigger. If `tool_timeout` shows up in the live logs for a *narrow*-scope `search_vault` or a small
  `create_note`, that is new signal worth investigating (it would mean a genuine OS/filesystem stall on
  the vault path, e.g. a sync daemon) — the diagnostics now make that visible (elapsed_ms, path_scope).
- **Default 30 s budget.** Chosen above a legitimate whole-vault scan and below Grok's client timeout.
  If a legitimate large `vault_map`/curation scan exceeds 30 s it will now return `tool_timeout`; raise
  `tool_timeout_seconds` via the settings API if that occurs.
- **Stale-branch operational defect.** The live `:8000` was running pre-expansion code. It must be
  restarted from the merged-main + fix code (this worktree) for the fix and the full 38-tool registry to
  take effect. Restarting ends the current schedule-hub dev session (Bobby authorized).
- **`api.py` pre-existing lint.** `api.py` carries 37 pre-existing ruff findings on `origin/main`
  unrelated to this change; not touched.
- **Not committed.** Left uncommitted on the feature branch pending Bobby's explicit authorization.
