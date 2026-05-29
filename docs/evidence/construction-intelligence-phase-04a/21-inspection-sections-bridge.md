# Phase 04A — `inspection-sections` bridge + 2-level `inspection-items` dispatch (2026-05-29)

## Objective

Add `inspection-sections` as a first-class Procore endpoint (the bridge
between inspections and inspection-items in the
`Inspection → Section → Item` checklist model the operator-supplied
sections detail URL revealed) and rewrite `inspection-items` to do a
2-level walk that supplies the required `section_id` query param to each
items GET. Registry row count goes 22 → **23**.

## Source

- `src/hb_assistant/procore/endpoints.py` — new `inspection-sections`
  adapter row; `inspection-items` row updated (path now project-scoped,
  `required_path_params` extended with `section_id` to reflect the 2-level
  dispatch). Both ship `live_verified=False` pending operator path
  confirmation (see Disposition below).
- `src/hb_assistant/procore/normalizers/inspection.py` — new
  `normalize_inspection_section`: preserves `id`, `name`, `position`,
  `list_id`, `not_applicable` verbatim; no PII, no hashing,
  `review_required=False`, `category="inspection_sections"`,
  `parent_inspection_stable_key = str(list_id)`.
- `src/hb_assistant/procore/normalizers/__init__.py` — re-exports the new
  normalizer.
- `src/hb_assistant/procore/live_sync.py`:
  - Added `inspection-sections` to `_NORMALIZER_BY_ID`.
  - Extended the meeting-detail / activities / inspection-items
    parent-path branch to also include `inspection-sections`.
  - Added an `inspection-sections` special-case dispatch block (1+N):
    list-fetch inspections → per-list sections GET → flat replace
    `items` → set `list_id` on each section.
  - Rewrote `inspection-items` dispatch from 1-level to 2-level
    (1+N+N×M): list-fetch inspections → per-list sections GET → for each
    non-`not_applicable` section, fetch items GET with `section_id` query
    param → flat replace `items` → set both `list_id` and `section_id`
    on each item.
  - Extended the upsert step's `parent_procore_id` branch to handle
    `inspection-sections` (parent = `raw["list_id"]`).
- Tests:
  - `tests/test_procore_inspection_normalizer.py` — 2 new cases:
    `test_inspection_section_canonical_fields_preserved` and
    `test_inspection_section_requires_list_id`.
  - `tests/test_procore_endpoint_registry.py` — `_CANONICAL_IDS` bumped
    to 23; verified-set assertion documents
    `{"inspection-sections", "inspection-items"}` as the not-verified
    set.
  - `tests/test_procore_live_gate.py` — count bumped to 23; not-verified
    set assertion mirrors the registry test.
  - `tests/test_procore_live_sync_verified_chain.py` — two chain tests:
    `test_inspection_sections_apply_list_plus_n_per_inspection` (1+N
    via fake transport, both endpoints monkeypatched to live_verified=
    True for the test) and `test_inspection_items_apply_via_sections_
    bridge` (1+N+N×M, verifies `not_applicable=True` sections are
    skipped, asserts each item carries `parent_procore_id = list_id`
    AND `canonical_fields.section_id`).
- Docs: architecture addendum in
  `docs/architecture/14-procore-live-sync-phase-04a.md`, runbook section
  in `docs/operations/procore-operator-runbook.md`.

## Endpoint adapter rows

| Field | inspection-sections | inspection-items (updated) |
| --- | --- | --- |
| family | `inspections` | `inspections` |
| path_template | `/rest/v1.0/projects/{project_id}/checklist/lists/{list_id}/sections` | `/rest/v1.0/projects/{project_id}/checklist/lists/{list_id}/items` |
| parent_path_template | `/rest/v1.0/projects/{project_id}/checklist/lists` | `/rest/v1.0/projects/{project_id}/checklist/lists` |
| required_path_params | `("project_id", "list_id")` | `("project_id", "list_id", "section_id")` |
| pagination | `page+per_page` | `page+per_page` |
| record_id_field | `id` | `id` |
| parent_record_id_field | `list_id` | `list_id` |
| review_required_default | False | True |
| sensitivity | `low` | `high` |
| sqlite_target | `procore_live_records` | `procore_live_records` |
| live_verified | **False** (path unconfirmed) | **False** (depends on sections) |

## Live cadence + receipts

Attempted both path variants against the operator's live Procore (project
`tropical` = procore_project_id `2525840`).

| Step | Path attempted | sync_run_id | state | retrieved | errors |
| --- | --- | --- | --- | --- | --- |
| sections smoke (unscoped) | `/rest/v1.0/checklist/lists/{list_id}/sections` | `a942dcef-b523-4dc0-996a-dcea48974613` | partial_success | 0 | 10× 404 |
| sections smoke (project-scoped) | `/rest/v1.0/projects/{project_id}/checklist/lists/{list_id}/sections` | `2c1d59d2-223f-4c01-a91c-7c9a283b8f2d` | partial_success | 0 | 10× 404 |
| sections smoke (post-demotion) | n/a (fail-closed) | n/a | gate_blocked | 0 | n/a |
| items smoke | not attempted post-demotion (depends on sections) | n/a | n/a | n/a | n/a |

