# AGENTS.md

Operational mandates for any agent (human or AI) changing this repository. This file complements
[CLAUDE.md](CLAUDE.md) — read both. Where CLAUDE.md describes architecture and working style, this file
carries the **non-negotiable maintenance contracts** that guard tests enforce.

## Mandatory MCP Tool-Surface Maintenance

The NAS MCP server exposes a governed tool surface to connected LLM clients. A **routing layer** (Prompt
Preflight & Tool Routing) tells clients which tool/workflow to use before they act, and a **freshness guard**
proves that routing layer still matches the live tool surface. If you add, remove, rename, or change the
arguments / read-write class / safety class / gateway scope of **any** MCP tool, the routing manifests and
their tests will drift unless you update them in the same change.

**Before you claim a tool-surface change is complete, do all ten:**

1. **Register/deregister the tool** in `nas_mcp/tool_registration.py` (and its dispatch in `nas_mcp/broker.py`).
2. **Update the canonical inventory** if it is an `assistant_*` tool (`ALL_ASSISTANT_TOOLS` stays exactly 78 —
   a new `pa_*`/helper tool never joins it).
3. **Map it to a family** in `obsidian_mcp/tool_family_manifest.py` (`family_for_tool` must stay a total
   function — every live tool resolves to exactly one of the 24 families).
4. **Add/adjust its workflow recipe(s)** in `obsidian_mcp/workflow_recipe_manifest.py` (a generation/write
   workflow must reference the real write tools, its authorization policy, and its provenance).
5. **Add/adjust its tool entry** in `obsidian_mcp/tool_entry_manifest.py` (use_when / do_not_use_when /
   replacement / deprecation).
6. **Update the route engine** in `obsidian_mcp/prompt_preflight.py` only if a new intent class / source-of-truth
   / authorization action-class is introduced.
7. **Update the gateway allowlist** in `nas_mcp/broker.py` (`GATEWAY_ALLOWLIST`) if the tool should be
   gateway-reachable — and confirm denied / root-db / legacy `hb_output_*` tools stay rejected.
8. **Update the freshness guard expectations** in `obsidian_mcp/tool_surface_freshness.py` if a new class /
   gateway-scope signal is added.
9. **Update the Client Tool Operating Manifest** docs
   (`docs/architecture/client-tool-operating-manifest.md`) and the routing docs
   (`docs/architecture/prompt-preflight-tool-routing.md`, `mcp-tool-surface-maintenance.md`,
   `tool-routing-freshness-policy.md`).
10. **Run the guard tests** — they fail if any step above was skipped:
    `tests/test_tool_surface_maintenance_contract.py`, `tests/test_tool_manifest_freshness_guard.py`,
    `tests/test_prompt_preflight_*.py`, plus the invariants `tests/test_n8c_final_validation.py`,
    `tests/test_n8c_mcp_tool_inventory_final.py`, `tests/test_n8c_client_exposure_bridge.py`.

The freshness guard (`pa_tool_surface_freshness_check` / `hb_mcp_status`) reports **stale** when the live
surface and the routing manifest diverge. **Read routes proceed with a warning; write / promotion / archive
routes must fail closed on a stale surface.** Do not suppress a staleness warning by editing the guard — fix
the manifest.

See `docs/architecture/mcp-tool-surface-maintenance.md` for the rationale and
`docs/architecture/prompt-preflight-tool-routing.md` for the routing model.
