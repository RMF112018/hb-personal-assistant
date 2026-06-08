# 13 Testing Plan

## New tests to add

- `tests/test_phase_10a_candidate_review.py`
- `tests/test_phase_10a_candidate_review_cli.py`

## Existing tests to preserve

- `tests/test_phase_10a_batch_extraction.py`
- `tests/test_phase_10a_packet_extraction_safety.py`
- `tests/test_phase_10a_raw_action_intelligence.py`
- `tests/test_phase_10_schema.py`
- `tests/test_phase_08d_no_raw_access.py`
- `tests/test_phase_08d_no_writeback.py`
- `tests/test_second_brain_no_writeback_proof.py`

## Required coverage

1. `review list`: pending task/commitment candidates, filters, sorting, snoozed exclusion policy.
2. `review show`: fields, source refs/evidence redacted, no raw body/prompt/response/tokens/URLs.
3. `review accept`: status update, review event, guard columns unchanged.
4. `review ignore/reject`: status update, note storage, event insertion.
5. `review edit`: enum validation, audit trail, source linkage preserved.
6. `review snooze`: snooze metadata and summary behavior.
7. `review summary`: grouped counts.
8. CLI errors: unknown ID, invalid enum, unsupported type.
