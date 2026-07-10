# Prompt Preflight & Tool Routing

A read-only control-plane layer that helps connected LLM clients decide, **before** answering or acting,
what to do with a prompt: intent → source-of-truth → tool family → workflow recipe → specific tools →
authorization → retrieval budget. So "generate a Word doc and save it" routes to the generated-output
workspace and "document this session" routes to the artifact workspace — without the operator naming tools.

The preflight **never writes, stages, promotes, commits, or reads source content.** It only reasons over
static routing manifests plus live availability/freshness signals and returns a route plan.

## Canonical metadata architecture

| Layer | Module | Role |
| --- | --- | --- |
| Pure types | `obsidian_mcp/tool_metadata_types.py` | Dataclasses/enums only; no NAS imports |
| Semantic authority | `obsidian_mcp/canonical_tool_specs.py` | ToolSpec classification, routing-tool specs, replacement map |
| Family/workflow seeds | `tool_family_manifest.py`, `workflow_recipe_manifest.py` | Compatibility views over durable seed data |
| Live surface join | `nas_mcp/live_tool_surface.py` | **Surface-level only**: installed / profile_enabled / direct / gateway — never request approval/token state |
| Failure envelope | `nas_mcp/failure_envelope.py` | Plugin-observed stages only |

**Group vs family (Option A):** registration/exposure group stays concrete (e.g. `source_structure`); semantic
family may be broader (e.g. `assistant_source_connector`). Route `next_step` carries both.

**Version fields:**

- `route_schema_version` — route plan contract (**2**, additive)
- `manifest_version` — **revision counter** (not schema version)
- `manifest_schema_version` — payload contract (**1** expanded; legacy rows = 0)

**Checksums (separated):** `semantic_surface_checksum`, `exposure_checksum`, `gateway_checksum`; deployment
identity is **not** part of the semantic fingerprint. Canonical JSON: UTF-8, sorted keys, set-like arrays
sorted, workflow step order preserved, form `sha256:<hex>`.

**Authorization:** multi-dimensional (`read_tool_calls_authorized`, `advisory_planning_authorized`,
`staging_authorized`, `write_authorized`, `promotion_authorized`, `external_action_authorized`, …).
Deprecated **`prompt_authorizes_execution`** is retained for this contract cycle, derived deterministically,
and must not be the sole client signal.

**Negation:** clause-scoped capability prohibitions (`do not promote`, `without writing`, `plan only`, …) —
not keyword-wide NLP. Prohibited capabilities never positively score matching write/promote workflows.

**Freshness:** compares live vs **persisted independent snapshot** (V118 payload/checksums). Never
live-vs-live as sole “current”. Failures report `check_failed` / `indeterminate`, not false current.
Kill-switch absence is expected-for-profile, not structural drift.

**Startup bootstrap:** no active → internal DB baseline, vault materialization pending review (unless
`HB_MCP_MANIFEST_FIRST_INSTALL_AUTOPROMOTE=1`). Existing active + drift → stale/review_required; never
auto-promote. Optional auto-stage only with `HB_MCP_MANIFEST_AUTO_STAGE_ON_DRIFT=1` (never promote).

**Failure attribution:** the plugin cannot prove a client or platform rejected a call when no call reached
plugin infrastructure. Do not claim “platform safety layer” without platform evidence.

**Runtime identity:** prefer `HB_RUNTIME_COMMIT` / `HB_BUILD_SHA` (validated SHA).
`runtime_identity()` is structured; `runtime_commit()` remains a string accessor. Package-only is not
“current”.

## Routing manifests (seed / compatibility)

- `obsidian_mcp/tool_family_manifest.py` — families; `family_for_tool` is total.
- `obsidian_mcp/workflow_recipe_manifest.py` — workflow recipes (including vault vs NAS retrieval).
- `obsidian_mcp/tool_entry_manifest.py` — per-tool use-when / deprecation seeds.
- Classification for help/manifest: `canonical_tool_specs.classify_tool` (shimmed by `client_tool_manifest.classify_tool`).

V114 tables still ship empty; static seed remains authoritative. V118 adds independent semantic payload
columns on `pa_client_tool_manifests`.

## Route engine (`obsidian_mcp/prompt_preflight.py`)

Deterministic. `route_prompt(...)` returns route schema **v2** (additive):

- Existing fields preserved: intent, source_of_truth, families, workflow, tools, authorization.action_class,
  write_risk, prompt_authorizes_execution (deprecated), retrieval_budget, …
- New: `route_schema_version`, dimensional auth, `prohibitions`, `next_step` / `additional_steps` with
  `tool_group`, constraints/warnings, compact `route` object
- `explain_route` explains the **same** normalized route + detail records

Preflight never writes, stages, promotes, commits, or reads source content.

## Freshness guard (`obsidian_mcp/tool_surface_freshness.py`)

Independent baseline categories include structural/semantic/workflow/exposure/gateway/schema/
classification/help/alias/deployment/manifest/checksum/profile_context. **Read routes proceed with a
warning; write / promotion / archive fail closed on a stale surface.**

## MCP tools (read-only, gateway-reachable)

`pa_prompt_route`, `pa_prompt_route_explain`, `pa_tool_family_get`, `pa_workflow_recipe_get`,
`pa_tool_surface_freshness_check`. Included in the client tool universe for **manifest help** (not in the
canonical assistant inventory count). Gate: `HB_MCP_PROMPT_PREFLIGHT` (default-on).

## Mandatory MCP tool-surface maintenance

Any change to the MCP tool surface must update the routing manifests, the gateway, and these docs, then pass
the guard tests. See [mcp-tool-surface-maintenance](mcp-tool-surface-maintenance.md), the root
[AGENTS.md](../../AGENTS.md), and [tool-routing-freshness-policy](tool-routing-freshness-policy.md).

## Known limitations

- Intent matching is deterministic trigger-phrase/keyword based (no LLM) — robust and auditable, but a novel
  phrasing that matches no trigger routes to a clarifying preflight rather than guessing.
- The V114 tables ship empty; the static seed is the authoritative routing source (consistent with the
  additive-empty pattern of prior N8C schema phases).
