# 07 Browser Smoke Test Plan

## Purpose

Confirm the local-first dashboard works as a user-facing app, not just as passing backend route tests.

## Roles to Test

Use the local dev role selector labeled `Local dev role — not production auth`.

- `operator`: default normal user role.
- `viewer`: read-limited role.
- `admin`: required for Admin / Data Confidence and first live sync governance surfaces.

## Smoke Script Checklist

| Step | Role | Route | Expected Result |
|---|---|---|---|
| 1 | operator | `/` | Redirects to `/today`. |
| 2 | operator | `/today` | Shows Today command center; required sections render. |
| 3 | operator | `/projects` | Shows All Projects and any project selector/cards from backend contract. |
| 4 | operator | `/projects/all/overview` | Renders dashboard envelope without TypeError. |
| 5 | operator | `/projects/all/meetings` | Renders meetings-prep view without TypeError. |
| 6 | operator | `/projects/all/field-operations` | Renders field operations signals without TypeError. |
| 7 | operator | `/projects/all/cost-time` | Renders cost/time advisory signals without TypeError. |
| 8 | operator | `/my-items` | No expected API 404s; sections render with useful empty states. |
| 9 | operator | `/admin` | Clear admin-required state, not endless loading. |
| 10 | admin | `/admin` | Six Data Confidence categories render. |
| 11 | operator | `/settings` | Guided setup sections render; no raw JSON/debug panels. |
| 12 | operator | `/chat` | No active chat UI; route unavailable or clearly disabled. |

## Console / Network Criteria

- No uncaught React errors.
- No TypeError from `.slice()` on object envelopes.
- No expected API 404s.
- Admin 403s are allowed only when they drive a clear role-denied UI state.
- No Tailwind/PostCSS/Vite compile errors.

## Evidence Capture

For each prompt closeout, include:

- browser routes tested;
- roles tested;
- any console/network issues found;
- screenshots optional, not required;
- remediation status.
