# 07 — Duplicate-Card Detection Proof

## Layers
1. **DB guard (existing):** `UNIQUE(source_id, note_rel_path)` on `source_intelligence_generated_notes`
   blocks exact `(source, path)` duplicates; `record_generated_note` upserts via `ON CONFLICT`.
2. **N8C-2 detection (read-only, `detect_duplicate_cards`)** covers the two vectors the UNIQUE does not:
   - **one source → multiple active card paths** → `is_duplicate = True`;
   - **one card path → multiple sources** → `cross_source_conflicts`.

`classify_card_state` returns `STATE_DUPLICATE` when a source has >1 active card path. Detection is
read-only — N8C-2 flags duplicates, it does not delete/merge them.

## Proof (`tests/test_obsidian_source_card_identity.py`)
- `test_duplicate_cards_one_source_multiple_paths` — a source with two active card rows →
  `is_duplicate`, `STATE_DUPLICATE`.
- `test_duplicate_cards_cross_source_conflict` — two sources at one card path → `cross_source_conflicts`
  lists the other source_id.
- `test_no_duplicate_for_clean_source` — a single-card source → not duplicate, no conflicts.
- Ambiguity partner: `test_card_to_source_reverse_lookup_ambiguous_never_arbitrary` (`05`).
