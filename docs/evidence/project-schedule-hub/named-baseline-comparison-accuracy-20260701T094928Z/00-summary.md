# Phase 13A — Named Baseline Comparison Accuracy

**Stamp:** `20260701T094928Z`  
**Branch:** `fix/schedule-named-baseline-comparison-accuracy-20260701T094928Z`  
**Commit:** `09a6f3bb` (+ evidence commit pending)  
**Base:** `fae13113` (Phase 13 named disposition persistence)

## Problem

Named baseline controls/workbench showed correct `baseline_context` and driver analysis vs the selected slot, but **movement**, **milestone cues**, and **change_impact** still compared against the prior update. Drilldown/export APIs ignored `comparison_basis`.

## Fix

1. Recompute `milestones`, `change_impact`, `remaining_health`, and `comparison_provenance` vs the named slot version.
2. Thread `comparison_basis` through controls preview, named workbench cue collection, drilldown, export, and driver drilldown APIs.
3. Basis-aware review cue copy (`comparison_label_for_basis`).
4. Frontend passes `comparison_basis` on schedule export.

## Tropical real-DB proof (read-only inventory + API)

**Inventory:** `tropical-readonly-db-inventory.md` / `.json` — schema v97, 3 active named slots, 10 committed imports.

**Differential movement (controls `finish_moved_later_count` @ `as_of=2026-07-03`):**

| comparison_basis | baseline_schedule_version_key | finish_moved_later_count |
|------------------|------------------------------|--------------------------|
| `prior_update` | — | 461 |
| `current_contract_baseline` | `tropical\|815\|2025-08-07 08:00` | **440** |
| `previous_progress_update_baseline` | `tropical\|1069\|2026-05-26 08:00` | **461** |
| `secondary_progress_update_baseline` | `tropical\|851\|2025-11-28 08:00` | **593** |

Slot changes **change computed movement** (440 ≠ 593). See `api-proof-meta.json`.

**Drilldown:** `api-drilldown-remaining-later-current_contract_baseline.json` includes `comparison_schedule_version_key` = contract slot key and `source_model: named_slot`.

**Workbench cues (POST sync):**

- Contract: `Milestone forecast moved 74 days later compared against current contract baseline.`
- Progress: `Milestone forecast moved 26 days later compared against previous progress update baseline.`

**Driver detail:** `api-driver-detail-current_contract_baseline.json` — `baseline_context.schedule_version_key` = `tropical|815|2025-08-07 08:00`.

## Validation

```
PYTHONPATH=src python -m pytest \
  tests/test_project_schedule_named_baseline_comparison_accuracy.py \
  tests/test_project_schedule_named_baseline_workbench.py \
  tests/test_project_schedule_named_baseline_dispositions.py \
  tests/test_project_schedule_multi_baseline_controls.py -q
```

**Result:** 62 passed, 1 skipped (`validation-output.txt`).

## Browser screenshots

**Manifest:** `screenshot-manifest.json` — **8/8 fully loaded** (`fully_loaded: true`).

| File | Proof |
|------|-------|
| `01-schedule-hub-baselines.png` | Hub + Baseline Anchors |
| `02–04` | Controls per named slot |
| `05-controls-disposition-item.png` | Named workbench disposition context |
| `06–07` | Workbench named filters |
| `08-driver-detail-named-baseline.png` | Driver detail named context |

Captured against 13A worktree backend (`:8000`) + frontend (`:5173`) with Playwright.

## Known limitations

See `13-known-limitations.md` (named export `narrative_qa_failed`, legacy baseline unavailable on Tropical).

## Guardrails

- **No push / PR** until operator approves after this evidence pass.
