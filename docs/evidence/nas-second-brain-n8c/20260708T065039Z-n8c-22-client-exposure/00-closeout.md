# N8C-22 — Connected Client Assistant Tool Exposure Bridge — Closeout

- Date (UTC): 2026-07-08
- Branch: `ops/nas-second-brain-n8c-22-client-exposure-20260708`
- Base / starting HEAD: `eebe72e0` (== origin/main, N8C-21 final validation)
- Local commit created: **no** (awaiting Bobby's authorization)
- Production deploy / push / PR / tunnel / credential change: **none**

## Corrected premise (Phase 1 finding)

The task premise — "78 assistant tools broker-registered + status-advertised but NOT client-callable" —
is **contradicted by repo truth at HEAD**. All 78 canonical `assistant_*` tools were already registered
as client-facing `@mcp.tool()` in `register_nas_mcp_tools()` and are returned by FastMCP `tools/list`.
The parity audit proves **78/78** across all four layers. Any live gap is runtime/client-side (stale
image, `HB_MCP_ASSISTANT_*` kill switch, or client tool-count limits) — see the operator runbook in
`docs/architecture/n8c-connected-client-exposure.md` §8.

Scope was therefore additive (confirmed with Bobby): **no duplicate wrappers**; exact-78 invariant kept.

## What shipped

| Phase | Deliverable | Files |
|---|---|---|
| 1 | Client-exposure parity audit (JSON + md) + CLI `mcp exposure-audit` | `src/hb_assistant/nas_mcp/exposure_audit.py`, `src/hb_assistant/cli/mcp_nas.py` |
| 2 | Canonical registry `ASSISTANT_TOOL_GROUPS`/`ALL_ASSISTANT_TOOLS`; 6 `assistant_client_exposure_*` status fields | `src/hb_assistant/nas_mcp/broker.py` |
| 3 | Fallback helpers `hb_assistant_catalog` / `hb_assistant_tool_help` / `hb_assistant_tool_query` | `src/hb_assistant/nas_mcp/tool_registration.py` |
| tests | `tests/test_n8c_client_exposure_bridge.py` (31 tests) | — |
| smoke | `scripts/smoke-n8c-client-exposure.sh` | — |
| docs | `docs/architecture/n8c-connected-client-exposure.md` | — |

## Results

- Parity audit: **78/78** broker_registered / status_advertised / client_manifest_exposed / callable_smoke_tested; missing 0; not_callable 0. (`client-exposure-parity.json` / `.md`)
- New module: **31 passed**. Existing gate + count-sensitive regression (inventory-final, final-validation, files-rw(56), workflows-delta(6), remote-profile, ai-outputs): **57 passed**.
- Smoke: all steps PASS; 6 negatives fail closed. (`smoke-results.txt`)
- ruff check on all touched files: clean. mypy: `nas_mcp` is `ignore_errors=true` (out of strict scope).

## Counts

- canonical_n8c_assistant_tool_count = **78** (unchanged)
- client_bridge_helper_tool_count = **3** (`hb_assistant_catalog`, `hb_assistant_tool_help`, `hb_assistant_tool_query`)
- total_client_assistant_surface_count = 78 + 3
- Only sanctioned remote write = `ai_outputs_card_upsert` (unchanged; NOT reachable via the gateway).

## Status fields added to `hb_mcp_status`

`assistant_client_exposure_enabled`, `assistant_client_exposure_mode` (`direct+gateway`),
`assistant_client_exposed_tool_count`, `assistant_client_missing_tool_count`,
`assistant_client_exposure_groups`, `runtime_commit`.

## Next manual validation step

Connect ChatGPT/Grok/Claude Desktop to `https://nas-mcp.bobby-fetting.me/mcp`, confirm
`hb_mcp_status.assistant_client_exposed_tool_count == 78` with a matching `runtime_commit`, then follow
the manual checklist (docs §10). If the client surfaces only a subset of tools, use the fallback gateway.

## Known limitations

- No live/connected-client call was made from this environment (barred from prod). Local FastMCP surface
  is the closest equivalent; the real-client check is the manual step above.
- `runtime_commit` falls back to `v<version>` unless `HB_RUNTIME_COMMIT`/`HB_BUILD_SHA` is set at deploy.
