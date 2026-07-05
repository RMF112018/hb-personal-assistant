# 12 — Git Status

- **Branch:** `ops/nas-second-brain-n8c-02-source-card-identity-20260705T200705Z`
- **Base:** `c454a581` (corrected N8C-1 HEAD = `acd22926` impl + `c454a581` evidence-fix). N8C-1 is
  local-only (not on remote), so N8C-2 branches locally off `c454a581`.
- **Not committed, not pushed.** Commit locally only after tests + evidence pass **and** explicit
  authorization.

## `git status --short`
```
 M src/hb_assistant/obsidian_mcp/source_index_repository.py
?? docs/architecture/n8c-source-card-identity-contract.md
?? docs/evidence/nas-second-brain-n8c/20260705T200705Z/
?? src/hb_assistant/obsidian_mcp/source_card_identity.py
?? tests/test_obsidian_source_card_identity.py
```

## Diffstat vs base (tracked modified)
```
 src/hb_assistant/obsidian_mcp/source_index_repository.py | 37 ++++++++++++++++++++++
 1 file changed, 37 insertions(+)
```

The single tracked modification adds two **read-only** repository methods (`get_sources_for_note`,
`list_cards_for_source`). New files: the read-only identity service, the identity contract doc, the
test suite, and this evidence bundle. Card rendering (`source_notes.py`) is **untouched** — no
byte-change. Nothing unrelated is touched.
