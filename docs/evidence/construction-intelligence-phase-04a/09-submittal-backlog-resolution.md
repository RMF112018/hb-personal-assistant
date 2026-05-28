# Phase 04A Backlog Resolution — Submittal-Responses / Submittal-Packages 404 Fix

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)
**Run mode:** Probe loop through the standard `live smoke` / `live sync` gate. Where smoke succeeded, full live apply at the E2E target caps `--max-pages 3 --max-items 100` + idempotent re-run.
**Operator gates active:** `HB_PROCORE_LIVE=1`, `--confirm-live-get`

This file resolves the Prompt 05 backlog for the two submittal child / sibling endpoints that returned HTTP 404 against `tropical`:

- `submittal-responses` — the per-submittal N+1 child endpoint
- `submittal-packages` — the top-level sibling endpoint

Operator-authorized aggressive multi-path probing was used (matches the Prompt 07 meetings precedent). One endpoint resolved on the first candidate; the other failed across four candidate paths and stays deferred with a refined `verification_reason` recording the full probe matrix.

## Outcome summary

| Endpoint              | Outcome             | Adopted path                                                            | Verified after | Notes                                                       |
| ---                   | ---                 | ---                                                                     | ---            | ---                                                         |
| `submittal-packages`  | **PROMOTED**        | `/rest/v1.0/projects/{project_id}/submittal_packages`                   | Yes (live_verified=True) | First-try success on the underscored-noun convention. 0 records in tropical at probe time. |
| `submittal-responses` | Deferred (backlog)  | (reverted to original `/rest/v1.0/projects/{project_id}/submittals/{submittal_id}/responses`) | No (live_verified=False) | All four candidate paths returned HTTP 404. Probe matrix preserved in verification_reason. |

Per the integrated E2E acceptance overlay:
- `submittal-packages` satisfies option 1 (live GET + normalization + SQLite upsert + records count works end-to-end; chain proven against an empty result set).
- `submittal-responses` satisfies option 2 (structured fail-closed receipt; backlog reason captures all attempts).

## Probe matrix — `submittal-packages`

| # | Candidate path                                                                  | HTTP | Retrieved | receipt_id   | Outcome           |
| - | ---                                                                             | ---  | ---       | ---          | ---               |
| 1 | `/rest/v1.0/projects/{project_id}/submittal_packages`                           | **200** | **0**  | `7b9077ee-…` | **ADOPTED**       |

Stop-on-first-success; remaining candidates (v1.1 underscored, v2.0 company-scoped) were not attempted.

## Probe matrix — `submittal-responses`

| # | Candidate child path                                                                            | HTTP | Per-submittal `child_errors_count` | receipt_id   | Outcome   |
| - | ---                                                                                             | ---  | ---                                | ---          | ---       |
| 1 | `/rest/v1.0/projects/{project_id}/submittals/{submittal_id}/approvers`                          | 404  | 5 / 5                              | `5e8ae63b-…` | failed    |
| 2 | `/rest/v1.0/projects/{project_id}/submittals/{submittal_id}/reviews`                            | 404  | 5 / 5                              | (apply rcpt) | failed    |
| 3 | `/rest/v1.1/projects/{project_id}/submittals/{submittal_id}/approvers`                          | 404  | 5 / 5                              | (apply rcpt) | failed    |
| 4 | `/rest/v1.1/projects/{project_id}/submittals/{submittal_id}/responses`                          | 404  | 5 / 5                              | (apply rcpt) | failed    |

For each candidate, the orchestrator's hard-coded N+1 child URL in `live_sync.py` was updated and a parent `submittals` apply was run at `--max-pages 1 --max-items 5`. Every probe surfaced `child_transport_error: http_error / status: 404` for all five parent submittals. The path is reverted to the documented v1.0 string and `live_verified=False` is preserved; the N+1 dispatch code stays in `live_sync.py` (already unit-tested) for future activation once the correct Procore child surface is identified.

The adapter's `verification_reason` is updated to:

```
phase_04a_backlog_2026-05-28:probed_v1.0_responses_v1.0_approvers_v1.0_reviews_v1.1_approvers_v1.1_responses_all_404
```

## Live applies — `submittal-packages` (caps 1/5 → 3/100 → 3/100 re-run)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint submittal-packages \
  --apply --sqlite-only \
  --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

