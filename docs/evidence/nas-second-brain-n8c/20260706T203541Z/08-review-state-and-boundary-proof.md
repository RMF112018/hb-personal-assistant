# N8C-8 — review-state & boundary proof

## Advisory posture (nothing auto-accepted)
- Every extracted record defaults to `status='candidate'` and `review_state='unreviewed'` (DB column
  defaults + model defaults); compilation-derived and question records default `needs_review`
  (`test_default_status_is_candidate_unreviewed`, `test_default_status_and_review_state`).
- `accepted`/`rejected`/`open`/`closed`/`operator_*` statuses are enum values RESERVED for a future
  operator-disposition slice — N8C-8 implements NO accept/reject/close/reopen workflow. The only
  lifecycle transitions are creation, explicit stale, and lineage-scoped supersede.

## No claim / memory mutation
- The extractor only READS claims — candidate claims stay `candidate`/`unreviewed` after apply
  (`test_claims_stay_candidate_unreviewed`). No claim auto-acceptance.
- The extractor only READS memory nodes/mentions/compilations — a memory node's status is unchanged
  after apply (`test_memory_node_status_unchanged`, node stays `active`).

## Writes confined to N8C-8-owned tables
- `preview` and `extract --dry-run` (`apply=False`) write nothing — every watched row count is unchanged
  (`test_preview_and_dry_run_are_read_only`; CLI smoke confirmed).
- `extract --apply` writes ONLY `assistant_decision_records` / `_preference_records` /
  `_open_loop_records` / `_decision_memory_events`; claim / enrichment / context-pack / memory / source
  tables are byte-for-byte unchanged (`test_apply_writes_only_n8c8_tables`; CLI smoke: non-N8C-8 tables
  unchanged after apply).

## Stale (explicit only)
- `DecisionMemoryRepository.mark_open_loop_stale` and `mark_open_loop_stale_if_needed` are the only
  stale paths — both explicit; no background scanner/scheduler exists
  (`test_decision_memory_repository.py::test_mark_open_loop_stale`).
