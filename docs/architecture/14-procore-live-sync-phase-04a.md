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

## Meetings family — Prompt 07 N+1 dispatch + path probe

`run_live_sync` now ships a third per-endpoint dispatch branch
(alongside `rfis` and `submittals`): when `adapter.endpoint_id ==
"meetings"`, after each parent upsert the orchestrator paginates
`f"/rest/v1.0/projects/{procore_project_id}/meetings/{record_id}/topics"`,
normalizes via `normalize_meeting_topic(..., parent_meeting_id=...)`,
and upserts as `endpoint_id="meeting-topics"` with
`parent_procore_id=<meeting_id>`. Topics are always
`review_required=True`. Description and action_items are reduced to
SHA-256 hash-only summaries by the normalizer — raw text never
persisted. The dispatch is fully covered by `_PathAwareFakeTransport`
tests in `tests/test_procore_live_sync_verified_chain.py`.

**Path probe outcome (Prompt 07 backlog).** Five candidate Procore
meeting paths were probed against `tropical`. The v1.0 project-scoped
path returns HTTP 404; the v1.1 project-scoped path returns 10 records
but the payload shape is incompatible with the current v1.0-tuned
`normalize_meeting` (every record raises `ValueError`). The adapter's
`path_template` is updated to v1.1 to preserve the discovery; both
`meetings` and `meeting-topics` stay `live_verified=False` pending a
follow-up prompt that updates the normalizer for v1.1 payload shape.

Evidence: `docs/evidence/construction-intelligence-phase-04a/07-meeting-live-sync.md`.

## Daily-log family expansion — Prompt 08

Prompt 08 grows the canonical registry from 14 to 16 rows by adding
`daily-log-inspections` (`/inspection_logs`) and `daily-log-dcrs`
(`/dcrs`), and promotes four previously-unverified daily-log sections
(`manpower`, `notes`, `deliveries`, `delays-review-routed`) plus
`inspections`. `dcrs` failed at HTTP 404 and stays unverified.

Per-section normalizer wrappers live inline in `live_sync.py` next to
the existing `_normalize_daily_log_weather`, all dispatched through
`_NORMALIZER_BY_ID`. The wrappers share a `_daily_log_canonical(...)`
helper that whitelists structured fields and reduces any free-text
field to a SHA-256 `*_summary` (`type`, `length`, `hash_prefix`) —
mirroring the pattern from `normalize_meeting_topic` and
`normalize_submittal_response`. Notes and delays carry
`review_required=True` (delays also `safety_route=True`); the
structured-only sections (manpower, deliveries, inspections) land with
`review_required=False`.

Evidence: `docs/evidence/construction-intelligence-phase-04a/08-selected-daily-log-live-sync.md`.

## Submittal backlog resolution

The Prompt 05 submittal-responses / submittal-packages 404 backlog was
addressed via an aggressive multi-path probe loop against `tropical`:

- **`submittal-packages`** — RESOLVED. The Procore path is
  `/rest/v1.0/projects/{project_id}/submittal_packages` (underscored
  noun, sibling to `/submittals`), not the previously-attempted
  `/submittals/packages` nested form. Adapter path updated; promoted.
- **`submittal-responses`** — DEFERRED. Four candidate child paths
  (`/v1.0/responses`, `/v1.0/approvers`, `/v1.0/reviews`,
  `/v1.1/approvers`, `/v1.1/responses`) all returned HTTP 404. The
  adapter's `path_template` was reverted to the documented v1.0 string;
  the `verification_reason` records the full probe matrix. The
  orchestrator's `elif fetch_submittal_responses` N+1 dispatch is
  preserved (unit-tested) for future activation once Procore docs
  identify the correct child surface.

Evidence: `docs/evidence/construction-intelligence-phase-04a/09-submittal-backlog-resolution.md`.

## Meetings v1.1 normalizer resolution

