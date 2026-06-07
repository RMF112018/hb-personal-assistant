# Implementation Gap Map

| Gap ID | Severity | Title | Prompt | Required fix |
|---|---:|---|---|---|
| GPC-P0-001 | P0 | Dev UI lacks aggregate source status | P01 | Add/adapt `/api/environment` and `/api/sources/status` |
| GPC-P0-002 | P0 | Graph UI lacks safe status/auth bridge | P02 | Add metadata-only Graph status and safe auth routes |
| GPC-P0-003 | P0 | Procore UI lacks safe status/auth bridge | P03 | Add metadata-only Procore status and safe OAuth routes |
| GPC-P0-004 | P0 | Connect buttons fail or are placeholders | P02/P03/P06 | Wire to backend-controlled flows or disabled next-action states |
| GPC-P0-005 | P0 | Refresh semantics are ambiguous | P04/P06 | Split dry-run, local/mock, and gated live actions |
| GPC-P0-006 | P0 | Frontend/backend endpoint mismatch likely | P05 | Normalize typed API client and response contracts |
| GPC-P1-001 | P1 | Dev/local mode is unclear | P07 | Show environment/source mode and live-disabled reason |
| GPC-P1-002 | P1 | Scheduler/freshness not surfaced | P04/P07 | Add read-only scheduler/daily-brief/source freshness |
| GPC-P1-003 | P1 | Internal copy/errors leak to UI | P07/P08 | Add copy/error mapper and admin-only diagnostics |
| GPC-P1-004 | P1 | No regression proof for safety gates | P08 | Add backend/frontend tests proving no live reads/writeback |

## Root-cause categories to classify in closeout

- missing backend endpoint;
- frontend calls wrong endpoint;
- response-shape mismatch;
- Dev mock/local policy not visible;
- auth exists only in CLI;
- UI has no auth/connect flow;
- source-refresh exists but UI is not wired;
- CORS/base-url/proxy issue;
- token/app-support path isolation issue;
- live-read guard too strict or too loose;
- frontend hardcodes mock state;
- normal UI exposes internal jargon.
