# 04 — DB Pre-Smoke Validation

**DB:** `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite`

## File metadata

| Field | Value |
|---|---|
| Owner/mode | `personal-assistant-svc:users`, **600** (`-rw-------`) |
| N3 baseline size | ~4.15 GB |

## Read-only service-user check (pre-smoke)

| Check | Result |
|---|---|
| `PRAGMA quick_check` | **ok** |
| Schema `MAX(version)` | **98** |
| Table count | **506** |

## Mutability boundary

N3 final DB opened read-only for validation; smoke used same path via container mount. No recopy or replacement.

Post-smoke re-validation: see [`09-db-post-smoke-validation.md`](09-db-post-smoke-validation.md) — unchanged schema/table count.
