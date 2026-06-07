# P04 — Source Refresh, Scheduler, and Daily Brief Status Surfaces

Wire UI-facing refresh/status actions without weakening gates.

Add/adapt:
- `POST /api/sources/refresh/dry-run`;
- `POST /api/sources/refresh/local`;
- `POST /api/sources/refresh/live`;
- `GET /api/scheduler/daily-source-refresh/status`;
- `GET /api/daily-brief/status`.

Dry-run must not write DB. Local/mock refresh must not call live clients. Live refresh must fail closed unless config and confirmation permit it.

Tests must prove dry-run no-write, local no-live, live fail-closed, and no raw payloads in receipts.
