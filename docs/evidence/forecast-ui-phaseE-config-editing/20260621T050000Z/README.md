# Forecast UI — Phase E: Config Editing (isolated proposal) — evidence

**Stamp:** 20260621T050000Z · **Branch:** `feature/forecast-ui-phaseE-config-editing`
(off `origin/main`, committed schema **v61**) · **Status:** uncommitted (awaiting authorization)

## What this phase delivers

The first config-**write** forecast surface, as an **isolated proposal**. An operator proposes edits
to forecast config items; the backend seeds a base config tree from a chosen **live** snapshot
(opened `mode=ro` — the live DB is never written and is never handed to a CFR function), applies the
validated edits in an isolated per-edit directory under a fail-closed **config-edit root**, runs the
CFR `import → snapshot → materialize → parity` pipeline in an **isolated temp DB**, and returns a
parity-proven materialized snapshot + a redacted report. **Zero live-DB writes, zero live-data-root
writes, no schema change, no migration.** A later phase can certify-promote a proposal.

### Editable domains
`project` (whitelisted business fields only — dev-internals preserved on disk, never surfaced),
`forecast_model_controls`, `forecast_staffing`, `owner_sov_crosswalk`. **`forecast_controls` is
deprecated** (superseded by `forecast_model_controls`) → rejected by the API and shown read-only with
a deprecation note in the viewer.

### Two load-bearing invariants
1. **No live write via the seed.** The service opens the live source DB itself with `?mode=ro`,
   SELECTs the chosen snapshot's grouped rows, and emits the base tree locally; every CFR write call
   (`import`/`snapshot`/`materialize`/`parity`) is given only an **isolated** temp DB.
2. **Redaction.** The materialize/parity manifests embed absolute paths/stamps; all returns go
   through `summarize_*` (parity → status + domain keys + per-domain counts; manifest endpoint
   rebuilds a path-free shape). Every payload passes `find_redaction_leaks == []`.

## Validation summary

- **Backend:** `test_forecast_config_edit_service.py` (11) + `test_fastapi_forecast_config_edit.py`
  (7) → 18 green; with runtime/app-shell/config-viewer regression → 56 green (`test_output.txt`).
  Covers: per-domain edits → parity **pass** + leak-free; **project whitelist-merge** (dev-internals
  preserved on disk AND absent from payload); `forecast_controls` rejected; Decimal money enforced;
  fail-closed (root unset / under data root); unknown snapshot/edit; live DB untouched; parity-fail
  rendering is path-free.
- **Lint/type:** `ruff` + `mypy` clean on the new modules.
- **Frontend:** typecheck / copycheck / build clean; new proposals page test 3/3 (full vitest: only
  the pre-existing `SettingsPage` ×5 fail).
- **CFR subrepo:** **565 passed**, unchanged — Phase E imports CFR but changes none of it
  (`cfr_test_posture.txt`).
- **Real read-only smoke** (`live_untouched_proof.txt`): seeded a project edit from the **real live
  194-item snapshot** (`tropical-phase16-live-config-…`). Result: status **succeeded**, parity
  **pass** over all 194 items, **zero redaction leaks**, and live DB sha **identical before == after**
  (`mode=ro`). This proves the full pipeline works against real data with no live writes, and that the
  base-tree emit round-trips the real config (the 193 unedited items materialize identically).

## Notes

- **No migration.** Committed `LATEST_SCHEMA_VERSION` stays **61**; config edits write the existing
  v60 tables only in an isolated temp DB (CFR auto-migrates that temp DB). The working tree's **v62**
  is the unrelated uncommitted **Procore** migration and is **excluded** from Phase E (`git_state.txt`,
  `preexisting_failures.txt`).
- A new `config_edit_root` was added to the Phase 6 runtime-config as a **7th write-root** (env
  `HB_FORECAST_CONFIG_EDIT_ROOT`, settings key `config_edit_root`), with the same under-data-root
  cross-check as `runs_root`/`eval_root`.
