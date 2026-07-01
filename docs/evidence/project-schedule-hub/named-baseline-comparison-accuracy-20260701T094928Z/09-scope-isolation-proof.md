# Scope isolation proof — prior_update vs legacy baseline vs named baselines

**Project:** `tropical` · **as_of:** `2026-07-03` · **Evidence:** read-only API + browser

## API movement isolation (`06-api-proof-controls.json`)

| Scope | `comparison_basis` | `available` | `baseline_schedule_version_key` | `finish_moved_later_count` |
|-------|-------------------|-------------|--------------------------------|----------------------------|
| Prior update | `prior_update` | true | n/a | **461** |
| Legacy baseline | `baseline` | **false** | n/a | n/a |
| Current contract | `current_contract_baseline` | true | `tropical\|815\|2025-08-07 08:00` | **440** |
| Previous progress | `previous_progress_update_baseline` | true | `tropical\|1069\|2026-05-26 08:00` | **461** |
| Secondary progress | `secondary_progress_update_baseline` | true | `tropical\|851\|2025-11-28 08:00` | **593** |

**Conclusion:** Named slot selection changes computed movement (440 ≠ 593). Prior update (461) matches previous-progress slot count in this dataset but uses a different comparison model (prior import vs named slot version). Legacy `baseline` is unavailable on Tropical at this as-of.

## Drilldown isolation (`13b-api-proof-drilldowns.json`)

Named drilldown `remaining_later` responses include `comparison_schedule_version_key` aligned to the selected slot and `source_model: named_slot` (see Phase 13A `api-drilldown-remaining-later-current_contract_baseline.json`).

## Workbench cue isolation (`07-api-proof-workbench.json`, read-only GET)

Cue summaries explicitly name the comparison anchor:

- *"…compared against current contract baseline."*
- *"…compared against previous progress update baseline."*
- *"…compared against secondary progress update baseline."*

## Disposition isolation (DB)

- prior_update queue: `psri-*` (`project_schedule_review_items`)
- named queue: `psnbri-*` (`project_schedule_named_baseline_review_items`) — see `10-tropical-real-db-readonly-inventory.txt`

## Browser isolation

- Shots `02–04`: distinct named basis labels + provenance in Controls
- Shot `09-scope-isolation-prior-vs-named.png`: Prior Update vs Secondary Progress Update Baseline movement text on same hub surface
- Manifest: `12-browser-screenshots/screenshot-proof.json`
