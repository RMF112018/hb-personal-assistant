# Phase 04A Prompt 07 — Meeting Live Sync (probe matrix + topic N+1 dispatch)

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)
**Run mode:** Prompt 07 ran a path-probe loop against the live Procore tenant under operator authorization for aggressive multi-path investigation. No `live_apply` runs landed records because every probed path either returned HTTP 404 or returned a payload schema incompatible with the existing v1.0-tuned `normalize_meeting`. The Phase 04A orchestrator dispatch for `meetings → meeting-topics` N+1 child fetches landed and is fully exercised by unit tests against fake transport.
**Operator gates active:** `HB_PROCORE_LIVE=1`, `--confirm-live-get`
**Caps:** smoke caps (single page) for each probe attempt.

This file documents the meetings family contract-drift investigation
prompted by the Prompt 03 evidence note ("the Procore REST surface for
meetings differs (likely `/rest/v1.1/...` or a different scoping
convention)") and authorized by the operator for Prompt 07.

## Outcome summary

| Endpoint        | Probe outcome                                                    | Promotion       |
| ---             | ---                                                              | ---             |
| `meetings`      | v1.1 path resolves with 10 records; v1.0-schema normalizer mismatch | NOT promoted; `live_verified=False` with new reason recording the v1.1 discovery |
| `meeting-topics`| Not exercised (parent never normalized → no N+1 fetch fires)        | Unchanged; `live_verified=False`              |

Per the integrated E2E acceptance overlay, Prompt 07 satisfies "the
endpoint fails closed with a structured receipt explaining the blocker":
the meetings family receipt now records *which path resolves and why
normalization blocks promotion*, which is materially better evidence
than the prior `live_smoke_failed:http_404_at_/rest/v1.0/...` reason.

## Probe matrix (key Prompt 07 artifact)

Each probe is a `procore live smoke` against `tropical` after editing
the `meetings` adapter's `path_template` and `live_verified=True` (so the
orchestrator dispatches the call). Receipts captured at
`/tmp/hb-prompt07-receipts/`.

| # | Candidate path                                                                       | HTTP   | retrieved | normalized | receipt_id                                | Notes                                          |
| - | ---                                                                                  | ---    | ---       | ---        | ---                                       | ---                                            |
| 1 | `/rest/v1.0/projects/{project_id}/meetings`                                          | 404    | 0         | 0          | (Prompt 03 evidence)                      | original adapter path; documented contract drift |
| 2 | `/rest/v1.1/projects/{project_id}/meetings`                                          | **200**| **10**    | **0**      | `16ff0fa3-8251-4473-9278-c491a228438e`    | **path exists**; every record raised `normalize_error: ValueError` (v1.0-shaped normalizer cannot resolve `raw['id']`) |
| 3 | `/rest/v2.0/companies/5280/projects/{project_id}/meetings`                           | 200    | 1         | 0          | `b7e78530-a4b9-47e3-a549-f0999b551896`    | v2.0 company-scoped surface returns one record; same v1.0-normalizer mismatch |
| 4 | `/rest/v1.0/companies/5280/meetings`                                                 | 404    | 0         | 0          | `56e2ede5-3d5d-4438-bffb-6879dab14a0c`    | not a valid Procore surface                    |
| 5 | `/rest/v1.0/projects/{project_id}/project_meetings`                                  | 404    | 0         | 0          | `f71d9c77-4b90-4a18-b89f-061321255209`    | alternate noun does not resolve                |

**Adopted state:** `meetings.path_template = "/rest/v1.1/projects/{project_id}/meetings"` with `live_verified=False` and `verification_reason="phase_04a_prompt_07:v1.1_path_resolves_10_records_but_normalize_meeting_v1.0_schema_mismatch_pending_normalizer_update"`. The path is preserved at the discovered working v1.1 endpoint so a future prompt that updates `normalize_meeting` for v1.1 payload shape can promote without re-probing.

## Orchestrator N+1 dispatch (landed)

Prompt 07 extends `run_live_sync` with a third per-endpoint dispatch
branch (alongside the existing rfis and submittals branches), mirroring
the canonical N+1 pattern:

- Inside the parent loop, after each meeting upsert, the orchestrator
  paginates `f"/rest/v1.0/projects/{procore_project_id}/meetings/{record_id}/topics"`
  (child path stays at v1.0 matching the registered child adapter), caps
  internally at `max_pages=1, max_items=50` per parent, normalizes each
  topic via `normalize_meeting_topic` (signature carries the
  `parent_meeting_id` kwarg), and upserts with
  `endpoint_id="meeting-topics"`, `parent_procore_id=<meeting_id>`,
  `review_required=True` (topics always carry review per the prompt-04
  stop condition).
