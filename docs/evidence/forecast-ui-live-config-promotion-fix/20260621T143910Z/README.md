# Live Config Promotion — Orphan Defect Fixed + Loop Closed (real re-promotion)

**Date:** 2026-06-21 · **Stamp:** 20260621T143910Z

## Outcome

The ADR 283 promotion defect is **fixed**, and the edit→promote→generate loop is now **closed against
live data**: the dormant `forecast_model_controls` edit was promoted into the live config DB, the
promoted snapshot is **fully reachable (194/194)** and **round-trips**, and **all four generators
consume it**. The promoted snapshot is **kept** (the edit is dormant, so forecast math is unchanged).

## The fix (CFR `live_db_config_registry_promotion.py`)

1. **Re-resolve `config_item_id` on the snapshot_items copy** — each promoted snapshot item is linked
   to the live row that wins the content-dedup `UNIQUE(project, domain, name, item_key, canonical_sha)`,
   so unchanged items (whose content-derived id collides and is `INSERT OR IGNORE`'d) no longer dangle.
2. **In-txn reachability guard (fail-closed before commit)** — zero orphaned snapshot_items required, or
   the transaction rolls back.
3. **Post-write materialize round-trip in the cert** — materialize → reimport → resnap must reproduce
   the stored `item_count` + `snapshot_sha256` (the same invariant the generation fidelity gate
   enforces), so a snapshot generation cannot consume can never certify.

Validated: new regression `test_colliding_source_same_path_different_content` (fails before, passes
after), full CFR suite **565 passed**, hb-layer promotion + config-edit tests pass, mypy + ruff clean.

## Real re-promotion results

- **Edit:** `tropical-example-explicit-final-pending` `explicit_value_amount` 3200000.00 → 3250000.00,
  `acceptance_status` stays `pending` (dormant). Proposal succeeded, parity pass, item_count 194.
- **Promotion:** `decision=live_db_config_registry_certified` — backup taken (sha `15b380fa…` ==
  pre-write baseline), additive txn, snapshot count 1→2, prior phase16 snapshot preserved,
  `non_tropical_preserved=true`.
- **Reachability:** promoted snapshot `cbae0702…` (`promotion_b4b30f830d40`) — **194 snapshot_items,
  194 reachable, model_controls 5/5 reachable** (was 1/5 in the ADR 283 broken run).
- **Round-trip cert:** `match: true` — resnap `cd73fd14…` == stored `cd73fd14…`, item_count 194==194.
- **Generation (all four kinds):** each `status=generated`, `config_snapshot_consumed=true`,
  `snapshot_name=promotion_b4b30f830d40`, fidelity gate passed. (Probability needed one re-checkpoint
  for the transient `physical.shm` quiescence churn — a sidecar-stability quirk, not a data issue.)
- **Final state:** live DB keeps **2 tropical snapshots** — `promotion_b4b30f830d40` (latest, 194) +
  `tropical-phase16-live-config-20260619T085305Z` (preserved, 194). The promoted snapshot is the new
  "latest" that future db-config generation selects; forecast math is unchanged (dormant control).

## Files

`baseline_live_db.json` / `final_live_db.json` (the main sha changes — a write happened and the snapshot
is kept), `pre_write_audit.json` / `post_write_audit.json`, `proposal_record.json`,
`promotion_report.json` (full, incl. the `round_trip` cert block) / `promotion_summary.json` (redacted),
`backup_fingerprint.json` (verified byte backup, sha == pre-write baseline), four `gen_<kind>_report.json`,
`db_schema_version.txt` (v61).

## Safety / revert

The verified byte backup at the promotion work_root
(`…/promotions/<edit_id>/<stamp>/backups/hb-personal-assistant.before-phaseE2-config-promotion.sqlite`,
sha `15b380fa…`) reverts the promotion if desired (stop writers → rm sidecars → cp backup over live DB →
audit → restart). No schema / id-derivation / hb_assistant change; live DB stays v61.
