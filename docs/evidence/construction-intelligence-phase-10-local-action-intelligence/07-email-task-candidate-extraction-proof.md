# Phase 10 Prompt 07 — Email Task Candidate Extraction Proof

**Status:** clean · **proof_passed:** True · **generated_utc:** 2026-06-08T07:50:30.783088+00:00

- repo_sha: `cf75fd33c33f948e0b9ec4d1e9f4d3db2cf95774`
- schema_version: V42
- guard_sum: 0 (must be 0)
- dry_run_task_rows: 0 (must be 0)

## Gates

| Gate | Pass |
| --- | --- |
| deterministic_signals_fire | True |
| success_yields_task | True |
| invalid_schema_rejected | True |
| stale_forbidden_field_rejected | True |
| no_accept_without_source_refs | True |
| unavailable_backend_surfaced | True |
| bounded_content_policy_gated | True |
| dry_run_zero_writes | True |
| apply_persists_candidate | True |
| guards_clean | True |
| no_raw_persistence | True |
| source_ref_linkage | True |
| contract_module_parity | True |

## Deterministic signals (fixtures)

| Scenario | Reason codes | Matched |
| --- | --- | --- |
| commitment_sent_by_user | due_date, waiting_on_others, project_source_confidence | True |
| follow_up_stale | unanswered_question, follow_up_stale, project_source_confidence | True |
| low_signal | low_signal | True |
| task_direct_ask_due | direct_ask, due_date, waiting_on_me, unanswered_question, project_source_confidence | True |

## Guardrails

Local-only deterministic-signal + structured-output extractor over metadata-safe email thread summaries; advisory and dry-run by default; bounded_content mode is policy-gated and reads local content only ephemerally (never persisted); only structured candidate fields, source refs, hashes, reason codes, and policy-approved bounded excerpts are written; the 13 no-raw/ no-writeback guard columns sum to 0; high-stakes items stay review-only; summary fixtures live in a subdirectory excluded from the ai_jobs glob.
