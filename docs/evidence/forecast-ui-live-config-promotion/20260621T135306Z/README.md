# Real Live Config Promotion (Phase E2) — Executed, Defect Found, Rolled Back

**Date:** 2026-06-21 · **Stamp:** 20260621T135306Z

## Outcome (read this first)

The first **real** authorized promotion of a config-edit proposal into the live config DB was
executed. The gated write **certified**, but the promotion produced an **internally broken
snapshot** that the downstream generation fidelity gate correctly rejected. The live DB was
**restored from a verified byte-identical backup** to its exact pre-promotion state. **Net change to
the live DB: none.** The edit→promote→generate loop is **not** closed — a real defect in the
promotion's source-copy was surfaced and must be fixed before promotion can be used.

This is the honest result: a first real run caught a latent bug that unit/cert tests did not.

## The edit (user-chosen, value-only / dormant)

`forecast_model_controls` control `tropical-example-explicit-final-pending` (budget code
`1000.15-15-410.SUB`): `explicit_value_amount` `"3200000.00"` → `"3250000.00"`, `acceptance_status`
left `pending` (dormant — no forecast-math impact intended).

## What happened, step by step

1. **Quiesce.** Stopped the :8000 dev server; DBeaver already released the DB; `PRAGMA
   wal_checkpoint(TRUNCATE)` → WAL=0; DB quiescent. Pre-write baseline captured
   (`baseline_live_db.json` main sha256 `15b380fa…`; `pre_write_audit.json` schema v61, 1 tropical
   snapshot).
2. **Proposal (Phase E).** `propose_config_edit` → `edit_id=30143beb454c`, **status=succeeded,
   parity=pass**, item_count 194, all **5** model-controls items present in `edited_config`, the edit
   correctly applied (`proposal_record.json`).
3. **Promotion (Phase E2).** `promote_config_edit(confirm=True)` with
   `HB_FORECAST_PROMOTION_ENABLED=1` → **decision `live_db_config_registry_certified`**, backup taken
   (`backup_fingerprint.json` sha `15b380fa…` == pre-write baseline), additive txn, snapshot count
   1→2, prior phase16 snapshot preserved, `non_tropical_preserved=true`
   (`promotion_report.json` / `promotion_summary.json`, redaction-clean).
4. **Generation (all four kinds) — REFUSED.** Every generator refused rc 3
   `config_fidelity_failed: materialized config does not round-trip to the snapshot digest`
   (`gen_<kind>_report.json`). (A first attempt also hit a transient `live_db_not_quiescent:
   physical.shm` until a post-write `wal_checkpoint(TRUNCATE)` stabilized the sidecars — the real
   blocker is the fidelity failure below.)
5. **Diagnosis (`defect_analysis.json`).** The promoted snapshot header says `item_count=194` and has
   194 `snapshot_items` rows, **but only 190 are reachable via the source→item join** — of its 5
   `forecast_model_controls` items, **only 1 (`tropical-example-explicit-final-pending`) is reachable;
   the other 4 are orphaned from their source**. Materialize emits 190 items → re-snapshot digest
   `e154d4e3…` ≠ stored `cd73fd14…` → fidelity refuses. The phase16 snapshot round-trips cleanly
   (194→194, `d42f2db6…`), confirming the gate is correct and the defect is specific to the promoted
   snapshot.
6. **Root cause (characterized).** The 5 items existed in the proposal's `edited_config`; they were
   lost in the **promotion's copy into the live DB** — the `INSERT OR IGNORE` source copy collides
   with phase16's *existing* `code_forecast_model_controls.jsonl` source row, so the new snapshot's
   extra model-controls items reference a source that was not re-inserted (orphaned). The promotion's
   post-write **dual-digest cert compares `raw_json` but does not verify source→item reachability**,
   so it certified a snapshot that materialize cannot fully reconstruct. **This is the latent bug.**
7. **Rollback (user-authorized).** Restored the verified backup over the live DB
   (`cp` after `rm` of sidecars). Live DB sha256 `15b380fa…` == pre-write baseline (byte-identical).
   `post_restore_audit.json`: back to **1 tropical snapshot** (phase16, 194 items). Comprehensive
   generation smoke on the restored DB **succeeds** (status=generated, consumes phase16). :8000 server
   restarted.

## Verification

- **Promotion certified** but **generation refuses** the promoted snapshot (fidelity) — the defect.
- **Defect localized:** proposal `edited_config` had 5 model-controls items; live promoted snapshot
  has 1 reachable (4 orphaned); header/rows 194 vs 190 reachable.
- **Full recovery:** live DB byte-identical to pre-write (`15b380fa…`); 1 snapshot; generation works.
- **No net live-DB change**; the prior phase16 snapshot was never altered.

## Files

`baseline_live_db.json` / `final_live_db.json` (pre/post-write fingerprints), `pre_write_audit.json` /
`post_write_audit.json` / `post_restore_audit.json`, `proposal_record.json`,
`promotion_report.json` / `promotion_summary.json`, `backup_fingerprint.json`, `defect_analysis.json`,
four `gen_<kind>_report.json` (the rc-3 refusals), `_edit_id.txt`.

## Follow-up (the fix, separate change)

Fix the promotion source-copy so a new snapshot's items keep their own source linkage when a source
with a colliding natural key already exists in the live DB (don't `INSERT OR IGNORE` a source and then
leave items pointing at it orphaned), **and** add a reachability/round-trip assertion to the
promotion's post-write certification (materialize → re-import → re-snapshot must reproduce the stored
digest + item_count) so a non-round-tripping snapshot can never certify. Re-attempt the real promotion
only after that fix + a regression test.