The Prompt 07 meetings backlog is RESOLVED. The Procore v1.1 meetings
endpoint returns a grouped payload (`[{"group_title": "...",
"meetings": [...]}, ...]`); `run_live_sync` now contains a
meetings-scoped flatten step that unwraps the `meetings` arrays before
normalization, honoring `--max-items` at the meeting-row level. v1.0
(flat list) passes through unchanged so the existing FakeTransport
unit tests continue to pass. The `normalize_meeting` field whitelist
was extended to carry v1.1 field names (`starts_at` / `ends_at` /
`created_by_id` / `meeting_topics_count`) alongside the existing v1.0
keys; the metadata-only contract is preserved (`description` is not
whitelisted, so free-text never persists).

`meeting-topics` stays deferred: both v1.0 and v1.1 child paths
returned 404 / 429 mixes against tropical during the parent apply. The
N+1 dispatch is preserved (unit-tested) for future activation.

Evidence: `docs/evidence/construction-intelligence-phase-04a/10-meetings-v1.1-normalizer-resolution.md`.

## Unverified-IDs resolution + N+1 → inline extraction pivot

The orchestrator's N+1 child GET dispatch (one HTTP call per parent
for `replies` / `responses` / `topics`) was identified as the source
of recurring Procore HTTP 429 rate-limit pressure. Procore's RFI and
submittal list endpoints already embed children inline; the
orchestrator now extracts them from the parent payload rather than
issuing per-parent GETs.

Two structural changes land together:

1. **Generic child-adapter dispatch.** The three hard-coded `if/elif`
   branches in `run_live_sync` (one each for rfis / submittals /
   meetings) are replaced by a single helper
   `_resolve_child_adapter(parent_adapter)` that scans the registry
   for an adapter in the same `family` with `parent_record_id_field`
   set. The child normalizer is resolved via a single
   `_CHILD_NORMALIZER_BY_ID` lookup.

2. **Inline child extraction.** A small map keyed on the parent
   `endpoint_id` (`rfis` → `replies`, `submittals` → `responses`,
   `meetings` → `topics`) tells the orchestrator which field to read
   on each parent record. If a list is present, each child dict is
   normalized via the child normalizer (with `parent_procore_id` set)
   and upserted under the child adapter's canonical `endpoint_id`.
   Zero additional HTTP calls are issued for children.

Behavioral consequences: a single parent apply now issues exactly one
HTTP request (the parent list call), bounded by the operator's
`--max-pages` / `--max-items` caps; the orchestrator persists both
parent and inline-embedded child rows in one pass. The verification
semantics of child endpoints stay correct: `procore live sync
--endpoint <child>` with no parent context still fail-closes because
the orchestrator's parent loop never runs.

`rfi-responses` and `submittal-responses` are promoted to
`live_verified=True` on the strength of this architecture.
`meeting-topics` stays deferred because the Procore v1.1 meetings
parent does NOT embed topics (only `meeting_topics_count`).
`daily-log-dcrs` stays deferred — it's a top-level endpoint with a
404 at `/dcrs`; inline extraction does not apply.

The three child normalizer signatures are standardized to a uniform
`parent_procore_id` kwarg (was `parent_rfi_stable_key` /
`parent_submittal_stable_key` / `parent_meeting_id`). Internal
canonical-fields data-key names are preserved for downstream
consumers.

Evidence: `docs/evidence/construction-intelligence-phase-04a/11-unverified-ids-resolution.md`.

## Final closeout — 16/16 verified

The last two deferred endpoints are now verified using exact Procore
paths supplied by the operator:

- `daily-log-dcrs` adopts `/rest/v1.0/projects/{project_id}/daily_construction_report_logs`
  as a top-level endpoint. The normalizer wrapper's
  `structured_keys` was expanded to match the real schema (labor-hour
  fields, position, nested `vendor`/`trade`/`location`); `hash_keys`
  changed to `("notes",)` matching the actual free-text field.

- `meeting-topics` is refactored from a "child of meetings" adapter to
  a standalone top-level v1.1 endpoint at
  `/rest/v1.1/projects/{project_id}/meeting_topics`. The
  `normalize_meeting_topic` function is registered in
  `_NORMALIZER_BY_ID` for the standalone fetch path; its
  `parent_procore_id` kwarg defaults to `None` so no signature change
  was needed. **Operational caveat:** Procore returns HTTP 500 at
  `per_page=100`; operators should cap `--max-items <= 10`.

