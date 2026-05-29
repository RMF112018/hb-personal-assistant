# Phase 04A — Inspection-sections + inspection-items flat-list re-target (2026-05-29)

## Objective

Re-target the `inspection-sections` and `inspection-items` adapter rows
to the canonical Procore list endpoints the operator supplied, replacing
the prior detail-URL guesses that returned 404 (see prior evidence file
21). Both endpoints become flat project-scoped paginated lists; the
prior 2-level dispatch infrastructure is removed. Registry row count
stays at 23. Both endpoints become live-verified end-to-end via the
2026-05-29 cadence.

## Source

- `src/hb_assistant/procore/endpoints.py` — both adapter rows
  re-targeted:
  - `inspection-sections`:
    `path_template="/rest/v1.0/projects/{project_id}/checklist/list_sections"`,
    `parent_path_template=None`, `parent_record_id_field=None`,
    `required_path_params=("project_id",)`, `live_verified=True`.
  - `inspection-items`:
    `path_template="/rest/v1.1/projects/{project_id}/checklist/list_items"`,
    `parent_path_template=None`, `parent_record_id_field="list_id"`,
    `required_path_params=("project_id",)`, `live_verified=True`.
- `src/hb_assistant/procore/normalizers/inspection.py`:
  - `normalize_inspection_section` structured-keys list updated to
    `(id, name, position, template_section_id, updated_at)`; dropped the
    `list_id` requirement and `parent_inspection_stable_key` field
    (sections are template-scoped on the v1.0 list endpoint).
  - `normalize_inspection_item` structured-keys list extended with
    `list_id`, `number`, `relative_position`, `parent_item_id`. New
    `company_template_item_details_summary` hash via `hash_summary`.
    `display_conditions[]` preserved as a structural array.
- `src/hb_assistant/procore/live_sync.py`:
  - Both `inspection-sections` and `inspection-items` removed from the
    parent-path-template tuple — the orchestrator's default flat-list
    paginate handles them now.
  - Both special-case dispatch blocks deleted.
  - `parent_id_for_upsert` branch simplified: only `inspection-items`
    derives a parent (from `raw["list_id"]`); sections have no parent.

## Endpoint adapter rows

| Field | inspection-sections | inspection-items |
| --- | --- | --- |
| family | `inspections` | `inspections` |
| path_template | `/rest/v1.0/projects/{project_id}/checklist/list_sections` | `/rest/v1.1/projects/{project_id}/checklist/list_items` |
| parent_path_template | None | None |
| required_path_params | `("project_id",)` | `("project_id",)` |
| pagination | `page+per_page` | `page+per_page` |
| record_id_field | `id` | `id` |
| parent_record_id_field | None | `list_id` |
| review_required_default | False | True |
| sensitivity | `low` | `high` |
| sqlite_target | `procore_live_records` | `procore_live_records` |
| live_verified | **True** | **True** |

## Response-shape highlights

### Inspection-sections (v1.0)

```
[
  {
    "id": 21,
    "name": "Framing",
    "position": 1,
    "template_section_id": 3,
    "updated_at": "2012-10-23T21:39:40Z"
  }
]
```

No `list_id` field — sections are template-scoped, not per-inspection.
`template_section_id` is the canonical cross-reference back to the
template tree.

### Inspection-items (v1.1)

Each item payload carries `list_id` and `section_id` directly:

```
[
  {
    "id": 2,
    "list_id": 1,
    "section_id": 21,
    "name": "Item 1",
    "number": "1.1",
    "relative_position": 1,
    "parent_item_id": 34,
    "details": "+/- 1 degrees",
    "company_template_item_details": "+/- 1 degrees",
    "status": "yes",
    "responded_with": "Safe - Knowledge",
    "item_response": {
      "item_id": 4323,
      "status": "conforming",
      "responder": {"id": 160586, "login": "...", "name": "..."},
      "payload": {
        "text_value": "...",
        "number_value": 4232,
        "date_value": "2019-01-20",
        "response_option": {"id": 3432, "name": "Safe"}
      }
    },
    "response_set": {...},
    "display_conditions": [...]
  }
]
```

