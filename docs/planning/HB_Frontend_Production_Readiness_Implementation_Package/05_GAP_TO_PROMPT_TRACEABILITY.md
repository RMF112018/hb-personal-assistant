# 05 Gap-to-Prompt Traceability

| Gap ID | Severity | Prompt Placement | Title |
|---|---|---|---|
| FPR-001 | P0 | Prompt 16 | Project tab pages can crash because frontend treats object read models as arrays |
| FPR-002 | P1 | Prompt 16 | My Items page calls unimplemented backend subroutes |
| FPR-003 | P1 | Prompt 18 | Projects portfolio selector does not consume backend project_keys |
| FPR-004 | P1 | Prompt 20 | Settings page still exposes raw JSON/debug response panels |
| FPR-005 | P1 | Prompt 20 | Daily Brief currentState expression has precedence bug |
| FPR-006 | P1 | Prompt 16 | BrowserRouter pages contain hash-style links |
| FPR-007 | P1 | Prompt 21 | Admin page does not present role-denied state clearly |
| FPR-008 | P1 | Prompt 17 | Today dashboard is missing explicit required sections |
| FPR-009 | P2 | Prompt 18 | Hardcoded freshness/confidence values remain on project pages |
| FPR-010 | P2 | Prompt 20 | Settings still feels like backend controls rather than onboarding |
| FPR-011 | P2 | Prompt 22 | alert() error handling remains in Settings |
| FPR-012 | P2 | Prompt 23 | No frontend test harness found |
| FPR-013 | P2 | Prompt 22 | Responsive/accessibility baseline is incomplete |
| FPR-014 | P2 | Prompt 24 | Daily Brief latest endpoint returns bounded Markdown content; needs explicit no-source-raw fixture coverage |
| FPR-015 | P3 | Post-production enhancement | Chart readiness dependency exists but chart UX is not implemented |
| FPR-016 | P3 | Prompt 20 or 24 | Preferences persistence is still an echo stub |
| FPR-017 | P3 | Prompt 20 or later | Project keyword UI is informational only |
| FPR-018 | P3 | Prompt 25 | End-to-end local smoke harness and runbook are not yet packaged |

## Severity Policy

- P0 and P1 gaps must be closed before declaring the app ready for meaningful local user testing.
- P2 gaps must be closed before production-readiness closeout unless explicitly deferred with a reason.
- P3 gaps may be deferred if the current scope remains launchable, stable, and honest.
