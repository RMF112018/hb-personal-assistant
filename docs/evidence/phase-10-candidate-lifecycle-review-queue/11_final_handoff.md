# Final Handoff

## Summary

- Manifest: Phase 10 Candidate Lifecycle, Review Queue & Feedback Read Model (247 v1)
- Branch: `feature/phase-10-candidate-lifecycle-review-queue`
- Commit SHA: `66157658d88265480d350678ac6826e2764e8986` (implementation commit)
- Base: `feature/phase-10-email-followup-candidate-projection` (== `origin/main` @ `512d103f`)
- Merge target: `main`
- Merge readiness: Merge-ready

## Changed files

```text
src/hb_assistant/store/migrator.py                                              (V50 additive migration + LATEST_SCHEMA_VERSION 49->50)
src/hb_assistant/construction/store/repositories.py                            (lifecycle/merge/suppression store helpers)
src/hb_assistant/construction/second_brain/local_ai/candidate_lifecycle.py             (new)
src/hb_assistant/construction/second_brain/local_ai/candidate_lifecycle_read_model.py  (new)
src/hb_assistant/construction/second_brain/local_ai/candidate_lifecycle_duplicates.py  (new)
src/hb_assistant/construction/second_brain/local_ai/candidate_lifecycle_feedback.py    (new)
src/hb_assistant/construction/second_brain/local_ai/candidate_lifecycle_daily_brief.py (new)
src/hb_assistant/construction/second_brain/local_ai/usefulness_gate.py         (opt-in lifecycle_context checks)
src/hb_assistant/construction/second_brain/local_ai/daily_run.py               (apply-run lifecycle stage context wiring)
src/hb_assistant/cli/second_brain.py                                           (additive `candidates` Typer group)
tests/test_phase_10_candidate_lifecycle_read_model.py                          (new)
tests/test_phase_10_candidate_lifecycle_operations.py                          (new)
tests/test_phase_10_candidate_duplicate_merge.py                               (new)
tests/test_phase_10_candidate_lifecycle_feedback.py                            (new)
tests/test_phase_10_candidate_lifecycle_daily_brief.py                         (new)
tests/test_phase_10_candidate_lifecycle_usefulness_gate.py                     (new)
tests/test_phase_10_candidate_lifecycle_cli.py                                 (new)
tests/test_phase_10_candidate_lifecycle_no_raw_leak.py                         (new)
tests/test_email_calendar_full_raw_content_ingestion.py                        (version-pin decoupled from literal 49)
docs/architecture/phase-10-candidate-lifecycle-review-queue.md                 (new)
docs/evidence/phase-10-candidate-lifecycle-review-queue/*                       (new evidence bundle 00-11)
docs/planning/phase-10-candidate-lifecycle-review-queue-package/*               (source package)
```

## Implementation summary

- Lifecycle/read model: append-only V50 overlay extends per-family review status; unified raw-safe
  review queue computed across all six families (no materialized queue table; no dual truth).
- Schema/migration: additive V50 (`candidate_lifecycle_events`, `candidate_merge_links`,
  `candidate_suppression_rules`), each with the 13 `CHECK(=0)` guard columns; idempotent re-apply.
- Disposition operations: accept/reject/snooze/close/reopen/merge/suppress — local-DB-only,
  idempotent, raw-safe; task/commitment delegate to the canonical `candidate_review` service.
- Promotion/source refs: explicit, idempotent (`acc-task:{cid}` / `acc-commit:{cid}`),
  source-ref gated; refs preserved via the candidate-id link (read-model join).
- Duplicate/merge/suppression: deterministic group keys (raw-free); merge hides source + preserves
  refs; group suppression hides recurring members; reversible.
- Feedback read model: deterministic raw-safe counts/rates/reason-codes/confidence-buckets.
- Daily brief integration: lifecycle-aware sections; hidden states excluded + counted; snooze
  returns on date; source-missing withheld.
- Usefulness gate/status: opt-in lifecycle contradictions; wired into apply runs.
- CLI/operator surface: additive `second-brain candidates` group; `review` verbs unchanged.
- Raw-safety hardening: `scrub_note` (URL/email/token/HTML) for notes + defensive read-model
  re-scrub; group keys hash only normalized redacted titles.

## Validation

