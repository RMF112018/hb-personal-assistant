# Pre-Fix PM Walkthrough

**STAMP:** 20260701T081419Z  
**Proof type:** real local DB + live browser (Playwright)

## Environment

| Service | URL | Status |
|---------|-----|--------|
| Backend | http://127.0.0.1:8000 | 200 |
| Frontend | http://127.0.0.1:5173 | 200 |
| DB | `hb-personal-assistant.sqlite` v96 tropical named baselines | real |

## Walkthrough results

| Step | Result | Notes |
|------|--------|-------|
| 1. Open tropical schedule hub | PASS | Story, metrics, schedule controls + baseline anchors sections present (`01-schedule-hub.png`) |
| 2. Baseline anchors — three selected | PASS (API) | Hub screenshot caught loading state; Phase 11 evidence confirms three tropical slots selected |
| 3. Controls placement | OBSERVED | Controls card appears above Baseline Anchors on hub |
| 4. Select Current Contract Baseline | PASS | Badge selection works (`02-controls-named-baseline.png`) |
| 5. Controls copy understandable | PARTIAL | Headline/supporting points OK; no persistent “comparing against” anchor line when controls load |
| 6. Named Workbench | PARTIAL | Route loads; screenshot caught loading spinner (`03-workbench-named-baseline.png`) |
| 7. Read-only explanation | PARTIAL | Muted subtext only — easy to miss |
| 8. Driver FAB/DEL-10 | PARTIAL | Query URL correct; screenshot caught loading (`04-driver-detail-slash-activity.png`). Phase 11 proof confirms full render |
| 9. Driver PM labels | FAIL (pre-fix) | H3 = “Driver Detail”; activity name in subtext |
| 10. Back navigation | PASS (API/Phase 11) | `comparison_basis` + `as_of` preserved in hrefs |
| 11. Missing baseline | SKIPPED (DB) | No slot cleared on real DB; fixture test planned |
| 12. Section order confusion | NOT P0/P1 | Controls-before-anchors is scrollable; anchors visible without reorder — **no section reorder** |

## Friction summary

- Driver detail title hierarchy weak (activity name not primary)
- Named workbench read-only posture not prominent
- Controls lack visible comparison-anchor context when available
- Missing/invalid baseline messages not actionable enough
- Driver conflict errors mention internal param names
- Logic changes may expose raw activity IDs (when present)

## Screenshots

`screenshots/pre-fix/` — some captures mid-load; Phase 11 `driver-route-encoding-phase11-20260701T075049Z/screenshots/` supplements fully loaded states.
