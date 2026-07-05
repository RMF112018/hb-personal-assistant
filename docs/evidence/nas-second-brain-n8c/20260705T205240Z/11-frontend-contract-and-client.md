# 11 — Frontend Contract & Client

Minimal read-only smoke surface only (clarification #6): no review/approve/reject, no Qwen controls,
no card refresh, no graph explorer, no write actions.

## Delivered
- **Client** — `frontend/src/lib/api.ts`: 12 flat `getAssistant*` wrappers (each `fetchJson('/api/assistant/…')`,
  GET, `X-HB-UI-Role` auto-injected; optional params query-encoded), all re-registered on the `api`
  object. Loose (all-optional) response interfaces matching the contract.
- **Smoke page** — `frontend/src/pages/AssistantPage.tsx`: `ForecastShell`/`ForecastHero` +
  three `ForecastPanel`s — source search (query-gated `useQuery`), recent changes, stale cards — each
  with explicit loading/error/empty branches (`EmptyState`). Verified read-only (grep found no
  `useMutation`/POST/PUT/PATCH/DELETE/save/apply/refresh handlers).
- **Route** — `frontend/src/app/routes.tsx`: `{ path: 'assistant', element: <AssistantPage/>, handle:{title:'Assistant'} }`.
- **Nav** — `frontend/src/navigation/navigationModel.ts`: `SUPPORT_NAV` entry + `getRouteTitleForPath`
  line.

## Verification
- `npx vitest run src/lib/assistantApi.test.ts src/pages/AssistantPage.test.tsx` → **6 passed** (client
  URL/method/`X-HB-UI-Role` assertions + page render with mocked api). Independently re-run by the
  owner agent, green.
- `npx tsc -b`: zero errors in the new/changed files (5 pre-existing errors remain in untouched files).
- Full frontend suite: 9 pre-existing failures (unrelated, confirmed identical via `git stash`), 448
  passed. No `package-lock.json` churn. `git status` confirms only `frontend/` files changed by the
  frontend work.

## Contract of record
`docs/architecture/n8c-read-navigation-contract.md`. Later slices (N8C-9+) can build richer views on
this same contract with no backend change.
