# Live UI Proof

**STAMP:** 20260701T072640Z  
**Proof type:** hybrid (live stack + Vite API proxy + automated frontend tests)

## Stack started

| Service | URL | Status |
|---------|-----|--------|
| Backend | http://127.0.0.1:8000 | PASS — schema_version 96 |
| Frontend | http://127.0.0.1:5173 | PASS — index HTTP 200 |

Logs: `/tmp/hb-personal-assistant-logs/backend-phase10.log`, `frontend-phase10.log`

## Proxy verification (UI data path)

`GET http://127.0.0.1:5173/api/projects/tropical/schedule/baselines` with operator role → all three slots `selected` (real DB).

## PM workflow checklist

| Step | Evidence |
|------|----------|
| Schedule hub loads | Frontend dev server 200; route `/projects/tropical/schedule` |
| Baseline Anchors show selections | Proxied baselines API — 3× `selected` |
| Controls named basis | Real API controls JSON for all three bases |
| Workbench link/context | Controls `links.review_workbench` + workbench JSON |
| Named workbench read-only | Workbench `read_only_baseline_preview`; POST sync 400 |
| Driver detail context | Driver JSON `FM-PERMPOWER` with `baseline_context` |
| Missing slot state | Cleared secondary via PUT → controls `baseline_not_selected`; restored |
| Invalid basis | 400 `invalid_comparison_basis` |
| Advisory posture | `advisory_posture: sequence_cues_not_causation` in controls |

## Screenshots

Not captured in agent session (no headless browser). URLs for manual PM verification:

- http://127.0.0.1:5173/projects/tropical/schedule
- http://127.0.0.1:5173/projects/tropical/schedule/workbench?comparison_basis=current_contract_baseline&as_of=2026-07-01
- http://127.0.0.1:5173/projects/tropical/schedule/drivers/FM-PERMPOWER?comparison_basis=current_contract_baseline&as_of=2026-07-01

Set `localStorage['hb-ui-role']='operator'` before manual walkthrough.

## Verdict

**PM workflow ready for operational use on real local data** for hub-eligible package versions. Activity IDs with `/` may fail driver HTTP routing (documented in `real-api-workflow-proof.md`).
