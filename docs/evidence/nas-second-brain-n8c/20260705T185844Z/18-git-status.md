# 18 — Git Status

- **Branch:** `ops/nas-second-brain-n8c-01-neutral-graph-20260705T185844Z`
- **Base:** `e80f3729c661a98daa04c2d393b19fce253eeb94` (`origin/main`); merge-base == base.
- **N8C-1 implementation commit:** `acd22926` (tests + evidence + implementation).
- **Committed locally, NOT pushed.** Working tree clean after commit.
- _(Corrected post-commit: this file originally read "Not committed"; the N8C-1 work was committed as
  `acd22926`. This evidence-metadata correction is a separate follow-up commit on the N8C-1 branch.)_

## `git status --short`
```
 M scripts/obsidian_source_card_append_local_summary.py
 M src/hb_assistant/nas_mcp/ai_outputs.py
 M src/hb_assistant/nas_mcp/broker.py
 M src/hb_assistant/nas_mcp/tool_registration.py
 M src/hb_assistant/obsidian_mcp/source_card_repair.py
 M src/hb_assistant/obsidian_mcp/source_local_summary.py
 M src/hb_assistant/obsidian_mcp/source_notes.py
 M tests/test_nas_mcp_remote_profile.py
?? docs/architecture/n8c-memory-classes-and-boundaries.md
?? docs/architecture/n8c-neutral-naming-policy.md
?? docs/architecture/n8c-personal-intelligence-operating-layer.md
?? docs/evidence/nas-second-brain-n8c/
?? src/hb_assistant/naming.py
?? tests/test_nas_mcp_ai_outputs.py
?? tests/test_obsidian_source_card_local_summary_marker.py
```

## Diffstat (tracked modified)
```
 scripts/obsidian_source_card_append_local_summary.py  | 15 +++++++++++----
 src/hb_assistant/nas_mcp/ai_outputs.py                | 17 ++++++++++++-----
 src/hb_assistant/nas_mcp/broker.py                    |  1 +
 src/hb_assistant/nas_mcp/tool_registration.py         |  2 ++
 src/hb_assistant/obsidian_mcp/source_card_repair.py   |  8 +++++---
 src/hb_assistant/obsidian_mcp/source_local_summary.py | 16 +++++++++-------
 src/hb_assistant/obsidian_mcp/source_notes.py         | 16 ++++++++++++----
 tests/test_nas_mcp_remote_profile.py                  | 15 +++++++++++++--
 8 files changed, 65 insertions(+), 25 deletions(-)
```

New files: `src/hb_assistant/naming.py`, three `docs/architecture/n8c-*.md`, two `tests/*`, and this
evidence bundle. All intended N8C-1 scope; nothing unrelated touched. The interim
`n8c-read-navigation-surface.md` + `n8c-personal-second-brain-architecture.md` drafts were removed
(content relocated into the three final docs).