The orchestrator captured each per-list 404 as a structured
`redacted_errors` entry (`{"detail_transport_error": "http_error",
"status": 404, "list_id": ...}`). No raw response bodies, no Bearer
literals, no `Authorization` headers appeared anywhere in the receipts —
the redaction stack held for the failure path the same way it does for
the success path.

## Disposition

Both endpoints ship `live_verified=False`. The operator-supplied
checklist sections URL
(`/rest/v1.0/checklist/lists/{list_id}/sections/{id}?project_id=X`) is a
**detail** endpoint; stripping `{id}` to get a list URL is the
established Procore convention used for every other endpoint in this
registry, but it failed for sections — suggesting Procore may not expose
a list-of-sections endpoint at all, or it lives under a different noun
(e.g., embedded in a `/lists/{id}` detail call, or only reachable via
`list_template_id`).

Possible avenues for the operator to confirm the correct path:

1. **Embedded in inspections detail**: `GET /rest/v1.0/projects/{project_id}/checklist/lists/{id}` may return sections + items inline.
2. **Via the checklist template**: `GET /rest/v1.1/projects/{project_id}/checklist/list_templates/{template_id}/sections` or similar.
3. **A different v1.0 noun**: e.g., `/rest/v1.0/projects/{project_id}/checklist_sections?list_id=X`.

The structural infrastructure ships in this commit: the normalizer, the
2-level dispatch, the parent_procore_id wiring, both chain tests, the
`_NORMALIZER_BY_ID` wiring, and the parent-path-template branch
extension. Flipping `live_verified=True` requires only the correct
`path_template` value on the `inspection-sections` adapter row once
confirmed — `inspection-items` follows automatically because its
2-level dispatch derives the items path from the verified sections
path.

## Live-records counts

```
$ hb-assistant procore live records count --project tropical --endpoint inspection-sections --json
{"count": 0}
$ hb-assistant procore live records count --project tropical --endpoint inspection-items --json
{"count": 0}
```

Both zero by construction (fail-closed; no live writes happened).

## No-secret / no-raw-body attestation

SQL probes against the new endpoint scope:

```bash
DB="$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"

sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id IN ('inspection-sections','inspection-items') AND raw_body_persisted != 0"
# -> 0
sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id IN ('inspection-sections','inspection-items') AND canonical_json_redacted LIKE '%Bearer %'"
# -> 0
sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id IN ('inspection-sections','inspection-items') AND (canonical_json_redacted LIKE '%access_token%' OR canonical_json_redacted LIKE '%refresh_token%' OR canonical_json_redacted LIKE '%client_secret%' OR canonical_json_redacted LIKE '%Authorization%')"
# -> 0
sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id IN ('inspection-sections','inspection-items') AND canonical_json_redacted LIKE '%@%'"
# -> 0
```

All four probes returned 0 (vacuous — no rows persisted; the
fail-closed gate prevented any write).

## Static verification

```
$ python -m pytest -q tests/test_procore_inspection_normalizer.py \
                     tests/test_procore_endpoint_registry.py \
                     tests/test_procore_live_gate.py \
                     tests/test_procore_live_sync_verified_chain.py
72 passed

$ python -m pytest -q --no-header
970 passed, 2 skipped in 19.86s

$ ruff check .
All checks passed!

$ mypy .
Success: no issues found in 184 source files

$ python -m compileall -q src tests
(clean)

$ hb-assistant procore validate --json
28/28
```

## Stop conditions

None violated. The 404s on both sections path variants were captured as
structured redacted errors and the orchestrator returned a
`partial_success` receipt; both adapters were demoted to
`live_verified=False` with structured `verification_reason` fields so
the operator can confirm the path without re-incurring the discovery
cost. No `Bearer`, no `client_secret`, no raw bodies appeared in any
receipt or any persisted row.

## Related references

- Architecture addendum:
  `docs/architecture/14-procore-live-sync-phase-04a.md`
  (section "Inspection-sections bridge + 2-level inspection-items
  dispatch (2026-05-29)").
- Operator runbook:
  `docs/operations/procore-operator-runbook.md`
  (section "Inspection-sections bridge + 2-level inspection-items
  dispatch (2026-05-29)").
- Predecessor in the evidence series:
  `docs/evidence/construction-intelligence-phase-04a/20-inspections-and-inspection-items.md`.
- Normalizer + dispatch:
  `src/hb_assistant/procore/normalizers/inspection.py`,
  `src/hb_assistant/procore/live_sync.py`
  (search for `inspection-sections` for the dispatch block).
