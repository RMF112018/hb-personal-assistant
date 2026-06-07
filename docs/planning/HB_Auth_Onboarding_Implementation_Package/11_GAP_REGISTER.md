# Gap Register

| Gap ID | Severity | Title | Affected Area | Recommended Fix | Prompt Placement |
|---|---:|---|---|---|---|
| AUTH-P0-01 | P0 | No usable frontend path to authenticate Microsoft Graph | Frontend Settings / API client / Graph auth | Add Graph connection card, typed API helpers, device-code start/status polling, safe connected summary, disconnect and reauth actions. | B,D,H |
| AUTH-P0-02 | P0 | No usable frontend path to authenticate Procore | Frontend Settings / API client / Procore auth | Add Procore connection card, OAuth start/callback/status flow, manual code fallback, safe connected summary, disconnect and reauth actions. | C,D,H |
| AUTH-P0-03 | P0 | Frontend API/proxy contract does not cover auth/setup routes | Backend routes / frontend api.ts / Vite proxy | Normalize frontend-facing routes under /api/settings/connections/* and expose typed client helpers. | A,D,E |
| AUTH-P0-04 | P0 | Project Connections setup is not exposed as a real UX flow | Settings Project Connections | Build auth-aware preview/save/approval setup workflow with no automatic sync. | E,F,H |
| AUTH-P0-05 | P0 | Fully unauthenticated sessions do not land on a dedicated Get Started screen | App routing / onboarding | Add /get-started and startup readiness routing using /api/onboarding/readiness. | A,D,H |
| AUTH-P1-01 | P1 | Graph status is not sufficiently verified for user-facing readiness | Graph backend status | Use silent MSAL status_info/account validation and return safe account/scopes/reauth state. | B,H |
| AUTH-P1-02 | P1 | Stale auth should attempt automated refresh before prompting reauth | Backend auth readiness / startup UX | Add refresh attempt behavior to readiness and explicit refresh endpoint. | A,B,C,D,H |
| AUTH-P1-03 | P1 | Procore lacks primary localhost callback flow | Procore OAuth backend | Add callback route with state validation and browser-safe completion page; retain manual fallback. | C,H |
| AUTH-P1-04 | P1 | Procore status lacks account/company confirmation | Procore backend status | Add safe identity/company metadata after auth without exposing raw API payloads. | C,H |
| AUTH-P1-05 | P1 | First-sync approval needs normalized sync eligibility enforcement | Admin approval / sync governance | Persist approvals consistently and block live sync until approved. | F,H |
| AUTH-P1-06 | P1 | Settings UI exposes raw JSON/debug panels instead of user workflow | Frontend Settings | Replace debug panels with cards, state badges, safe messages, and admin-only diagnostics. | D,E,G |
| AUTH-P1-07 | P1 | Non-admin data quality should be simple and non-diagnostic | Sidebar / data quality UX | Add Data Quality footer indicator with green/yellow/red dot and hover timestamp. | G,H |
| AUTH-P2-01 | P2 | Graph permission posture may be broader than no-writeback product intent | Config / delegated scopes | Assess narrowing default scopes to read-only and enforce no-writeback policy regardless of consent scope. | B,H,I |
| AUTH-P2-02 | P2 | Procore exchange response may expose local cache path | Procore backend response hygiene | Remove cache_path from frontend-facing response envelopes. | C,H |
| AUTH-P2-03 | P2 | Missing complete loading/error/expired/cancel states | Frontend auth UX | Implement explicit UI state machines for Graph and Procore auth flows. | D,H |
| AUTH-P3-01 | P3 | Advanced account/company/project discovery can be enriched later | Procore/Graph discovery | Add optional governed metadata-only verification after core auth flow is stable. | I |
