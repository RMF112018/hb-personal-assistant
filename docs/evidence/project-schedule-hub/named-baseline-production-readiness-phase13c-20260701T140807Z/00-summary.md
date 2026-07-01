# Phase 13C — Named Baseline Production Readiness

**Stamp:** `20260701T140807Z`  
**Branch:** `fix/schedule-named-baseline-production-readiness-phase13c-20260701T140807Z`  
**Base:** `ac6b9441` (Phase 13A/13B merged)

## Scope

Close Phase 13B production blockers:

1. Named export built from resolved named hub context (not prior-update patch).
2. Deterministic named export fallback when narrative QA fails but comparison context is complete.
3. Driver Detail scoped disposition lookup + PM-facing UI overlay.
4. Workbench export passes `asOf` + `comparisonBasis`.
5. Regression tests + read-only Tropical proof + fully loaded browser proof.

## Tropical real-DB proof (read-only)

**Export @ `as_of=2026-07-03` — all bases HTTP 200:**

| `comparison_basis` | Movement excerpt | Baseline version key |
|--------------------|------------------|----------------------|
| `prior_update` | 461 later | prior update window |
| `current_contract_baseline` | **440** later | `tropical\|815\|2025-08-07 08:00` |
| `previous_progress_update_baseline` | 461 later | `tropical\|1069\|2026-05-26 08:00` |
| `secondary_progress_update_baseline` | **593** later | `tropical\|851\|2025-11-28 08:00` |

Named exports include `## Comparison Context` with slot label and version keys. No silent prior-update fallback on named bases.

**Driver detail (`FILTER-OUT-50`):** disposition fields present per basis (`review_status`, `disposition_source`, `disposition_basis`, `disposition_schedule_version_key`, `review_scope`). Scoped preview when not persisted.

## Validation

| Suite | Result |
|-------|--------|
| Backend focused (`05-test-results.txt`) | 33 passed, 1 skipped |
| Frontend export/disposition (`13c-frontend-test-results.txt`) | 35 passed |
| Browser proof (`12-browser-screenshots/screenshot-proof.json`) | 8/8 fully loaded |

## Phase 13C verdict

| Dimension | Verdict |
|-----------|---------|
| Named export from hub context | **Proven** — API + unit tests |
| Deterministic QA fallback | **Proven** — classified `export_mode: deterministic_fallback` |
| Driver Detail disposition | **Proven** — scoped API + UI card |
| Workbench export propagation | **Proven** — frontend tests (4 bases) |
| Tropical read-only proof | **Complete** — no DB writes |
| Browser proof | **Complete** — selector/text gates, no loading-state shots |
| **Ready to push/open PR** | **yes** |
| **Ready for production rollout** | **yes** — residual limitations documented in `11-known-limitations.md` |

## Guardrails

- No push / PR in this phase
- No Tropical DB mutation
- Read-only GET API proof only
