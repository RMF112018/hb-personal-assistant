# Priority 3 — Deterministic Candidate Projection + Source Refs (Prompt 03)

## What changed (Refinement 3 — central persistence contract)

- **New** `src/hb_assistant/construction/second_brain/local_ai/daily_brief_candidate_writer.py` —
  the single persistence contract:
  - `persist_candidate_with_refs(store, *, brief_date, section, title_redacted, confidence,
    group_key, source_refs, project_key, priority, reason_redacted, recommended_next_action)`
    derives the candidate id (delegating to the store's shared `daily_brief_action_candidate_id_for`),
    inserts the candidate (idempotent), and upserts one `candidate_source_refs` row per source ref —
    **hash-only** (`sha256` of the deterministic ref), `candidate_type="daily_brief_action"`,
    idempotent ref id from `(candidate_id, family, ref)`. Returns a `CandidateWriteReceipt`.
  - `candidate_source_ref_coverage(store, *, brief_date, section=None)` computes per-brief coverage
    (total / covered / ratio / uncovered ids) used by Priorities 4 and 5.
- **Routed both stages through the writer** (no per-stage hand-rolling of ids, ref hashing, or
  idempotency): `calendar_prep.py` and `procore_digest.py` now call `persist_candidate_with_refs`
  with their in-memory `source_refs` (calendar → `calendar_event_raw_content`; procore →
  `procore_action_signals`). This closes the audit's `candidate_source_ref_coverage = 0.0` gap — the
  refs table was never written before.

## Why this fixes the audit

`candidate_source_refs` existed with an idempotent upsert, but no projection stage wrote it, so
coverage was 0.0 and the model could emit "source-looking" bullets with nothing underneath. Routing
persistence through one writer means every persisted candidate is source-linked; the gate (P4) can
require it.

## Tests

- `tests/test_phase_10_daily_brief_candidate_projection.py` — 6 passed:
  - calendar apply persists candidate + 1 source ref (project_key=`tropical` via category resolution);
  - calendar coverage = 1.0 after apply;
  - procore apply persists candidate + 1 source ref (`procore_action_signals`);
  - writer idempotency (no duplicate candidate or ref on repeat);
  - empty-source coverage graceful (vacuous 1.0; the usefulness gate handles "no candidates");
  - a ref-less data-gap row is correctly counted as uncovered (coverage 0.0).
- `tests/test_phase_10_calendar_meeting_prep.py` + `test_phase_10_procore_digest.py` +
  `test_phase_10_procore_ranking.py` + `test_phase_10_calendar_category.py` — all green (no regression).
- `ruff check` on changed files: clean.

Idempotency + hash-only refs verified; coverage is now computable and non-zero. Full DB-copy proof in
`06-db-copy-live-proof/`.
