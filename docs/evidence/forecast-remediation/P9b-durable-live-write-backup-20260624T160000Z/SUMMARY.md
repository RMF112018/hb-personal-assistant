# P9b — Durable gated live-write backup relocation (CFR Phase 14)

- Phase: forecast-model remediation **P9b** (split from P9)
- ADR: `docs/architecture/311-forecast-p9b-durable-live-write-backup.md`
- Gap: #9 (durability)
- Scope: relocate the CFR Phase-14 pre-write live-DB backup from the **ephemeral** `work_root/backups`
  to a **durable, configurable** root. **Sensitive** (gated live-DB write path) → routed through the
  sensitive-operation gate. **No** schema/migration/`table_count`/hb_assistant-schema change; **no**
  live-DB write or real managed-DB run.

## Problem

CFR Phase 14 (`workflows/live_db_source_domain_projection.py`) backed the live DB up to
`work_root/backups/...` before the gated write. `work_root` is the per-run temp dir, so the only
pre-write backup was discarded with it — a failed post-write certification could find nothing to
restore from.

## What landed

1. **`PathPolicy.get_db_backups_dir()`** (`src/hb_assistant/config/path_policy.py`) →
   `<app_support>/db/backups` (sibling of the managed DB, outside `_LIVE_ROOT`).
2. **CFR workflow** (`.../workflows/live_db_source_domain_projection.py`):
   - `BACKUP_NAME` → `BACKUP_NAME_PREFIX` + `_backup_name(context_stamp)` (stamp-qualified).
   - `_backup_live_db` + `run_controlled_live_db_source_domain_projection` take
     `backup_root: Path | None = None`. None ⇒ unchanged `work_root/backups` fallback; supplied ⇒
     durable dest, with the **same** `_is_under(_LIVE_ROOT)` fail-closed refusal as `work_root`.
   - Resolved base recorded as `backup["backup_root"]`.
3. **CFR CLI** (`.../cli.py`): new optional `--backup-root`; when omitted,
   `cmd_live_db_source_domain_project` lazily imports `PathPolicy` and defaults to
   `get_db_backups_dir()` (module stays hb_assistant-free at import time — the CLI is the only
   Phase-14 entry point, so it is the host-side resolution boundary). rc 0/1/3 unchanged.

## Key decisions

- **Phase-14 only.** Phase 3 (`live_db_run_output_projection.py`) + Phase E2
  (`live_db_config_registry_promotion.py`) keep their own `_backup_live_db` copies for a later pass.
- **Default `backup_root=None` preserves current behavior** so direct-call tests stay green; only the
  filename becomes stamp-qualified.
- **All fail-closed gates preserved** (nonzero-WAL, no-overwrite, backup-readable + schema≥REQUIRED) +
  the new backup_root live-root refusal. No consistent-snapshot mechanism added.

## Validation

See `validation.txt` / `new_tests.txt`. Forecasting bundle 0 failing (Phase-14 file in the bundle);
`tests/test_config.py` PathPolicy test run directly; `ruff check` clean on the enforced Python.
Real managed DB untouched — tests use the monkeypatched synthetic live DB only.
