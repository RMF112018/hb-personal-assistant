# Browser Sign-Off

**STAMP:** 20260701T075049Z  
**Proof type:** live browser (Playwright headless Chromium)

## Stack

| Service | URL | Status |
|---------|-----|--------|
| Backend | http://127.0.0.1:8000 | 200 /health |
| Frontend | http://127.0.0.1:5173 | 200 |

## Walkthrough

| Step | Result |
|------|--------|
| Tropical schedule hub loads | PASS — `screenshots/01-schedule-hub.png` |
| Workbench named Current Contract Baseline | PASS — `02-workbench-named-baseline.png` |
| Driver detail `activity_id=FAB%2FDEL-10` loads | PASS — URL preserved; `03-driver-detail-slash-activity.png` |
| Query-param encoding visible | PASS — `04-driver-url-encoding.png` |
| Back to Workbench preserves basis + as_of | PASS — `05-back-to-workbench.png` |

## URLs verified

- Driver: `http://127.0.0.1:5173/projects/tropical/schedule/driver-detail?activity_id=FAB%2FDEL-10&comparison_basis=current_contract_baseline&as_of=2026-07-01`
- Back: `http://127.0.0.1:5173/projects/tropical/schedule/workbench?comparison_basis=current_contract_baseline&as_of=2026-07-01`

## Notes

- `localStorage['hb-ui-role']='operator'` set before navigation.
- Real API proof confirms `FAB/DEL-10` decoded activity_id and named `baseline_context` (see `real-api-driver-route-proof.md`).
- Screenshots show live tropical schedule UI (activity names and movement deltas) for route-encoding verification only; committed API JSON artifacts are redacted summaries.
