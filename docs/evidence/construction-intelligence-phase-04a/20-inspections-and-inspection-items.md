# Phase 04A — Inspections + Inspection Items endpoints (2026-05-29)

## Objective

Add two new Procore endpoint adapters to the Phase 04A live-sync stack
with the appropriate redaction contracts and live verification per the
established cadence (implement → smoke → apply 1/5 → apply 3/100 →
idempotency rerun). Registry row count goes 20 → 22.

- **Inspections** — `GET /rest/v1.0/projects/{project_id}/checklist/lists`,
  paginated list of checklist instances. Heavy PII (inspectors,
  distribution_members, signature_requests, point_of_contact,
  created_by, closed_by, responsible_contractor), free-text
  (description), attachments, custom_fields.
- **Inspection Items** — per-list child endpoint. Carries observations[],
  comments[], histories[], attachment_histories[], item_response with
  responder PII and payload.text_value.

## Source

- `src/hb_assistant/procore/endpoints.py` — two new `EndpointAdapter`
  rows appended (inspections + inspection-items).
- `src/hb_assistant/procore/normalizers/inspection.py` (new file) —
  `normalize_inspection`, `normalize_inspection_item`, plus local
  helpers for signatures / attachments / observations / comments /
  histories / item_response / custom_fields.
- `src/hb_assistant/procore/normalizers/hashing.py` — promoted
  `hash_identifier` and `person_hash_summary` from `punch_item.py`'s
  private surface into the shared module. `punch_item.py` now imports
  them from `.hashing`.
- `src/hb_assistant/procore/normalizers/__init__.py` — exports the new
  normalizers.
- `src/hb_assistant/procore/live_sync.py` — added `inspections` and
  `inspection-items` to `_NORMALIZER_BY_ID`; added the inspection-items
  special-case dispatch block (list-fetch via parent_path_template,
  per-list N+1, replace items, derive parent_procore_id from
  `raw["list_id"]` at upsert time); extended the meeting-detail /
  activities parent-path branch to also handle `inspection-items`.
- Tests:
  `tests/test_procore_inspection_normalizer.py` (6 unit cases),
  `tests/test_procore_endpoint_registry.py` (canonical-set bump 20 → 22;
  verified-set asserts inspection-items in the unverified set),
  `tests/test_procore_live_gate.py` (count bump 20 → 22; not-verified
  set asserts `{"inspection-items"}`),
  `tests/test_procore_live_sync_verified_chain.py` (two chain tests for
  inspections list and inspection-items list+N+1 dispatch).
- Docs: architecture addendum in
  `docs/architecture/14-procore-live-sync-phase-04a.md` and runbook
  section in `docs/operations/procore-operator-runbook.md`.

## Endpoint adapter rows

| Field | inspections | inspection-items |
| --- | --- | --- |
| family | `inspections` | `inspections` |
| path_template | `/rest/v1.0/projects/{project_id}/checklist/lists` | `/rest/v1.0/projects/{project_id}/checklist/lists/{list_id}/items` |
| parent_path_template | None | `/rest/v1.0/projects/{project_id}/checklist/lists` |
| required_path_params | `("project_id",)` | `("project_id", "list_id")` |
| pagination | `page+per_page` | `page+per_page` |
| record_id_field | `id` | `id` |
| parent_record_id_field | None | `list_id` |
| review_required_default | False (heuristic) | True (unconditional) |
| sensitivity | `high` | `high` |
| sqlite_target | `procore_live_records` | `procore_live_records` |
| live_verified | **True** | **False** (pending operator path confirmation) |

## Redaction posture

### Inspections (parent)

- Structured canonical fields preserved verbatim (counts, ids,
  timestamps, status flags, template ids, drawing_ids).
- Free-text `description` → `description_summary` via `hash_summary`.
- People refs (created_by, closed_by, point_of_contact,
  responsible_contractor, inspectors, distribution_members) → reduced
  via the new shared `person_hash_summary`.
- `signature_requests` → count + per-signatory hashed identifier +
  hashed captured_by + path-only attachment URL + hashed filename.
