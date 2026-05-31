# 07B Prompt 03 — Read-only Graph Calendar Status & Endpoint Mutation-Lockout Proof

**Phase:** 07B — Prompt 03 (Read-only Graph Calendar Status And Guardrails)
**Scope:** Add the calendar endpoint contract (allowlist/blocklist), an in-process endpoint guard that
blocks every mutation verb/path **before** HTTP, a guarded read-only calendar client, and the
`hb-assistant graph calendar status` command. Additive, local-only, read-only external posture.
No event indexing/matching/persistence (07B Prompts 04–05). No 07D readiness claimed.

All private values below are reduced to **structural facts only** — no UPN, tenant GUID, object id,
cache path, token, secret, event subject/organizer/attendee/location, or join URL is reproduced.

## 1. Repo-truth preflight (before edits)

| Command | Exit |
|---|---|
| `git rev-parse --abbrev-ref HEAD` | `main` |
| `git rev-parse HEAD` | `a64c09a3ea7d2e0d9c723af079552640d6ac7c9a` |
| `git status --short` | only `?? .claude/` (untracked, not committed) |
| `python -m compileall src tests` | 0 |
| `ruff check .` | 0 (`All checks passed!`) |
| `mypy src` | 0 (`Success: no issues found in 156 source files`) |
| `pytest -m "not live and not integration and not manual"` | 0 (8 xfail, 0 failed) |
| `hb-assistant graph calendar status --json` | **2** (`No such command 'calendar'`) — surface absent pre-edit |

## 2. Files added / modified

**Added**
- `resources/config/graph_calendar_read_endpoint_allowlist.yaml` — GET-only; 11 allowed read paths;
  body-/join-URL-free `event_metadata_select`.
- `resources/config/graph_calendar_mutation_endpoint_blocklist.yaml` — forbidden verbs
  (POST/PATCH/DELETE/PUT), 12 forbidden paths, 13 forbidden operation keywords.
- `src/hb_assistant/graph/calendar_endpoint_guard.py` — `CalendarEndpointContract`,
  `CalendarMutationBlockedError`, `assert_calendar_request_allowed`,
  `run_calendar_no_writeback_self_test`, `load_calendar_endpoint_contract`.
- `src/hb_assistant/graph/calendar_readonly_client.py` — `ReadOnlyCalendarClient` (guarded GET-only).
- `tests/test_graph_calendar_endpoint_guard.py`, `tests/test_graph_calendar_readonly_client.py`,
  `tests/test_graph_calendar_status.py`.
- `docs/architecture/20-phase-07b-calendar-readonly-guardrail.md`.

**Modified**
- `src/hb_assistant/cli/graph.py` — calendar imports, `_WRITE_CAPABLE_CALENDAR_SCOPES` /
  `_READ_CALENDAR_SCOPES`, `calendar_app` Typer subgroup, `_calendar_probe` helper, and the
  `graph calendar status` command (import block re-sorted by `ruff --fix`).

No `pyproject.toml` change: the guard reads its contract from the repo-root `resources/config/` via
`PathPolicy().resolve_repo_root()`, exactly like the mail/files guards (not packaged data).

## 3. Mutation-lockout proof (in-process, no network)

`run_calendar_no_writeback_self_test()`:

```
passed=True  read_paths_allowed=11  mutation_attempts_blocked=16  anomalies=[]
```

Spot checks (sanitized; ids replaced with `AAA`):

| Request | Result |
|---|---|
| `GET /me/calendarView` | permitted (returns `None`) |
| `POST /me/events` | blocked (forbidden verb) |
| `PATCH /me/events/AAA` | blocked |
| `DELETE /me/events/AAA` | blocked |
| `POST /me/events/AAA/accept` | blocked |
| `POST /me/events/AAA/cancel` | blocked |
| `POST /me/events/AAA/forward` | blocked |
| `PUT /me/calendarView` | blocked (non-GET on a read path) |

`CalendarMutationBlockedError` carries only `{method, normalized_path, reason}` — verified no
`Bearer`/`access_token` substring on the exception.

## 4. `graph calendar status --json` (AFTER) — redacted

`hb-assistant graph calendar status --json --no-probe` → **exit 0**. Structural shape (auth block
elided; it is `provider.status_info()` — redacted claims, **no tokens**):

```json
{
  "command": "graph calendar status",
  "ok": true,
  "calendar_read_capability_present": true,
  "write_capable_calendar_scopes_present": ["Calendars.ReadWrite.Shared"],
  "auth": { "<redacted: token_type, classification, redacted-claims, cache path-status — NO tokens>": "..." },
  "guard_self_test": { "passed": true, "read_paths_allowed": 11, "mutation_attempts_blocked": 16, "anomalies": [] },
  "calendar_probe": { "attempted": false },
  "guardrails": {
    "calendar_read_only": true,
    "mutation_endpoints_blocked": true,
    "event_body_excluded": true,
    "join_url_excluded": true,
    "permission_tightening": "deferred",
    "residual_risk": "write-capable scope configured; runtime calendar endpoint guard enforces read-only behavior",
    "guardrail_status": "passed"
  },
  "contract": { "allowed_methods": ["GET"], "allowed_paths_count": 11,
                "forbidden_methods": ["DELETE","PATCH","POST","PUT"], "forbidden_paths_count": 12 }
}
```

`--probe` (default) → **exit 0**: probe `attempted=true`, returned a non-fatal readiness status
(`"Failed to acquire delegated token (expired or revoked). Re-login required."`) — no network
mutation, `ok` unaffected. The probe surfaces only an event **count**, never event values.

## 5. Validation matrix (AFTER) — exit codes

| Command | Exit |
|---|---|
| `python -m compileall src tests` | 0 |
| `ruff check .` | 0 |
| `mypy src` | 0 (156 source files) |
| `pytest tests/test_mutation_lockout.py` | 0 (graph/ static no-write-verb scan still clean) |
| `pytest -m "not live and not integration and not manual"` | 0 (8 xfail, 0 failed) |
| `hb-assistant construction-agent validate --json` | 0 |
| `hb-assistant procore validate --json` | 0 |
| `hb-assistant graph files status --json` | 0 |
| `hb-assistant graph mail status --json` | 0 |
| `hb-assistant graph calendar status --json` | **0** (new; `ok:true`) |
| `hb-assistant construction-agent data-quality gates --json` | 0 |
| `hb-assistant construction-agent data-quality no-writeback-proof --json` | 0 |

New calendar test files: 40 tests, all passed.

## 6. Guardrail attestations

- **No M365 calendar mutation** — every mutating verb/path/keyword refused before HTTP (self-test +
  CLI). The `graph/` static no-write-verb scan (`test_mutation_lockout`) remains clean: the new guard
  and client use mutation verbs only as string arguments, never as `.post(/.put(/.patch(/.delete(`.
- **No body / join URL** — `event_metadata_select` excludes `body`, `bodyPreview`, `onlineMeeting`.
- **No raw/private values** — no token, secret, subject, organizer, attendee, location, event id, or
  join URL appears in code, JSON, or this evidence; auth uses redacted claims only.
- **Deferred tightening** — `Calendars.ReadWrite.Shared` reported as residual risk, not changed
  (per decision); guard enforces read-only regardless.
- **No 07D readiness** — not claimed; calendar ingestion/matching/gates remain for Prompts 04–12.
