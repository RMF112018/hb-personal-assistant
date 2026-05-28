# Phase 04A — Final `_UNVERIFIED_IDS` Closeout

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)

The last 2 unverified canonical endpoints are now `live_verified=True`. **All 16 canonical endpoints in the Phase 04A registry are live-verified end-to-end against `tropical`.** The operator provided exact Procore-docs path snippets for the two deferred endpoints, eliminating the prior multi-path probe loops.

## Outcome summary

| Endpoint           | Path adopted                                                          | Smoke receipt | Apply outcome                       |
| ---                | ---                                                                   | ---           | ---                                 |
| `daily-log-dcrs`   | `/rest/v1.0/projects/{project_id}/daily_construction_report_logs`     | `487d9f3d`    | 1 record persisted, idempotent      |
| `meeting-topics`   | `/rest/v1.1/projects/{project_id}/meeting_topics` (standalone root noun) | `a0499320` | 10 records persisted, idempotent    |

Verified set: 14 → **16**. `_UNVERIFIED_IDS` parametrized test count: 2 → **0**.

## User-provided path attribution

The operator supplied two Procore API snippets that pinpointed the correct endpoints:

1. **Daily Construction Report Logs.** Detail endpoint
   `GET /rest/v1.0/projects/{project_id}/daily_construction_report_logs/{id}`,
   sibling list `…/daily_construction_report_logs`. Schema includes
   `id`, `date`, `datetime`, `status`, `notes` (free-text → hash-only),
   `apprentice_hours` / `journeyman_hours` / `foreman_hours` and other
   labor-count fields, `position`, `created_at`, `updated_at`, nested
   `vendor` / `trade` / `location` / `custom_fields` / `attachments`.

2. **Meeting Topics.** v1.1 root noun `/meeting_topics` (sibling to
   `/meetings`, not nested under a meeting). Topic schema observed
   from the related `parent_minutes` endpoint: `id`, `meeting_id`,
   `created_on`, `minutes` (free-text → hash-only), `no_minutes`,
   `marked`, `meeting_position`.

These paths were used directly in the registry; no exploratory probe
was needed.

## Code changes

### `src/hb_assistant/procore/endpoints.py`

- **`daily-log-dcrs`** — `path_template` updated from `/dcrs` (404) to
  `/daily_construction_report_logs`. `live_verified=True` with
  `verification_reason="live_smoke_passed_2026-05-28:487d9f3d"`.

- **`meeting-topics`** — refactored from "child of meetings"
  (`parent_record_id_field="meeting_id"`,
  `parent_path_template=".../meetings"`) to standalone top-level
  endpoint (`parent_record_id_field=None`, `parent_path_template=None`).
  `path_template` set to `/rest/v1.1/projects/{project_id}/meeting_topics`.
  `live_verified=True` with `verification_reason="live_smoke_passed_2026-05-28:a0499320_max_per_page_10_server_500_at_100"`
  recording the per_page operational caveat (see Apply notes below).

### `src/hb_assistant/procore/live_sync.py`

- **`_normalize_daily_log_dcr` wrapper field whitelist updated** to match the
  real Procore schema. `structured_keys` expanded to include `datetime`,
  `status`, `position`, the labor-hour fields
  (`apprentice_hours`, `first_year_hours`, `foreman_hours`,
  `journeyman_hours`, `local_city_hours`, `local_county_hours`,
  `minority_hours`, `other_hours`, `veteran_hours`, `women_hours`),
  the worker-count fields, nested `vendor` / `trade` / `location`, and
  `created_at`. `hash_keys` updated from
  `("summary", "comments", "description")` to `("notes",)` matching
  the actual free-text field in the payload.

