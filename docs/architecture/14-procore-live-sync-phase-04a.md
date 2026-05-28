# 14 — Procore live sync (Phase 04A Prompt 03B)

Per-endpoint live sync command path for the 14 canonical Phase 04A endpoint
IDs. Composes the existing live-readiness gate, GET-only HTTP client, OAuth
access-token provider, paginator, and per-endpoint normalizers into a single
end-to-end chain that lands in local SQLite only.

## One-command operator surface

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint <endpoint-id> \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

Plus `procore live smoke ...` (read-only, no SQLite write) and `procore live
records count --project --endpoint --json` for verification.

## Layered components

| Layer | Module | Responsibility |
| --- | --- | --- |
| CLI | `src/hb_assistant/cli/procore.py` (`live_sync`, `live_smoke`, `live_records_count`, `live_endpoints_list`) | Argument surface; delegates to orchestrator. Adds canonical 14-row `endpoints list`. |
| Orchestrator | `src/hb_assistant/procore/live_sync.py::run_live_sync` | Gate → adapter → verified-or-fail-closed → token → paginate → normalize → upsert → watermark → receipt. |
| Endpoint registry | `src/hb_assistant/procore/endpoints.py` | 14 `EndpointAdapter` rows. `live_verified` flag; legacy `list-*` aliases. |
| Live gate | `src/hb_assistant/procore/live_gate.py` (unchanged) | `HB_PROCORE_LIVE=1` exact-match; `assert_live_mapping_strict`. |
| HTTP client | `src/hb_assistant/procore/http_client.py` (unchanged) | GET-only; `Authorization: Bearer <access_token>`; token never stored on the instance. |
| Token provider | `src/hb_assistant/procore/token_provider.py` (unchanged) | `default_procore_token_provider()` chain: env/keychain → refreshing OAuth → missing (fail-closed). |
| Paginator | `src/hb_assistant/procore/pagination.py` (unchanged) | `per_page`, `max_pages`, `max_items`, 429 backoff. |
| Normalizers | `src/hb_assistant/procore/normalizers/*` (unchanged); plus inline `_normalize_project` and `_normalize_daily_log_weather` in the orchestrator | Pure dict-in/dict-out; no body persisted. |
| Redaction | `src/hb_assistant/procore/redaction.py` (added `redact_source_url`) | Path-only source URL; token-shape masking. |
| SQLite layer | `src/hb_assistant/store/procore_repositories.py` (new) + V6 migration in `migrator.py` | `procore_live_sync_runs`, `procore_live_records`, `procore_live_sync_watermarks` with CHECK constraints on `raw_body_persisted=0` and `redaction_applied=1`. |

## Inline N+1 child fetch (rfis -> rfi-responses)

Procore's RFI list endpoint does not return replies inline, so the
orchestrator special-cases `rfis`: after each parent RFI is upserted, it
issues one additional GET to `/rest/v1.0/projects/{project_id}/rfis/{rfi_id}/replies`,
normalizes each reply via `normalize_rfi_reply`, and upserts as
`endpoint_id="rfi-responses"` with `parent_procore_id=<rfi_id>` set. The
child fetch is capped internally at `max_pages=1, max_items=50` per parent
and shares the same GET-only / bearer-token / redaction guarantees as the
parent path. A 4xx on one child fetch increments `child_errors_count` in
the receipt and continues to the next parent — the run is not aborted.

This pattern is the template for other parent/child families once their
adapters land. The registry's `rfi-responses` row stays `live_verified=False`
because there is no usable direct-call surface (no `--parent-id` flag);
child rows are populated only as a byproduct of the parent fetch.

## Inline N+1 child fetch (submittals -> submittal-responses) — Prompt 05

The submittal family mirrors the RFI shape. `run_live_sync` dispatches on
`adapter.endpoint_id == "submittals"`, fetching one additional GET per
parent at `/rest/v1.0/projects/{project_id}/submittals/{submittal_id}/responses`,
normalizing via `normalize_submittal_response`, and upserting as
`endpoint_id="submittal-responses"` with `parent_procore_id` set. The
sibling endpoint `submittal-packages` is wired as a standalone top-level
sync (no parent path) via `_normalize_submittal_package_top_level`
registered in `_NORMALIZER_BY_ID`. Dispatch is hard-coded per-endpoint
(`if rfis ... elif submittals ...`) — a generic adapter-driven dispatch
keyed on `parent_record_id_field` is a deferred refactor candidate.

