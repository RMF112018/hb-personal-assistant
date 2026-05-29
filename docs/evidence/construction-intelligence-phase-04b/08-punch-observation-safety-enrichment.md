# Phase 04B — Prompt 08 — Punch, Observation & Safety Enrichment

**Date:** 2026-05-29
**Branch:** main
**Scope:** Improve safety/action memory from punch items and observations —
assignments, unresolved responses, location/trade/vendor edges, and text
intelligence.

## Scope decisions (deliberate)

- **No normalizer change.** Both projections read the raw payload directly
  (mirror `project_rfi` / `project_submittal`). Raw people/vendor dicts are passed
  to the redacting extractors (`extract_people_refs` hashes login/name), so
  reading raw upholds the redaction posture.
- **No migration / V7 change.** All target tables exist in V7. Migration version
  stays **7**; endpoint registry stays **27** (`punch-items` + `observations`
  already canonical).
- **No live GETs, no writeback.** Pure local projection over already-synced raw.

## Files

### Created
- `src/hb_assistant/store/procore_punch_projection.py` — `project_punch_item()`.
- `src/hb_assistant/store/procore_observation_projection.py` — `project_observation()`.
- `tests/test_procore_punch_projection.py` — 7 tests.
- `tests/test_procore_observation_projection.py` — 5 tests.

### Modified
- `src/hb_assistant/procore/live_sync.py` — import `project_punch_item` /
  `project_observation`; added two guarded post-upsert dispatch blocks for
  `adapter.endpoint_id == "punch-items"` and `== "observations"`, after the
  submittal block, matching the inspection / meeting / RFI / submittal pattern. A
  projection failure only appends a redacted receipt error (`punch_projection_error`
  / `observation_projection_error`) and never breaks the latest-state upsert.

## Punch projection mapping

Record key `tropical|punch-items||<id>`. All writes idempotent;
`raw_body_persisted = 0` enforced by the table CHECK constraints.

| Source | Extractor | Edge / target |
| --- | --- | --- |
| `location` (id/name/code/parent_id) | `extract_location_refs` | `at_location` (`procore_location_entities`, parent kept) |
| `trade` | `extract_company_refs` | `trade` |
| `ball_in_court` | `extract_people_refs` | `ball_in_court` |
| `created_by` (+ `company_name`) | `extract_people_refs` / `extract_company_refs` | `created_by` / `created_by_company` |
| `assignees` | `extract_people_refs` | `assignee` |
| `assignments[].login_information` | `extract_people_refs` | `assignee` (edge metadata: status/approved/notified_at/responded_at/manager_accepted_at) |
| `assignments[].vendor` | `extract_company_refs` | `vendor` |
| `assignments[].attachments` | `extract_attachment_refs` | path-only refs |
| `assignments[].comment` | encrypted text intelligence | — |
| `custom_fields` | `extract_custom_field_values` | — |
| `schedule_risk_reason`, `description` | encrypted text intelligence (`excerpt_chars=160`) | — |

Assignment-level (metadata-bearing) assignee edges are emitted **before** the
plain top-level `assignees` edge so that, when both reference the same person
(shared `edge_id`), the workflow metadata is the first write — the edge
`ON CONFLICT` clause does not overwrite `metadata_json`.

**Required punch signals:** `punch_overdue` (open and `due_date` < now),
`punch_due_tomorrow` (open and `due_date - now == 1` day),
`punch_unresolved_response` (`has_unresolved_responses` or an assignment
`status == "unresolved"`), `punch_assignment_waiting` (open and an assignment
notified with no `responded_at`). Cost/schedule impact carried as metadata on the
primary signal. Open = status not closed/completed and `closed_at` empty.

## Observation projection mapping

Record key `tropical|observations||<id>`.

| Source | Extractor | Edge / target |
| --- | --- | --- |
| `location` | `extract_location_refs` | `at_location` |
| `trade` | `extract_company_refs` | `trade` |
| `vendor` (raw or `assignee.vendor`) | `extract_company_refs` | `vendor` |
| `assignee` (dict or `assignee_id`) | `extract_people_refs` | `assignee` |
| `created_by` (dict or `created_by_id`; + `company_name`) | `extract_people_refs` / `extract_company_refs` | `created_by` / `created_by_company` |
| `custom_fields` | `extract_custom_field_values` | — |
| `description`, `rich_text_description`, `html_description` | encrypted text intelligence (`excerpt_chars=160`) | — |

**Safety classification:** `_is_safety(raw)` scans `type` / `subtype` / `status` /
`title` / `description` / `category` (each may be a string or a `{name|category}`
dict) for the safety token set (`safety, incident, injury, near-miss, near_miss,
near miss, unsafe, violation, ppe, fall, first aid, corrective`) — mirroring the
safety keyword set in `normalizers/observation.py`.

**Required observation signals:** `observation_open_safety` (open and safety),
`observation_high_priority` (`priority`/`severity` in high/urgent/critical),
`observation_closed` (closed or `closed_at` set), `observation_due_soon` (open and
`0 <= due_date - now <= 3` days). `{category, type, subtype, priority, severity,
personal, date_notified, safety}` carried as metadata on the primary signal.

## Redaction / safety guarantees

- People PII (login / name) reduced to a SHA-256 prefix; raw login/name never
  stored (asserted: punch `carl.contractor@example.com` and observation
  `super@example.test` absent from `procore_people_entities`).
- Attachment URLs reduced to path-only + hash; signed-URL query strings dropped
  (asserted: `?` / `token=secret` absent; `url_path_redacted == "/f/abc"`).
- Free text (descriptions, schedule-risk-reason, comments) stored as hash + length
  + PII-masked excerpt; full text only in the encrypted vault outside the repo.
- String custom-field values reduced to a hash (`secret custom value` absent).
- Organisation / place labels (company, trade, vendor, location names) kept
  verbatim — not personal PII (matches the existing inspection posture).

## Validation

- `python -m pytest -q tests/test_procore_punch_projection.py tests/test_procore_observation_projection.py`
  → **12 passed**.
- `python -m pytest -q --no-header` → full suite **green** (pre-existing skips
  only; endpoint count 27, migration version 7 unchanged).
- `ruff check .` → **All checks passed**.
- `mypy .` → **Success: no issues found in 199 source files**.
- `python -m compileall -q src tests` → **OK**.
- `hb-assistant diagnostics scan-sensitive --repo . --json` → **0 findings** in the
  newly created / edited files.
