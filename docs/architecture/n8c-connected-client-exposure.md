# N8C Connected-Client Assistant Tool Exposure (N8C-22)

Status: current-state contract for how connected LLM clients (ChatGPT, Grok, Claude Desktop, future MCP
clients) consume the N8C second-brain assistant surface. This layer performs no deployment.

## 1. Problem statement

N8C-1…N8C-21 built a 13-group / **78-tool** read-only assistant surface on the NAS MCP. The intent is for
connected clients to act as the second-brain **UI layer** — searching source files, reading bounded
excerpts, retrieving context packs / memory / decisions / research packets / drafts, routing workflows,
and inspecting review / feedback / action-stage / quality state — instead of falling back to low-level
`hb_db_select` / `hb_root_search` / raw vault search.

A field observation reported that a ChatGPT-connected client saw only the generic tools
(`hb_mcp_status`, `hb_db_select`, `hb_root_search`, `hb_root_read_file`, `hb_output_*`, legacy vault
tools, `ai_outputs_card_upsert`) and **not** the 78 `assistant_*` tools.

## 2. Repo-truth finding (corrected premise)

Investigation at HEAD proved the 78 tools are **already** client-exposed in code:

- `register_nas_mcp_tools()` in `src/hb_assistant/nas_mcp/tool_registration.py` is the single function that
  registers every client-facing `@mcp.tool()` — the generic tools **and** all 78 `assistant_*` tools, in
  13 kill-switch-gated blocks. FastMCP's `tools/list` serves exactly that set.
- The parity audit (`hb-assistant mcp exposure-audit`, `src/hb_assistant/nas_mcp/exposure_audit.py`) shows
  **78/78** for broker-registered, status-advertised, client-manifest-exposed, and callable-smoke-tested.

Therefore the observed live gap is **not** a missing code projection layer. It is runtime/client-side —
see §8. N8C-22 is an additive **verification + status + fallback-gateway** phase, not a duplicate-wrapper
phase. No duplicate wrappers were added; the exact-78 invariant is preserved.

## 3. Target state

Connected clients use the N8C assistant surface first. Two access modes coexist:

- **Direct wrapper mode** — every one of the 78 canonical tools is a named client tool (already true).
- **Fallback catalog/help/gateway mode** — three `hb_assistant_*` helpers for clients that cannot ingest
  a large tool manifest, so they can still discover and reach the full 78 through one entry point.

> Root / vault / DB tools (`hb_db_select`, `hb_root_search`, `hb_root_read_file`, `search_vault`) remain
> available for admin/debug but are **not** the normal second-brain UI abstraction. Normal client usage
> flows through the semantic `assistant_*` tools.

## 4. Architecture (text)

```
connected client (ChatGPT / Grok / Claude Desktop)
   │  MCP tools/list  ──────────────►  FastMCP manifest (server.py: FastMCP + register_nas_mcp_tools)
   │                                     ├─ 78 direct assistant_* wrappers  ─┐
   │  MCP tools/call ─────────────────►  ├─ hb_assistant_catalog / _tool_help │
   │                                     └─ hb_assistant_tool_query (gateway) ─┤
   ▼                                                                          ▼
                                              NasMcpBroker.dispatch(tool_name, args)
                                              deny/safe-mode/profile/token gates + kill switches
                                                          │  (audit written centrally)
                                                          ▼
                                              _invoke → per-group _invoke_assistant_*
                                                          │
                                                          ▼
                                              read-only DB snapshot (mode=ro&immutable=1,
                                              PRAGMA query_only=ON) — no live-DB fallback
```

The gateway and direct wrappers share the identical `broker.dispatch` path, so gates, per-group kill
switches, the read-only snapshot, bounded results, and audit logging apply uniformly.

## 5. Direct wrapper mode

The 78 tools are registered per group in `tool_registration.py`, each gated at registration by its
`assistant_<group>_enabled()` predicate and re-gated at dispatch. Canonical source of truth:
`ASSISTANT_TOOL_GROUPS` / `ALL_ASSISTANT_TOOLS` in `broker.py`. Priority groups for client usage:

1. **Source access/search** — `assistant_source_file_search`, `assistant_source_file_read`,
   `assistant_search_sources`, plus source status/roots/list/metadata and card nav.
2. **Context + memory** — context packs; memory nodes/mentions/compilations; decisions/preferences/open-loops.
3. **Research / drafts / workflow** — research packets + citations; citation-safe drafts; workflow route/context/policy.
4. **Review / feedback / action-stages / quality** — review state; feedback + recommendations; staged
   action candidates; advisory quality findings.

## 6. Fallback catalog / help / gateway mode

