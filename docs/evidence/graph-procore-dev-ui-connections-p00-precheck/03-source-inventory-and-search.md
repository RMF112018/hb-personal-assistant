# P00 — 03 Source Inventory and Search Sweeps

Captured: 2026-06-07

## File counts

| Tree | Files (depth-bounded) |
|---|---|
| `src/` | 1373 |
| `frontend/src/` | 87 |
| `tests/` | 1942 |

## Search-sweep match counts (files with ≥1 hit)

| Sweep | `src/` | `frontend/src/` |
|---|---|---|
| Graph / Microsoft / M365 / mail / calendar / OneDrive / SharePoint | 229 | 10 |
| Procore / OAuth / token / mapping / sync | 279 | 27 |
| source-refresh / scheduler / freshness / confidence / data-quality | 228 | 24 |

Backend (`src/`) is rich in Graph/Procore/scheduler capability; the frontend touches the same domains
through the API client only.

## Frontend API client (`frontend/src/lib/api.ts`)

```
29: const API_BASE = ((import.meta as any)?.env?.VITE_API_BASE as string | undefined) || '';
101: async function fetchJson<T = any>(path: string, init?: RequestInit): Promise<T> {
104:   headers.set('X-HB-UI-Role', role);
108:   const res = await fetch(`${API_BASE}${path}`, { ... });
```

- `API_BASE` defaults to **empty string** → all calls use **relative `/api/...`** paths → resolved by
  the Vite dev-server proxy to `http://127.0.0.1:8000`. No hard-coded host; `VITE_API_BASE` is an
  opt-in override only. **No base-URL/CORS misconfiguration.**
- Every request injects `X-HB-UI-Role` from `localStorage['hb-ui-role']` (default `viewer`).

## Aggregate source-status references

`rg '/api/environment|/api/sources|sources/status'` over `frontend/src` returns **no** functional
references (only a copy string in `GetStartedPage.tsx:37` mentioning "environment"). The aggregate
`/api/environment` + `/api/sources/status` endpoints (gap **GPC-P0-001**) are therefore a
**target-architecture addition**, not a currently-wired-but-broken call.
