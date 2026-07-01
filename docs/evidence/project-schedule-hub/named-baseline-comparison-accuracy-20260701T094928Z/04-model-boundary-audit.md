# Model boundary audit — comparison vs disposition

## Comparison model (ephemeral / computed)

- **Inputs:** current schedule version @ `as_of`, comparison target version (prior update or named slot).
- **Outputs:** `sections.movement`, milestone/change-impact metrics, driver deltas, drilldown rows.
- **Provenance:** `baseline_context`, `provenance.comparison_label`, drilldown `comparison_schedule_version_key`.
- **Must not** read disposition tables to compute movement counts.

## Disposition model (persisted)

- **Table:** `project_schedule_named_baseline_review_items` (`psnbri-*` IDs).
- **Scope:** `review_scope=named_baseline`, `comparison_basis` + `baseline_schedule_version_key` per slot.
- **Separate from** prior-update queue (`project_schedule_review_items`, `psri-*`).
- **Overlay only:** `review_status`, `pm_notes` on workbench items; Controls may link via `review_item_id` without altering movement math.

## Boundary checks (13B evidence)

| Check | Result |
|-------|--------|
| Named movement uses slot version keys | yes — `06-api-proof-controls.json` |
| Workbench items are `psnbri-*` for named bases | yes — DB inventory + `07-api-proof-workbench.json` |
| prior_update controls still use `psri-*` links | yes — `06-api-proof-controls.json` prior_update block |
| Driver detail exposes comparison context, not disposition | yes — `08-api-proof-driver-detail.json`; disposition is P2 follow-up |

## Driver Detail disposition gap

Driver detail API/UI does **not** expose `review_status` or disposition fields. This is a **P2 / follow-up** limitation — it does not block proving named-baseline **comparison** accuracy (Controls + Workbench + provenance are sufficient).
