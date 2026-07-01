# Phase 18 rollout checklist

- [x] Review portfolio dashboard on fixture DB (`fixture-phase18-portfolio.db`) — artifacts `03`–`14`
- [x] Verify `/projects/all/schedule/review` navigation from All Projects subnav — `14-browser-navigation-entry.png`
- [x] Confirm PM-safe API/export (no raw IDs in default payloads) — `06`, `07`, `24-live-redaction-proof.txt`
- [x] Operator-only `include_technical=1` gate on dashboard API — covered by API tests
- [x] Phase 18 tests pass — see `15-test-results.txt`
- [x] Live DB GET-only smoke — artifacts `18`–`26` (`capture_phase18_live_smoke.py`)
- [ ] Run full acceptance suite before merge (exclude or expect the two pre-existing named-baseline failures on `main`)
- [ ] Approve push/PR before publishing branch
