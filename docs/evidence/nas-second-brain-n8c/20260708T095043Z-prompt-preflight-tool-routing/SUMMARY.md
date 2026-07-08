# Evidence — Prompt Preflight & Tool Routing

Branch `ops/nas-second-brain-prompt-preflight-tool-routing-20260708` off N8C-24 `a476c35f`. Schema **V114**.
Local commit only (no push). No AI trailer.

## What shipped

A read-only control-plane routing layer for connected LLM clients: intent → source-of-truth → tool family →
workflow recipe → specific tools → authorization → retrieval budget, plus a tool-surface freshness guard.

- **Routing manifests (static seed):** `obsidian_mcp/tool_family_manifest.py` (24 families +
  `family_for_tool` total function), `obsidian_mcp/workflow_recipe_manifest.py` (37 workflow recipes),
  `obsidian_mcp/tool_entry_manifest.py` (per-tool records).
- **Route engine:** `obsidian_mcp/prompt_preflight.py` (deterministic; full route-plan schema; read-only).
- **Freshness guard:** `obsidian_mcp/tool_surface_freshness.py` (added/removed/family/class/workflow/gateway
  drift; reads warn, writes fail closed).
- **Schema V114:** `store/pa_prompt_routing_tables.py` — `pa_tool_families`, `pa_prompt_workflow_recipes`,
  `pa_tool_routing_entries` (additive, ship empty; migrator `LATEST_SCHEMA_VERSION=114`).
- **MCP tools (read-only, gateway-reachable):** `pa_prompt_route`, `pa_prompt_route_explain`,
  `pa_tool_family_get`, `pa_workflow_recipe_get`, `pa_tool_surface_freshness_check`
  (`nas_mcp/prompt_routing_tools.py`). Gate `HB_MCP_PROMPT_PREFLIGHT` (default ON).
  `hb_mcp_status` gains `prompt_preflight_*` + `tool_surface_*` fields.
- **Maintenance mandate:** root `AGENTS.md` (10-step checklist) + `docs/architecture/`
  prompt-preflight-tool-routing / mcp-tool-surface-maintenance / tool-routing-freshness-policy; CLAUDE.md +
  client-tool-operating-manifest.md cross-link it; guard tests enforce it.

## Invariants preserved

Canonical `ALL_ASSISTANT_TOOLS` stays exactly **78**; the 5 `pa_prompt_*` tools never join it. Gateway
allowlist expanded to include them (117 total). Denied/raw-SQL/shell/exec/root-db/legacy `hb_output_*`/
non-allowlisted tools stay gateway-rejected. Preflight writes/stages/promotes/commits **nothing**.

## Artifacts in this bundle

- `pytest-output.txt` — routing suite + invariants, all green.
- `smoke-output.txt` — `scripts/smoke-prompt-preflight-tool-routing.sh`, 21/21 PASS.
- `ruff-output.txt` — clean on all new modules.
- `migration-proof.txt` — fresh + idempotent migrate to V114; 3 new tables present (empty).
- `org-neutral-scan.txt` — no organization-specific terms in routing content or docs.
- `git-status-before.txt`, `preflight.txt` — pre-change repo state.

## Known limitations

- Deterministic trigger-phrase matching (no LLM); a novel phrasing that matches no trigger routes to a
  clarifying preflight rather than guessing.
- V114 tables ship empty; the static seed is the authoritative routing source (additive-empty pattern).
