# 02 — N8C-16 Baseline + Carry-Forward

## Baseline (committed this session)
N8C-16 (`65ee1268`, `feat(nas): add n8c workflow mcp tools`) exposed the N8C-15 route-only router over six
read-only remote MCP tools served from the `mode=ro&immutable=1` snapshot, kill-switch gated, finality-guard
clean, +6 tool delta, no schema. At that point the four context workflows (`meeting_prep`,
`daily_brief_context`, `project_intelligence_context`, `open_loop_triage`) were "route + mark deferred to
N8C-17" stubs — they confirmed supplied artifact existence and returned `deferred_capabilities` /
advisory "deferred to N8C-17" text.

## Carry-forward into N8C-17
- The N8C-15 router, models, registry, and the N8C-16 MCP wiring are the substrate. N8C-17 fills in the four
  stubs and adds two additive envelope fields — it does NOT alter routing/intent resolution, the six tool
  names, the RO snapshot, the kill switch, or the finality guard.
- The router's existing `_artifact` / `bounded_metadata` / whitelists / `_guard_one`/`_guard_many` /
  `_inspect_draft` idioms are reused verbatim; N8C-17 adds bounded LIST accessors in the same guarded style.
- The bounded `WorkflowRequest` is extended additively; `compute_workflow_id` still folds `to_public_dict()`
  so ids stay deterministic.

## Repo-truth verification (read-only, pre-implementation)
- Confirmed the four `_handle_*` delegated to `_route_deferred_context` / a partial open-loop handler.
- Mapped every repository LIST signature actually used (type/status/limit kwargs; `domain` only on
  `list_nodes`; claims via `ClaimRepository.list_claims`; source FILES via
  `source_connector_service.search_source_files`, index-only).
- Confirmed the enum vocabularies used by `_classify` from the live schema (decision/open-loop/preference
  status + review-state CHECKs; review effective-state map) — see `06-artifact-policy.md`.
