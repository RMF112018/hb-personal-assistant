# Phase 07B — Live End-to-End Calendar Smoke Proof

- **generated_utc:** `2026-05-31T12:58:30Z`
- **repo_sha at run:** `2038d89`
- **account:** `<delegated-user>` · **tenant:** `<tenant-guid>` · **schema_version:** 23
- **posture:** delegated Microsoft Graph **read-only** (GET-only, endpoint-guard enforced); local SQLite
  writes only behind `--apply`; no token/UPN/tenant/cache-path/raw subject/organizer/attendee/location/
  join-URL in this artifact.

## What ran live (real Microsoft Graph + real local store)

| Step | Command | Exit | Result |
|---|---|---|---|
| 1 | `graph calendar status --json` | 0 | `ok=true`; probe **HTTP 200**; `event_sample_count=1`; `guardrail_status=passed` |
| 2 | `graph calendar index --json` (dry-run) | 0 | `events_seen=108`, `persisted=false` |
| 3 | `graph calendar index --apply --json` | 0 | **108 indexed** (0 private, 2 cancelled, 0 review); `persisted=true` |
| 4 | `graph calendar project-match --json` (dry-run) | 0 | 108 evaluated, 8 matched, 100 unmatched, 8 candidates |
| 5 | `graph calendar project-match --apply --json` | 0 | 8 candidates persisted (8 weak, 8 review-routed, 0 deterministic, 0 conflicting) |

## Precondition + the scope fix that unblocked it

`hb-assistant auth login --json` refreshed a delegated token (account `<delegated-user>`). The first live
attempt failed because the calendar token-getter **hardcoded `Calendars.Read`**, which was never consented
(only `Calendars.ReadWrite.Shared` is). Diagnostic: `User.Read` ✅, `Calendars.Read` ❌ (not consented),
`Calendars.ReadWrite.Shared` ✅. Fix (`src/hb_assistant/cli/graph.py`): `_configured_calendar_scopes()`
requests the configured `Calendars.*` scope; the read-only **endpoint guard is unchanged**, so behavior
stays read-only (same deferred-tightening posture as `Files.ReadWrite.All`).

## Persistence snapshot (read-only counts)

`<app-support>/db/hb-personal-assistant.sqlite`

| Table | Rows |
|---|---|
| calendar_event_index | 108 |
| calendar_event_attendees | 1250 |
| calendar_crawl_runs | 1 |
| calendar_sync_state | 1 |
| calendar_project_match_candidates | 8 |

## Guardrail attestations

- `mutations_attempted: 0` · `event_body_persisted: false` · `join_url_persisted: false` ·
  `external_writeback_performed: false`.
- CHECK-column sums (`raw_body_persisted` / `full_text_persisted` / `external_writeback_performed`) = **0**
  across `calendar_event_index`, `calendar_crawl_runs`, `calendar_project_match_candidates`.
- Read-only leak scan of the calendar tables: **0** raw email addresses, **0** http URLs, **0**
  non-redacted subjects (all `[redacted:<hex>]`); attendees stored as `attendee_hash` + bare domain.
- `construction-agent data-quality no-writeback-proof --json` → exit 0, `proof_passed=true`.
- `construction-agent data-quality table-inventory --json` → exit 0.

## Notes

- 0 deterministic project matches: no real event subject contained a full `NN-NNN-NN` HB project number
  matching a known project; the 8 weak candidates are single project-name-token overlaps, all routed to
  review (no auto-promotion).
- No 07D meeting-prep readiness is claimed.
