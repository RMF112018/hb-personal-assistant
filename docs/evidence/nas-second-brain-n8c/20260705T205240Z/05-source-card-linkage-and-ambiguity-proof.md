# 05 — Source↔Card Linkage & Ambiguity Proof

## Covered by
`tests/test_obsidian_source_navigation.py`:
- `test_get_card_for_source` — source → primary active card (`note_rel_path` + `source_id`).
- `test_card_to_source_unique_and_ambiguous` — card → source:
  - unique card path resolves `resolution="unique"`, `source_id=sid_a`.
  - after a second source is recorded at the same card path,
    `resolution="ambiguous"`, `source_id=None`, `count=2` — **never picks one arbitrarily**.
- `test_card_to_source_none` — unknown card path → `resolution="none"`, `sources=[]`.

## Basis
Reuses the N8C-2 read-only identity layer: `identity.get_card_for_source` /
`identity.get_source_for_card` (`ReverseLookup`) over `repo.get_sources_for_note` /
`repo.list_cards_for_source`. No new reverse-lookup logic; N8C-3 only wraps it into the stable
`{note_rel_path, resolution, source_id, sources, count}` shape.

## Result
All pass. Ambiguity is surfaced, never resolved arbitrarily.
