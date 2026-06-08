# 224. Phase 10A — Candidate review service layer

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10A Candidate Review CLI Implementation Package (repo-truth update)

## Context

Phase 10A adds an operator workflow to triage local-model action candidates
(`task_candidates` / `commitment_candidates`) before downstream use. This record
covers the **service layer** — pure functions holding all review business logic so
the later Typer verbs stay thin. It sits on the V43 columns added in record 223
(`snoozed_until_utc`, `reviewed_utc`, `reviewed_by`, `review_note_redacted` on the
candidate tables; `changes_json_redacted`, `snoozed_until_utc`, `reviewer_ref` on
`candidate_review_events`).

The current store surface could not express the nine required operations: the
candidate list SELECTs omitted the V43 columns, `set_candidate_review_status`
wrote only `review_status`/`updated_utc`, there was no targeted edit UPDATE, and
`insert_candidate_review_event` was the dead write flagged in the Prompt 00
rebaseline (it inserted `event_id`/`decision` against a table whose columns are
`review_event_id`/`action`/…). Prompt 00 assigned that reconciliation to the
review-CLI phase; this is it. The store changes are additive and backward
compatible with the existing `phase-10 review-candidate` caller.

## Decision

### Store (`construction/store/repositories.py`, additive/surgical)
- `list_task_candidates` / `list_commitment_candidates` SELECTs + returned key
  tuples extended with the 4 V43 lifecycle columns (additive keys; no test asserts
  an exact key-set).
- `set_candidate_review_status` gains optional `reviewed_utc` / `reviewed_by` /
  `review_note_redacted` / `snoozed_until_utc`, written via a dynamically built
  `SET` clause only when provided — legacy 3-arg callers unchanged.
- New `update_candidate_fields(*, candidate_type, candidate_id, fields)` — targeted
  UPDATE whitelisted to `{title_redacted, assignee_class, commitment_actor_class,
  waiting_state}`; always bumps `updated_utc`; never touches `stable_key`, review
  status, source refs, or guard columns.
- `insert_candidate_review_event` rewritten to the real V41+V43 schema
  (`review_event_id, candidate_type, candidate_id, action, prior_status,
  new_status, user_note_redacted, reviewer_ref, changes_json_redacted,
  snoozed_until_utc, created_utc`). Existing params `decision`→`action`,
  `reason_redacted`→`user_note_redacted` preserved; optional status/diff/snooze
  params added. The audit row now actually persists (the existing phase-10 caller
  benefits automatically).

### Service (`construction/second_brain/local_ai/candidate_review.py`, new)
Keyword-only pure functions taking an injected `ConstructionStore`, returning safe
dicts. Enums validated against the canonical `ReviewStatus` / `Assignee` /
`WaitingState` Literals from `local_ai/models.py` via `typing.get_args`. Notes and
edit diffs bounded with the shared `_truncate` helper.

- Read-only: `review_summary`, `list_review_candidates`, `show_review_candidate`
  (includes immutable source refs).
- Decisions (status transition + V43 lifecycle columns + audit row):
  `accept_candidate` (`accepted`), `reject_candidate` (`rejected`),
  **`ignore_candidate` → stored `suppressed`** (the operator-verb normalization),
  `snooze_candidate` (ISO-8601 `until`, validated), `edit_candidate`
  (title/assignee/waiting_state; records a redacted before/after diff; leaves
  `review_status` and source refs untouched).
- `export_review_queue` returns the safe queue payload (candidates + source refs);
  file writing is deferred to the CLI layer.

## Verified

`pytest tests/test_phase_10a_candidate_review.py` (12 tests) — summary counts,
list+filter+enum-reject, show found/not-found with refs, accept lifecycle columns
+ audit row (`action`/`prior_status`/`new_status`), `ignore→suppressed`, snooze
persists `snoozed_until_utc` (+ bad-timestamp ValueError), edit updates fields /
records diff / preserves refs+status / maps commitment actor class / validates
enums, export safety, and a recursive no-forbidden-key assertion across every
output. `mypy` clean (module is in the strict `second_brain.*` scope); `ruff`
clean. Regression suites (`raw_content_review`, `batch_extraction`,
`email_task_extraction`, `schema`, `packet_extraction_safety`,
`raw_extraction_hardening`) unchanged — the one failing
`test_commitment_persists_to_commitment_table` is a pre-existing failure on clean
`main` (verified by stashing the store change), not a regression.

## Guardrails / non-goals

No CLI/Typer verbs yet; no change to extraction prompt/model/stable-key behavior;
no broadening of packet scope. Review actions are local DB updates only; source
refs immutable. No email send, calendar mutation, or Graph/Procore/external
writeback. No raw body/prompt/response/URL/token read or emitted (candidate rows
expose only redacted fields; notes/diffs truncated). No new migration; no
`table_lifecycle_status_contract.json` change.
