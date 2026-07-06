# N8C-8 — provenance & idempotency proof

## Provenance (every record source-backed)
- DB backstop: a table CHECK on all three record tables requires ≥1 provenance anchor
  (`test_decision_memory_v104_migration.py::test_provenance_check_enforced`).
- Model backstop: `to_row()` raises `DecisionMemoryValidationError("record_without_provenance")` before
  write when no anchor is present (`test_decision_memory_repository.py::test_record_requires_provenance`).
- Every extracted record carries an anchor + bounded evidence excerpt
  (`test_decision_memory_extractor.py::test_every_record_has_provenance_and_bounded_evidence`).
- `anchor_key` precedence makes identity robust when `source_id` is absent (falls back to
  `claim_id`, …) — `test_anchor_key_falls_back_when_source_absent`.

## Deterministic ids
- `decision_id` / `preference_id` / `open_loop_id` are deterministic — identical inputs → identical id
  (`test_decision_id_determinism`, `test_preference_and_open_loop_id_determinism`).

## Idempotency
- Same inputs → no duplicate: re-`upsert` of the same id is a `reused` no-op; count stays 1
  (`test_upsert_idempotent_no_duplicate`). Re-running the full extractor over an unchanged pack creates
  0 new records and 0 supersessions (`test_decision_memory_extractor.py::test_apply_is_idempotent`).

## Changed evidence → new record + lineage-scoped supersede
- A changed evidence digest for the SAME lineage yields a new record; the prior `candidate` of that
  `identity_key` is marked `superseded` (statuses become `["candidate","superseded"]`) —
  `test_changed_evidence_supersedes_same_lineage`. A `superseded` event is logged.
- **Independent corroborating sources coexist:** the same subject+decision from a DIFFERENT source
  lineage gets a different `identity_key` and is NOT superseded — both remain active candidates
  (`test_independent_sources_coexist`). This is the explicit rule: supersede only within the same
  identity + provenance lineage on an evidence change; never auto-obsolete independent sources.
- No silent overwrite: an existing id is never rewritten (returns `reused`); only status transitions
  (supersede/stale) mutate an existing row, each with a logged event.