Detail-only fields (`observations[]`, `comments[]`, `histories[]`,
`attachment_histories[]`, `attachments[]`) may not appear on the list
response; the normalizer's "preserve if present" idiom is no-op when
they're absent.

## Live cadence + receipts

All commands ran against the operator's live Procore (project
`tropical` = procore_project_id `2525840`) under `HB_PROCORE_LIVE=1`
with `--confirm-live-get`. Receipts captured into `/tmp/hb-inspect/`.

### Inspection-sections

| Step | sync_run_id | state | retrieved | upserted | requests |
| --- | --- | --- | --- | --- | --- |
| smoke | `85cabcc6-e450-46a3-94f5-6646ea1e3545` | success | 10 | n/a | 1 |
| apply 1/5 | `2dce4778-d982-47b2-8ebc-80bb0b8764a5` | success | n/a | 5 | 1 |
| apply 3/100 | `300ecf8c-a3e1-48d1-8e7d-517bc2fcd954` | success | n/a | 100 | 1 |
| rerun | `8631fe02-78cd-4b4f-b7a0-039f523c7bb9` | success | n/a | **100** (idempotent) | 1 |

### Inspection-items (v1.1)

| Step | sync_run_id | state | retrieved | upserted | requests |
| --- | --- | --- | --- | --- | --- |
| smoke | `73979b2d-c660-4f85-8e90-bbfcba380f2b` | success | 10 | n/a | 1 |
| apply 1/5 | `1fc9d0f9-73d4-43a6-a570-a1df2378c9f9` | success | n/a | 5 | 1 |
| apply 3/100 | `864f85c3-25cd-4d2f-bdf3-36084a522a3b` | success | n/a | 100 | 1 |
| rerun | `59c89c15-42d6-444c-a3e1-a085b56a42a0` | success | n/a | **100** (idempotent) | 1 |

Both reruns produced byte-equal canonical_json on every row: the
`sqlite_upserted_count` stayed at 100 on the second apply with zero new
inserts (every upsert returned `"updated"`). Mirrors the Prompt 11
idempotency proof.

## Live-records counts

```
$ hb-assistant procore live records count --project tropical --endpoint inspection-sections --json
{"count": 100}
$ hb-assistant procore live records count --project tropical --endpoint inspection-items --json
{"count": 100}
```

## No-secret / no-raw-body attestation

SQL probes against the new endpoint scope (post-apply state):

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

All four probes return 0 across all 200 persisted rows. The
inspection-items rows that came back with PII responders had every
email/name hashed via `person_hash_summary`; free-text fields
(`details`, `company_template_item_details`, `item_response.payload.text_value`)
all reduced to `*_summary` hash blocks.

## Static verification

```
$ python -m pytest -q tests/test_procore_inspection_normalizer.py \
                     tests/test_procore_endpoint_registry.py \
                     tests/test_procore_live_gate.py \
                     tests/test_procore_live_sync_verified_chain.py
73 passed

$ python -m pytest -q --no-header
970 passed, 2 skipped in 18.79s

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

None triggered. Every smoke + apply + rerun returned `state="success"`
with `no_live_call_performed=False` for apply runs. All four SQL
attestation probes returned 0. The receipt counts match the canonical
DB row counts and remain stable across the idempotency rerun.

## Related references

- Architecture addendum:
  `docs/architecture/14-procore-live-sync-phase-04a.md`
  (section "Inspection-sections + inspection-items flat-list re-target
  (2026-05-29)").
- Operator runbook:
  `docs/operations/procore-operator-runbook.md`
  (section "Inspection-sections + inspection-items flat-list re-target
  (2026-05-29)").
- Predecessor in the evidence series:
  `docs/evidence/construction-intelligence-phase-04a/21-inspection-sections-bridge.md`
  (the prior fail-closed disposition this slice supersedes).
- Normalizers + dispatch:
  `src/hb_assistant/procore/normalizers/inspection.py`,
  `src/hb_assistant/procore/live_sync.py`.
