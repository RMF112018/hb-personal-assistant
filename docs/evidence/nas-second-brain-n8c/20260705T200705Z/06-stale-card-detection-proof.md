# 06 — Stale-Card Detection Proof

## Implementation (`source_card_identity.detect_stale_card`, read-only, ordered)
1. `source_deleted` — source row absent or `deleted=1`.
2. `card_file_missing` — DB row generated but the `.md` is gone.
3. `source_id_mismatch` — card at that path is not a source card, or frontmatter `source_id` ≠ source.
4. `card_version_obsolete` — card `card_version` present but ≠ `source_notes.CARD_VERSION` (named
   constant, revision 3).
5. `source_digest_drift` — card frontmatter `source_sha256` ≠ current `_metadata.content_sha256`
   (mirrors the summary-drift pattern; no stored per-card digest, no migration).

**Legacy ≠ corruption (revision 3):** a card missing `card_version`/`source_sha256` is flagged
`legacy_no_card_version` / `legacy_no_source_digest` and is **not** declared stale on that basis.

`classify_card_state` rolls a source up to `current | stale | missing | duplicate | source_deleted |
no_card`. **Source-deleted-but-card-active is classified only — never retired/deleted (revision 4).**

## Proof (`tests/test_obsidian_source_card_identity.py`)
- `test_stale_by_source_digest_drift` — mutate source + re-index → card frontmatter sha ≠ current
  content_sha → `source_digest_drift` (detected even though the DB status was not changed).
- `test_missing_card_file` — delete the `.md` → `card_file_missing` / `STATE_MISSING`.
- `test_source_deleted_card_active_is_classification_only` — `mark_deleted` → `STATE_SOURCE_DELETED`;
  **card file and source row remain** (identity layer mutates nothing).
- `test_source_id_mismatch` — card checked against the wrong source → `source_id_mismatch`.
- `test_card_version_obsolete_uses_constant_not_legacy` — `card_version` present-but-old →
  `card_version_obsolete`, and `legacy_no_card_version` NOT flagged.
- `test_current_card_is_not_stale` — freshly generated card → `STALE_NONE` / `STATE_CURRENT`.
- `test_legacy_card_missing_fields_is_distinct_not_corruption` — legacy card validates ok; missing
  fields reported as `legacy_*`, not failure.
