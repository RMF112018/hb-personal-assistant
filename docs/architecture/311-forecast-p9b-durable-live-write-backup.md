# 311 — Forecast P9b: durable gated live-write backup relocation (CFR Phase 14)

- Status: accepted
- Date: 2026-06-24
- Phase: forecast-model remediation P9b
- Gap: #9 (durability), split from P9 as a sensitive CFR live-write-path change

## Context

CFR Phase 14 (`workflows/live_db_source_domain_projection.py`) is the first/primary **gated
live-DB write**: before replacing the tropical rows of the three v59 source-domain tables, it
takes a byte-for-byte backup of the live SQLite DB. That backup was written to
`work_root / "backups" / "hb-personal-assistant.before-phase14.sqlite"`. `work_root` is the
**ephemeral** per-run working directory (temp DB + report + sub-runs), so the only pre-write
backup of the live DB is discarded with the temp dir. If post-write certification fails and the
operator needs to restore, the backup may no longer exist.

P9 deliberately split this item out (sensitive-op gate) — see ADR 310. There is **no
hb_assistant service caller** for Phase 14; the only entry point is the CFR CLI
`live-db-source-domain-project`. So the durable root must be resolved at the CLI boundary, and
the CFR module must stay hb_assistant-free at import time (it already imports hb_assistant
lazily, only for the non-live temp DB).

## Decision

1. **Durable default home (host-side).** New `PathPolicy.get_db_backups_dir()` →
   `<app_support>/db/backups` — a sibling of the managed DB, outside the Synology live forecast
   data root (`_LIVE_ROOT`). The default is resolved host-side, never hardcoded in CFR.
2. **Configurable backup root (CFR workflow).** `_backup_live_db` and
   `run_controlled_live_db_source_domain_projection` gain `backup_root: Path | None = None`.
   - `backup_root=None` ⇒ unchanged ephemeral fallback `work_root / BACKUP_SUBDIR` (keeps all
     direct-call tests and any file-mode use working).
   - When supplied, `backup_root` gets the **same** `_is_under(.., _LIVE_ROOT)` fail-closed
     refusal already applied to `work_root`.
   - The resolved base dir is recorded as `backup["backup_root"]` for evidence.
3. **Stamp-qualified filename.** `BACKUP_NAME` (fixed) → `BACKUP_NAME_PREFIX` +
   `_backup_name(context_stamp)` = `hb-personal-assistant.before-phase14.<stamp>.sqlite`, so
   durable re-runs into a shared dir don't collide and each backup is traceable to its run. The
   no-overwrite gate stays meaningful (an exact-stamp re-run is still refused).
4. **CLI wiring.** New optional `--backup-root`. When omitted,
   `cmd_live_db_source_domain_project` lazily imports `PathPolicy` and defaults to
   `get_db_backups_dir()`; when supplied it is used verbatim. rc 0/1/3 contract and the
   clean-JSON-stdout posture are unchanged.

## Consequences

- All existing fail-closed gates preserved: nonzero-WAL refusal, no-overwrite (`backup_path.exists()`),
  backup readable + schema ≥ `REQUIRED_SCHEMA_VERSION`, plus the new backup_root live-root refusal.
- **Phase-14 only.** Phase 3 (`live_db_run_output_projection.py`) and Phase E2
  (`live_db_config_registry_promotion.py`) keep their own `_backup_live_db` copies for a later
  pass — out of scope here to keep the sensitive surface minimal.
- **No** schema/migration/`table_count`/hb_assistant-schema change; **no** consistent-snapshot/WAL
  mechanism added (nonzero-WAL still fails closed); **no** live-DB write or real managed-DB run in
  implementation or tests — tests exercise the monkeypatched synthetic live DB only.
- Tests: 2 phase-14 location assertions retargeted to `proj._backup_name(STAMP)`; new
  `test_backup_root_param_durable` (durable dest + recorded `backup_root` + no ephemeral fallback)
  and `test_backup_root_under_live_root_refused` (fail-closed) in the (already-bundled) phase-14
  file; `test_db_backups_dir_is_sibling_of_db` in `tests/test_config.py`.
- The real durable backup relocation takes effect only on an authorized live run that omits
  `--backup-root` (or passes the durable path); this PR ships the capability, not a live write.