Three always-on read-only helpers (names prefixed `hb_assistant_`, never `assistant_`, so they stay
outside the exact-78 count and the `assistant_`-prefixed finality guard, and carry no finality/write verb):

- **`hb_assistant_catalog(group?)`** — the 13 groups + canonical tools with purpose, required/optional
  args, result limits, safety class, and direct-exposure availability. Secret-free, bounded.
- **`hb_assistant_tool_help(tool_name)`** — schema + usage for one approved tool; rejects unknown, denied,
  and non-assistant names.
- **`hb_assistant_tool_query(tool_name, arguments?)`** — allowlisted gateway to the canonical 78 only. It
  rejects denied names, write/finality/action/non-assistant tools, unknown handlers, arbitrary
  module/function names, SQL/shell/exec, file paths, non-dict args, and unbounded limits, then calls the
  same audited `broker.dispatch`. **Not** a generic RPC escape hatch.

## 7. Status fields

`hb_mcp_status` (and `hb_assistant_catalog.exposure`) report, via `assistant_client_exposure_status()`:

| field | meaning |
|---|---|
| `assistant_client_exposure_enabled` | bridge present (True) |
| `assistant_client_exposure_mode` | `direct+gateway` |
| `assistant_client_exposed_tool_count` | canonical tools currently client-exposed (kill-switch aware) |
| `assistant_client_missing_tool_count` | `78 − exposed` (nonzero only when a group is killed) |
| `assistant_client_exposure_groups` | enabled group labels |
| `runtime_commit` | deploy build stamp (`HB_RUNTIME_COMMIT`/`HB_BUILD_SHA`, else `v<version>`) |

## 8. Runtime diagnosis (operator-run — read-only)

Because code-level exposure is already correct, a live client-visibility gap has three likely causes.
These are **operator-run** read-only checks; no deployment/runtime change is performed by N8C-22.

1. **Stale deployed image.** Confirm the running NAS MCP image was built from a commit that includes the
   N8C assistant registrations (≥ commit `14a0613a`). On the NAS:
   `docker inspect --format '{{.Image}} {{.Config.Image}}' <mcp-container>` and compare the build to the
   current `git rev-parse HEAD`; the container's `hb_mcp_status.runtime_commit` should match the deployed build.
2. **Kill-switch env.** A group disabled by `HB_MCP_ASSISTANT_*=0` is not registered. Check the container
   env: `docker exec <mcp-container> env | grep HB_MCP_ASSISTANT_` — expect none set to `0`. Cross-check
   `hb_mcp_status.assistant_client_missing_tool_count` (should be `0`).
3. **Client-side tool-count/manifest limit.** ChatGPT/Grok connectors may surface only a subset of a large
   tool manifest. If (1) and (2) are clean, this is the cause — clients should use the **fallback gateway**
   (`hb_assistant_catalog` → `hb_assistant_tool_query`) to reach all 78 through a small entry point.

## 9. Smoke test procedure

`bash scripts/smoke-n8c-client-exposure.sh` — builds a real FastMCP surface + fresh migrated test DB,
reads the live client manifest, and exercises status, catalog/help, all four priority groups (direct +
gateway), and fail-closed negatives (denied tool, raw SQL, shell/exec, write/finality, absolute read,
unbounded limit). Prints PASS/FAIL per step; exits non-zero on any failure.

Parity artifact: `hb-assistant mcp exposure-audit --out-json parity.json --out-md parity.md`.

## 10. Manual validation checklist (ChatGPT / Grok / Claude Desktop)

- [ ] Connect the client to `https://nas-mcp.bobby-fetting.me/mcp` (OAuth) and open its tool inventory.
- [ ] Confirm `hb_mcp_status` returns `assistant_client_exposed_tool_count = 78`, `missing = 0`, and a
      `runtime_commit` matching the deployed build.
- [ ] If the client lists the 78 `assistant_*` tools: call `assistant_source_file_search` then
      `assistant_source_file_read` directly.
- [ ] If the client lists only a subset (tool-count limit): call `hb_assistant_catalog`, then
      `hb_assistant_tool_query("assistant_source_file_search", {...})`.
- [ ] Confirm the client does **not** need `hb_root_search` / `hb_db_select` / raw vault search for
      ordinary source discovery.
- [ ] Confirm no write path is reachable except `ai_outputs_card_upsert` (and it is not reachable via the
      gateway).

## 11. Safety boundaries

Read-only/advisory assistant tools; bounded results; read-only immutable DB snapshot, no live-DB fallback;
central audit; per-group kill switches; profile write-gates unchanged. `ai_outputs_card_upsert` remains the
only sanctioned remote write and is **not** reachable via `hb_assistant_tool_query`. No new raw SQL / shell
/ exec / absolute-read / traversal / source-reindex / email / calendar / external-writeback surface.
