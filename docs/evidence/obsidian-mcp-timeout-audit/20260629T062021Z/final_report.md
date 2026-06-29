# Final Report — Obsidian MCP Grok Tool-Timeout Audit & Fix

1. **Branch / commit state.** Fix built in isolated worktree `hb-personal-assistant-worktrees/obsidian-mcp-timeout-fix`,
   branch `fix/obsidian-mcp-tool-timeout-guard` off `origin/main` (`97252eae`). Uncommitted.

2. **Runtime process / Python at audit time.** `:8000` PID ran the Homebrew framework Python that backs
   the repo `.venv` (3.14.5), CWD = repo root, `VIRTUAL_ENV` = repo `.venv`. *But* the checkout was on
   `codex/project-schedule-hub-performance` — stale, PR1-only `obsidian_mcp`, not the merged 38-tool main.

3. **PYTHONPATH / import-path.** `PYTHONPATH` = repo `src` (+CFR), harmlessly duplicated; imports resolve
   under the repo `src`. H1 contamination disproven as the cause.

4. **Route / mount.** OAuth metadata/authorize/token routes declared before the catch-all `app.mount("/")`;
   not swallowed.

5. **OAuth / MCP transport.** `json_response=True`, `stateless_http=True`; allowed hosts/origins include
   `127.0.0.1`/`localhost`/`mcp.bobby-fetting.me`/`grok.com`/`x.ai`; `BearerTokenMiddleware` static+OAuth,
   header-only, fast; per-tool scopes via `enforce_tool_scope`.

6. **Direct service timing.** ~1–2 ms for list/search/create — service logic is not slow.

7. **Strict-JSON serialization.** All 38 tool results round-trip strict `json.loads` (no NaN/Inf) over
   `/mcp` — `test_every_tool_result_is_strict_json` (38 cases). No serialization defect.

8. **Local MCP protocol tests.** `initialize → notifications/initialized → tools/list → tools/call`
   exercised for list_directory/read_file/search_vault/create_note/patch_note and all 38 in the strict-JSON
   sweep. A stalled tool returns structured `tool_timeout` while a concurrent light tool still responds.

9. **Pre/post runtime contrast (real /mcp, stalled search_vault 3 s).** PRE-FIX (origin/main): 3.01 s,
   unbounded, no timeout. POST-FIX (timeout=1 s): 1.01 s, structured `tool_timeout`.

10. **Root cause (ranked, evidenced).** H6 — sync `@mcp.tool()` handlers run directly on the single
    event-loop thread (mcp 1.27–1.28, no `to_thread`) with no per-tool timeout, so any stalled vault I/O
    hangs the whole server indefinitely (production log: dispatched, no response). H1/H4/H5/H7 disproven as
    cause. Independent defect: live server on stale branch. Exact stall trigger not pinned (no locks/loops;
    vault fully materialized) — fix is trigger-independent.

11. **Fix.** All 38 closures → `async def`, ctx resolved on the loop, blocking `svc.*` call offloaded via
    `anyio.to_thread.run_sync(call, abandon_on_cancel=True)` under `anyio.fail_after(tool_timeout_seconds)`;
    `TimeoutError` → `ObsidianMcpToolError("tool_timeout")`, unexpected → `internal_error` (no leak);
    redacted `tool_start/end/error` diagnostics. New `tool_timeout_seconds` config (default 30, operator-tunable).

12. **Files changed.** `mcp_app.py`, `config.py`, `construction/analytics/api.py` (one field),
    `tests/test_obsidian_mcp_timeout.py` (new). No changes to tools/service/mutations/pathsafe/oauth_store.

13. **Tests added/updated.** `test_obsidian_mcp_timeout.py` — 42 tests (timeout fast+structured, responsive
    under stall, tool_error diagnostic, no token/content leak, insufficient_scope-before-offload, strict-JSON×38).

14. **Commands run.** See `tests_run.txt`. 42 + 154 passed; ruff/mypy clean on changed obsidian_mcp modules.

15. **Security / guardrail review.** No token/Authorization/content/raw-body logged (allow-list redactor;
    verified by test). Scope enforcement and protected/hidden-path blocking unchanged and run before any
    offload. `internal_error` mapping prevents raw-exception leakage. Atomic writes prevent corruption on
    abandoned-timeout. No secrets committed; state stays outside the repo.

16. **Remaining risks.** See `remaining_risks.md` (abandoned thread on timeout; default 30 s budget;
    stale-branch operational restart; trigger not pinned).

17. **Recommended follow-up.** Restart `:8000` from this worktree (gets the fix + full 38-tool registry);
    run the Grok smoke (search_vault/create_note/patch_note); if `tool_timeout` ever fires for a small/narrow
    call, investigate the vault filesystem (sync daemon) using the new elapsed_ms/path diagnostics.

18. **Commit status.** UNCOMMITTED on the feature branch, pending Bobby's explicit authorization.