- Child fetch errors increment `child_errors_count` on the receipt
  without aborting the run.

Unit coverage in `tests/test_procore_live_sync_verified_chain.py`:
- `test_meetings_apply_persists_parents_and_topics_separately`
- `test_meetings_apply_is_idempotent_for_parents_and_topics`
- `test_meetings_apply_tolerates_child_404_without_aborting`
- `test_meeting_topic_canonical_json_carries_no_description_body_literal`

Each test uses the `_meetings_promoted` pytest fixture which temporarily
promotes the adapter to `live_verified=True` so the chain is exercised
against `_PathAwareFakeTransport`. The registry state itself remains
`live_verified=False`.

## Why no `live_apply` runs landed

The orchestrator's `_NORMALIZER_BY_ID["meetings"] = normalize_meeting`
contract is unchanged for Prompt 07 (explicitly out of scope per plan:
"Changes to normalize_meeting / normalize_meeting_topic — the
normalizers are the contract"). With the v1.1 payload shape, every
record raised `ValueError` at `normalize_meeting(raw, ...)` because the
v1.0-shaped extractor expects `raw["id"]` and the v1.1 payload
apparently uses a different key. Without successful normalization, no
parent row enters the upsert path and the N+1 topic fetch is never
issued.

The structured `partial_success` receipt with N `normalize_error:
ValueError` entries (one per retrieved record) is the canonical
fail-closed shape per the E2E overlay's option 2.

## Stop conditions honored

- No live request fired outside `HB_PROCORE_LIVE=1` + `--confirm-live-get`.
- Every probe call used `GET`; no non-GET methods were attempted.
- No secret / token surfaced in evidence, logs, or SQLite.
- No raw body persisted (zero parent rows reached the upsert path).
- Tropical project mapping resolved to `2525840` consistently.
- The single retrieved record from the v2.0 probe was discarded at the
  normalizer (not adopted as a working path) because the schema cannot
  be reconciled without a normalizer change.

## SQLite state

No new `procore_live_records` rows or `procore_live_sync_runs` rows
landed for the meetings family from Prompt 07 — the probe smokes do not
write (smoke never writes by design). The contract-drift backlog from
Prompt 05 (submittal-responses, submittal-packages) is unchanged.

## Promotion delta

- `meetings`: `live_verified=False` (unchanged from Prompt 03
  disposition). `path_template` updated `…v1.0… → …v1.1…` (Prompt 07
  discovery). `verification_reason` updated to
  `phase_04a_prompt_07:v1.1_path_resolves_10_records_but_normalize_meeting_v1.0_schema_mismatch_pending_normalizer_update`.
- `meeting-topics`: unchanged.
- `_UNVERIFIED_IDS` parametrized test in
  `tests/test_procore_live_sync_unverified_fail_closed.py` extended to
  include `"meetings"` (closes the latent inconsistency that meetings
  was demoted in Prompt 03 but never added to the unverified test set).

## Verification (repeatable, post-commit)

```bash
# Re-confirm the v1.1 path is reachable and the schema mismatch persists:
# (Note: live_verified=False, so this returns a not_live_verified receipt
#  WITHOUT calling the API. To re-run the probe, provisionally flip
#  live_verified=True in endpoints.py and re-run smoke.)
hb-assistant procore live endpoints list --json \
  | python -c "import json,sys; print([r for r in json.load(sys.stdin)['endpoints'] if r['endpoint_id']=='meetings'][0])"

# Unit chain test for the N+1 dispatch (lands regardless of live state):
python -m pytest -q tests/test_procore_live_sync_verified_chain.py -k meetings
```

Acceptance:
- `procore live endpoints list` shows meetings carrying the new v1.1
  `path_template` and the schema-mismatch `verification_reason`.
- All four meeting verified-chain unit tests pass against
  `_PathAwareFakeTransport`.
- The verified set count remains five (`projects`, `rfis`, `submittals`,
  `daily-log-weather`, `observations`) — meetings did not promote.

## Contract-drift backlog (updated)

| Endpoint              | Status                                                                                  |
| ---                   | ---                                                                                     |
| `meetings`            | Path corrected to v1.1; **payload schema update required in `normalize_meeting`** for promotion. |
| `meeting-topics`      | Awaiting `meetings` promotion to populate via parent N+1.                                |
| `submittal-responses` | HTTP 404 at v1.0 child path (Prompt 05 backlog).                                         |
| `submittal-packages`  | HTTP 404 at v1.0 sibling path (Prompt 05 backlog).                                       |
