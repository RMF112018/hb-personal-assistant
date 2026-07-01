# Service computation audit — named baseline comparison accuracy

## Defect (pre-13A)

`build_schedule_hub_context_with_named_baseline` inherited prior-update `milestones` and `change_impact`, so Controls movement and review cues remained prior-update-derived despite a selected named slot.

## Fix (`project_schedule_summary_service.py`)

1. Recompute `milestones`, `change_impact`, `remaining_health` against the named slot `schedule_version_key`.
2. Emit `comparison_provenance` with slot label and version key.
3. Thread `comparison_basis` through `build_drilldown`, `build_export`, `build_driver_drilldown`.

## Controls preview (`project_schedule_controls_service.py`)

- Passes the real requested `basis` into preview builder (not a hardcoded `preview_basis`).

## Workbench cues (`project_schedule_named_baseline_review_service.py`, `project_schedule_review_cue_service.py`)

- `_collect_candidates` receives `comparison_basis` (was hardcoded `"baseline"`).
- Cue copy uses `comparison_label_for_basis` — e.g. *"compared against current contract baseline"*.

## Tropical real-DB differential (controls `finish_moved_later_count`)

| `comparison_basis` | `baseline_schedule_version_key` | `finish_moved_later_count` |
|--------------------|---------------------------------|----------------------------|
| `prior_update` | n/a | **461** |
| `current_contract_baseline` | `tropical\|815\|2025-08-07 08:00` | **440** |
| `previous_progress_update_baseline` | `tropical\|1069\|2026-05-26 08:00` | 461 |
| `secondary_progress_update_baseline` | `tropical\|851\|2025-11-28 08:00` | **593** |

Slot changes alter movement (440 ≠ 593). Source: `06-api-proof-controls.json`.

## Workbench cue proof (read-only GET)

Named GET returns persisted `psnbri-*` rows with basis-specific cue summaries, e.g.:

- *"Milestone forecast moved 74 days later compared against current contract baseline."*
- *"Milestone forecast moved 26 days later compared against previous progress update baseline."*

Source: `07-api-proof-workbench.json` (no POST sync in 13B).
