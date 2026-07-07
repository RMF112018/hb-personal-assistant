# 11 — Tests, Ruff, Secret-Scan

Shared venv: `/Users/bobbyfetting/hb-personal-assistant/.venv/bin/python`,
`PYTHONPATH=src:subrepos/construction-financial-review/src`. (The environment drops pytest's summary line
from captured output; **exit code 0 with zero FAILED/ERROR lines is authoritative**.)

## N8C-17 focused + workflow surfaces — GREEN (exit 0)
```
tests/test_workflow_models.py  tests/test_workflow_registry.py  tests/test_workflow_router.py
tests/test_workflow_handlers.py  tests/test_cli_workflow.py  tests/test_fastapi_analytics_workflows.py
tests/test_nas_mcp_workflows.py
```
- `test_workflow_handlers.py` — NEW: 21 functions / **48 parametrized cases** (classification, per-workflow
  sections, conservative split, bounded no-blob, advisory-only, policies, limit clamp, unmigrated
  degradation, handler AST guard).
- `test_workflow_router.py` — updated: implemented-behavior for the four workflows + `test_handlers_call_
  no_writer_or_worker` + envelope now asserts `workflow_sections`/`workflow_policy`.
- `test_workflow_registry.py` — updated: `implementation_deferred_to == "N8C-18"`, no `build_*` marker.
- `test_nas_mcp_workflows.py` — updated: route + get_workflow_context return `workflow_sections`
  (clarification #11); +daily-brief sections; existing finality/kill-switch/RO-snapshot/no-persistence
  tests still pass.

## nas_mcp regression (incl. N8C-12 finality guard) — GREEN (exit 0)
```
test_nas_mcp_answer_drafts, _readonly, _remote_profile, _review, _decision_memory, _intelligence,
_research_packets, _context_packs, _memory, _source_connector, _assistant_nav, _ai_outputs,
_safe_mode_limits_freshness, _files_rw
```

## N8C repository / builder / analytics-API regression — GREEN (exit 0)
```
test_answer_draft_repository, _research_packet_repository, _intelligence_projection_repository,
_context_pack_repository, _decision_memory_repository, _memory_repository, _review_repository,
_claim_repository, _source_connector_service, test_answer_draft_v108_migration,
fastapi_analytics_{answer_drafts, review, decision_memory, claims}
```

## Ruff — clean
`ruff check` on all changed sources + tests → "All checks passed!".

## Schema — unchanged
`LATEST_SCHEMA_VERSION == 108`; `store/migrator.py` not in the diff.

## scripts/test-schedule.sh (cross-domain migrator canary) — GREEN
`345 passed, 2 deselected, 1 warning in 526.32s`, exit 0. Confirms the (unchanged) migrator/schema is intact
across the cross-domain canary — no regression from the N8C-17 obsidian_mcp/nas_mcp changes.

## Secret-scan
`grep` for tailnet IPs / host:port / tokens / private keys / absolute home paths over the evidence bundle →
clean (the only "SECRET …" strings are the test-fixture body markers referenced when PROVING they never
leak).
