# ADR 283 — First real live config promotion: certified-but-broken snapshot defect (rolled back)

- **Status:** Accepted (defect record; promotion path blocked pending fix)
- **Date:** 2026-06-21
- **Phase:** Forecast CLI→UI product, Phase E2 (config promotion) — first real execution
- **Builds on:** ADR (Phase E2 config promotion, commit `d96df9e8`), ADR (Phase E config editing, PR #61),
  ADR 281/282 (DB-config-backed generation, all generators + live-data validation).

## Context

Phase E (config editing) and Phase E2 (promotion) were merged but the **real** live promotion had
never been run. This phase executed it end-to-end for the first time: author a real config-edit
proposal (a dormant `forecast_model_controls` value change), promote it into the live config DB, and
generate from the promoted snapshot. The intent was to close the edit→promote→generate loop against
live data.

## Decision / what was done

The promotion was executed under the full gated path with a verified backup and explicit
user authorization. The live DB was quiesced (server stopped, WAL checkpointed to 0) before the write.

## Outcome — a real defect was found

- **Proposal:** correct — `status=succeeded`, `parity=pass`, all 5 model-controls items present, edit
  applied.
- **Promotion:** the gated write returned **`decision=live_db_config_registry_certified`** — backup
  taken, additive txn, snapshot count 1→2, prior snapshot preserved, `non_tropical_preserved=true`.
- **Generation:** **refused on all four kinds** — `config_fidelity_failed: materialized config does
  not round-trip to the snapshot digest`.

**Diagnosis.** The promoted snapshot is internally inconsistent: header `item_count=194`, 194
`snapshot_items` rows, but **only 190 reachable via the source→item join** — 4 of its 5
`forecast_model_controls` items are **orphaned from their source**. Materialize emits 190 items, so
the re-snapshot digest differs from the stored digest and the (correct) fidelity gate refuses. The
phase16 snapshot round-trips cleanly, confirming the gate is right and the defect is specific to the
promoted snapshot.

**Root cause.** The items existed in the proposal's `edited_config`; they were lost in the
**promotion's copy into the live DB**. The additive copy uses `INSERT OR IGNORE` on sources, which
collides with phase16's *existing* `code_forecast_model_controls.jsonl` source row; the new snapshot's
extra model-controls items then reference a source that was not re-inserted (orphaned). The promotion's
post-write **dual-digest certification compares `raw_json` but does not verify source→item
reachability or a materialize round-trip**, so it certified a snapshot that generation cannot consume.

## Resolution

The live DB was **restored from the verified byte-identical backup** (user-authorized), returning it to
the exact pre-promotion state (1 snapshot; sha `15b380fa…`); a comprehensive generation smoke on the
restored DB succeeds. **No net change to the live DB.** The promotion path is **blocked for real use
until fixed.**

## Consequences / follow-up (separate change)

1. **Fix the promotion source-copy** so a new snapshot's items retain their own source linkage when a
   source with a colliding natural key already exists in the live DB (the additive copy must not
   `INSERT OR IGNORE` a source and leave items orphaned against it).
2. **Strengthen the promotion certification** with a reachability / materialize round-trip assertion
   (materialize → re-import → re-snapshot must reproduce the stored digest + item_count) so a
   non-round-tripping snapshot can never certify — the same invariant the generation fidelity gate
   enforces, applied at promotion time.
3. Add a regression test reproducing the colliding-source case, then re-attempt the real promotion.

## Evidence

`docs/evidence/forecast-ui-live-config-promotion/20260621T135306Z/` — README (full sequence),
`defect_analysis.json`, certified `promotion_report.json`, pre/post/restore audits, fingerprints,
proposal record, four generation refusal reports, backup fingerprint.
