# Phase 04A Backlog Resolution — Meetings v1.1 Normalizer + Promotion

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)
**Run mode:** Discovery probe + normalizer + orchestrator update + live smoke / apply.
**Operator gates active:** `HB_PROCORE_LIVE=1`, `--confirm-live-get`, `--apply --sqlite-only`
**Caps:** apply at `--max-pages 3 --max-items 100` (E2E target) with same-caps re-run for idempotency.

This file resolves the Prompt 07 backlog for the meetings family. Prompt 07 discovered that `/rest/v1.1/projects/{project_id}/meetings` resolves with 10 records but every record raised `ValueError` at `normalize_meeting` because the v1.0-tuned normalizer expected `raw["id"]`. The Prompt 07 evidence file flagged this as "v1.1 path resolves but normalize_meeting v1.0 schema mismatch pending normalizer update".

This backlog resolution:
1. Probed the v1.1 payload shape with a controlled one-off script (only field NAMES recorded — no values).
2. Found that v1.1 returns **grouped** meetings: `[{"group_title": ..., "meetings": [...]}, ...]`. The records inside each group DO carry `id`; the prior ValueError was the orchestrator passing the top-level group dict (which has no `id`) directly to `normalize_meeting`.
3. Added an inline orchestrator flatten step that unwraps the `meetings` arrays from each group before normalization, honoring the operator's `--max-items` cap at the meeting-row level (not the group level). v1.0 (flat list) passes through unchanged.
4. Extended `_MEETING_CANONICAL_FIELD_KEYS` to include v1.1 field names (`starts_at`, `ends_at`, `created_by_id`, `meeting_topics_count`) alongside the existing v1.0 keys (`start_time`, `end_time`, `organizer_id`).
5. Re-ran live smoke + applies. Meetings now promotes with 96 live records persisted; idempotent re-run at the same caps confirms.

`meeting-topics` was also probed (both v1.0 and v1.1 child paths) and stays deferred — the v1.0 path returned 404 on every parent and v1.1 returned a mix of 404 + HTTP 429 (rate-limit), so per the stop conditions the probe was aborted and the endpoint stays unverified with a refined backlog reason.

## Outcome summary

| Endpoint        | Outcome              | Adopted path                                          | Verified after |
| ---             | ---                  | ---                                                   | ---            |
| `meetings`      | **PROMOTED**         | `/rest/v1.1/projects/{project_id}/meetings` (grouped → flattened) | Yes |
| `meeting-topics`| Deferred (backlog)   | v1.0 child path retained (v1.1 also returned 404/429) | No  |

Verified set: 11 → 12.

## Discovery probe (redacted output)

A one-off script at `/tmp/hb-prompt07-meetings-probe.py` (deleted after this evidence captured its output) used `ProcoreHTTPClient` + `default_procore_token_provider` to GET the v1.1 path through the same authenticated gate as `procore live smoke`. The script printed only field NAMES — no values:

```
Path: /rest/v1.1/projects/2525840/meetings
Items retrieved (sample): 2

--- first record top-level keys ---
['group_title', 'meetings']

--- first record key shape ---
{
  'group_title': 'str',
  'meetings': [
    {
      'id': '...', 'created_at': '...', 'created_by_id': '...',
      'description': '...', 'distributed_at': '...', 'distributed_by': '...',
      'ends_at': '...', 'is_private': '...', 'last_distributed_event': '...',
      'location': '...', 'meeting_template_id': '...', 'meeting_topics_count': '...',
      'mode': '...', 'occurred': '...', 'parent_id': '...', 'position': '...',
      'starts_at': '...', 'title': '...', 'updated_at': '...'
    },
    '... +30 more'
  ]
}
```

Each top-level "record" is a group containing 31+ meetings. The records inside the `meetings` array carry the expected `id` primary key, but the field names diverge from v1.0 (`starts_at` / `ends_at` / `created_by_id` instead of `start_time` / `end_time` / `organizer_id`).

## Code changes

### `src/hb_assistant/procore/normalizers/meeting.py`

