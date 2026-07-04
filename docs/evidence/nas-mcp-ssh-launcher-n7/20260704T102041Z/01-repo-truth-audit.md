# 01 — Repo-truth audit (N7 gate)

**Branch:** `feat/nas-mcp-ssh-launcher-n7-20260704T102041Z`  
**Base:** `feat/nas-sqlite-hardening-pr-a` @ `31ba0434` (15 commits ahead of `origin/main` @ `d54f07dd`)

## 1. MCP server entrypoints

| Surface | Path | CLI | Transport |
|---|---|---|---|
| Phase 08D second-brain MCP | `src/hb_assistant/construction/second_brain/mcp/server.py` | `hb-assistant second-brain mcp serve --stdio` | **stdio only**; no network listener |
| Obsidian MCP HTTP | `src/hb_assistant/obsidian_mcp/mcp_app.py` | via FastAPI `create_app` | Streamable HTTP mounted on backend |
| NAS MCP (N7 — **new**) | `src/hb_assistant/nas_mcp/` | `hb-assistant mcp serve --nas-readonly --streamable-http` | Dedicated loopback HTTP `:8765` |

**N7 decision:** New `nas_mcp` package; do **not** extend obsidian_mcp or mount MCP on `create_app`.

## 2. Tool / resource registry

| Registry | Location | N7 use |
|---|---|---|
| Phase 08D allowed tools | `resources/json/phase_08d_mcp_allowed_tools_contract.json` + `second_brain/mcp/registry.py` | **Reference only** (broker pattern); NAS tools are separate |
| Obsidian MCP tools | `obsidian_mcp/mcp_app.py` `_TOOL_SCOPES` | **Rejected** — includes writes, OAuth, LLM, source watcher |
| NAS MCP (N7) | `nas_mcp/db_allowlist.py`, `nas_mcp/broker.py` | Default-deny table/column + root-key FS tools |

## 3. Backend coupling (rejected for NAS MCP)

`create_app` (`src/hb_assistant/construction/analytics/api.py`):
- Starts FastAPI on port 8000
- Calls `ensure_forecast_managed_storage`, `apply_startup_schema_policy`, `SQLiteMigrator`
- Mounts `build_streamable_http_app()` at `/` when SDK present
- Starts source watcher when configured

**NAS MCP must not import or call any of the above.**

## 4. DB access patterns

| Path | Mode | N7 |
|---|---|---|
| PR A `db_storage_guard.py` | fail-closed NAS path guard | **Reuse** |
| PR A `startup_schema_policy.py` | blocks silent migration on NAS | **NAS MCP must not call migrator** |
| `validate-db.sh` | `file:...?mode=ro` | **Reuse pattern** for `hb_db_select` |
| second-brain MCP wrappers | read-only query tools via broker | Pattern reference only |

## 5. Filesystem access

| Path | Notes | N7 |
|---|---|---|
| `obsidian_mcp/source_subroot.py` | lexical containment, no `..` | **Reuse patterns**, not ObsidianMcpService |
| Obsidian vault tools | broad read/write vault surface | **Rejected** |

## 6. Denied actions (existing + N7)

Existing Phase 08D: deny-first broker, no raw SQL, metadata receipts.  
N7 adds: no arbitrary SQL, no arbitrary paths, no token/cache/key/.enc, no network calls from tools, no backend port 8000.

## 7. NAS deploy (worktree only)

Present on branch, **not** on `origin/main`:
- `deploy/nas/compose.yaml` — backend viewer, loopback `127.0.0.1:8000`
- `deploy/nas/Dockerfile` — uvicorn `create_app` default CMD
- `deploy/nas/scripts/*` — viewer lifecycle

**Gap:** no `deploy/nas/mcp/`, no MCP compose, no tunnel docs.

## 8. Docker networking correction (plan)

- **Bridge network** + host publish `127.0.0.1:8765:8765`
- Container process binds `0.0.0.0:8765`
- **Not** `network_mode: none` + `ports`

## 9. Tests covering MCP / NAS

| Test file | Coverage |
|---|---|
| `tests/test_phase_08d_mcp_*.py` | second-brain stdio broker |
| `tests/test_obsidian_mcp_backend.py` | obsidian streamable HTTP on FastAPI |
| `tests/test_nas_runtime_scaffold.py` | NAS viewer compose safety |
| `tests/test_db_storage_guard.py` | NAS DB path guard |
| `tests/test_startup_schema_policy.py` | migration gate |

**Gap:** no NAS MCP port/compose/tool tests (N7H).

## 10. Audit receipt patterns

- Phase 08D: SQLite `second_brain_mcp_tool_call_receipts` + denials
- N7: JSONL under `/app-support/audit/mcp/` (file-based, MCP-specific)

## Implementation gate

Audit complete. Proceed to N7B design docs and implementation.