- `attachments` → count + per-attachment hashed filename + path-only
  URL + path-only thumbnail_url + content_type/viewable_document_id
  verbatim.
- Structured nested objects (location, inspection_type, trade,
  specification_section, default_response_phrasing) preserved verbatim
  — no PII inside.
- `custom_fields` → `_custom_fields_summary`: numeric / boolean /
  lov_entry / lov_entries values preserved verbatim; string values
  hashed.
- `review_required` heuristic — True when
  `inspection_type.name` matches a safety fragment (`safety`,
  `incident`, `injury`, `near miss`, `near-miss`, `near_miss`, `osha`,
  `ppe`, `fall protection`, `fall`) OR `overdue=True` OR `status`
  matches a non-Closed fragment (`open`, `in progress`, `incomplete`,
  `rejected`). `safety_route=True` only on the inspection_type-safety
  branch.

### Inspection-items (child)

- Always `review_required=True`,
  `routing_reason="inspection_item_default_review_required"`.
- `parent_list_id` set on the canonical record + on the row's
  `parent_procore_id` so operators can join items back to their parent
  inspection.
- `details` → `details_summary`.
- `observations[]` → `observations_summary` (count + per-observation
  hashed title + hashed assignee + hashed created_by + structural type
  preserved).
- `comments[]` → `comments_summary` (count + per-comment hashed body +
  hashed created_by).
- `histories[]` → `histories_summary` (count + per-history hashed body
  + hashed created_by).
- `attachment_histories[]` → count + per-history hashed attachment +
  hashed created_by.
- `attachments[]` → count + per-attachment hashed filename + path-only
  URL.
- `item_response` → preserves item_id / status / responded_at /
  item_type structurally; payload.text_value hashed; payload
  number_value / date_value / response_option preserved verbatim;
  responder hashed.

## Live cadence + receipts

All commands run against `--project tropical` (procore_project_id
`2525840`) under `HB_PROCORE_LIVE=1` with `--confirm-live-get`. Receipts
captured into `/tmp/hb-inspect/`. Synthetic identifiers redacted in this
evidence file; the receipt ids below are valid sync_run_ids that the
operator can join back to `procore_live_sync_runs` for audit.

### Inspections

| Step | Command shape | sync_run_id | state | retrieved | upserted | request_count |
| --- | --- | --- | --- | --- | --- | --- |
| smoke | `live smoke --endpoint inspections` | `d90b1851-e5c3-4279-a6c6-eb915f562b15` | success | 10 | n/a | 1 |
| apply 1/5 | `live sync --endpoint inspections --apply --sqlite-only --max-pages 1 --max-items 5` | `c426e87f-202b-41f8-b9b5-94bae8e1c459` | success | n/a | 5 | 1 |
| apply 3/100 | `live sync --endpoint inspections --apply --sqlite-only --max-pages 3 --max-items 100` | `5477dc21-2b0c-4fe0-96a9-cefe846de9f9` | success | n/a | 74 | 3 |
| rerun (idempotency) | same command | `0e7153f4-29ad-47b5-9dd7-7df8f74ff569` | success | n/a | 74 | 3 |

The rerun's `sqlite_upserted_count` matches the prior apply exactly (74
on both runs); zero new inserts (every upsert returned `"updated"`).
Mirrors the Prompt 11 idempotency proof for rfis/submittals.

### Inspection-items

| Step | sync_run_id | state | retrieved | redacted_errors |
| --- | --- | --- | --- | --- |
| smoke (unscoped path attempt) | `12298720-a1ac-4dc7-8fb5-4615e26a95ab` | partial_success | 0 | 10× 404 |
| smoke (project-scoped path attempt) | `0482d06c-e303-438c-bb5c-273b0bbf6465` | partial_success | 0 | 10× 404 |
| smoke (post-demotion) | not run | not_live_verified | 0 | n/a (fail-closed) |

