# Prompt D — Get Started and Account Connections UX

You are working on the `hb-personal-assistant` repository.

Repository: `/Users/bobbyfetting/hb-personal-assistant`

Repository truth is authoritative. If repo truth differs from this prompt, adapt the implementation to repo truth without weakening the security, local-first, no-writeback, admin-approval, or onboarding requirements.

Do not expose tokens, secrets, signed URLs, download URLs, PEM material, raw source payloads, raw email bodies, raw document text, raw prompts/responses, or local token cache paths to the frontend.

No setup, auth, preview, save, refresh, or approval action may start live sync automatically.


## Objective

Implement first-time onboarding and usable account authentication UX in the frontend.

## Scope

- Add `/get-started` route.
- Add startup readiness logic using `GET /api/onboarding/readiness`.
- Route fully unauthenticated sessions to Get Started.
- For returning stale-auth users, show refresh/reauth state without resetting to first-time onboarding unless no usable prior setup/data exists.
- Build Microsoft 365 account connection card.
- Build Procore account connection card.
- Add typed `frontend/src/lib/api.ts` helpers for normalized auth/account routes.
- Remove normal-user raw JSON/debug panels from Settings account connection UX.
- Add clear copy that connecting auth does not start sync.

## Non-Scope

- Do not build detailed project connection setup here; Prompt E handles it.
- Do not build admin first-sync queue here; Prompt F handles it.
- Do not build full data-quality detail here; Prompt G handles it.

## Likely Files Touched

- `frontend/src/App.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/GetStartedPage.tsx`
- `frontend/src/components/settings/AccountConnectionsPanel.tsx`
- `frontend/src/components/settings/GraphConnectionCard.tsx`
- `frontend/src/components/settings/ProcoreConnectionCard.tsx`
- `frontend/src/hooks/useOnboardingReadiness.ts`
- `frontend/src/lib/api.ts`
- `frontend/vite.config.ts` if proxy changes are required

## Acceptance Criteria

- First-time session lands on `/get-started`.
- Get Started explains connect/preview/save/admin approval sequence.
- Graph card can start auth and display verification URL/user code safely.
- Graph card can poll status and render connected/expired/failed states.
- Procore card can start auth, open authorization URL, poll callback completion, and use manual fallback.
- Returning stale-auth users see refresh attempt before reauth prompt.
- Frontend never renders raw JSON for normal users.
- No setup/auth action starts sync.

## Validation Commands

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

If frontend tests exist:

```bash
cd frontend
npm test -- --run
```

## Risk Notes

- Keep UI simple for non-engineering local user.
- Do not add active in-app chat.
- Do not introduce localStorage token storage.
- If Vite proxy currently only proxies `/api`, prefer normalized `/api` backend routes rather than widening frontend calls to root `/auth` routes.
