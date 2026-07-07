# N8C-15 — Workflow Contract & Routing Layer — Closeout

**Phase:** N8C-15 (NAS second-brain workflow contract + deterministic routing layer)
**Status:** implemented + verified; **UNCOMMITTED** (stop-before-commit per authorization)

## Commit lineage
- N8C-11 research packets: `0e2876c7`
- N8C-12 source connector: `e6a75838`
- N8C-14 citation-safe drafts (committed this session): `ae483f39`
- N8C-15 branch: `ops/nas-second-brain-n8c-15-workflow-contract-routing-20260707T113906Z`
- N8C-15 base commit: `ae483f39`
- N8C-15 HEAD at close: still `ae483f39` (N8C-15 uncommitted)

## What N8C-15 delivers
A deterministic, **route-only** layer that turns a bounded workflow request into a normalized
workflow-result envelope over EXISTING N8C read surfaces — no execution, no persistence, no schema,
no MCP, no LLM.

- `workflow_models.py` — 11 canonical workflow types, 11 routing targets, 5 result statuses, fixed
  no-execution policy block, bounded `WorkflowRequest`, conservative keyword classifier, ephemeral
  deterministic `workflow_id`, `bounded_metadata` (scalar-only, drops every `*_json`).
- `workflow_registry.py` — per-type routing-target contract + deferred-capability markers + catalog.
- `workflow_router.py` — `WorkflowRouter` reads existing repositories and returns the normalized
  envelope; degrades to "absent" on an unmigrated table rather than crashing.
- `cli/workflow.py` — read-only `hb-assistant workflow catalog|route` (no apply/build/execute flag).
- `api.py` — two read-only GET routes (`/api/assistant/workflows/catalog`, `.../route`).

## Deferred (unchanged this phase)
- N8C-13 operator UI / command center — no branch, no UI, no schema.
- N8C-16 live MCP/ChatGPT workflow consumption — no MCP tools added here.
- N8C-17 full workflow implementations (meeting_prep / daily_brief / project_intel / open_loop_triage).
- N8C-18 action staging (`action_draft_preparation` is contract-only → deferred capabilities only).
- N8D agent_bridge — untouched, not imported.