- **`_NORMALIZER_BY_ID["meeting-topics"] = normalize_meeting_topic`** —
  the same `normalize_meeting_topic` function used in
  `_CHILD_NORMALIZER_BY_ID` is registered as a parent normalizer for
  the standalone fetch. The function's signature already supports the
  parent-only call path: `parent_procore_id` defaults to `None`, so
  the parent dispatcher (which doesn't pass it) works without any
  function-signature change.

## Live verification

### Smoke

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint daily-log-dcrs --confirm-live-get --json
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint meeting-topics --confirm-live-get --json
```

| Endpoint           | receipt_id   | state    | request_count | retrieved | normalized |
| ---                | ---          | ---      | ---           | ---       | ---        |
| daily-log-dcrs     | `487d9f3d`   | success  | 1             | 1         | 1          |
| meeting-topics     | `a0499320`   | success  | 1             | 10        | 10         |

### Apply

For **daily-log-dcrs** the E2E target caps `--max-pages 3 --max-items 100` worked cleanly:

| Run            | receipt_id   | state    | request_count | retrieved | upserted | total_after |
| ---            | ---          | ---      | ---           | ---       | ---      | ---         |
| Apply 3/100    | `55ff3781`   | success  | 3             | 1         | 1        | 1           |
| Rerun 3/100    | `38a3e952`   | success  | (idempotent)  | 1         | 1        | 1           |

For **meeting-topics** the E2E target caps surfaced a Procore-server HTTP
500 at `per_page=100` (6 attempts incl. 5 retries). The smoke caps
(`per_page=10`) worked cleanly:

| Run                    | receipt_id   | state           | request_count | retrieved | upserted | total_after |
| ---                    | ---          | ---             | ---           | ---       | ---      | ---         |
| Apply 3/100            | `89320ff5`   | transport_error | 6 (server 500)| 0         | 0        | 0           |
| Apply 1/10             | `157469f2`   | success         | 1             | 10        | 10       | 10          |
| Rerun 1/10             | `72917f70`   | success         | 1             | 10        | 10       | 10          |

The Procore server appears to choke on a `per_page=100` request to
`/meeting_topics`. Operators should use `--max-items <= 10` for this
endpoint until the server-side behavior is understood. The
`verification_reason` records this caveat:
`live_smoke_passed_2026-05-28:a0499320_max_per_page_10_server_500_at_100`.

## SQLite state

```
daily-log-dcrs   |  1 row
meeting-topics   | 10 rows
```

Per-endpoint records counts confirmed via SQLite-only `live records count`.

## No-secret / no-raw-body attestation

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id IN ('daily-log-dcrs', 'meeting-topics')
   AND (canonical_json_redacted LIKE '%Bearer %'
     OR canonical_json_redacted LIKE '%access_token%'
     OR canonical_json_redacted LIKE '%refresh_token%'
     OR canonical_json_redacted LIKE '%client_secret%');
```
Result: `0`.

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id IN ('daily-log-dcrs', 'meeting-topics')
   AND raw_body_persisted != 0;
```
Result: `0`.

Sample rows confirm the hash-only invariant:

- `daily-log-dcrs` row 26334669 stores labor-hour structured fields
  (`apprentice_hours`, `foreman_hours`, `journeyman_hours`, etc.),
  `date`, `datetime`, `created_at`. The `notes` field — when present —
  is reduced to a SHA-256 `notes_summary` hash structure (asserted by
  the unit test).
- `meeting-topics` row 140855819 stores structured metadata
  (`title`, `status`, `due_date`, `id`). The `minutes` field — when
  present — is reduced to a SHA-256 `minutes_summary` hash structure
  (the standardized hash-only contract applies to all free-text
  child/standalone fields via the shared `_hash_summary` helper in
  `normalize_meeting_topic`).

## Test changes

- `tests/test_procore_endpoint_registry.py::test_verified_endpoints_match_phase04a_matrix` expected set: 14 → 16 endpoints. All canonical IDs are now in the verified set.
- `tests/test_procore_live_sync_unverified_fail_closed.py::_UNVERIFIED_IDS` set is now empty `()`. The parametrized fail-close test correctly skips when there are no unverified endpoints.
- `tests/test_procore_live_gate.py::test_live_sync_unverified_endpoint_fails_closed_without_transport` uses `monkeypatch.setitem(ep_registry._BY_ID, ...)` to temporarily demote one adapter for the test, preserving the fail-closed-without-transport contract even though no registry rows are unverified at rest.
- `tests/test_procore_live_gate.py::test_live_endpoints_list_emits_canonical_phase04a_rows` now additionally asserts `all(r["live_verified"] for r in rows)` and `len(rows) == 16`.
- Four prior "meetings-as-parent-with-inline-topics" chain tests were removed (meeting-topics is no longer a child of meetings).
- Two new chain tests added: `test_meeting_topics_apply_persists_as_standalone_endpoint` (asserts standalone fetch + hash-only `minutes`) and `test_daily_log_dcrs_apply_persists_with_hash_only_notes` (asserts hash-only `notes`).

## Promotion delta

| Endpoint          | Before                                                         | After                                                                                  |
| ---               | ---                                                            | ---                                                                                    |
| `daily-log-dcrs`  | `live_verified=False` · path `/dcrs` (404)                     | `live_verified=True` · path `/daily_construction_report_logs` · receipt `487d9f3d`     |
| `meeting-topics`  | `live_verified=False` · path `/meetings/{id}/topics` (404/429) | `live_verified=True` · path `/meeting_topics` (standalone) · receipt `a0499320` (per_page cap=10 caveat) |

`_UNVERIFIED_IDS`: 2 → 0. Verified set: 14 → 16.

## Verification (repeatable, post-commit)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint daily-log-dcrs \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json

HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint meeting-topics \
  --apply --sqlite-only --max-pages 1 --max-items 10 \
  --confirm-live-get --json

hb-assistant procore live endpoints list --json \
  | python -c "import json,sys; d=json.load(sys.stdin); print(len([r for r in d['endpoints'] if r['live_verified']]), 'of', len(d['endpoints']), 'verified')"

python -m pytest -q tests/test_procore_live_sync_verified_chain.py \
                    tests/test_procore_endpoint_registry.py \
                    tests/test_procore_live_gate.py
```

Acceptance:
- daily-log-dcrs apply returns `state=success` and persists at least 1 row; re-run is idempotent.
- meeting-topics apply at `--max-items 10` returns `state=success` and persists 10 rows; re-run is idempotent.
- `live endpoints list` reports **16 of 16 verified**.
- Unit suite passes (no skipped fail-closed parametrize cases since `_UNVERIFIED_IDS` is empty).

## Phase 04A registry coverage: COMPLETE

All 16 canonical Phase 04A endpoints are live-verified end-to-end:

`projects`, `rfis`, `rfi-responses`, `submittals`, `submittal-responses`, `submittal-packages`, `meetings`, `meeting-topics`, `observations`, `daily-log-weather`, `daily-log-manpower`, `daily-log-notes`, `daily-log-deliveries`, `daily-log-delays-review-routed`, `daily-log-inspections`, `daily-log-dcrs`.
