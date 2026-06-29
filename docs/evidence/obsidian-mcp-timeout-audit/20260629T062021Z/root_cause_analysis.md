# Obsidian MCP — Grok Tool-Timeout Root Cause Analysis

Date: 2026-06-29 (UTC). Audit + fix worktree: `hb-personal-assistant-worktrees/obsidian-mcp-timeout-fix`
on branch `fix/obsidian-mcp-tool-timeout-guard` off `origin/main` (`97252eae`).

## Symptom

Through the Grok MCP client (`https://mcp.bobby-fetting.me/mcp` → Cloudflare → `localhost:8000`):
`list_directory` and `read_file` work; `search_vault`, `create_note`, `patch_note` time out. Direct
in-process service calls for all three complete in ~1–2 ms.

## Hypotheses — verdicts (evidence-ranked)

- **H1 wrong interpreter / PYTHONPATH contamination — DISPROVEN as cause.** Live process CWD = repo
  root, `VIRTUAL_ENV` = repo `.venv`, `PYTHONPATH` = repo `src` (+CFR, only harmlessly duplicated),
  Python 3.14.5 = the venv's own base; the `ps` framework path is normal for macOS venvs.
  *Independent real defect found:* the live process was running **stale code** — branch
  `codex/project-schedule-hub-performance`, whose `obsidian_mcp` is PR1-only (`ddc6013c`); `origin/main`
  (38 tools) is not an ancestor.
- **H7 transport/envelope — DISPROVEN.** `FastMCP(json_response=True, stateless_http=True)`,
  `allowed_hosts`/`allowed_origins` include `127.0.0.1`/`localhost`/`mcp.bobby-fetting.me`/`grok.com`/`x.ai`,
  OAuth metadata/authorize/token routes declared before the catch-all `app.mount("/", …)`.
- **H4 request shape / H5 OAuth scope — DISPROVEN as cause.** The production log
  (`/tmp/hb-personal-assistant-backend.log`, 2026-06-28 11:35:51) shows the failing call got past auth
  and was dispatched (`Processing request of type CallToolRequest`), then produced **no response** —
  a server-side hang after dispatch, not an auth/parse failure. `BearerTokenMiddleware` is header-only;
  `enforce_tool_scope` raises `insufficient_scope` fast.
- **H6 sync handler on the event loop — PROVEN (structural root cause).** mcp 1.27.2–1.28.1 runs sync
  `@mcp.tool()` functions **directly on the single asyncio event-loop thread**
  (`func_metadata.py`: `return fn(**args)`, no `anyio.to_thread`; only *resources* offload). All 38
  tools on `origin/main` are plain `def` with the same pattern and **no per-tool timeout**. So any tool
  whose filesystem I/O stalls freezes the entire server indefinitely → Grok sees a timeout, with no
  structured error and no diagnostic. The two working tools do the lightest I/O (`iterdir` one dir; read
  one known file); the three failing tools do heavier vault I/O (`search_vault` scans/reads across the
  whole `vault_root = ~/Documents/Obsidian Vault`; `create_note`/`patch_note` backup + atomic-write +
  `os.fsync` + audit append).
- **Stall trigger not pinned by static analysis.** No event-loop re-entry, file locks, subprocess, or
  unbounded sockets in `obsidian_mcp` (the one socket is `settimeout(0.2)`, health-only). Vault fully
  materialized (0 `.icloud` evicted files) → the iCloud-eviction variant is *not* claimed. The fix is
  deliberately correct regardless of the exact trigger.

## Runtime proof (pre vs post, real `/mcp` tools/call, stalled `search_vault` sleeping 3 s)

```
[PRE-FIX]  (origin/main: sync tool on loop, no timeout)  elapsed=3.01s isError=False tool_timeout=False
[POST-FIX] (offloaded + fail_after, timeout=1s)          elapsed=1.01s isError=True  tool_timeout=True
```

PRE-FIX is **unbounded** — blocked for the full duration of the stalled I/O (a truly stuck call hangs
forever = the Grok timeout). POST-FIX is **bounded** at the configured budget and returns a structured
`tool_timeout`. This reproduces the failure mode and proves the fix.

## Conclusion

Root cause = **H6**: MCP tool handlers run synchronously on the event loop with no offloading and no
timeout, so any I/O stall in a heavier tool hangs the whole server with no recovery and no signal. The
fix offloads every tool's blocking call to a worker thread under a bounded `fail_after`, converting an
indefinite hang into a fast structured `tool_timeout` (and keeping other tools responsive). A second,
independent defect — the live server running stale pre-expansion code — is resolved operationally by
restarting `:8000` from the merged-main + fix code.