Evidence: `docs/evidence/construction-intelligence-phase-04a/12-final-unverified-resolution.md`.

## meeting-detail endpoint — controlled exception to the inline default

`meeting-detail` is a 17th canonical endpoint introduced for rich
per-meeting data (attendees, full topics with `minutes` HTML, nested
categories, conclusion). Unlike every other Phase 04A endpoint, the
list payload at `/rest/v1.1/projects/{project_id}/meetings` does NOT
embed the rich detail — the operator must call the per-meeting detail
endpoint `/rest/v1.1/projects/{project_id}/meetings/{id}` to retrieve
it.

The orchestrator special-cases `adapter.endpoint_id == "meeting-detail"`:
1. Fetch the meetings list at `parent_path_template` (one HTTP call).
2. Apply the existing v1.1 grouped-flatten step.
3. **Issue one detail GET per meeting** (N+1, bounded by `--max-items`).
4. Replace the items list with the detail payloads; the existing
   normalize + upsert loop then processes each detail row.
5. The child dispatcher is hardcoded to `meeting-topics` (the family
   resolver would otherwise miss it because `meeting-topics`'
   `parent_record_id_field` is `None` — it's a standalone endpoint at
   `/meeting_topics`). Topics nested under
   `meeting_categories[].meeting_topic[]` are extracted via the public
   helper `extract_topics_from_categories(raw)` (a two-level walk, not
   the single-field lookup used by other parents).

PII handling: `normalize_meeting_detail` reduces attendees and
assignment arrays to `{count, hashed_identifiers}` summaries using a
SHA-256 prefix of the email address. Free-text bodies (`description`,
`conclusion`, topic `minutes`) reduce to `*_summary` hash structures
via the shared `_hash_summary` helper. `remote_meeting_url` is
path-only (query strings stripped) — Zoom/Teams join tokens never
persist.

The N+1 cost is operator-acknowledged: at `--max-items N` the apply
issues `1 + N` HTTP requests. The trade-off enables a depth of data
that the standalone `/meeting_topics` endpoint (which suffers a
server-side HTTP 500 at `per_page=100`) cannot match.

Evidence: `docs/evidence/construction-intelligence-phase-04a/13-meeting-detail-endpoint.md`.

## punch-items endpoint — project_id-as-query-param pattern

`punch-items` is the 18th canonical endpoint and the first Phase 04A
adapter where `project_id` is passed as a **query parameter** rather
than as a path placeholder. The path template is
`/rest/v1.1/punch_items` (no `{project_id}` segment); the orchestrator's
existing branch
`params={"project_id": ...} if "{project_id}" not in path else None`
routes the project_id into the query string automatically. No
orchestrator dispatch change was needed.

PII handling: the endpoint surfaces seven distinct people-ref fields
(`ball_in_court`, `created_by`, `closed_by`, `punch_item_manager`,
`final_approver`, `assignees`, `assignments[].login_information`)
plus free-text bodies. The `normalize_punch_item` normalizer in
`src/hb_assistant/procore/normalizers/punch_item.py` reduces every
people ref to `{count, hashed_identifiers: [{hash_prefix, id}, …]}`
summaries (SHA-256 prefix of the `login` email or `name`; numeric `id`
preserved as an opaque Procore identifier). Free-text fields
(`description`, `schedule_risk_reason`, per-assignment `comment`) go
through `_hash_summary`. Structured risk + financial signals are
preserved verbatim. Variable-shape `custom_fields` keep
numeric/boolean/lov_entry values verbatim and hash string-type values.

Every punch-item row carries `review_required=1` because of the PII
surface.

Evidence: `docs/evidence/construction-intelligence-phase-04a/14-punch-items-endpoint.md`.

## v2.0 schedules + activities — `{company_id}` substitution + data envelope

