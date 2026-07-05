# 02 — Source/Card Current-State Audit

Read-only audit of the existing source/card layer on base `c454a581`.

## DB (`store/source_intelligence_tables.py`, `LATEST_SCHEMA_VERSION = 99`)
- `source_intelligence_sources`: `source_id` PK, `source_kind`, `source_root_key`, `rel_path`,
  `domain_ref_table/id`, `deleted`, `active`. Content digest lives in `_metadata.content_sha256` +
  `mtime_ns`.
- `source_intelligence_generated_notes`: `generated_note_id, source_id, note_rel_path,
  generation_status ∈ {not_generated,generated,stale}, generated_at, updated_at`, `UNIQUE(source_id,
  note_rel_path)`. **No** per-card digest column, **no** `card_status`/`last_refreshed_at`, **no**
  UNIQUE on `note_rel_path` alone.
- Stale-on-delete + stale-on-reindex already wired (`_mark_generated_notes_stale`). Summary drift
  (`_summaries.source_sha256` vs `_metadata.content_sha256`) is the existing pattern reused for cards.

## Card frontmatter (`obsidian_mcp/source_notes.py::_frontmatter`) — already carries identity
`note_type: source_card`, `source_id`, `source_kind`, `source_root_key` (file) /
`source_ref_table`+`source_ref_id` (link), `source_sha256` (= `content_sha256`), `source_mtime_ns`,
`domain`, `card_version` (`phase10a-v1`), `template_version` (`source-card-v1`). **No** `card_id`,
`managed_by`, or `card_status`. Frontmatter is **already neutral** (no `hb_` keys). Card path:
`<Source Notes>/<Domain>/<basename>__<source_id12>.md`.

## Gaps N8C-2 fills
- No card→source reverse lookup → added read-only `get_sources_for_note` (ambiguity-aware) +
  `list_cards_for_source`.
- No `card_id` → computed `sha256(source_id|note_rel_path)[:16]` (no storage/migration).
- No stale-by-digest for cards → compare card frontmatter `source_sha256` vs current `content_sha256`.
- No duplicate-card detector / note-type classifier / frontmatter validator → new read-only service.

## Decision: no migration
Every N8C-2 need is met by existing columns + card frontmatter; a per-card digest column,
`last_refreshed_at`, a `note_rel_path` UNIQUE, or a reverse-lookup index would each be a migration and
are **not** required. `LATEST_SCHEMA_VERSION` stays 99.