Extended `_MEETING_CANONICAL_FIELD_KEYS` to include v1.1 field names alongside the existing v1.0 keys:

```python
_MEETING_CANONICAL_FIELD_KEYS = (
    "number",
    "title",
    "status",
    "start_time",
    "end_time",
    # Procore v1.1 field names (carried alongside v1.0 keys above so the
    # whitelist accepts either payload shape without losing fidelity).
    "starts_at",
    "ends_at",
    "created_by_id",
    "meeting_topics_count",
    "location",
    ...
)
```

The whitelist iterates over present-in-raw fields, so a v1.0 record (no `starts_at`) loses nothing and a v1.1 record (no `start_time`) loses nothing. **Metadata-only contract preserved**: `description` (free-text in v1.1) is intentionally NOT whitelisted; raw text never persisted.

### `src/hb_assistant/procore/live_sync.py`

Added an inline orchestrator flatten step for v1.1 grouped meeting payloads:

```python
if adapter.endpoint_id == "meetings" and items:
    flattened: List[Dict[str, Any]] = []
    grouped = False
    for raw in items:
        if isinstance(raw, dict) and isinstance(raw.get("meetings"), list):
            grouped = True
            for inner in raw["meetings"]:
                if isinstance(inner, dict):
                    flattened.append(inner)
        elif isinstance(raw, dict):
            flattened.append(raw)
    if grouped:
        items = flattened[:max_items]
        retrieved_count = len(items)
```

The flatten is endpoint-id-scoped (only `meetings`), grouped-detection is duck-typed (`meetings` key with a list value), and v1.0 records pass through the `elif` fallback unchanged. Truncation honors the operator's `--max-items` cap at the meeting-row level, not at the group level.

### Backward compatibility

- The existing meeting normalizer tests (`tests/test_procore_meeting_normalizer.py`) pass unmodified — the v1.0 fixture continues to produce v1.0 canonical fields.
- The existing meeting verified-chain tests (`tests/test_procore_live_sync_verified_chain.py::test_meetings_apply_…`) pass unmodified — the v1.0 FakeTransport fixtures bypass the grouping flatten and persist as before.
- A new test `test_meetings_apply_flattens_v1_1_grouped_payload` asserts the grouped flatten produces one row per meeting (3 from 2 groups), not one per group.
- A new test `test_normalize_meeting_accepts_v1_1_shape_and_carries_v1_1_keys` asserts the normalizer correctly carries v1.1 keys and excludes `description`.

## Live verification

### Smoke

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint meetings \
  --confirm-live-get --json
