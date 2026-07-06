# N8C-8 — git status (uncommitted)

## Baseline & branch
- N8C-6 commit: `c9866927207190a8cae092125107148285d6f46d` (`feat(nas): add n8c context pack builder`).
- N8C-7 commit: **`b99151f175c2028fcda255b449be050172a50f0a`** (`feat(nas): add n8c memory compiler`) —
  committed in Part 1 this session (staged-only, no AI trailer, not pushed).
- N8C-8 branch: **`ops/nas-second-brain-n8c-08-decision-open-loop-memory-20260706T203541Z`**, base `b99151f1`.
- Worktree: `/Users/bobbyfetting/hb-pa-n8c02-20260705T200705Z`. No `src/hb_assistant/agent_bridge/`
  (no N8D). No `agent_bridge` import in any changed file.

## Change set — 10 modified + 10 new (+ this evidence bundle)

### Modified (10)
```
 M src/hb_assistant/cli/main.py                        (+2  — register `decision-memory` typer)
 M src/hb_assistant/construction/analytics/api.py      (+67 — 6 read-only GET routes; 0 new ruff findings)
 M src/hb_assistant/nas_mcp/broker.py                  (+68 — allowlist + read-only-snapshot dispatch + status)
 M src/hb_assistant/nas_mcp/profile.py                 (+13 — assistant_decision_memory_enabled() gate)
 M src/hb_assistant/nas_mcp/tool_registration.py       (+38 — gated read-only tool block, 6 tools)
 M src/hb_assistant/obsidian_mcp/memory_repository.py  (+22 — read-only list_built_compilations_for_sources)
 M src/hb_assistant/store/migrator.py                  (+22 — V104 wiring + head bump 103→104)
 M tests/test_memory_v103_migration.py                 (head assertion → V103-present + head ≥103)
 M tests/test_schema_version_head_consistency.py       (+v104 row present + prior-tables-survive-v104)
 M tests/test_source_identity_v99_migration.py         (latest-head assertion 103→104)
```

### New (10)
```
?? src/hb_assistant/store/assistant_decision_memory_tables.py   (V104 DDL — 4 tables, enum tuples)
?? src/hb_assistant/obsidian_mcp/decision_memory_models.py      (enums, anchor/identity/record ids, records)
?? src/hb_assistant/obsidian_mcp/decision_memory_repository.py  (sole reader/writer of the 4 N8C-8 tables)
?? src/hb_assistant/obsidian_mcp/decision_memory_extractor.py   (deterministic 2-path extractor, no LLM)
?? src/hb_assistant/cli/decision_memory.py                      (preview|extract|export|list)
?? tests/test_decision_memory_v104_migration.py
?? tests/test_decision_memory_repository.py
?? tests/test_decision_memory_extractor.py
?? tests/test_fastapi_analytics_decision_memory.py
?? tests/test_nas_mcp_decision_memory.py
```

Plus `docs/evidence/nas-second-brain-n8c/20260706T203541Z/**` (this bundle; `local-sensitive/` is
gitignored per `.gitignore:209`, consistent with N8C-6/7).

## Not touched
N8D / `agent_bridge/`, source/card rendering, `construction/second_brain/`, the Obsidian vault, and
every raw/import/source/claim/enrichment/context-pack/memory table (only the 4 N8C-8 tables are written;
the one memory_repository edit is a READ-ONLY helper).

## Commit posture
**Working tree remains uncommitted.** N8C-8 commit NOT authorized — stopped before commit. No push, no
PR, no merge. Plain commit message + no AI co-author trailer if/when a commit is later authorized.
