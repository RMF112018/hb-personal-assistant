# Phase 09 — Vector Index Build (Apply) Proof

- proof_passed: True
- generated_utc: 2026-06-04T23:39:45.309062+00:00
- applied_run_id: vir_apply_1fe305b8bfc3aa7e059010d2bdf9136a
- applied_item_count: 3
- embedding_dim: 384
- vectors_written_outside_sqlite: True
- vectors_persisted_to_sqlite: False (must be false)
- run_record_guard_clean: True
- item_records_guard_clean: True
- no_forbidden_persisted_columns: True
- blocked_no_indexable_nodes: True
- blocked_sdk_absent: unit_tested

## Build-rule cases

- [ok] safe_node: expected_indexable=True indexable=True violations=0
- [ok] missing_review_tier: expected_indexable=False indexable=False violations=2
- [ok] missing_confidence: expected_indexable=False indexable=False violations=2
- [ok] missing_source_ref: expected_indexable=False indexable=False violations=2
- [ok] missing_freshness: expected_indexable=False indexable=False violations=2
- [ok] raw_shape_text: expected_indexable=False indexable=False violations=1
- [ok] non_embeddable_family: expected_indexable=False indexable=False violations=1
