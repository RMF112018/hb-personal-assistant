# 03 — Current-State Audit + No-Schema-Bump Proof

## No schema bump (default held)
- `LATEST_SCHEMA_VERSION = 107` unchanged (`store/migrator.py` NOT in the N8C-12 changed set — see `14`).
- No new tables, no migrator block, no schema head test modified
  (`test_schema_version_head_consistency.py` / `test_source_identity_v99_migration.py` untouched).
- Reused, existing V93/V94 `source_intelligence_*` schema supplies every field:
  `source_intelligence_sources` (`source_id`, `source_root_key`, `rel_path`, `deleted`),
  `source_intelligence_metadata` (`file_ext`, `size_bytes`, `mtime_ns`, `content_sha256`, `extraction_status`,
  `fts_rowid`), `source_intelligence_text` (`text_excerpt`, `excerpt_truncated`),
  `source_intelligence_generated_notes` (card linkage), and the `source_intelligence_fts` FTS5 table.

## Stable identity reuse
`source_id = sha256(source_kind|file|source_root_key|rel_path)[:32]`
(`source_index_repository.source_id_for`) is already stable + root-aware → used directly as the connector's
source identity; `source_ref` is a bounded opaque wrapper around it (see `05`).

## Working tree
N8C-12-only: 6 modified + 4 new source + 4 new test files (enumerated in `14`). No
`agent_bridge`/`second_brain`/`construction/email`/source-card-render/scratch/recovery paths touched.
`local-sensitive/` git-ignored (confirmed before writing).
