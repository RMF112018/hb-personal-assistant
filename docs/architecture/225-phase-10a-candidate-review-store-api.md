# 225. Phase 10A — Candidate review store API + review-event drift fix

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10A Candidate Review CLI Implementation Package (repo-truth update)

## Context

Records 223 (V43 columns) and 224 (review service) landed the schema and the
service layer. This record formalizes the **store-layer candidate API** the
package envisions and closes the last of the `candidate_review_events` drift
flagged in the Prompt 00 rebaseline.

Two gaps remained after 224: the service located a candidate by scanning up to
100k rows through the list helpers (no primary-key getter existed), and
`insert_candidate_review_event` — though already schema-correct — still wrapped its
INSERT in `try/except … return None`, silently swallowing failures. The review
event is required evidence, not optional telemetry, so the swallow had to go.

## Decision

### Store (`construction/store/repositories.py`)
- **Getters:** `get_task_candidate(id)` / `get_commitment_candidate(id)` —
  single-row `SELECT … WHERE candidate_id = ?` over the safe, review-relevant
  column projection (incl. the four V43 columns; never the guard columns); column
  names derived from `cursor.description` so there is no second hard-coded key
  tuple to drift. `get_candidate(id, *, candidate_type=None)` resolves the row and
  tags it with `candidate_type` (task tried first, then commitment, when type is
  omitted).
- **Merge:** `list_review_candidates(*, status=None, project_key=None, limit=100)`
  concatenates the two per-type list methods (each row tagged `candidate_type`) and
  caps the combined result — centralizing the merge previously done in the service.
- **Rename:** `set_candidate_review_status` → `update_candidate_review_state`
  (identical signature incl. the optional V43 lifecycle params), giving a coherent
  `update_candidate_*` family alongside `update_candidate_fields`. All three callers
  updated (CLI `phase-10 review-candidate`, the review service, one
  `raw_content_review` test); no alias retained.
- **Drift fix:** `insert_candidate_review_event` no longer swallows — the INSERT
  runs inside `transaction(conn)` and propagates on failure; return type is now
  `str` (the `review_event_id`). The `candidate_review_events` table is always
  present (V41, migrated in the store ctor), so the old "table may be absent"
  rationale no longer applies.

### Service (`local_ai/candidate_review.py`)
Refactored to consume the new API and drop the O(100k) scan: `_find_candidate`
is now a thin wrapper over `store.get_candidate`; `review_summary`,
`list_review_candidates`, and `export_review_queue` use `store.list_review_candidates`
(the service retains enum validation, per-type/combined counts, and response
shaping); the decision path calls `store.update_candidate_review_state`. Behavior
is unchanged — the existing service tests pass untouched.

### CLI (`cli/second_brain.py`)
`phase-10 review-candidate --emit` calls the renamed updater and now passes
`prior_status`/`new_status` to the audit insert (a complete audit row). The audit
insert propagates on failure, surfaced by the command's existing outer error
handling (exit 1) — no new silent swallow introduced.

## Verified

`pytest tests/test_phase_10a_candidate_review.py tests/test_phase_10a_raw_content_review.py`
(21 tests) — getters (found/None), `get_candidate` resolution (auto / explicit
mismatch / missing), `list_review_candidates` merge+filters,
`update_candidate_review_state` lifecycle columns + unknown-id no-op,
`update_candidate_fields` whitelist (disallowed `stable_key`/`review_status` keys
ignored; all-disallowed → `False`), and **`insert_candidate_review_event`
propagation** (`sqlite3.IntegrityError` on a NULL `action`). `mypy` clean (service
in strict `second_brain.*` scope); `ruff` clean. Regression suites
(`batch_extraction`, `schema`, `packet_extraction_safety`) unchanged; the one
failing `test_commitment_persists_to_commitment_table` is pre-existing on clean
`main`, not a regression.

## Guardrails / non-goals

No new migration; no change to extraction prompt/model/stable-key behavior; no
packet-scope broadening. Read methods return only redacted/safe columns; review
actions are local DB updates only; source refs immutable. No email send, calendar
mutation, or Graph/Procore/external writeback; no raw body/prompt/response/URL/
token read or emitted.
