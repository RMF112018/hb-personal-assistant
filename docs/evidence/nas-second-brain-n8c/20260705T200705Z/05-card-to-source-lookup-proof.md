# 05 — Card → Source Reverse Lookup Proof (ambiguity-aware)

## Implementation
- Repo (read-only): `SourceIndexRepository.get_sources_for_note(note_rel_path) -> list[dict]` — joins
  `generated_notes → sources` `WHERE note_rel_path=?`. Returns a **list** on purpose: there is no
  UNIQUE on `note_rel_path` alone, so two `source_id`s can claim one card path (revision 2).
- Service: `get_source_for_card(repo, note_rel_path) -> ReverseLookup` with
  `resolution ∈ {none, unique, ambiguous}`. Ambiguous → `source_id=None` + the full list; it **never
  picks a source arbitrarily**.

## Proof (`tests/test_obsidian_source_card_identity.py`)
- `test_card_to_source_reverse_lookup_unique` — one card path → its single source; `resolution="unique"`.
- `test_card_to_source_reverse_lookup_none` — unknown path → `resolution="none"`, empty list.
- `test_card_to_source_reverse_lookup_ambiguous_never_arbitrary` — two sources recorded at one card
  path → `resolution="ambiguous"`, `source_id is None`, both source_ids returned.

Read-only; the second record in the ambiguity test uses the existing `record_generated_note` write
path only to construct the fixture state, not as a feature of the identity layer.
