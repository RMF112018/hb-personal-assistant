# 11 — Tests

## New N8C-18 suites (68 test functions, all green)
| file | functions | focus |
| --- | --- | --- |
| `test_feedback_v109_migration.py` | 13 | head-agnostic, 5 tables, idempotent, prior survive, policy/target CHECKs, no action-stage table, no finality/disposition columns |
| `test_feedback_models.py` | 14 | deterministic + idempotent ids, sorted-anchor signatures, bounded caps, fixed policy block, advisory-only derivation map |
| `test_feedback_repository.py` | 7 | idempotent upsert, writes ONLY feedback tables, ≥1 target required, lifecycle events, pinned policy |
| `test_feedback_service.py` | 13 | preview read-only, apply persists + no upstream mutation, source-ref warning, bounded export, code-symbol + AST guards |
| `test_feedback_cli.py` | 6 | dry-run default / apply write, list/show/recommendations/export, no disposition/execution command |
| `test_fastapi_analytics_feedback.py` | 8 | GET-only, /summary + /recommendations not shadowed, advisory, redacted, 404, no write route |
| `test_nas_mcp_feedback.py` | 7 | RO snapshot, kill-switch scoped, finality-clean, status advert, ai_outputs sole write |

Run command (env strips the pytest summary line; exit 0 + zero FAILED/ERROR is authoritative):
```
PYTHONPATH=src:subrepos/construction-financial-review/src .venv/bin/python -m pytest \
  tests/test_feedback_*.py tests/test_fastapi_analytics_feedback.py tests/test_nas_mcp_feedback.py -q
```
Result: all pass (0 FAILED / 0 ERROR).

## Schema-head tests made head-agnostic (the V109 bump)
- `test_answer_draft_v108_migration.py` — `== 108` → `== LATEST_SCHEMA_VERSION`; head floor `>= 108`.
- `test_source_identity_v99_migration.py` — `test_latest_schema_version_is_108` renamed
  `..._at_least_108`, `== 108` → `>= 108`.
- `test_nas_mcp_workflows.py::test_no_schema_bump` — `== 108` → `>= 108` (companion
  `test_no_workflow_persistence_table_in_migrator` still proves no workflow tables).
- `test_workflow_registry.py::test_no_schema_bump` — `== 108` → `>= 108`.

## Regression + cross-domain
- N8C MCP regression subset (workflow_handlers, workflow_router, nas_mcp_{workflows, research_packets,
  answer_drafts, source_connector, review, intelligence, decision_memory, context_packs, memory, readonly})
  — exit 0, zero FAILED/ERROR. Includes `test_existing_finality_guard_still_passes` (covers the six feedback
  tools).
- `scripts/test-schedule.sh` (migrator cross-domain canary) — see 13-git-status / run log.
- `scripts/test-forecasting.sh` — see run log.
- `ruff check` on all changed source + new test files — All checks passed. (Pre-existing `api.py` ruff
  findings are outside the additive feedback block, lines 3327–3409, and `api.py` is not in the strict ruff
  scope per CLAUDE.md.)
