# ADR 284 — Fix live config promotion orphaned-items defect; loop closed

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast CLI→UI product, Phase E2 (config promotion) — defect fix
- **Builds on / fixes:** ADR 283 (the defect this resolves), Phase E2 promotion (commit `d96df9e8`),
  Phase E config editing (PR #61), ADR 281/282 (DB-config-backed generation).

## Context

ADR 283 recorded a real defect: the first live config promotion produced a snapshot with orphaned
items — generation refused it and the live DB had to be rolled back. Root cause (validated by a failing
regression test): `config_item_id = sha256(source_id | item_order | item_key | canonical_sha)` includes
`source_id` (a **whole-file** content hash), so editing one item gives **every** item in that file a new
`config_item_id`; but `forecast_config_items` dedups on `UNIQUE(project, domain, name, item_key,
canonical_sha)` — **content-based, excluding `source_id`** — so when the promotion copies the new items
into a live DB that already holds content-identical items, the **unchanged** items' new ids collide on
that UNIQUE and `INSERT OR IGNORE` skips them. The snapshot_items were copied with the temp's
`config_item_id` verbatim, so the skipped ids dangled. Neither the row-count in-txn check nor the
`raw_json` dual-digest cert caught the broken source→item reachability.

## Decision

Fix in the CFR promotion workflow only (`live_db_config_registry_promotion.py`) — no schema, no
id-derivation, no `hb_assistant` change. Two facts make it clean: `snapshot_sha256` is **content-based**
(not id-based) and `materialize` groups by **`(source_path, source_format)`** (not `source_id`).

1. **Re-resolve `config_item_id` when copying `forecast_config_snapshot_items`** — for each temp
   snapshot item, resolve the live `config_item_id` by the items table's content UNIQUE key
   `(project, domain, name, item_key, canonical_sha)` and insert with that id. After the content-deduped
   items copy, exactly one live row exists per content key, so every snapshot item references a present,
   reachable row. Unchanged items reuse the prior source's row (same `source_path`), the edited item
   uses the new source — and they merge into one faithful file on materialize.
2. **In-transaction reachability guard** — assert zero orphaned snapshot_items (join through items →
   sources) before commit, else raise → rollback (rc 3). An orphaned snapshot can never commit.
3. **Post-write materialize round-trip in the certification** — materialize the promoted snapshot
   read-only → reimport into a fresh temp DB → resnap, and require it reproduces the stored `item_count`
   + `snapshot_sha256` (the same invariant the DB-config generation fidelity gate enforces). A snapshot
   generation cannot consume can never certify (failure → `not_ready` rc 1, backup recorded).

The hb service, CLI, and route are unchanged — all callers get the fix.

## Validation

- New regression `test_colliding_source_same_path_different_content` (repo-root
  `tests/test_forecast_live_db_config_registry_promotion_phaseE2.py`): **fails before** (2 orphans),
  **passes after**. Full CFR suite **565 passed**; hb-layer promotion + config-edit tests pass; mypy +
  ruff clean on the changed workflow.
- **Real re-promotion (loop closed):** the dormant `forecast_model_controls` edit promoted into the live
  DB — certified, promoted snapshot **194/194 reachable** (model_controls 5/5, was 1/5), round-trip cert
  `match: true`, prior phase16 snapshot preserved, verified backup captured. **All four generators
  consume the promoted snapshot** (`status=generated`, `config_snapshot_consumed=true`). The promoted
  snapshot is kept (dormant edit → forecast math unchanged).

## Consequences

Config promotion now produces snapshots that survive materialize → reimport, so a promoted config
genuinely drives generation; the in-txn reachability guard + round-trip cert make a certified-but-broken
snapshot impossible. Evidence: `docs/evidence/forecast-ui-live-config-promotion-fix/20260621T143910Z/`.
No schema/id-derivation/`hb_assistant` change; live DB stays v61.