`schedules` (registry row #19) and `activities` (#20) are the first
Phase 04A endpoints that introduce two v2.0-specific shape elements:

1. **`{company_id}` path placeholder.** v2.0 paths are company-scoped:
   `/rest/v2.0/companies/{company_id}/projects/{project_id}/schedules/...`.
   `_resolve_path` is extended to substitute `{company_id}` from the
   existing module-level `COMPANY_ID = "5280"` constant alongside
   `{project_id}`. The substitution is a no-op for endpoints whose
   path template doesn't include `{company_id}`.

2. **`data` envelope.** v2.0 responses wrap their result in
   `{"data": [...]}` rather than a bare array (v1.0) or `{"items":
   [...]}` (legacy v1.1). The shared `http_client.paginate.fetch`
   body unwrap now accepts both `items` and `data` envelopes; a bare
   dict still falls through to a single-row response.

`activities` is the per-schedule child of `schedules`. The orchestrator
mirrors the meeting-detail dispatch shape: when `adapter.endpoint_id
== "activities"`, the initial paginate uses `parent_path_template`
(the schedules list), then iterates per-schedule
`/schedules/{schedule_id}/activities` GETs (N+1, bounded by
`--max-items`). Each activity's `parent_procore_id` is derived from
`raw["schedule_id"]` at upsert time so the SQLite PK correctly links
child rows back to their source schedule.

Both normalizers (`normalize_schedule` and `normalize_activity`) live
in `src/hb_assistant/procore/normalizers/schedule.py`. Activity `notes`
is the only free-text field; it reduces to a SHA-256 `notes_summary`.
`category_data` and `resource_data` arrays are preserved verbatim as
short-label structured collections.

Evidence: `docs/evidence/construction-intelligence-phase-04a/15-schedules-and-activities-endpoints.md`.

## Obsidian register from live SQLite (Prompt 09A)

Phase 04A's twenty endpoints land in `procore_live_records`, but the older
`procore obsidian preview` command queries the Phase 03 `procore_synced_entities`
table and therefore cannot project any of the new Phase 04A surfaces into the
local vault. `procore obsidian register` closes that gap with a focused,
endpoint-scoped projection.

Surface:

```bash
hb-assistant procore obsidian register \
  --project tropical --endpoint rfis --from-sqlite --dry-run --json

hb-assistant procore obsidian register \
  --project tropical --endpoint rfis --from-sqlite --apply --confirm --json
```

Read source: the local SQLite `procore_live_records` table, scoped by
`(project_key, endpoint_id)`. The code path is hard-wired never to touch HTTP;
the `--from-sqlite` flag is a mandatory, semantic gate that asserts no live
Procore call will be attempted. The command also never reads
`raw_body_persisted` — the V6 schema's CHECK constraint guarantees the column
is always `0`.

Endpoint → register-family template mapping
(`_ENDPOINT_TO_REGISTER_TEMPLATE` in `src/hb_assistant/procore/obsidian.py`):

| Endpoint id | Family template |
| --- | --- |
| `rfis`, `rfi-responses` | `rfi_register` |
| `submittals`, `submittal-responses`, `submittal-packages` | `submittal_register` |
| `observations` | `observation_register` |
| `meetings`, `meeting-detail` | `meeting_register` (Meetings table) |
| `meeting-topics` | `meeting_register` (Topics table) |
| `daily-log-weather`, `daily-log-manpower`, `daily-log-notes` | `daily_log_index` |

Endpoints **without** a register-family template (`projects`, `punch-items`,
`schedules`, `activities`) are deliberately rejected with `ok=False`,
`status="unsupported_endpoint"`, and a `next_steps` hint pointing at
`procore obsidian preview` for foundational artifacts. Adding register
templates for those families is future work.

Write target reuses the existing hybrid layout used by `obsidian preview`:
`<vault_root>/01_Projects/<project_key>.procore-<family>-register.md`. The
marker-bounded region (`<!-- HB-PROCORE-<FAMILY>-REGISTER:START/END -->`)
is shared with `preview` so the two commands are interchangeable, and reruns
of either are byte-identical when the underlying records are unchanged.

Sensitive routing is the same posture as `preview`: any row with
`procore_live_records.review_required = 1` is excluded from the register
table and surfaced in `review_items` (procore_record_id + endpoint_id +
sensitive_reason). Free-text excerpts route through
`ProcoreObsidianRenderer._safe_excerpt`, which redacts and hashes anything
over the per-field length cap.

Evidence: `docs/evidence/construction-intelligence-phase-04a/16-obsidian-register-from-live-records.md`.

## Sensitive routing and redaction proof (Prompt 10)

Phase 04A's routing + redaction posture is enforced at three layers:

1. **Normalizer triggers** — `_REVIEW_STATUS_FRAGMENTS`,
   `_REVIEW_SUBJECT_FRAGMENTS`, and (for observations)
   `_REVIEW_BODY_FRAGMENTS` in each `src/hb_assistant/procore/normalizers/*.py`
   set `review_required=True` with a `routing_reason` naming the matched
   fragment. Reply / response / comment / package / meeting-detail
   normalizers default to `review_required=True` unconditionally.
2. **YAML rule catalog** — `resources/config/procore_sensitive_routing_rules.yaml`
   carries declarative parity for the normalizer triggers
   (`procore-incident-injury-personnel`, `procore-rfi-legal-or-contractual`,
   `procore-submittal-financial-or-legal`, `procore-observation-safety`,
   `procore-daily-log-delays`, `procore-meeting-sensitive-topic`,
   `procore-daily-log-personnel-pii`, `procore-financial-summary`,
   `procore-contractual-records`).
3. **Schema invariants** — V6 CHECK constraints on
   `procore_live_records.raw_body_persisted = 0` and
   `procore_live_sync_runs.redaction_applied = 1` enforce no-raw-body /
   redacted-only persistence at the storage layer, independent of caller
   correctness.

Prompt 10 closes the explicit-bucket coverage gap with three load-bearing
tests:

- `tests/test_procore_sensitive_routing_proof.py::test_bucket_routes_to_review_and_redacts`
  walks the nine named buckets
  (incidents / injuries / safety / claims / notices / delay / cost /
  schedule / contract) and proves each routes via a real normalizer
  trigger.
- `tests/test_procore_sensitive_routing_proof.py::test_routing_rules_yaml_covers_prompt_10_buckets`
  proves the same buckets are covered by the YAML rule catalog
  (with documented synonyms for `schedule → daily_log_delays`).
- `tests/test_procore_sensitive_routing_proof_corpus.py::test_no_secret_literals_in_live_records_corpus`
  scans every row of `procore_live_records` for
  `Bearer / access_token / refresh_token / client_secret / Authorization`
  literals; corresponding constraint tests cover both CHECK constraints
  end-to-end.

Evidence: `docs/evidence/construction-intelligence-phase-04a/17-sensitive-routing-and-redaction-proof.md`.

## Idempotency, reconciliation, and rollback (Prompt 11)

Phase 04A's apply pipeline is idempotent by primary key
(`project_key, endpoint_id, parent_procore_id, procore_record_id`):
`upsert_procore_live_record` returns `"inserted"` on first write and
`"updated"` on every subsequent write. Each `procore_live_records` row
also carries `last_sync_run_id`, which advances on every replay and
groups rows by the sync run that last touched them.

Three Prompt 11 invariants are pinned by
`tests/test_procore_live_apply_idempotency_reconciliation_rollback_proof.py`:

1. **Receipt counts reconcile.** The sync-run row's
   `sqlite_upserted_count` matches the live `COUNT(*)` of
   `procore_live_records` for the same scope.
2. **Replay is update-only.** A second apply of the same payloads under a
   new sync_run_id returns `"updated"` for every row, leaves the row
   count unchanged, and advances `last_sync_run_id` on every existing
   row.
3. **Per-run grouping reconciles.** `SELECT COUNT(*) FROM
   procore_live_records WHERE last_sync_run_id = ?` matches each run's
   receipt-side `sqlite_upserted_count` independently.

Rollback has two documented recipes:

- **By receipt id (sync_run_id)** —
  `delete_procore_live_records_by_sync_run(sync_run_id=..., dry_run=...)`
  in `src/hb_assistant/store/procore_repositories.py`. Default
  `dry_run=True` returns `{would_delete, dry_run}` with no mutation;
  `dry_run=False` deletes every row attributed to that run and returns
  `{deleted, dry_run}`. The matching `procore_live_sync_runs` row is
  intentionally preserved as an audit trail of the rolled-back run.
- **By backup restore** — `sqlite3 Connection.backup()` (or the
  shell-form `sqlite3 db.sqlite ".backup backup.db"`). WAL-safe by
  contract; the proof test exercises the round trip and asserts the
  restored DB has zero records and zero sync-run rows.

Evidence: `docs/evidence/construction-intelligence-phase-04a/18-idempotency-reconciliation-rollback.md`.

## Mapping consistency closeout (2026-05-29)

The Phase 04A seed had carried two `pending` rows in
`resources/config/procore_projects.seed.yaml` (`hilltop` and
`hilltop-gardens`) since Phase 03. Both were SharePoint-side aliases for
the same construction project (24-606-01, procore_project_id `2982068`),
which is already mapped under `alton-hilltop-pbg`. The pending rows were
retired into the existing `alton-hilltop-pbg` mapping; the SharePoint
sources seed (`resources/config/sharepoint_onedrive_sources.seed.yaml`)
is left untouched so the two distinct SharePoint surfaces remain
identifiable as separate source records that index one Procore project.

Net effects:

- `hb-assistant procore validate --json` now returns **28/28** (was 27/28
  for the entire Phase 04A series).
- `EndpointAuditor.validate_mapping()` returns `ok=True` against the live
  seed: 4 pilot rows, 0 pending, 0 deprecated.
- `mapping_consistent` remains a strict stop condition for any *future*
  pending entry — the check itself was not loosened. The pending-handling
  invariant is exercised structurally in
  `tests/test_procore_endpoint_audit.py::test_mapping_validation_reports_pending_as_not_ok`
  and in the synthetic-registry tests in
  `tests/test_procore_sync_guards.py`.
- `tests/test_procore_endpoint_audit.py::test_seed_projects_covers_canonical_construction_registry_keys`
  now allows a documented `KNOWN_ORPHAN_SHAREPOINT_KEYS` set
  (`{"hilltop", "hilltop-gardens"}`); any *new* SharePoint-only
  project_key not on that list still fails the drift guard.

Evidence: `docs/evidence/construction-intelligence-phase-04a/19-mapping-consistent-resolution.md`.

## Inspections + Inspection Items (2026-05-29)

Two new endpoint adapters bring the canonical registry to 22 rows:

- **`inspections`** — `GET /rest/v1.0/projects/{project_id}/checklist/lists`,
  paginated list of checklist instances. `live_verified=True`; smoke
  receipt `d90b1851` retrieved 10, apply receipts `c426e87f` / `5477dc21`
  upserted 5 then 74; idempotent rerun `0e7153f4` upserted 74 (zero new
  inserts).
- **`inspection-items`** — child fetch from each inspection's id. The
  normalizer + orchestrator dispatch (mirrors the activities list+N+1
  pattern) are wired and tested via fake transport. The adapter ships
  with **`live_verified=False`** pending operator confirmation of the
  canonical list-items path — Procore returned 404 against both
  `/rest/v1.0/checklist/lists/{list_id}/items` and
  `/rest/v1.0/projects/{project_id}/checklist/lists/{list_id}/items`
  (smokes `12298720`, `0482d06c`). The operator detail URL the registry
  inherits its schema from carries `section_id` as a required query
  parameter, implying a list-by-section endpoint that has not yet been
  identified. Flipping `live_verified` to `True` requires only the path
  correction in `src/hb_assistant/procore/endpoints.py`; the dispatch,
  normalizer, and tests are already in place.

Redaction posture for both endpoints:

- Inspections — `review_required` heuristic mirrors
  `observation._safety_route_decision`: True when status is non-Closed
  OR `overdue` OR `inspection_type.name` matches the safety fragment
  list (`safety`, `incident`, `injury`, `near miss`, `osha`, `ppe`,
  `fall`). `safety_route=True` only on the inspection_type-safety
  trigger. PII person refs (created_by, closed_by, point_of_contact,
  responsible_contractor, inspectors, distribution_members) reduce via
  the new shared `person_hash_summary` helper in
  `src/hb_assistant/procore/normalizers/hashing.py`. Signature requests
  reduce to per-signatory hashed identifiers plus path-only attachment
  URLs + hashed filenames. Custom fields preserve numeric / boolean /
  lov_entry values verbatim; string values hash via `hash_summary`.
  `description` is the only top-level free-text field and is hashed.
- Inspection-items — default `review_required=True`,
  `routing_reason="inspection_item_default_review_required"`. Every
  per-item array (observations, comments, histories,
  attachment_histories, attachments) reduces to a `*_summary` count +
  per-entry hashed bodies + hashed identifiers. `item_response.payload.
  text_value` hashes; structured payload fields (number_value,
  date_value, response_option) preserve verbatim.

A small secondary consolidation lands with this slice: `hash_identifier`
and `person_hash_summary` graduated from `punch_item.py`'s private
surface into the shared `normalizers/hashing.py` module so the new
inspection normalizer doesn't reintroduce the duplication the prior
slice removed. The 64-char `_hash_identifier` variant in `meeting.py`
stays separate per the prior session handoff.

Evidence: `docs/evidence/construction-intelligence-phase-04a/20-inspections-and-inspection-items.md`.

## Inspection-sections bridge + 2-level inspection-items dispatch (2026-05-29)

The operator-supplied checklist sections detail URL
(`/rest/v1.0/checklist/lists/{list_id}/sections/{id}?project_id=X`)
revealed the Procore checklist data model: `Inspection (list) → Section →
Item`. The 23rd canonical endpoint `inspection-sections` (registry row
between `inspections` and `inspection-items`) was added as the bridge,
and the `inspection-items` dispatch was rewritten from a single-level
N+1 to a 2-level walk (inspections → sections → items) so each item
fetch carries the required `section_id` query param the operator detail
URL signaled.

Disposition (2026-05-29):

- **`inspection-sections`** (live_verified=False): both
  `/rest/v1.0/checklist/lists/{list_id}/sections` (smoke `a942dcef`) and
  `/rest/v1.0/projects/{project_id}/checklist/lists/{list_id}/sections`
  (smoke `2c1d59d2`) returned 404 against tropical. The operator schema
  is a detail URL only; Procore may not expose a list-of-sections
  endpoint via strip-the-id convention. Possible alternatives the
  operator can confirm: sections embedded in a `/lists/{id}` detail
  call, or only reachable via the checklist template
  (`list_template_id`).
- **`inspection-items`** (live_verified=False): depends on
  `inspection-sections`. The 2-level dispatch requires `section_id` from
  the sections sub-fetch; until sections is verified, items cannot be
  reached.

The structural infrastructure is in place: `normalize_inspection_section`
(trivial — preserves `id, name, position, list_id, not_applicable`
verbatim, no PII, no hashing), the 2-level dispatch block in
`live_sync.py` (skips `not_applicable=True` sections to avoid wasted
items GETs), parent_procore_id wiring for both endpoints, two
fake-transport chain tests (each monkeypatches `live_verified=True` for
its run), and the `_NORMALIZER_BY_ID` + parent-path-template wiring.
Flipping live_verified to True requires only the correct `path_template`
once the operator confirms it.

Evidence: `docs/evidence/construction-intelligence-phase-04a/21-inspection-sections-bridge.md`.

## Inspection-sections + inspection-items flat-list re-target (2026-05-29)

The operator supplied the canonical Procore list endpoints, replacing
the prior detail-URL guesses:

- **Sections**: `GET /rest/v1.0/projects/{project_id}/checklist/list_sections`
  — project-wide flat paginated list. Response shape:
  `{id, name, position, template_section_id, updated_at}`. NOT per-
  inspection (no `list_id` field). Sections are template-scoped
  surfaces; their per-inspection relationship lives at the items
  layer.
- **Items**: `GET /rest/v1.1/projects/{project_id}/checklist/list_items`
  — project-wide flat paginated list. Items are at **v1.1**, not v1.0.
  Each item payload carries `list_id` and `section_id` directly, so
  `parent_procore_id = raw["list_id"]` is derivable at upsert (same
  shape as `activities` deriving from `schedule_id`).

The prior 2-level dispatch (inspections → sections → items) was
removed: it was unnecessary because both endpoints are flat lists. The
orchestrator's special-case dispatch blocks for `inspection-sections`
and `inspection-items` were deleted; the parent-path-template tuple was
shrunk back to `("meeting-detail", "activities")`. Both endpoints now
use the default flat-list paginate path.

Normalizer extensions:

- `normalize_inspection_section` structured-keys list is now
  `(id, name, position, template_section_id, updated_at)`. The prior
  `list_id` field was dropped (not present on the list response);
  `parent_inspection_stable_key` is no longer emitted.
- `normalize_inspection_item` structured-keys list gains `list_id`,
  `number`, `relative_position`, `parent_item_id`. New free-text field
  `company_template_item_details` reduces to
  `company_template_item_details_summary` via `hash_summary`.
  `display_conditions[]` is preserved as a structural array.

Disposition: both endpoints are **`live_verified=True`** (verified
end-to-end via the 2026-05-29 live cadence — receipt ids below).

Evidence: `docs/evidence/construction-intelligence-phase-04a/22-inspection-flat-list-endpoints.md`.

## Verified vs unverified endpoints

Post schedules + activities addition, **all 20 of 20 canonical
endpoint IDs are `live_verified=True`** and execute the full chain:
the prior 18 plus `schedules` (v2.0 company-scoped list) and
`activities` (per-schedule N+1 child). Phase 04A registry coverage
spans foundational v1.0/v1.1 endpoints, rich per-item fetches
(`meeting-detail`), PII-bearing surfaces (`punch-items`,
`meeting-detail`), and v2.0 scheduling data with the `data` envelope
+ `{company_id}` path-substitution pattern.

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
| `tests/test_procore_obsidian_register.py` | Prompt 09A unit coverage: dry-run table render, review_required exclusion, unsupported endpoint rejection, marker-bounded write idempotency, user-content preservation outside markers, corrupted-JSON tolerance. |
| `tests/test_procore_cli_obsidian_register.py` | Prompt 09A CLI coverage: missing `--from-sqlite` rejection, unknown alias rejection, unsupported endpoint rejection, dry-run happy path, apply + confirm happy path, non-TTY `--apply` without `--confirm` rejection. |
| `tests/test_procore_sensitive_routing_proof.py` | Prompt 10 routing proof: per-family pre-existing parameterized blob coverage plus new per-bucket (incidents/injuries/safety/claims/notices/delay/cost/schedule/contract) trigger proofs, YAML rule-catalog coverage assertion, and `mask_pii_in_excerpt` redaction. |
| `tests/test_procore_sensitive_routing_proof_corpus.py` | Prompt 10 corpus attestation: `redact_body` strips secret-shaped literals from dict/list payloads, V6 CHECK constraints reject `raw_body_persisted=1` and `redaction_applied=0`, no secret-shaped literals present in the local `procore_live_records` corpus. |
| `tests/test_procore_live_apply_idempotency_reconciliation_rollback_proof.py` | Prompt 11 proof: receipt counts reconcile with `procore_live_records` row count; replay is update-only with `last_sync_run_id` advance; per-sync_run_id grouping reconciles; `delete_procore_live_records_by_sync_run` rolls back exactly the targeted rows and preserves the audit trail; `sqlite3.Connection.backup()` round trip restores pre-apply state. |
