# Phase 13A — Named Baseline Comparison Accuracy

**Stamp:** `20260701T094928Z`  
**Branch:** `fix/schedule-named-baseline-comparison-accuracy-20260701T094928Z`  
**Base:** `fae13113` (includes Phase 13 named disposition persistence)

## Problem

Named baseline controls/workbench showed correct `baseline_context` and driver analysis vs the selected slot, but **movement**, **milestone cues**, and **change_impact** still compared against the prior update because `build_schedule_hub_context_with_named_baseline` inherited prior-update `milestones` / `change_impact`. Drilldown/export APIs ignored `comparison_basis`.

## Fix (P0–P1)

1. Recompute `milestones`, `change_impact`, `remaining_health`, and `comparison_provenance` vs the named slot version in `build_schedule_hub_context_with_named_baseline`.
2. Pass named `comparison_basis` through controls preview, named workbench cue collection, drilldown, export, and driver drilldown APIs.
3. Basis-aware review cue copy (`comparison_label_for_basis`).
4. Frontend passes `comparison_basis` on schedule export; drilldown panel supports optional basis param.

## Validation

```bash
cd worktree
PYTHONPATH=src python -m pytest \
  tests/test_project_schedule_named_baseline_comparison_accuracy.py \
  tests/test_project_schedule_named_baseline_workbench.py \
  tests/test_project_schedule_named_baseline_dispositions.py \
  tests/test_project_schedule_multi_baseline_controls.py -q
```

**Result:** 57 passed, 1 skipped (legacy `baseline` drilldown — fixture uses named slots only).

## Differential proof

Seeded May / mid-June / June / July versions with distinct `A100` finishes. Asserts:

- `comparison_provenance.comparison_schedule_version_key` follows slot selection
- Activity `A100` finish delta differs between contract vs progress baselines
- Prior-update disposition does not appear on named workbench items (separate persistence scope)

## Guardrails

- No push / PR / merge (per operator instruction)
- Local commit only
