# End-User Copy Remediation Standard

## Voice

- Professional.
- Plainspoken.
- Construction-management-first.
- Action and outcome focused.
- Advisory without exposing implementation mechanics.

## Required replacements

| Current/internal copy | Replace with | Surface |
|---|---|---|
| Local dev role — not production auth | Developer testing (hidden unless enabled) | AppShell |
| Admin / Data Confidence | Admin & Data Health or Data Health | Navigation/Admin |
| View source & sync details | Check data health | Today/Projects |
| Prompt 14B / Prompt 20 / FPR-004 | Remove from visible UI | Settings |
| Load Accounts Status | Check connection status | Settings |
| Load Projects | Review project connections | Settings |
| preview→save | Review before saving | Settings |
| raw panels removed | Remove entirely | Settings |
| Project key | Project | Keywords |
| JSON.stringify output | Formatted table/cards | Keywords/Project data |
| Evidence / Guardrail Health | Safety Checks | Admin |
| Retrieval / AI Quality | Answer Quality | Admin |
| Workflow / Job Health | Background Tasks | Admin |
| Source / Sync Health | Source Updates | Admin |
| FastAPI analytics shell / uvicorn | The local app service is not running. Restart the app. | Today error |
| read models | latest project information | Core pages |
| external Markdown / MCP / scheduled prompt | Daily Brief file / advanced setup | Daily Brief |
| Chat (disabled) | No visible chat nav item | Support nav |

## Forbidden production UI terms and patterns

These terms should not appear in production-rendered frontend TS/TSX/CSS unless explicitly allowlisted as developer-only, docs-only, test-only, or hidden behind a dev flag:

- `local dev role`
- `not production auth`
- `Prompt 14B`
- `Prompt 20`
- `FPR-004`
- `raw panels`
- `JSON.stringify`
- `FastAPI`
- `uvicorn`
- `read models`
- `source/sync/evidence`
- `guardrail`
- `retrieval`
- `MCP`
- `endpoint`
- `payload`
- `route`
- `backend`
- `Vite`
- `HMR`
- `Count is`
- `Chat (disabled)`

## Allowlist guidance

- `docs/**`
- `tests/**`
- developer-only panels hidden behind `VITE_HB_SHOW_DEV_TOOLS=true`
- technical details disclosure available only to Admin users where appropriate

## Required normal-user behavior

- Do not show prompt IDs.
- Do not show raw JSON or `JSON.stringify` fallback output.
- Do not show route/endpoint/FastAPI/uvicorn/backend/Vite/HMR terms.
- Do not show local development role simulation in normal app chrome.
- Do not render disabled Chat.
- Do not describe source/sync/evidence/retrieval architecture in ordinary page instructions.
- Use Data Quality/Data Health labels instead of Data Confidence unless the route name remains internal.
