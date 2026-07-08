# MCP Tool-Surface Maintenance

The NAS MCP tool surface is governed by three coupled layers that must stay in lockstep:

1. **Registration + broker** (`nas_mcp/tool_registration.py`, `nas_mcp/broker.py`) — what tools exist, their
   gates, and the `GATEWAY_ALLOWLIST`.
2. **Client Tool Operating Manifest** (`obsidian_mcp/client_tool_manifest.py` + docs) — the versioned record
   of what tool to use, when, and what not to do, with its own freshness contract.
3. **Prompt Preflight routing** (`obsidian_mcp/tool_family_manifest.py`,
   `workflow_recipe_manifest.py`, `tool_entry_manifest.py`, `prompt_preflight.py`,
   `tool_surface_freshness.py`) — the read-only route engine + tool-surface freshness guard.

If any tool is **added, removed, renamed, or changes its arguments / read-write class / safety class /
gateway scope**, all three layers drift unless updated together.

## The maintenance contract

The authoritative 10-step checklist lives in the root [AGENTS.md](../../AGENTS.md) ("Mandatory MCP
Tool-Surface Maintenance"). In short: register → classify into a family → add/adjust the workflow recipe →
add/adjust the tool entry → update the gateway allowlist if reachable → update the docs → run the guard
tests.

## Guard tests (enforce the contract)

- `tests/test_tool_surface_maintenance_contract.py` — every live tool classifies into a known family; the
  live surface is not stale; every workflow tool is live; `AGENTS.md` declares the mandate; routing content is
  organization-neutral.
- `tests/test_tool_manifest_freshness_guard.py` — added/removed/family-changed/gateway-scope-changed tools
  make the surface stale; a stale surface blocks write routes but not read routes.
- `tests/test_prompt_preflight_*.py` — route schema, family/workflow routing, authorization, retrieval
  budget, source-of-truth, memory opportunities, fallbacks.
- Invariants: `tests/test_n8c_final_validation.py`, `tests/test_n8c_mcp_tool_inventory_final.py`,
  `tests/test_n8c_client_exposure_bridge.py` (canonical 78 unchanged; gateway allowlist decoupled).

## Freshness signal at runtime

`pa_tool_surface_freshness_check` and the `tool_surface_*` fields on `hb_mcp_status` report drift.
`staleness_state` ∈ `{current, stale, structural_only, unknown}`. **Reads warn; writes/promotion/archive fail
closed on stale.** Never silence the signal by editing the guard — fix the manifest.
