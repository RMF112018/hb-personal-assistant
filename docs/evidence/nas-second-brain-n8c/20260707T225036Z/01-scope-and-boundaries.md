# N8C-20 — scope and boundaries

## Files added (12)

```
src/hb_assistant/store/assistant_quality_tables.py     V111 DDL (5 tables) + enum tuples
src/hb_assistant/obsidian_mcp/quality_models.py        dataclasses + deterministic ids + caps + policy
src/hb_assistant/obsidian_mcp/quality_repository.py    sole reader/writer of the 5 quality tables
src/hb_assistant/obsidian_mcp/quality_evaluator.py     deterministic read-only advisory evaluator
src/hb_assistant/cli/quality.py                        `hb-assistant quality` (preview/build/list/show/summary/export)
tests/test_quality_v111_migration.py
tests/test_quality_models.py
tests/test_quality_repository.py
tests/test_quality_evaluator.py                        guardrail-heavy: snapshot-before/after immutability
tests/test_quality_cli.py
tests/test_fastapi_analytics_quality.py
tests/test_nas_mcp_quality.py
```

## Files modified (6, additive only)

```
src/hb_assistant/store/migrator.py                     LATEST_SCHEMA_VERSION 110→111 + _v111_statements() + guarded V111 apply block
src/hb_assistant/cli/main.py                           register `quality` typer (alphabetical import)
src/hb_assistant/construction/analytics/api.py         6 GET-only /api/assistant/quality* routes
src/hb_assistant/nas_mcp/profile.py                    assistant_quality_enabled() + gate_status line
src/hb_assistant/nas_mcp/broker.py                     ASSISTANT_QUALITY_TOOLS + dispatch branch + _invoke_assistant_quality (RO snapshot)
src/hb_assistant/nas_mcp/tool_registration.py          6 gated @mcp.tool() read-only quality tools
```

## Explicitly NOT touched / NOT implemented

- No `agent_bridge/`, no N8D worktree file, no N8C-13 UI.
- No `construction/email/`, `construction/second_brain/`, source/card rendering, `tests/test_review_router.py`.
- No execution, no automatic repair, no external integration, no source scan/reindex, no source_file_read,
  no `SourceContentProvider`, no source-card generation, no live LLM/Qwen/Ollama.
- No review-disposition write (outside the feedback-owned lifecycle, which this phase does not touch).
- No MCP write/build/apply/evaluate/repair tool; the finality guard is not weakened.
- `ai_outputs_card_upsert` remains the only sanctioned remote write.

## Clarifications honored

- **#4** — CLI uses the repo `build --dry-run/--apply` convention; MCP is read-only inspection ONLY (no
  build/apply/evaluate/run/repair MCP tool).
- **#5** — `evaluated` is a quality-run lifecycle status only (never execution/repair/acceptance/application).
- **#6** — findings are advisory only; no type/status/event/route/command/tool accepts/rejects/defers/
  disposes/closes/reopens anything.
- **#7** — snapshot-before/after tests prove preview, dry-run, and apply mutate no upstream table; only
  `assistant_quality_*` change on `quality build --apply` (see `05-no-upstream-mutation.md`).