```

- `receipt_id`: `452d9421-9f80-4a61-963a-4e589f213ebc`
- `state`: `success` · `status`: `success`
- `retrieved_count`: 10 · `normalized_count`: 10 (smoke `--max-items` default)
- `sqlite_upserted_count`: 0 (smoke never writes)
- `reason_codes`: `[]` · `redacted_errors`: `[]`

### Apply — caps 1/5

- `receipt_id`: `b6597066-d12c-47e4-af85-38a40974b2c6`
- `state`: `partial_success` (parent persistence clean; child topic N+1 returned 404)
- `parent_retrieved_count`: 5 · `parent_upserted_count`: 5
- `child_endpoint_id`: `meeting-topics` · `child_upserted_count`: 0 · `child_errors_count`: 5 (all topic GETs 404)
- `sqlite_total_count_after`: 5

### Apply — caps 3/100 (E2E target)

- `receipt_id`: `09b03acb-fc03-4b79-9921-a8370eb74ca9`
- `state`: `partial_success`
- `parent_upserted_count`: **96** · `child_errors_count`: 96
- `sqlite_total_count_after`: 96

The `tropical` project has 96 live meetings across the v1.1 groups. The flatten step correctly emitted 96 distinct meeting rows even though Procore returned them grouped.

### Idempotency re-run — caps 3/100

- `receipt_id`: `5706228e-ecd1-4945-a3a3-3e5a1b21ace1`
- `state`: `partial_success`
- `parent_upserted_count`: 96 (UPSERT, no new INSERT)
- `sqlite_total_count_after`: 96 (unchanged)

Idempotency confirmed. The upsert PK `(project_key, endpoint_id, parent_procore_id, procore_record_id)` correctly handles re-runs without duplication.

## Meeting-topics probe

The submittals N+1 dispatch was also exercised for meeting-topics during the parent applies. Two paths were tried:

| # | Topic child path                                                              | Outcome (5 parents)         |
| - | ---                                                                          | ---                         |
| 1 | `/rest/v1.0/projects/{id}/meetings/{meeting_id}/topics`                      | 5 × HTTP 404                |
| 2 | `/rest/v1.1/projects/{id}/meetings/{meeting_id}/topics`                      | 1 × HTTP 404 + 4 × HTTP 429 |

The v1.1 attempt triggered Procore rate-limiting (429) on four of five parents. Per the Phase 04A stop conditions, probing was aborted; the child path was reverted to v1.0 (the documented value); meeting-topics stays `live_verified=False` with `verification_reason="phase_04a_backlog_2026-05-28:probed_v1.0_topics_v1.1_topics_mixed_http_404_and_429_rate_limit"`. The orchestrator's `elif fetch_meeting_topics` dispatch is preserved (unit-tested) for future activation once a clean child surface is identified.

## SQLite readback

```bash
hb-assistant procore live records count --project tropical --endpoint meetings --json        # 96
hb-assistant procore live records count --project tropical --endpoint meeting-topics --json  # 0
```

Sample meeting row (truncated `canonical_json_redacted`):

```
12888268 | {"created_at": "2026-05-27T12:20:44Z", "created_by_id": 3584438,
            "ends_at": "2026-05-27T19:00:00Z", "location": "...",
            "meeting_topics_count": 19, "starts_at": "2026-05-27T18:00:0...
```

The persisted row carries v1.1 canonical fields (`created_by_id`, `starts_at`, `ends_at`, `meeting_topics_count`). The location field is preserved (structured metadata, not free text). `description` is NOT carried.

## No-secret / no-raw-body attestation

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id LIKE 'meeting%'
   AND (canonical_json_redacted LIKE '%Bearer %'
     OR canonical_json_redacted LIKE '%access_token%'
     OR canonical_json_redacted LIKE '%refresh_token%'
     OR canonical_json_redacted LIKE '%client_secret%');
```
Result: `0`.

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id LIKE 'meeting%' AND raw_body_persisted != 0;
```
Result: `0`.

## Promotion delta

- `meetings` → `live_verified=True`, reason `live_smoke_passed_2026-05-28:452d9421`. Path remains v1.1.
- `meeting-topics` → remains `live_verified=False`. Reason updated to capture the v1.0 + v1.1 probe matrix.
- Verified set: 11 → **12**.
- `_UNVERIFIED_IDS` parametrized fail-closed test: 5 → 4 (removed `meetings`).

## Verification (repeatable, post-commit)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint meetings \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json

hb-assistant procore live records count --project tropical --endpoint meetings --json
python -m pytest -q tests/test_procore_meeting_normalizer.py tests/test_procore_live_sync_verified_chain.py
```

Acceptance:
- meetings apply returns `state=partial_success` (parents land cleanly, topic N+1 still 404).
- records count returns 96.
- Re-running at the same caps preserves the row count.
- All meeting normalizer + chain tests pass (including the new v1.1 tests).

## Updated backlog table

| Endpoint              | Status                                                                                  |
| ---                   | ---                                                                                     |
| `meetings`            | RESOLVED — v1.1 grouped payload supported by flatten + extended normalizer (this prompt). |
| `meeting-topics`      | Deferred — v1.0 child path 404s, v1.1 returned mixed 404 + 429 rate-limit (this prompt). |
| `submittal-responses` | Deferred — all four child candidate paths returned HTTP 404 (Prompt 09 evidence).        |
| `daily-log-dcrs`      | HTTP 404 at `/rest/v1.0/projects/{project_id}/dcrs` (Prompt 08 backlog).                 |