Both list-items path attempts returned 404 for every inspection list_id
in tropical's corpus. The orchestrator's `redacted_errors` array
captured `{"detail_transport_error": "http_error", "status": 404,
"list_id": ...}` for each per-list sub-fetch. The operator-supplied
detail URL carries `section_id` as a required query param
(`/rest/v1.0/checklist/lists/{list_id}/items/{id}?project_id=X&section_id=Y`),
implying the list-of-items endpoint may also require `section_id` —
suggesting a list-by-section endpoint that has not yet been identified.

Disposition: `inspection-items.live_verified=False` with a structured
`verification_reason` documenting the smoke ids and the
section_id-requirement hypothesis. The normalizer + orchestrator
dispatch + chain test + unit tests are all in place; flipping the
adapter row to `live_verified=True` requires only the correct
`path_template` value once the operator confirms it. A re-smoke against
the corrected path is a one-command operation.

## Live-records counts

```
$ hb-assistant procore live records count --project tropical --endpoint inspections --json
{"count": 74}
$ hb-assistant procore live records count --project tropical --endpoint inspection-items --json
{"count": 0}
```

## No-secret / no-raw-body attestation

SQL probes against the inspections + inspection-items endpoint scope:

```bash
DB="$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"

sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id IN ('inspections','inspection-items') AND raw_body_persisted != 0"
# -> 0
sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id IN ('inspections','inspection-items') AND canonical_json_redacted LIKE '%Bearer %'"
# -> 0
sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id IN ('inspections','inspection-items') AND canonical_json_redacted LIKE '%access_token%'"
# -> 0
sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id IN ('inspections','inspection-items') AND canonical_json_redacted LIKE '%refresh_token%'"
# -> 0
sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id IN ('inspections','inspection-items') AND canonical_json_redacted LIKE '%client_secret%'"
# -> 0
sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id IN ('inspections','inspection-items') AND canonical_json_redacted LIKE '%Authorization%'"
# -> 0
sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id IN ('inspections','inspection-items') AND canonical_json_redacted LIKE '%@%'"
# -> 0
```

All six secret-shape probes return 0 across all 74 persisted rows; the
email-leak probe also returns 0 (every PII email path landed in a
`hashed_identifier` `hash_prefix` block, never as a raw `@`-bearing
string).

## Static verification

```
$ python -m pytest -q tests/test_procore_inspection_normalizer.py \
                     tests/test_procore_endpoint_registry.py \
                     tests/test_procore_live_gate.py \
                     tests/test_procore_live_sync_verified_chain.py \
                     tests/test_procore_punch_item_normalizer.py
68 passed

$ python -m pytest -q --no-header
967 passed, 2 skipped in 18.95s

$ ruff check .
All checks passed!

$ mypy .
Success: no issues found in 184 source files

$ python -m compileall -q src tests
(clean)

$ hb-assistant procore validate --json
28/28

$ hb-assistant procore tools list --json    # canonical envelope (endpoint_count: 16 — Phase 03 contract surface, separate from the 22-row Phase 04A live-sync registry)
$ hb-assistant procore mapping validate --json   # canonical envelope
```

## Stop conditions

None triggered. Every probe at the live-attestation step returned the
required zero. The inspection-items 404s were caught structurally and
the adapter was demoted to fail-closed before any speculative apply
ran.

## Related references

- Architecture addendum:
  `docs/architecture/14-procore-live-sync-phase-04a.md`
  (section "Inspections + Inspection Items (2026-05-29)").
- Operator runbook:
  `docs/operations/procore-operator-runbook.md`
  (section "Inspections + Inspection-Items (2026-05-29)").
- Predecessor in the evidence series:
  `docs/evidence/construction-intelligence-phase-04a/19-mapping-consistent-resolution.md`.
- Normalizer + shared helpers:
  `src/hb_assistant/procore/normalizers/inspection.py`,
  `src/hb_assistant/procore/normalizers/hashing.py`.
- Orchestrator dispatch:
  `src/hb_assistant/procore/live_sync.py` (search for
  `"inspection-items"` for the special-case dispatch block).
