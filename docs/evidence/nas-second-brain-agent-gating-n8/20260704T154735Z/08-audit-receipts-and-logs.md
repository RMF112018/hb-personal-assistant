# 08 — Audit Receipts, Row-Count Deltas, Redaction / Secret-Scan

## Test receipts (temp/scratch DBs only — no live NAS)

| Suite | Result |
|---|---|
| `test_source_identity_v99_migration.py` (6) + flipped collision test + `test_v99_migration_row_present` | pass |
| `test_nas_default_off_gating.py` (6) | pass |
| `test_obsidian_source_watch_ownership.py` (11, incl. host-stamp) | pass |
| Consolidated N8-touched suites (identity/migration, default-off, ownership, schema-version, pm-grade cards, watch, auto-generate, source-index repo, db-storage-guard, nas-mcp, nas-runtime-scaffold) | **114 passed** |

## DB row-count / mutation receipts

- **Migration V99 backfill** (`test_v99_migration_remaps_old_colliding_ids_and_children`): seeded 1 pre-V99
  `sources` row + 1 `metadata` + 1 `generated_notes` child → after reconcile, all 3 remapped to the
  root-scoped `source_id`; old id count = 0; `PRAGMA foreign_key_check` returned `[]` (FK integrity intact).
- **Idempotency** (`test_same_root_upsert_is_idempotent`): two upserts of the same (root, rel_path) →
  exactly **1** `sources` row.
- **Cross-root coexistence** (`test_distinct_roots_same_relpath_coexist`): same rel_path under 2 roots →
  **2** distinct rows, distinct `source_id`s.
- All row-count assertions ran against `tmp_path` scratch DBs. **No live NAS DB was opened or mutated
  this session** (live-DB backfill row-count deltas are captured in Phase 05/07 with Bobby).

## Ownership / lock receipts

- Watcher lease owner now records `hostname` + `pid` + `db_path` + `roots_hash` (token redacted from
  `status()`); `watcher_not_owner` logs `owner_host`/`owner_pid`.
- Run no-overlap lock payload records `hostname` + `pid` + `run_kind` + `acquired_utc` (token stored
  raw only on disk under `<app_support>/locks`; stale-reclaim records the prior token **hashed**).

## Redaction / secret-scan proof

- **`tests/test_repo_sensitive_scan.py`**: reports 16 findings (bearer_token/pem/oauth), **all in
  pre-existing test files & the CFR subrepo** (`test_procore_full_raw_payload_ingestion`,
  `test_obsidian_mcp_oauth`, `frontend/**`, `subrepos/construction-financial-review/**`). The failure is
  **identical on the clean `recon/nas-code-n7` base** — pre-existing allowlist drift in this environment,
  **not** introduced by N8. **Zero findings in any N8-added/modified file.**
- **N8 code diff** (`recon/nas-code-n7..HEAD`, `src/` + `tests/`): no bearer/PEM/password/client_secret/
  access_token/live-DB-path additions (grep clean).
- **N8 evidence**: no tailnet-IP/private-IP literals; `/Users/` paths present are non-secret local dev
  paths, consistent with existing committed N-track evidence (nas-copied-db-n3, nas-runtime-scaffold-n1b).
  No tokens/keys/decrypted content.
- Reconciliation stack carries **0** attribution trailers (Cursor stripped; no Claude/Anthropic).
