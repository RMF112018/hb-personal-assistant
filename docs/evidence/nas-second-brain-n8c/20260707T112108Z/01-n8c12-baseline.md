# 01 — N8C-12 Baseline

N8C-14 branches off the committed N8C-12 source connector.

- `git rev-parse HEAD` = `e6a75838fafb603e17251b99f64e83952da3c70f` (N8C-12, parent `0e2876c7` N8C-11).
- Branch: `ops/nas-second-brain-n8c-14-citation-safe-answer-drafts-20260707T102742Z` (base `e6a75838`).
- No `agent_bridge` dir; no N8D worktree files in the tree.
- N8C-12 shipped 6 read-only source-connector MCP tools (remote assistant tool total 42→48) + 6 GET routes +
  a `source-connector` CLI group, all read-only over V93/V94 `source_intelligence_*`. N8C-14 reuses N8C-12's
  `SourceIndexRepository.get_source_detail` (DB read) + `encode_source_ref` (pure) for **metadata-only**
  citation enrichment — never `SourceContentProvider` / `source_file_read`.
