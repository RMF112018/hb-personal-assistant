# 09 — Tests

## New N8C-19 suites (68 test functions, all green)
| file | functions | focus |
| --- | --- | --- |
| `test_action_stage_v110_migration.py` | 14 | head-agnostic, 5 tables, idempotent, prior survive, stage+item policy CHECKs (execution/external/staged_state/operator-review), citation anchor CHECK, no finality/dispatch columns |
| `test_action_stage_models.py` | 13 | deterministic ids, fixed no-execution policy, pinned non-execution item fields, internal-review-only kinds, provenance-anchored citations, bounded caps |
| `test_action_stage_repository.py` | 8 | idempotent upsert, lineage supersede (+ non-supersede across lineage), writes ONLY stage tables, non-executing items |
| `test_action_stage_builder.py` | 13 | preview/dry-run read-only, apply non-executing + no upstream mutation, advisory-execution-verb → blocked, feedback rec → advisory candidate, trusted skipped / terminal blocked, code-symbol + AST guards |
| `test_action_stage_cli.py` | 5 | preview RO, dry-run default / apply write, list/show/export, no execution command |
| `test_fastapi_analytics_action_stages.py` | 8 | GET-only, /summary not shadowed, non-executing items, redacted, 404, no write route |
| `test_nas_mcp_action_stages.py` | 7 | RO snapshot, kill-switch scoped, finality-clean, status advert, ai_outputs sole write |

Result: all pass (0 FAILED / 0 ERROR). Combined N8C-19 + schema-head + feedback-migration run: 126 passed.

## Schema-head + companion updates
- The four schema-head tests were already head-agnostic (`>= 108` / `== LATEST_SCHEMA_VERSION`) from N8C-18;
  they cover the V110 head unchanged.
- `test_feedback_v109_migration.py::test_no_action_stage_tables` was reframed to
  `test_v109_statements_create_no_action_stage_tables` (asserts the V109 STATEMENTS themselves define no
  action-stage table) — head-agnostic, since V110 legitimately adds those tables at a higher schema version.

## Regression + cross-domain
- N8C MCP regression subset (workflow_handlers/router, nas_mcp_{workflows, research_packets, answer_drafts,
  source_connector, review, readonly, feedback}) — exit 0, zero FAILED/ERROR. Includes
  `test_existing_finality_guard_still_passes` (covers the six action-stage tools).
- `scripts/test-schedule.sh` (migrator cross-domain canary) — see 10-git-status.
- `scripts/test-forecasting.sh` — see 10-git-status.
- `ruff check` on all changed source + new test files — All checks passed. (Pre-existing `api.py` findings are
  outside the additive action-stage block and outside strict ruff scope per CLAUDE.md.)
