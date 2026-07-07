# N8C-12 NAS Source-Root Connector Surfaces & Indexed File Discovery — Closeout

**Phase:** N8C-12 (NAS second-brain). Read-only. Makes indexed NAS source-root FILES first-class,
root-aware, cursor-paged, bounded, read-only MCP/API/CLI objects — distinct from vault notes and generated
source cards. **No schema bump.** **Uncommitted** (stop-before-commit per authorization). No push/PR/merge.

## Lineage
- N8C-10 intelligence projections: `bfc1e743`
- N8C-11 research packets (V107): `0e2876c7` (committed this session, no AI trailer, parent bfc1e743)
- N8C-12 branch: `ops/nas-second-brain-n8c-12-source-root-connector-20260707T091206Z` (base = `0e2876c7`)
- N8C-12 HEAD still at base `0e2876c7` — all N8C-12 work is uncommitted working tree.

## Problem resolved
The live NAS MCP behaved like a vault/note connector, not a private-Drive-style source-file connector.
Repo truth (audited): generic `hb_root_search` lists ONE directory, name-only, non-recursive, hard-capped,
no cursor; the index-backed `search_sources`/`search_knowledge`/`source_index_status` are blocked on the NAS
adapter; and FTS search rows omitted `source_root_key`, so follow-up original-file access was ambiguous, with
no cursor pagination and no on-demand bounded original-file reader.

## What N8C-12 adds (read-only)
- 6 remote MCP tools `assistant_source_*` (status / roots_list / files_list / file_search / file_metadata /
  file_read); new assistant remote tool total **42 → 48**; `ai_outputs_card_upsert` stays the only remote
  write.
- 6 read-only GET API routes; `hb-assistant source-connector` CLI group (status/roots/search/list/metadata/
  read).
- Root-aware search/list rows always carrying `source_root_key` + root-relative `rel_path` + an **opaque
  path-free `source_ref`**; deterministic **keyset** cursor windows; metadata distinguishing the original
  source file (primary) from a supplemental generated card; bounded, extension-gated single-file reads via a
  narrow `SourceContentProvider` with an `indexed_excerpt_fallback`.

## No schema change
`LATEST_SCHEMA_VERSION` stays **107**; `store/migrator.py` untouched; no schema head tests modified. All needs
are read-model adaptations over the existing V93/V94 `source_intelligence_*` tables (see `03`).

## Verification (all green)
- 42 new N8C-12 tests pass (18 service + 10 API + 8 MCP + 6 eval-fixture).
- N8C-1→N8C-11 regression + N8C-12: **479 passed** (0 failures).
- ruff: clean on all in-scope N8C-12 files.
- `scripts/test-schedule.sh`: green (migrator NOT edited; run as the cross-domain canary).

## One route-collision fix during verification
`/api/assistant/sources/status` collided with the N8C-3 `/api/assistant/sources/{source_id}` route → used
the collision-free `/api/assistant/source-index/status`. Literal `/source-files/search` is declared before
`/source-files/{source_id}` (N8C-11 shadowing lesson).

## Boundaries held
No live recursive scan in the request path; no scan/reindex; no source-card generation; no raw SQL; no
absolute host paths; no vault/raw/import/source mutation; no action execution; no `hb_root_*` broadening; no
unblocking of the raw obsidian source tools; no N8D/`agent_bridge` touch.
