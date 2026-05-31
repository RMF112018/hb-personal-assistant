# Phase 07B — Read-only Graph Calendar Status & Endpoint Mutation Lockout

**Phase:** 07B — Prompt 03 (Read-only Graph Calendar Status And Guardrails)
**Status:** Implemented (read-only calendar status + endpoint guard; event indexing/matching land in 07B Prompts 04–05).
Evidence: `docs/evidence/construction-intelligence-phase-07b-calendar-email/03-calendar-readonly-guardrail-proof.md`.

This record documents the read-only calendar **probe + mutation lockout** surface. It adds the
HTTP-layer of the calendar read-only defense-in-depth (mirroring the Phase 06 mail/files stacks) and
the `hb-assistant graph calendar status` operator command. It performs **no** event indexing,
project matching, or persistence — those land in later 07B prompts.

## Components

| Component | Path | Role |
|---|---|---|
| Read allowlist (GET-only) | `resources/config/graph_calendar_read_endpoint_allowlist.yaml` | Calendar read patterns + body-/join-URL-free `event_metadata_select` |
| Mutation blocklist | `resources/config/graph_calendar_mutation_endpoint_blocklist.yaml` | Forbidden verbs/paths/keywords (create, update, delete, accept, decline, cancel, forward, reminder snooze/dismiss) |
| Endpoint guard | `src/hb_assistant/graph/calendar_endpoint_guard.py` | `assert_calendar_request_allowed()` refuses any non-allowlisted GET **before** HTTP; `run_calendar_no_writeback_self_test()` proves it in-process |
| Read-only client | `src/hb_assistant/graph/calendar_readonly_client.py` | `ReadOnlyCalendarClient` — guarded GET-only `calendarView`; no mutation method |
| CLI | `src/hb_assistant/cli/graph.py` (`graph calendar status`) | Reports auth posture, guard self-test, bounded probe, guardrails |

The guard loads its contract from the repo-root `resources/config/` via
`PathPolicy().resolve_repo_root()` — identical to the mail/files guards, so no `pyproject.toml`
package-data change is required. The mutation verbs/paths/keywords are kept in YAML (not hard-coded
in `graph/`) so the module stays clean under the `test_mutation_lockout` static scan, which greps
`graph/` for any `.post(/.put(/.patch(/.delete(` call.

## Enforcement model (positive-allowlist-first)

`assert_calendar_request_allowed(method, path)` permits a request **only** when it is a `GET` whose
normalized path matches an allowlisted template; otherwise it raises `CalendarMutationBlockedError`
with the most specific reason (forbidden verb → non-GET → forbidden path → forbidden keyword →
unknown path). Allowlist-first means a legitimate event read can never false-positive on a keyword
inside an opaque event id. The exception is sanitized — it carries only the method, normalized path,
and a short reason, never tokens, headers, event bodies, join URLs, or attendee values.

`run_calendar_no_writeback_self_test()` walks the contract in-process (no network): every allowlisted
template is permitted under `GET`, every forbidden path is blocked under `POST`, and every forbidden
verb is blocked even on an otherwise-readable event path. Result: `passed=True`, 11 read paths
allowed, 16 mutation attempts blocked, zero anomalies.

## Read-only `$select` boundary

`event_metadata_select` is body-free: `body`/`bodyPreview` (the event description) and `onlineMeeting`
(which carries the join URL) are **never** requested — only the safe `onlineMeetingProvider` flag.
`sensitivity` (valid on the Graph `event` entity, unlike `message`) is read to drive private-event
handling. Subject/organizer/attendees/location are read only to be hashed/redacted by the later
indexing prompt; they are never persisted raw, and the status probe surfaces only an event **count**.

## Scope posture — deferred tightening (documented residual risk)

Runtime config (`config/models.py`) requests the write-capable `Calendars.ReadWrite.Shared` scope,
consented at the tenant — mirroring the existing `Files.ReadWrite.All` "broad scope, runtime
read-only, tightening deferred" posture. Prompt 03 deliberately does **not** change auth/config
scope. `graph calendar status` reports the write scope as a residual risk rather than a failure:

- `write_capable_calendar_scopes_present: ["Calendars.ReadWrite.Shared"]`
- `guardrails.permission_tightening: "deferred"`
- `guardrails.residual_risk: "write-capable scope configured; runtime calendar endpoint guard enforces read-only behavior"`
- `guardrails.guardrail_status: "passed"` — only when the in-process mutation-lockout proof passes.

`ok` (exit 0) is driven by the mutation-lockout proof **and** calendar read capability
(`Calendars.Read` or the broader `Calendars.ReadWrite.Shared`, which also grants read). The bounded
probe is non-fatal: an expired/absent token yields a readiness status, not a failure, and never makes
a mutation call (the guard permits only GET).

## Guardrails proven

- No Microsoft 365 calendar mutation: create/update/delete, attendee response, cancel, forward, and
  reminder mutations are all blocked before HTTP (self-test + CLI guard status).
- No event body/description or online-meeting join URL requested or persisted.
- No token, secret, raw subject/attendee/organizer/location, or join URL emitted to code, JSON, or
  evidence (status uses `provider.status_info()` — redacted claims, no tokens; evidence redacts
  UPN/tenant/paths to structural facts).
- Local-only, additive, read-only external posture preserved; no 07D meeting-prep readiness claimed.
