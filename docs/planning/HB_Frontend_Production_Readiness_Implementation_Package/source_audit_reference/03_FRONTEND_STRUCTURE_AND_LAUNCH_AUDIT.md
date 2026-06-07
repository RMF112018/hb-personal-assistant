# 03 Frontend Structure and Launch Audit

Generated: 2026-06-07T07:17:24.406486+00:00

Audit scope: `hb-personal-assistant` FastAPI / Vite React frontend analytics dashboard. Repository truth reviewed through the GitHub connector because the sandbox could not access `/Users/bobbyfetting/hb-personal-assistant` and network clone failed. No production source changes were made.


## Structure Reviewed

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/src/app/routes.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/*`
- `frontend/src/components/*`
- `frontend/src/layouts/*`
- `frontend/src/navigation/navigationModel.ts`
- `frontend/src/index.css`

## Confirmed Strengths

- Root route redirects to `/today`.
- Chat is not routed.
- Top-level navigation is CM-first: Today, Projects, My Items; Admin / Data Confidence and Settings are supporting surfaces.
- Local dev role selector is visibly labeled “Local dev role — not production auth”.
- API client sends `X-HB-UI-Role` and defaults invalid/empty role to `operator` locally.
- TanStack Query is used for live API loading.
- Tailwind + CSS variables implement dark/light/system-aware styling.
- Daily Brief renderer is split into a component and Settings includes external-agent setup flow.

## Launch / Build Status

Not validated in this sandbox. The GitHub connector confirms package files and scripts, but `npm install`, `npm run lint`, `npm run typecheck`, and `npm run build` were not executed because there is no local repo worktree and network clone failed.

## Frontend Blocking Issues

- Project subpages can crash due object-vs-array response handling.
- My Items performs five API calls to routes not registered by backend.
- Projects portfolio does not consume `project_keys` returned by backend.
- Settings raw JSON/details and alerts remain.
- Hash-style links are incompatible with BrowserRouter.