| Check | Result | Evidence |
|---|---|---|
| Compile | PASS (`python -m compileall src tests`) | this run |
| Ruff | PASS (lifecycle modules, gate, CLI, store, migrator, tests) | this run |
| mypy (strict scope) | PASS (7 lifecycle/gate/daily_run source files) | this run |
| Targeted pytest (new) | PASS (8 new files) | 02–09 |
| Existing Phase 10A review regression | PASS (no regressions) | this run |
| DB integrity on `/tmp` copy | `ok` before + after | 10 |
| Migration check | V50 applies + idempotent re-apply | 10 |
| Idempotency replay | no new events on replay | 03, 05, 10 |
| No-raw-leak scan | PASS (0 matches; structured test pass) | 09 |
| Usefulness gate | lifecycle contradictions fail honestly | 08 |
| Rendered daily brief | raw-safe markdown | 07 |

## DB-copy validation results

- Production DB copied from: `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- Copy path: `/tmp/hb-phase10-candidate-lifecycle-validation-20260611-154632/validation-copy.sqlite`
- Production DB SHA before: `d0c3e52a15b9dbdf65174f9347e1c596ed97ca2098e167902d94406a9ceccdb7`
- Production DB SHA after:  `d0c3e52a15b9dbdf65174f9347e1c596ed97ca2098e167902d94406a9ceccdb7`
- Integrity check: `ok` (before + after)
- Migration result: applied 50; re-applied 50 (idempotent)
- Candidate counts: 6 synthetic seeded into the copy (prod plain-root has 0 Phase 10 candidate rows)
- Review queue counts: total 7, visible-default 1 (source-missing withheld)
- Lifecycle transition counts: 6 events; counts-by-state accepted 1 / rejected 1 / snoozed 1 / closed 1 / merged 1
- Accepted task count: 1
- Accepted commitment count: 0
- Rejected count: 1 · Snoozed count: 1 · Merged count: 1 · Suppressed count: 0 · Closed count: 1 · Reopened: exercised (see 03)
- Source-ref coverage: gate-enforced; one deliberate source-missing row surfaced as `source_missing`
- Project-key coverage: `project_review_required` surfaced for null-project candidate families
- Duplicate/idempotency result: replay adds no new events; merge replay no-op
- Guard-column result: sum = 0 across the 3 V50 tables
- Raw access event delta: 0 (no raw content read or persisted by the slice)

## Usefulness / status

- Lifecycle gate result: contradictions detected and surfaced (`lifecycle_source_ref_coverage_below_100` on the source-missing fixture)
- Daily-brief lifecycle status: hidden states excluded + counted; source-missing withheld; snooze returns on date
- Degraded/withheld reasons: source-missing actionable rows withheld with explicit status
- Data-gap cards: source-missing surfaced; project-review-required surfaced
- Known lifecycle contradictions: none unhandled

## Raw-safety statement

No raw email body, raw HTML, recipient array, attendee array, private/join/signed URL, token,
model prompt/response, or raw Procore detail leaked into any output or evidence. Verified by the
structured no-raw-leak test and an rg scan over the evidence bundle (0 matches).

## Production safety statement

The production DB and all external systems were NOT mutated. All apply/idempotency checks ran on a
`/tmp` copy; the production DB SHA-256 is identical before and after. No Graph/Procore/email/
calendar/SharePoint/OneDrive/Obsidian writeback occurred.

## Known failures / limitations

- **Pre-existing (not this slice):** the `test_v*_tables_classified_in_lifecycle_contract` family
  and `test_second_brain_no_writeback_proof` / `test_phase_08b_gate_coverage::test_no_writeback_proof_passes_at_latest_schema`
  / `test_procore_endpoint_structured_projection_remediation::test_v47_schema_head_and_tables_present`
  assert a GLOBAL "every DB table is classified in `table_lifecycle_status_contract.json`" invariant.
  The V49 email/calendar PR added ~16 tables to the DB without registering them in that governance
  contract, so these tests are already RED on clean base `512d103f` (verified in a base worktree:
  `in_db_not_in_contract` lists `calendar_raw_event_*` / `email_raw_*` / `email_calendar_*`). This
  slice's 3 V50 tables lengthen that same unclassified list but cause **no new red/green transition**.
  Reconciling the contract (registering the ~16 V49 tables + the 3 V50 tables, bumping `table_count`,
  and cascading the `== 347` count literals across 13 test files) is a standalone governance cleanup,
  intentionally out of scope here; partially editing the contract would break the currently-passing
  `test_data_quality_table_inventory` count assertion. Recommended as a follow-up V49/V50 contract
  reconciliation PR.
- The plain-root production DB carries 0 Phase 10 candidate rows (the dev scheduler writes the
  `(Dev)` root), so DB-copy lifecycle behavior was validated with synthetic rows seeded into the
  copy. Functional behavior is fully covered by the pytest fixtures.
- `follow_up_watch` source-ref coverage is treated as inherited (not_applicable) from its accepted
  item rather than independently recomputed.

## Merge readiness statement

`Merge-ready`
