# 06 — Card State / Stale / Duplicate / Ambiguous Proof

## Covered by
`tests/test_obsidian_source_navigation.py`:
- `test_card_state_current` — fresh card classifies `state="current"` (vault-aware; reads the card
  file, digest matches). Read-only — reports state, never retires/deletes/rewrites (N8C-2 rule).
- `test_list_stale_cards` — after `mark_generated_notes_stale`, the source appears in `stale_cards`;
  bounded envelope.
- `test_list_duplicate_cards` — recording a 2nd active card path for one source yields a
  `duplicate_cards` entry with `card_count=2` (a duplicate the DB `UNIQUE(source_id, note_rel_path)`
  does NOT prevent).
- `test_list_ambiguous_card_links` — one card path claimed by two sources appears in
  `ambiguous_card_links` with both `source_ids`.

## Basis
`get_card_state` → N8C-2 `classify_card_state`; stale/duplicate/ambiguous listings are bounded scans
over `repo.list_generated_notes(statuses=("generated","stale"))` grouped by source_id / note_rel_path,
returning the `truncated` flag if capped (no silent truncation).

## Result
All pass. Health classifications are read-only and bounded.