| Run                       | receipt_id                                | state    | retrieved | upserted | total_after |
| ---                       | ---                                       | ---      | ---       | ---      | ---         |
| Smoke                     | `7b9077ee-cd36-427c-b65a-4eef02978ab5`    | success  | 0         | 0 (smoke writes none) | 0 |
| Apply caps 1/5            | `27f41bd3-8693-4b60-ae3b-6b4b2cdd58e7`    | success  | 0         | 0        | 0           |
| Apply caps 3/100          | `962d980e-4b7a-4c30-af58-468d716bbf07`    | success  | 0         | 0        | 0           |
| Idempotency re-run 3/100  | `e4fcf076-bde6-4382-b710-810383124152`    | success  | 0         | 0        | 0           |

The `tropical` project carries no submittal packages at probe time, so `retrieved_count=0` throughout. The chain — gate → transport → paginate → normalize → upsert → records count — is exercised end-to-end against an empty result set; idempotency is trivial.

## SQLite state

```bash
hb-assistant procore live records count --project tropical --endpoint submittals --json          # 100
hb-assistant procore live records count --project tropical --endpoint submittal-packages --json  # 0
hb-assistant procore live records count --project tropical --endpoint submittal-responses --json # 0
```

Sync-run audit trail (this prompt only):

```
submittals               | live_apply | partial | partial_success | 5  | 2026-05-28T20:57:29  (probe #1: approvers v1.0)
submittals               | live_apply | partial | partial_success | 5  | 2026-05-28T20:57:49  (probe #2: reviews v1.0)
submittals               | live_apply | partial | partial_success | 5  | 2026-05-28T20:58:03  (probe #3: approvers v1.1)
submittals               | live_apply | partial | partial_success | 5  | 2026-05-28T20:58:16  (probe #4: responses v1.1)
submittal-packages       | live_apply | success | success         | 0  | 2026-05-28T20:59:18
submittal-packages       | live_apply | success | success         | 0  | 2026-05-28T20:59:19
submittal-packages       | live_apply | success | success         | 0  | 2026-05-28T20:59:20
```

Each of the four submittals applies (`partial_success`) corresponds to a submittal-responses probe attempt — five parent submittals fetched, every per-submittal child fetch returning HTTP 404. No child rows persisted from any probe attempt.

## No-secret / no-raw-body attestation

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id LIKE 'submittal%'
   AND (canonical_json_redacted LIKE '%Bearer %'
     OR canonical_json_redacted LIKE '%access_token%'
     OR canonical_json_redacted LIKE '%refresh_token%'
     OR canonical_json_redacted LIKE '%client_secret%');
```
Result: `0`.

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id LIKE 'submittal%' AND raw_body_persisted != 0;
```
Result: `0`.

No row across the submittal family contains a token, header, secret, or raw response body. The schema-level CHECK constraint enforces `raw_body_persisted=0` on every persisted row.

## Promotion delta

- `submittal-packages` → **`live_verified=True`**, path updated to `/rest/v1.0/projects/{project_id}/submittal_packages`, `verification_reason="live_smoke_passed_2026-05-28:7b9077ee"`.
- `submittal-responses` → remains `live_verified=False`. Path reverted to the documented v1.0 string. `verification_reason` updated to record the four-candidate probe matrix.
- `_UNVERIFIED_IDS` parametrized fail-closed test count: 6 → 5 (removed `"submittal-packages"`).
- Verified-set test: 10 → 11 endpoints.

## Verification (repeatable, post-commit)

```bash
# Confirm submittal-packages still works end-to-end:
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint submittal-packages \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json

# Confirm submittal-responses continues to fail-closed:
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint submittal-responses \
  --apply --sqlite-only --max-pages 1 --max-items 1 \
  --confirm-live-get --json | python -c "import json,sys; d=json.load(sys.stdin); print('responses:', d.get('state'), d.get('reason_codes'))"

# Confirm the N+1 child dispatch tests still pass:
python -m pytest -q tests/test_procore_live_sync_verified_chain.py -k submittal
```

Acceptance:
- submittal-packages apply returns `state=success`.
- submittal-responses returns `state=not_live_verified` with reason codes including `endpoint_unverified_for_live`.
- All existing submittal verified-chain unit tests pass against `_PathAwareFakeTransport`.

## Updated backlog table

| Endpoint              | Status                                                                                  |
| ---                   | ---                                                                                     |
| `meetings`            | v1.1 path resolves; v1.0 normalizer schema mismatch (Prompt 07 backlog).                |
| `meeting-topics`      | Awaiting `meetings` promotion to populate via parent N+1 (Prompt 07 backlog).            |
| `submittal-responses` | All four child candidate paths returned HTTP 404 (this prompt); refined verification_reason recorded. |
| `submittal-packages`  | RESOLVED at `/submittal_packages` (this prompt).                                         |
| `daily-log-dcrs`      | HTTP 404 at `/rest/v1.0/projects/{project_id}/dcrs` (Prompt 08 backlog).                 |
