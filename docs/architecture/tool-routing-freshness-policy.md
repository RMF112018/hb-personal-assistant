# Tool-Routing Freshness Policy

The prompt-preflight routing layer is only trustworthy while it matches the live tool surface. This policy
defines what "fresh" means and what happens when it isn't.

## What is compared

`obsidian_mcp/tool_surface_freshness.check_tool_surface` compares, per check:

- **Tool set** — added / removed / renamed tools vs the stored routing manifest.
- **Per-tool class** — each tool's family, read-write class, and safety class.
- **Workflow coverage** — every workflow `tool_sequence` entry resolves to a live tool (or the routing layer).
- **Gateway scope** — the live `GATEWAY_ALLOWLIST` vs the scope routing assumes (`tool_surface_gateway_current`).

## Staleness states

- `current` — no drift.
- `stale` — any drift above (added/removed/family/class/workflow/gateway).
- `structural_only` — only self-consistency was checked (no stored baseline / no gateway inputs).
- `unknown` — freshness could not be computed (reported safely; never crashes status).

## Enforcement

- **Read routes** proceed with a warning (`freshness.warnings`), so retrieval is never blocked by a
  benign additive change.
- **Write / canonical-promotion / archive routes fail closed** on a stale surface
  (`freshness.write_blocked_by_staleness == true`). A controlled write is never routed against a tool surface
  the manifest no longer describes.

## Where it surfaces

- Tool: `pa_tool_surface_freshness_check` (read-only, gateway-reachable).
- Status: `hb_mcp_status` → `tool_surface_manifest_current`, `tool_surface_missing_count`,
  `tool_surface_extra_count`, `tool_surface_schema_mismatch_count`, `tool_surface_gateway_current`,
  `tool_surface_staleness_state`.

## Maintenance

A stale signal is a prompt to update the routing manifests (see
[mcp-tool-surface-maintenance](mcp-tool-surface-maintenance.md) and the root
[AGENTS.md](../../AGENTS.md)) — **not** to edit the guard.
