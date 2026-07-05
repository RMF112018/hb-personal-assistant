# 04 — Source → Card Lookup Proof

## Implementation
- `source_card_identity.get_card_for_source(repo, source_id)` — returns the active card row (prefers
  `generated` over `stale`), enriched with the computed `card_id`. `None` if no card.
- `source_card_identity.list_cards_for_source` / repo `list_cards_for_source(source_id)` — all rows
  for a source (any status), the basis for duplicate/state detection. Read-only.
- `compute_card_id(source_id, note_rel_path) = sha256("{source_id}|{note_rel_path}")[:16]` — a
  deterministic card identity **distinct from** `source_id` (16-hex vs 32-hex, different key space);
  the same source at a different path is a different card.

## Proof (`tests/test_obsidian_source_card_identity.py`)
- `test_source_to_card_lookup` — indexed source → its generated card row; `card_id` matches
  `compute_card_id(source_id, note_rel_path)`; status `generated`.
- `test_compute_card_id_is_deterministic_and_distinct_from_source_id` — deterministic; `!= source_id`;
  16 chars; different path → different card_id.

All read-only; no card written, no DB mutated.
