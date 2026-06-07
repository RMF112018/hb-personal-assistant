# Prompt 20 — Settings and onboarding polish

Repository: `RMF112018/hb-personal-assistant`  
Working path: `/Users/bobbyfetting/hb-personal-assistant`  
Prompt dependency: Prompt 19 should be closed or explicitly waived with evidence.

## Objective

Replace backend-console controls with guided local-first setup and preference flows.

## Repo-Truth First Step

Before changing files, run the preflight commands in `02_REPO_TRUTH_PREFLIGHT.md` or update the existing preflight evidence if it has already been run in this implementation sequence. Repository truth is authoritative over this package.

## Gaps Addressed

### FPR-004 — Settings page still exposes raw JSON/debug response panels

- Severity: P1
- Affected area: Settings / UX / sensitive posture
- Recommended fix: Replace raw JSON panels with concise status cards and optional admin-only redacted diagnostics routed to Admin/Data Confidence.
- Validation: grep no Raw response in SettingsPage; frontend smoke settings load buttons; safe serialization tests remain green

### FPR-005 — Daily Brief currentState expression has precedence bug

- Severity: P1
- Affected area: Settings / Daily Brief
- Recommended fix: Use explicit parentheses and helper function: if disabled -> not_configured; else detectResult.state ?? status.state. Add test around configured_waiting and brief_available states.
- Validation: npm run typecheck; Daily Brief state unit test; manual Settings detect states

### FPR-010 — Settings still feels like backend controls rather than onboarding

- Severity: P2
- Affected area: Settings / Product fit
- Recommended fix: Convert to guided Account Connections, Project Connections, Daily Brief, Preferences sections with preview→save cards and clear next actions.
- Validation: UX smoke path new user setup; no stub text grep; settings backend tests

### FPR-016 — Preferences persistence is still an echo stub

- Severity: P3
- Affected area: Settings / Preferences
- Recommended fix: Persist preferences to local Application Support JSON with schema/version and safe validation.
- Validation: pytest preferences roundtrip; browser reload persistence

### FPR-017 — Project keyword UI is informational only

- Severity: P3
- Affected area: Settings / Project Matching
- Recommended fix: Add project keyword management UI with project selector, active/disabled/excluded lists, preview explain, and safe validation.
- Validation: pytest keyword routes; frontend keyword CRUD smoke


## Scope

- Refactor Settings into clear sections: Account Connections, Project Connections, Daily Brief, Preferences, Admin Sync Queue visibility where appropriate.
- Remove raw JSON/details response panels from the normal Settings UI.
- Fix Daily Brief currentState precedence with an explicit helper and tests.
- Replace “Load”/sample/stub copy with guided status cards and next actions.
- Preserve preview → save → admin approval flow for setup.
- Ensure Procore URL parsing and SharePoint/OneDrive preview flows remain setup-only and do not start live sync.
- Clarify Outlook/Calendar project-matching-only optional false-default behavior.
- Implement or honestly label preferences persistence. If persistence remains stubbed, move it out of the production-ready path or create a real local preference store consistent with current architecture.
- Project keyword UI may remain informational only only if clearly labeled and not presented as active management; otherwise implement safe keyword management around existing backend routes.

## Non-Scope

- Launching live sync from Settings setup.
- Showing tokens/secrets.
- Embedding external AI chat in Settings.

## Files Likely Touched

- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/components/settings/*`
- `frontend/src/components/ui/*`
- `frontend/src/lib/api.ts`
- `src/hb_assistant/construction/analytics/api.py`
- `src/hb_assistant/construction/analytics/daily_brief.py`
- `src/hb_assistant/construction/analytics/service.py`
- `tests/test_fastapi_analytics_settings.py`
- `tests/test_fastapi_analytics_connection_setup.py`
- `tests/test_fastapi_analytics_daily_brief.py`

## Implementation Guidance

- Prefer typed adapters and explicit view-model normalization over permissive `any` fallbacks.
- Preserve the current safety boundaries: no source-system writeback, no active chat, no raw/secrets serialization, no setup-triggered live sync.
- Keep the UI construction-management-first and avoid backend-console labels.
- Update tests and evidence in the same prompt; do not defer validation to a later session unless blocked by environment.
- When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily.

## Acceptance Criteria

- No normal Settings UI text contains “Raw response”, “sent (stub)”, or backend-console debug panels.
- No `alert()` calls remain in Settings.
- Daily Brief states display correctly for disabled, configured-waiting, missing-file, stale, and available cases.
- Setup interactions preview/save only and do not start live sync.
- No secrets/tokens/signed URLs are displayed.
- Daily Brief external-agent Markdown workflow is clearly explained.

## Validation Commands

- `python -m pytest tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_daily_brief.py`
- `cd frontend && npm run lint && npm run typecheck && npm run build`
- `grep -R "Raw response\|sent (stub)\|alert(" -n frontend/src || true`
- `Browser smoke: /settings full setup walkthrough without live sync`

## Evidence Required

Create or update:

```text
docs/evidence/frontend-production-readiness-implementation/prompt-20-settings-onboarding-polish-closeout.md
```

Include branch, HEAD, files changed, gaps closed/deferred, validation command output summary, browser smoke notes, and guardrail confirmation.

## Risk Notes

- Auth setup routes may legitimately initiate OAuth/device login; keep that distinct from dashboard read models and live syncs.
- Preference persistence may require a small local storage/read-model decision; document the chosen architecture.
