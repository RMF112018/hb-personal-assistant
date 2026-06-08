# 223. Phase 10A — Candidate review schema (V43)

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10A Candidate Review CLI Implementation Package (repo-truth update)

## Context

Phase 10A is adding an operator CLI to triage local-model action candidates
(`task_candidates` / `commitment_candidates`) before any downstream use. The
existing review path (`second-brain phase-10 review-candidate`) can only flip
`review_status` — it has nowhere to persist a snooze-until time, who/when a
candidate was reviewed, a redacted review note, or a structured edit diff that
the planned `snooze` / `edit` verbs and audit trail require. The audited head was
**V42**. This record covers the smallest additive migration (**V43**) that
unblocks snooze/edit/auditability. No data backfill, table rewrite, or behavior
change.

It also adds the `reviewer_ref` column to `candidate_review_events`, which the
existing `insert_candidate_review_event` repo method already references (a cause
of its current silent dead-write, flagged in the Prompt 00 rebaseline). Adding
the column is in scope here; reconciling the insert statement itself is a later
prompt.

## Decision

`SQLiteMigrator.V43_STATEMENTS` (`src/hb_assistant/store/migrator.py`), applied
by a **version-gated** block in `apply()` and recorded as
`v43_phase_10a_candidate_review`. The block is gated on the `schema_migrations`
version row (like V13/V15) because `ALTER TABLE ADD COLUMN` is **not** idempotent
— unlike the unconditional V41/V42 `CREATE … IF NOT EXISTS` blocks, re-running an
ungated ADD COLUMN raises "duplicate column name". `LATEST_SCHEMA_VERSION` bumped
42 → 43.

New columns (all **nullable `TEXT`, no CHECK** — SQLite cannot add CHECK via
ALTER, and the 13 `_P10_GUARDS` already protect these rows):

- `task_candidates`, `commitment_candidates` (mirror): `snoozed_until_utc`,
  `reviewed_utc`, `reviewed_by`, `review_note_redacted`.
- `candidate_review_events`: `changes_json_redacted` (structured edit diff,
  redacted), `snoozed_until_utc`, `reviewer_ref`.

Indexes (matching the existing `ix_*_review_status` style):
`ix_task_candidates_snoozed_until`, `ix_commitment_candidates_snoozed_until`.

## Verified

`pytest tests/test_phase_10_schema.py` — existing 21-table / 13-guard / idempotency
/ schema-status assertions still pass (they key off `LATEST_SCHEMA_VERSION`, not a
literal), plus a new `test_v43_candidate_review_columns_present` asserting the V43
columns via `PRAGMA table_info`. `tests/test_phase_10a_raw_content_review.py` and
`tests/test_phase_10a_batch_extraction.py` pass unchanged (added columns are
nullable; no upsert/extraction path touched).

## Guardrails / non-goals

Additive only; V1–V42 untouched. `changes_json_redacted` / `review_note_redacted`
are redacted holders — no raw bodies, payloads, prompts, responses, URLs, or
tokens. No extraction prompt/model/stable-key change, no fix to
`insert_candidate_review_event` (later prompt), no CLI verbs yet, no
`table_lifecycle_status_contract.json` change (it enumerates tables, not columns;
verified the schema suite stays green). No email send, calendar mutation, or
Graph/Procore/external writeback.
