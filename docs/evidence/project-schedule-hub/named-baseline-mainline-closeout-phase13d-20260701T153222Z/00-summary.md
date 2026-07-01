# Phase 13D — Mainline Merge Verification Closeout

**Stamp:** `20260701T153222Z`  
**Objective:** Prove Phase 13 named-baseline workflow is production-ready from fresh `origin/main` after Phase 13C merge.

## PR / merge

| Field | Value |
|-------|-------|
| PR | [#249](https://github.com/RMF112018/hb-personal-assistant/pull/249) |
| Merged | yes — `2026-07-01T14:51:39Z` |
| Merge commit | `c983b1f4` |

## Verification worktree

| Field | Value |
|-------|-------|
| Branch | `verify/schedule-named-baseline-phase13d-mainline-20260701T153222Z` |
| Path | `/Users/bobbyfetting/hb-personal-assistant-worktrees/verify/schedule-named-baseline-phase13d-mainline-20260701T153222Z` |
| HEAD | `c983b1f4` |

## Test results

| Suite | Result |
|-------|--------|
| Backend focused (`02-backend-test-results.txt`) | 97 passed, **2 failed**, 1 skipped |
| Frontend focused (`03-frontend-test-results.txt`) | **35 passed** |

**Backend failures (non-blocking):** `test_project_schedule_hub_api.py` PM-field identifier tests fail because `comparison_schedule_version_key` (Phase 13A provenance) contains substring `schedule_version_key`. Named-baseline tests all pass. Classified **P3 test assertion drift**, not a named-baseline workflow regression.

## Tropical read-only proof

- DB schema v97; 3 active named slots (`04-tropical-readonly-db-state.txt`)
- No DB writes; GET-only API smoke

**Movement @ `as_of=2026-07-03` (`08b-movement-counts.txt`):**

| Basis | `finish_moved_later_count` |
|-------|----------------------------|
| `prior_update` | 461 |
| `current_contract_baseline` | 440 |
| `previous_progress_update_baseline` | 461 |
| `secondary_progress_update_baseline` | 593 |

## API smoke

- Controls / workbench / driver detail / export: `05`–`08` artifacts
- All four primary bases + legacy `baseline` export: **HTTP 200** (markdown + html)
- Named exports include `Comparison Context`; no silent prior-update fallback

## Browser smoke

- `09-browser-smoke/screenshot-proof.json` — **5/5 loaded**, `fully_loaded_required: true`
- Driver disposition card visible; no raw `psri-*`/`psnbri-*` in primary disposition copy

## Final rollout verdict

See [`10-mainline-verdict.md`](10-mainline-verdict.md).
