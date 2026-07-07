# N8C-20 — tests

Run with `PYTHONPATH=src:subrepos/construction-financial-review/src`. The environment strips pytest's summary
line, so exit-0 with zero `FAILED`/`ERROR` is the authoritative pass signal.

## New N8C-20 suite — 70 tests, green (exit 0, 70 `.`)

| file | tests | covers |
|------|-------|--------|
| `test_quality_v111_migration.py` | 17 | additive+idempotent V111, head==LATEST, prior V100–V110 survive, all policy/status/kind/finding-type/severity/event CHECKs fire, no repair/execution/disposition columns |
| `test_quality_models.py` | 12 | fixed advisory policy, pinned finding row, deterministic+idempotent ids, changed-target→changed digest, bounded text, enum validation |
| `test_quality_repository.py` | 8 | idempotent upsert, lineage-scoped supersede, writes ONLY the 5 quality tables, lifecycle events, invalid event rejected |
| `test_quality_evaluator.py` | 13 | **snapshot-before/after immutability (preview/dry-run/apply)**, advisory posture, defect detection (missing_citation/execution-language/missing_source_ref/unknown_target), policy/text-risk helpers, AST no-execution-entrypoint + no-forbidden-import + no-source-read guards |
| `test_quality_cli.py` | 5 | preview RO, dry-run default, apply persists, summary/export RO, command set has no execution/disposition verb |
| `test_fastapi_analytics_quality.py` | 8 | 6 GET-only routes, /summary not shadowed, advisory policy, 404s, all-roles, no write/build route, no token leak |
| `test_nas_mcp_quality.py` | 7 | 6 RO tools return data, RO snapshot, kill-switch scoped to quality only, no write/build/evaluate tool, status advertises group, safe-mode reads-not-writes |

## Regression (green, exit 0)

- `test_schema_version_head_consistency.py` — fresh DB migrates to `LATEST_SCHEMA_VERSION`==111; recorded head
  == constant.
- `test_nas_mcp_workflows.py`, `test_nas_mcp_action_stages.py`, `test_nas_mcp_feedback.py` — sibling MCP groups
  intact; finality guard passes.
- `test_action_stage_v110_migration.py`, `test_feedback_v109_migration.py` — prior N8C migrations unaffected.

## Cross-domain bundles (migrator edit canary)

- `scripts/test-schedule.sh` — GREEN (see `09b-bundle-schedule.txt`).
- `scripts/test-forecasting.sh` — GREEN (see `09c-bundle-forecasting.txt`).

## Lint

`ruff check` clean on all 12 new files + the 5 fully-owned modified files (migrator/main/profile/broker/
tool_registration). `api.py` retains 48 pre-existing errors (module not in strict ruff scope per CLAUDE.md);
none fall within the N8C-20 quality route block.
