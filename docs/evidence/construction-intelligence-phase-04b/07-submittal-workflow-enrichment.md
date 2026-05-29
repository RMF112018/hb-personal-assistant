# Phase 04B — Prompt 07 — Submittal Workflow Enrichment

**Date:** 2026-05-29
**Branch:** main
**Scope:** Turn submittals from flat latest-state rows into workflow memory —
approvers, responses, attachments, due/returned/sent dates, custom fields, and
procurement / schedule action signals.

## Scope decisions (deliberate)

- **No normalizer change.** The projection reads the raw submittal payload
  directly (mirrors `project_rfi`). There is no history-diff requirement in this
  prompt (no `*_changed` signal), so `normalizers/submittal.py` was left
  untouched.
- **No migration / V7 change.** All target tables already exist in V7. Migration
  version stays at **7**; endpoint registry stays at **27** (no count/version
  test churn).
- **No live GETs, no writeback.** Pure local projection over already-synced raw.

## Files

### Created
- `src/hb_assistant/store/procore_submittal_projection.py` — `project_submittal()`
  enrichment projection.
- `tests/test_procore_submittal_projection.py` — 8 tests.

### Modified
- `src/hb_assistant/procore/live_sync.py` — import `project_submittal`; added a
  guarded post-upsert dispatch block for `adapter.endpoint_id == "submittals"`
  (immediately after the RFI block), matching the inspection / meeting / RFI
  pattern. A projection failure only appends `submittal_projection_error` to the
  redacted receipt and never breaks the latest-state upsert.

## Projection mapping

Record key: `tropical|submittals||<id>`. All writes are idempotent
(conflict-upsert / `INSERT OR IGNORE`); `raw_body_persisted = 0` is enforced by
the table CHECK constraints.

**Parent fields → entities / edges (`procore_record_edges`):**

| Raw field | Extractor | Edge type |
| --- | --- | --- |
| `submittal_manager` | `extract_people_refs` | `submittal_manager` |
| `received_from` | people if it has `login`, else company | `received_from` |
| `responsible_contractor` | `extract_company_refs` | `responsible_contractor` |
| `scheduled_task` | record→record (`schedule-tasks`) | `scheduled_task` |
| `custom_fields` | `extract_custom_field_values` | — (`procore_custom_field_values`) |

Scalar parent fields (`formatted_number`, `current_revision`, `revision`,
`is_rejected`, `for_record_only`, `issue_date`, `required_on_site_date`,
`received_date`, `specification_section`) are carried as `metadata_json` on the
primary status action signal — no raw body persisted.

**Approvers (`raw["approvers"]`, also accepts `submittal_workflow` /
`workflow_data`):** user entity → `extract_people_refs` + an `approver` edge whose
`metadata_json` carries the workflow-duration metrics
`{approver_type, workflow_group, response_name, response_considered,
response_required, sent_date, returned_date, due_date, days_to_respond}`
(`days_to_respond` is the provided value or computed sent→returned, falling back
to sent→now). Approver `attachments` + `attachment_ids` → `extract_attachment_refs`
(path-only; signed-URL query strings dropped). Non-empty approver `comment` →
encrypted text intelligence (`store_encrypted=True`, `excerpt_chars=160`).

**Inline responses (`raw["responses"]`):** author → people ref + `response_author`
edge; non-empty `comment` → encrypted text intelligence; a non-pending
`response_status` marks the submittal as returned.

## Required action signals

| Signal | Condition |
| --- | --- |
| `submittal_open` | status not approved / rejected / terminal |
| `submittal_overdue` | open and `due_date` < now |
| `submittal_rejected` | `is_rejected` truthy or status contains `reject` |
| `submittal_approved` | status contains `approv` |
| `submittal_waiting_on_approver` | open and an approver `response_required` with no `returned_date` |
| `submittal_required_on_site_date_near` | `required_on_site_date` within 14 days of now |
| `submittal_response_returned` | any approver/response has been returned |

## Redaction / safety guarantees

- People PII (login / name) reduced to a SHA-256 prefix; raw login/name never
  stored (asserted in tests).
- Attachment URLs reduced to path-only + hash; query strings (signed tokens) never
  persisted (asserted: `?` / `token=secret` absent).
- Free text (approver/response comments) stored as hash + length + PII-masked
  excerpt; full text only in the encrypted vault outside the repo.
- String custom-field values reduced to a hash (`secret cost note` absent;
  asserted); only safe typed values (boolean/integer/decimal/datetime/lov) kept
  verbatim.

## Validation

- `python -m pytest -q tests/test_procore_submittal_projection.py` → **8 passed**.
- `python -m pytest -q --no-header` → full suite **green** (pre-existing skips
  only; endpoint count 27, migration version 7 unchanged).
- `ruff check .` → **All checks passed**.
- `mypy .` → **Success: no issues found in 197 source files**.
- `python -m compileall -q src tests` → **OK**.
- `hb-assistant diagnostics scan-sensitive --repo . --json` → **0 findings** in the
  newly created / edited files (projection, test, `live_sync` block).
