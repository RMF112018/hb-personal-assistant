# Forecast UI — Phase E2: Config Promotion (certified live write) — evidence

**Stamp:** 20260621T060000Z · **Branch:** `feature/forecast-ui-phaseE2-config-promotion`
(off `origin/main`, committed schema **v61**) · **Status:** uncommitted (awaiting authorization)

## What this phase delivers

Closes the Phase E loop: take an **approved** proposal (status `succeeded` + parity `pass`) and
**certify-promote** it into the LIVE v60 config-registry DB as a **new snapshot**, making the live
registry the auditable system-of-record the config viewer shows as "current config". This is the
**first analytics live-DB write**, mirroring the Phase 14 gated discipline (backup → single txn →
certification).

**Scope:** config is lineage-only — the controlled generators do not consume DB config — so promotion
updates the recorded current config / viewer, **not** how forecasts are generated.

### The load-bearing invariant

`create_forecast_config_snapshot` snapshots `WHERE status='active'`, so importing an edited config into
the live DB would double-count (base + edited both active). Therefore the snapshot is built in a
**fresh temp DB** (only the edited config active there) and its rows are **copied** into the live DB —
the workflow never snapshots on the live DB. Promotion is **additive** (one new snapshot; history +
non-tropical preserved).

### Gated sequence (mirrors Phase 14)

`allow_live_db_write` gate → preflight (schema ≥ v60, config tables present) → fresh temp
import+snapshot → **expected-match gate** (temp snapshot's item_count + hashes_by_domain MUST equal the
approved proposal's) → byte **backup** (fail-closed on nonzero WAL; verify readable) → single
`BEGIN IMMEDIATE` transaction (column-match; refuse double-promote; insert; in-txn verify) →
post-write **dual-digest certification** of the promoted snapshot + assert every pre-existing snapshot
byte-unchanged → manifest + rc (0 certified / 1 not_ready / 3 refused).

Three-way analytics gating: default-OFF opt-in `HB_FORECAST_PROMOTION_ENABLED` + per-request
`confirm:true` + the proposal already parity-passed. Role: operator or admin. The returned payload is
redaction-safe (sha + counts + decision + booleans; all paths/stamps stripped).

## Validation summary

- **Backend:** `test_forecast_live_db_config_registry_promotion_phaseE2.py` (8 workflow tests) +
  `test_fastapi_forecast_config_promotion.py` (6 route/service tests) → 14 green; with app-shell +
  runtime regression → **37 passed** (`test_output.txt`). Covers: certified additive promotion;
  other/non-tropical snapshots preserved; expected-hash/count mismatch refused **before backup**;
  missing `allow_live_db_write` refused; non-live DB refused; double-promote refused; the
  **active-item-duplication guard** (promoted item_count == edited, not base+edited); opt-in disabled
  → 503; confirm=false → 400; not-parity-pass → 400; unknown → 404; viewer → 403; the happy path
  writes the **fixture** live DB (real one untouched) and is redaction-clean; promotion record persisted.
- **Lint/type:** `ruff` + `mypy` clean on all new modules.
- **Frontend:** typecheck / copycheck / build clean; proposals page test 6/6 (only the pre-existing
  `SettingsPage` ×5 fail in the full run).
- **CFR subrepo:** **565 passed**, unchanged (`cfr_test_posture.txt`) — Phase E2 adds a workflow + CLI;
  the workflow's tests are repo-root.
- **Fixture-live smoke** (`fixture_live_smoke_proof.txt`): a synthetic config DB treated as "live"
  (monkeypatched `is_live_db_path`, WAL=0) → **certified_match**, additive (0→1 snapshot), byte +
  canonical digests match, backup verified at v61, every safety stamp correct. **The real live DB is
  never touched in CI.**

## Notes

- **No migration.** Committed `LATEST_SCHEMA_VERSION` stays **61**; promotion writes the existing v60
  tables additively, only inside the single backed-up transaction (`db_schema_version.txt`).
- **A real promotion against the actual live DB is a separate, authorized, human-gated op** —
  documented in `real_promotion_op.md`, **pending**, not run in CI. The default-OFF opt-in, the
  per-request confirm, and the byte backup are the three load-bearing safeties.
- ADR: `docs/architecture/277-forecast-phaseE2-config-registry-promotion.md`.