**Contract drift observed against `tropical` (deferred).** Both
`/rest/v1.0/projects/{project_id}/submittals/{submittal_id}/responses`
and `/rest/v1.0/projects/{project_id}/submittals/packages` return HTTP 404.
Parent `submittals` returns data normally. Per-fetch fail-closed
behavior verified end-to-end: each child 404 surfaces a structured
`child_transport_error` receipt entry and the run continues to the next
parent. Both endpoints stay `live_verified=False` in the registry with
HTTP-404 verification reasons; the verified set after Prompt 05 still
contains the four parents from Prompt 03 (`projects`, `rfis`, `submittals`,
`daily-log-weather`). Path remediation is deferred to a future prompt
that consults current Procore REST docs.

Evidence: `docs/evidence/construction-intelligence-phase-04a/05-submittal-live-sync.md`.

## Observations parent-only verified endpoint — Prompt 06

`observations` (`/rest/v1.0/projects/{project_id}/observations/items`) is
promoted to `live_verified=True` after a successful live smoke and three
applies against `tropical`. It has no N+1 child fetch: the orchestrator
treats it as a single-page parent endpoint identical to `projects` and
`daily-log-weather`. Review routing is heuristic — `normalize_observation`
runs `_safety_route_decision()` across status / type / subtype / title /
description and emits `review_required` + `safety_route` + a structured
`routing_reason` (`"type_contains:near-miss"`, `"body_contains:injury"`,
`"assignee_missing"`, `"default_low_risk"`). The registry's
`review_required_default=True` on this row is family metadata for
documentation and downstream routing; the orchestrator does not enforce
it at the row level — the normalizer's heuristic is the source of truth.

Evidence: `docs/evidence/construction-intelligence-phase-04a/06-observation-live-sync.md`.

## Verified vs unverified endpoints

5 of 14 endpoint IDs are `live_verified=True` and execute the full chain:
`projects`, `rfis`, `submittals`, `meetings`, `daily-log-weather`. The other
9 are command-visible (`endpoints list`) and command-accepted, but the
orchestrator returns a structured `state="not_live_verified"` receipt with
`no_live_call_performed=true` and zero counts; no API call and no DB write
occur. Promotion is a one-line flag flip in `endpoints.py` after a future
docs/live smoke proof.

## Receipt shape

See `docs/evidence/construction-intelligence-phase-04a/01-live-transport-token-proof.md`
for the canonical receipt body and the proof that `Authorization` carries
the OAuth access token only — never `PROCORE_CLIENT_SECRET`, never a refresh
token, never an OAuth payload.

## Stop conditions enforced

- `procore live sync --apply` is rejected unless `--sqlite-only` is also set.
- All live transports require `HB_PROCORE_LIVE=1` + `--confirm-live-get`.
- `ProcoreHTTPClient._require_get` rejects any non-GET attempt.
- Schema-level CHECK constraints reject any sync-run or record row claiming
  `raw_body_persisted=1` or `redaction_applied=0`.
- Repository functions accept only normalized dicts; raw Procore response
  bodies cannot flow into the SQLite tables.

## Tests

| File | Coverage |
| --- | --- |
| `tests/test_procore_endpoint_registry.py` | Registry shape, alias resolution, verified-vs-unverified flagging. |
| `tests/test_procore_repositories_v6.py` | V6 migration idempotency, insert/update semantics, CHECK constraint enforcement. |
| `tests/test_procore_live_sync_unverified_fail_closed.py` | 9 unverified IDs each return `not_live_verified` with no transport call and no DB write. |
| `tests/test_procore_live_sync_verified_chain.py` | RFI + submittal fake-transport end-to-end: GET-only, bearer-token header, idempotent upsert, no raw body persisted, review_required flag set on sensitive parents, child fetches tolerate 404 without aborting. |
| `tests/test_procore_live_gate.py` | Updated to assert the new canonical endpoint matrix surface. |
