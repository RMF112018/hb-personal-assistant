# Phase 04B Prompt 06 — RFI & RFI-Response Enrichment

**Date:** 2026-05-29 · **Modules:** `src/hb_assistant/store/procore_rfi_projection.py`,
`src/hb_assistant/procore/normalizers/rfi.py` (extended) · **Wiring:** `src/hb_assistant/procore/live_sync.py`.

## Summary

Captures RFI questions/answers, responsibility, official-answer state, cost/schedule impacts, and
record relationships. RFIs have no dedicated V7 tables, so enrichment lands in the cross-cutting
tables (people/company/attachment/edges/action_signals/text_intelligence). Replies are projected from
the orchestrator's inline `replies` under the parent `rfis` record. Wired into the `rfis` endpoint
(after latest-state upsert + Prompt-02 history, guarded).

## RFI normalizer extension (additive, `normalizers/rfi.py`)

`normalize_rfi` now also captures structured/derived fields in `canonical_fields`: `full_number`,
`prefix`, `revision`, `current_revision`, `has_revisions`, `location_id`, `translated_status`,
`time_resolved`, `private`, `priority_name`, opaque ids `received_from_id` /
`responsible_contractor_id` / `rfi_manager_id`, `ball_in_court_id` + `ball_in_court_count`, and
`cost_impact_status`/`cost_impact_value` + `schedule_impact_status`/`schedule_impact_value`; `link`
added to the source-URL candidates. `normalize_rfi_reply` adds `official`, `answer_date`,
`created_by_id`, and reads the body from `plain_text_body`/`rich_text_body`. People remain opaque ids
only (no names/logins); bodies are still excluded from canonical. This gives latest-state visibility
**and** lets the Prompt-02 history diff detect `ball_in_court_changed` / `cost_impact_changed` /
`schedule_impact_changed` / `status_changed`.

## Projection (`procore_rfi_projection.py`)

- `project_rfi`: people/company edges — `received_from`/`rfi_manager`/`assignee`/`assignees[]`/
  `ball_in_court(s)`/`created_by` (hashed people) + `responsible_contractor` (company); question +
  proposed-solution text intelligence (hash + tokens + redacted excerpt + encrypted vault ref via
  `_scan_text`); inline replies → `project_rfi_response`.
- `project_rfi_response`: `plain_text_body`/`rich_text_body` text intelligence (encrypted);
  `attachments` → refs (path-only); `created_by_id` → person + edge; `response_to_rfi` edge; `official`
  → signals on the parent RFI.

## Action signals (8)

`rfi_open`, `rfi_overdue` ("overdue" in status/translated_status), `rfi_unanswered` (open + no official
reply), `rfi_answered` + `rfi_official_answer_added` (official reply), `rfi_cost_impact_flagged` /
`rfi_schedule_impact_flagged` (impact status not none/no_impact/tbd), and `rfi_ball_in_court_changed`
(emitted when the history diff recorded a `ball_in_court_changed` change event for this record in this
sync).

## Tests (`tests/test_procore_rfi_projection.py`)

People/company edges with hashed people (raw login absent); question text intelligence (encrypted ref
decrypts to the question + `rfi:7` mentioned token); cost flagged / schedule not; official answer +
`response_to_rfi` edge + encrypted answer body + path-only attachment; `rfi_unanswered` when no
official reply; response projection without a parent; idempotency; and a `run_live_sync` `rfis`-twice
test asserting the `ball_in_court_changed` change event + `rfi_ball_in_court_changed` signal.

## Guardrails / validation

People hashed (ids/hashes only); contractor names kept as org labels; attachment URLs path-only;
question/answer prose → hash + tokens + redacted excerpt + encrypted vault ref; `raw_body_persisted=0`;
deterministic keys + conflict-upsert / INSERT OR IGNORE keep enrichment idempotent; guarded so it never
breaks latest-state/history; no schema change; existing RFI tests still pass after the additive
normalizer extension.

```
python -m pytest -q --no-header   # full suite green (1 pre-existing skip)
ruff check .                      # All checks passed
mypy .                            # Success: no issues found in 196 source files
python -m compileall src tests    # OK
```
