# ADR 280 — Forecast UI: wire the comprehensive generator to consume live DB config

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast CLI→UI product, DB-config-backed generation
- **Builds on:** ADR 272 (v60 config registry), ADR 276 (Phase 20 comprehensive db-config proof),
  ADR 277 (Phase E2 config promotion), the Phase 3 Run Center, Phase 6 runtime config wiring.

## Context

Config promotion (Phase E2) writes an operator-approved snapshot into the live v60 config-registry DB
as the auditable system-of-record, but **generation still read file config** —
`config_snapshot_lineage_block` reported `config_snapshot_consumed: False`. So promoting a config edit
updated the viewer but did **not** change forecasts. The Phase 17–20 "db-config proof" workflows had
already proven the real generators produce parity-equivalent output when run with
`CFR_CONFIG_ROOT = <materialized snapshot>` through the Phase 16 bridge — the gap was purely that the
controlled run path never set it. This phase productionizes that proven path for the **comprehensive**
generator (the integrated final package the catalog shows).

## Decision

A CFR-only workflow + CLI generate the comprehensive package consuming the live snapshot, exposed via
a default-OFF Run Center action.

### Materialization fidelity, not output parity (the key safety model)

A generator-output parity gate (file vs DB) only passes when DB config == file config — which is
exactly **not** the case once an operator promotes an edit (the forecast *should* change). So the gate
is **materialization fidelity**: re-import the materialized config tree into a temp DB, re-snapshot,
and assert the resulting `snapshot_sha256` + `item_count` equal the live snapshot's **stored** values
(`hashes_by_domain` is a derived return, never persisted — so the persisted digest is the invariant).
This proves the materialized files faithfully represent the snapshot, independent of whether config
diverged from the on-disk files. The optional `--prove-file-equivalence` flag (default OFF, never on
the UI path) additionally runs file-backed + compares, for evidence only.

### Read-only materialize (live-DB safety)

`materialize_forecast_config_snapshot` opened the DB read-write; against the multi-GB live DB that
could create `-wal`/`-shm` and take a write lock. A new `materialize_forecast_config_snapshot_readonly`
opens `mode=ro` and delegates to a shared `_materialize(conn, ...)` (the original RW function is
unchanged — it is used by parity against temp DBs). The Phase 17–20 proofs were **not** switched to
the RO helper: a fresh `mode=ro` open of a temp WAL DB without `-shm` fails, which broke their
fixtures; the RO helper is for the live DB (which has its sidecars present) and is exercised by the
live read-only smoke. (Recorded here as a known minor posture gap in the proofs.)

### Workflow

CFR `run_forecast_db_config_backed_generation` (new `workflows/forecast_db_config_backed_generation.py`)
reuses the Phase 20 proof helpers: select the snapshot (explicit id, else latest live), live-DB
schema/tables check + quiescence preflight, RO materialize, fidelity gate, predecessor-package +
cost-frequency guards (BEFORE invoking — comprehensive `SystemExit`s otherwise and would generate
cost-frequency into the read-only data root), then run comprehensive with scoped `CFR_CONFIG_ROOT`,
emitting the package + a deterministic report with `config_snapshot_consumed: True`. `require_item_count`
defaults to None (accept the current snapshot's own count — a promoted edit legitimately changes it),
not the proof's fixed 194. CLI `forecast-db-config-backed-generate` (rc 0 generated / 1 validation-fail
/ 3 refusal).

### Run Center surface

`HB_FORECAST_DB_CONFIG_RUN_ENABLED` opt-in (default OFF) mirrors `HB_FORECAST_PROMOTION_ENABLED` +
`surfaces_ready["db_config_run"]`. A new `ForecastDbConfigRunService` consumes the live config snapshot
from the live app DB (`PathPolicy().get_db_path()` — where the registry lives, NOT the runtime
`db_path`), opened read-only, into an isolated runs-root; it maps the workflow's coded refusals to
path-free friendly messages and persists a redacted record. Routes `POST/GET /api/forecast/runs/db-config`
+ `GET /api/forecast/runs/db-config/{run_id}` (operator POST, viewer GET) are registered **before** the
`{run_id}` catch-all. The frontend adds a "Generate from live config" action and a "Source" column.

## Consequences

- A promoted config snapshot now actually drives the comprehensive forecast (`config_snapshot_consumed`
  is True for these runs).
- Live config DB is read-only throughout; writes confined to the isolated runs-root; no DB/schema
  change. Structural redaction holds (UI payloads carry the friendly snapshot name + booleans/counts,
  never paths/stamps/snapshot-id-in-text).
- Live read-only smoke confirmed the real snapshot (194 items, 6 files) round-trips with fidelity and
  the live DB byte-unchanged.
- model_controls / monthly / probability consumers (already proven by Phases 17–19) can be wired the
  same way in a follow-up.
