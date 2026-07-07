# 01 — N8C-14 baseline & carry-forward

## N8C-14 committed this session
- Commit `ae483f39` — `feat(nas): add n8c citation-safe drafts` (plain message, **no AI trailer**).
- Staged with explicit paths (no blind `git add -A`): 9 modified + 5 new source + 5 new test + the
  N8C-14 evidence dir (`docs/evidence/nas-second-brain-n8c/20260707T112108Z/`). `local-sensitive/`
  confirmed git-ignored and unstaged.
- Pre-commit confidence gate (fresh session): 70 tests green (N8C-14 suite + N8C-12 finality guard +
  schema-head-consistency), exit 0.
- Working tree clean after commit; not pushed.

## Carry-forward into N8C-15
- Schema head remains **V108** (N8C-15 adds none).
- N8C-14 draft tables/repos/models are the primary artifacts N8C-15 routes to (read-only).
- The N8C-12 finality guard (`test_nas_mcp_source_connector.py`) forbids the substring `answer`,
  `build`, `generate`, etc. in assistant MCP tool names — N8C-15 adds **no** MCP tools, so the guard
  is untouched and still passing.
