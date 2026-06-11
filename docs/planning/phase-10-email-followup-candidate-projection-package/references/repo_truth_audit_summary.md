# Repo-Truth Audit Summary Used to Shape This Package

This package was generated after a connector-based repo-truth audit. Local repo and DB commands were not available in the GPT environment, so the local agent must rerun `prompts/00_repo_truth_audit.md` and all DB validation on Bobby's machine.

## Findings

1. Recent PR metadata shows PR 23 present as `feat(second-brain): activate source-linked daily brief projection sli…` and PR 22 present as `Fix/email calendar full raw content ingestion`.
2. PR 23 added an explicit `email_calendar_projection` stage to the Phase 10 local-agent pipeline. The stage runs before candidate-generation stages and does not consume candidate caps.
3. PR 23 added `projection_activation.run_email_calendar_projection_stage(...)`, which wraps the V49 projection engine and returns raw-free counts/statuses/reason codes.
4. PR 23 added/extended email follow-up data-gap classification: source email rows with empty follow-up/task/commitment/enrichment tables produce a data-gap card rather than silent success.
5. PR 22 added structured email/calendar projection registry and read models. The read models prefer structured rows over raw/legacy and expose `body_ref` / `load_body(...)` for audited raw access.
6. Central candidate persistence exists in `daily_brief_candidate_writer.persist_candidate_with_refs(...)`, deriving deterministic candidate and source-ref IDs and writing hashed source refs.
7. Source-ref gating exists in `source_ref_gate.py`; model-facing candidate context excludes candidates without refs.
8. The first slice usefulness gate checks source-row/candidate contradictions, including email rows without data-gap acknowledgment.
9. Existing validation evidence records a failure for `test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table`; the attached objective explicitly corrects the prior classification and requires this package to treat it as a deterministic/offline failure unless current repo truth proves otherwise.

## Design Consequence

The next slice should:

- consume structured V49 email/thread tables and read models;
- implement deterministic extraction first;
- persist domain rows and daily-brief rows;
- use the central source-ref writer;
- integrate with the daily run/status/usefulness gate;
- validate on `/tmp` DB copies only;
- add email-specific no-raw-leak proof.
