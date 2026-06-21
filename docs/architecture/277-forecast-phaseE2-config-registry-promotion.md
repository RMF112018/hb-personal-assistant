# ADR 277 — Forecast Phase E2: config-registry promotion (certified live write)

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast CLI→UI product, Phase E2 (config promotion)
- **Builds on:** ADR 270 (Phase 14 gated live source-domain write), ADR 272 (v60 config registry), the
  Phase E config-edit proposals (PR #61), and the Phase 6 runtime config wiring (PR #60).

## Context

Phase E lets an operator propose config edits and produces a parity-proven **isolated** materialized
snapshot, but proposals never reach the live config DB — they are rehearsals only. Phase E2 closes the
loop: take an **approved** proposal (status `succeeded` + parity `pass`) and certify-promote it into the
LIVE v60 config-registry DB as a **new snapshot**, making the live registry the auditable
system-of-record the config viewer shows as "current config".

This is the **first analytics live-DB write** (every prior analytics phase is read-only or
isolated-write), so it mirrors the Phase 14 gated-live-write discipline: explicit gate → preflight →
byte backup → single transaction → post-write certification.

**Scope:** config is lineage-only — the controlled generators do not consume DB config — so promotion
updates the recorded current config / viewer, **not** how forecasts are generated.

## Decision

A CFR workflow `run_live_db_config_registry_promotion` performs the gated additive write; a thin
analytics service (`forecast_config_promotion_service.py`) + route
`POST /api/forecast/config/edits/{edit_id}/promote` orchestrates it from the proposal artifacts.

### The load-bearing invariant (active-item duplication)

`create_forecast_config_snapshot` snapshots `WHERE status='active'`. Importing an edited config into
the live DB (which already holds the base config's active items) would leave both active → a live
snapshot would double-count. **Therefore the snapshot is built in a FRESH temp DB (only the edited
config is active there) and its rows are COPIED into the live DB.** The workflow never calls
`create_forecast_config_snapshot` against the live DB.

### Additive model

Promotion INSERTs exactly one new `forecast_config_snapshots` row + its self-contained
`forecast_config_snapshot_items` (+ `INSERT OR IGNORE` backing sources/items) and **never deletes** —
snapshot history and non-tropical config are preserved.

### Gated sequence (mirrors Phase 14)

1. `allow_live_db_write` gate + preflight (tropical only; edited config tree present; `work_root` not
   under the live root; live DB resolves + schema ≥ v60 + the 4 config tables present). Capture the
   pre-existing snapshot set + header digests.
2. Fresh temp DB: `import_forecast_config_to_db` → `create_forecast_config_snapshot` (never live).
3. **Expected-match gate (before backup):** the temp snapshot's `item_count` + `hashes_by_domain` MUST
   equal the approved proposal's recorded values — binds the promotion to exactly the approved bytes.
4. Byte backup of the live DB (fail closed on a nonzero WAL; verify readable at v60).
5. Single `BEGIN IMMEDIATE` transaction: column-match check; refuse an already-present promoted
   snapshot id (no silent double-promote); insert; in-txn verify (promoted item count == temp;
   snapshots after == before + 1); commit or rollback+raise.
6. Post-write certification: dual-digest (byte-exact + canonical) the promoted snapshot's items
   live-vs-temp → `certified_match`; assert every pre-existing snapshot is byte-unchanged.
   `certified` → rc 0 / `status=ready`; else `not_ready` rc 1 (backup recorded). Refusal → rc 3.

### Three-way gating at the analytics boundary

The promote action requires (a) a default-OFF opt-in `HB_FORECAST_PROMOTION_ENABLED`, (b) an explicit
per-request `confirm: true`, and (c) the proposal already parity-passed. Role: operator or admin. The
returned payload is redaction-safe (sha + counts + decision + booleans; all workflow-report paths and
the raw stamp are stripped — only a friendly display crosses the boundary). A redacted promotion block
is recorded on the proposal.

## Safety / no-schema-change

No migration — writes the existing v60 tables only; committed `LATEST_SCHEMA_VERSION` stays 61. The CFR
workflow is CFR-only/stdlib at import; `hb_assistant` (migrator) is lazy and only against the temp DB;
the live DB is read-only except the single backed-up transaction. The CI-safe proof is the fixture-live
test (monkeypatched `is_live_db_path`, WAL=0); a real promotion against the actual live DB is a
separate, authorized, human-gated operation (opt-in + confirm + byte backup are the three load-bearing
safeties).

## Consequences

- The live config registry becomes the auditable current-config of record; the viewer reflects promoted
  edits. Generation is unaffected (lineage-only).
- A future phase can wire generators to consume the live config snapshot (deferred).
- New CLI `forecast-config-registry-promote` (rc 0/1/3, JSON stdout) mirrors the Phase 14 contract.
