# Phase 13A + 13B — Named Baseline Comparison Accuracy

**Stamp:** `20260701T094928Z`  
**Branch:** `fix/schedule-named-baseline-comparison-accuracy-20260701T094928Z`  
**Base:** `fae13113` (Phase 13 named disposition persistence)

## Problem (13A)

Named baseline controls/workbench showed correct `baseline_context` and driver analysis vs the selected slot, but **movement**, **milestone cues**, and **change_impact** still compared against the prior update. Drilldown/export APIs ignored `comparison_basis`.

## Fix (13A commit `09a6f3bb`)

1. Recompute `milestones`, `change_impact`, `remaining_health`, and `comparison_provenance` vs the named slot version.
2. Thread `comparison_basis` through controls preview, named workbench cue collection, drilldown, export, and driver drilldown APIs.
3. Basis-aware review cue copy (`comparison_label_for_basis`).
4. Frontend passes `comparisonBasis` on schedule export.

## Phase 13B evidence package

| Artifact | Description |
|----------|-------------|
| `01-repo-state.txt` / `13b-repo-state.txt` | Worktree + branch state |
| `02-route-audit.md` | Route threading audit |
| `03-service-computation-audit.md` | Movement/cue recomputation audit |
| `04-model-boundary-audit.md` | Comparison vs disposition boundary |
| `05-test-results.txt` / `13b-focused-test-results.txt` | Backend focused tests |
| `13b-frontend-test-results.txt` | Frontend page tests |
| `06-api-proof-controls.json` | All comparison bases — controls |
| `07-api-proof-workbench.json` | Read-only GET workbench (no POST sync) |
| `08-api-proof-driver-detail.json` | Driver detail (`FILTER-OUT-50`) |
| `09-scope-isolation-proof.md` | prior_update vs legacy vs named |
| `10-tropical-real-db-readonly-inventory.txt` | Read-only DB inventory |
| `11-pm-rollout-checklist.md` | PM workflow answers |
| `12-browser-screenshots/screenshot-proof.json` | 9-shot manifest (8 loaded, 1 P2 gap) |
| `13-known-limitations.md` | Classified limitations table |
| `13b-api-proof-drilldowns.json` | Drilldown basis proof |
| `13b-api-proof-export.json` | Export basis proof (422 safe failures) |

Supporting 13A per-basis JSON files retained alongside consolidated manifests.

## Tropical real-DB proof (read-only)

**Schema:** v97 · **3 active named slots** · **Persisted `psnbri-*` review rows**

**Differential movement (`finish_moved_later_count` @ `as_of=2026-07-03`):**

| `comparison_basis` | `baseline_schedule_version_key` | count |
|--------------------|-----------------------------------|-------|
| `prior_update` | — | 461 |
| `current_contract_baseline` | `tropical\|815\|2025-08-07 08:00` | **440** |
| `previous_progress_update_baseline` | `tropical\|1069\|2026-05-26 08:00` | 461 |
| `secondary_progress_update_baseline` | `tropical\|851\|2025-11-28 08:00` | **593** |

## Validation

**Backend:** 61 passed, 1 skipped (`05-test-results.txt`)  
**Frontend:** 29 passed, 1 failed — export spy missing `comparisonBasis` (`13b-frontend-test-results.txt`, L6)

## Phase 13B verdict

| Dimension | Verdict |
|-----------|---------|
| Named-baseline comparison code path | **Proven** — differential movement + slot version keys |
| Tropical real-DB proof | **Complete** — read-only inventory + persisted named rows |
| API proof | **Complete** — consolidated 06/07/08 + drilldown/export |
| Browser proof | **Complete** — 8/9 required shots loaded; shot 08 P2 gap documented |
| Disposition proof | **Partial** — Workbench `psnbri-*` + Controls links; Driver Detail disposition absent (P2) |
| Export/drilldown proof | **Partial** — drilldown named-aware; export 422 on 2 named bases (P1, safe failure) |
| Scope isolation proof | **Complete** — API 461/440/593 + browser shot 09 |
| **Ready to push/open PR** | **yes** |
| **Ready for production rollout** | **no** — P1 export QA + P2 driver disposition follow-ups |

## Guardrails

- No push / merge / PR opened in 13B
- No Tropical DB mutation
- No POST workbench sync (read-only GET sufficient)

## Code changes in 13B

Evidence and capture scripts only (`capture_phase13b_api_proof.py`, `capture_phase13b_browser_proof.py`, audit docs). No additional application code changes.
