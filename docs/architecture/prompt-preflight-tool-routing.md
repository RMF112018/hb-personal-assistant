# Prompt Preflight & Tool Routing

A read-only control-plane layer that helps connected LLM clients decide, **before** answering or acting,
what to do with a prompt: intent → source-of-truth → tool family → workflow recipe → specific tools →
authorization → retrieval budget. So "generate a Word doc and save it" routes to the generated-output
workspace and "document this session" routes to the artifact workspace — without the operator naming tools.

The preflight **never writes, stages, promotes, commits, or reads source content.** It only reasons over
static routing manifests plus live availability/freshness signals and returns a route plan.

## Routing manifests (the seed source of truth)

- `obsidian_mcp/tool_family_manifest.py` — **24 families** (§the coarse routing unit). `family_for_tool` is a
  total function: every live tool maps to exactly one family (`pa_output_*` → `client_output_workspace` /
  `output_receipts_manifests`; legacy `hb_output_*` → `legacy_low_level`, deprecated → replaced-by
  `pa_output_*`; `pa_prompt_*` → `prompt_routing`; denied → `blocked_deprecated`).
- `obsidian_mcp/workflow_recipe_manifest.py` — **workflow recipes**: ordered tool sequences with intent
  classes, authorization policy, write risk, retrieval layer, required provenance, must-not-use, and
  fallback rules. Generation workflows reference the real N8C-24 `pa_output_*` tools; `generate_pdf_output`
  is available (reportlab).
- `obsidian_mcp/tool_entry_manifest.py` — per-tool records joining name+group → family + read/write + safety
  class + use-when / do-not-use-when / replacement / deprecation.

These are mirrored durably in the **V114** tables `pa_tool_families`, `pa_prompt_workflow_recipes`,
`pa_tool_routing_entries` (additive; ship empty; the static seed is authoritative).

## Route engine (`obsidian_mcp/prompt_preflight.py`)

Deterministic. `route_prompt(prompt, available_tools=…, has_exact_id=…, freshness=…)` returns the full route
plan dict:

- `intent` (primary + classes), `source_of_truth`, `candidate_families`, `primary_family`
- `recommended_workflow`, `alternative_workflows`, `recommended_tools` (filtered by live availability),
  `workflow_available`, `unavailable_tools`
- `authorization` — action class + `prompt_authorizes_execution` (reads self-authorize; writes/promotion/
  archive need an explicit operator go + server-minted approval) + `additional_approval_required`
- `retrieval_budget` — default layer, recommended next layer, candidate/char caps,
  `deep_parse_requires_operator_selection`, `why_not_deep_read_all` (broad/ambiguous → metadata discovery +
  candidate triage first; exact id/filename → bounded read allowed)
- `provenance_required`, `memory_opportunity` (flags a durable fact worth capturing but **never auto-stages**),
  `must_not_use`, `fallback_plan` (unsafe fallback from a controlled write is blocked), `route_confidence`,
  `routing_rationale`, and a `clarifying_question` when confidence is low on a write.

## Freshness guard (`obsidian_mcp/tool_surface_freshness.py`)

Compares the live tool surface (names, family/read-write/safety class, and the **gateway allowlist scope**)
against the routing manifest. Detects added / removed / renamed tools, family/class changes, workflows
referencing missing tools, and gateway-scope drift. **Read routes proceed with a warning; write / promotion
/ archive routes fail closed on a stale surface.**

## MCP tools (read-only, gateway-reachable)

`pa_prompt_route`, `pa_prompt_route_explain`, `pa_tool_family_get`, `pa_workflow_recipe_get`,
`pa_tool_surface_freshness_check`. None contains a write-verb or finality substring; none joins the canonical
78; all are added to `GATEWAY_ALLOWLIST`. Gate: `HB_MCP_PROMPT_PREFLIGHT` (default-on kill-switch).
`hb_mcp_status` surfaces `prompt_preflight_*` + `tool_surface_*` fields and never crashes.

## Mandatory MCP tool-surface maintenance

Any change to the MCP tool surface must update the routing manifests, the gateway, and these docs, then pass
the guard tests. See [mcp-tool-surface-maintenance](mcp-tool-surface-maintenance.md), the root
[AGENTS.md](../../AGENTS.md), and [tool-routing-freshness-policy](tool-routing-freshness-policy.md).

## Known limitations

- Intent matching is deterministic trigger-phrase/keyword based (no LLM) — robust and auditable, but a novel
  phrasing that matches no trigger routes to a clarifying preflight rather than guessing.
- The V114 tables ship empty; the static seed is the authoritative routing source (consistent with the
  additive-empty pattern of prior N8C schema phases).
