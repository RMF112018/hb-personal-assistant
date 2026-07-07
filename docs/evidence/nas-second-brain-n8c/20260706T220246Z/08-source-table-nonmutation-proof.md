# 08 — Source-table nonmutation proof

N8C-9 writes ONLY the three review-overlay tables: `assistant_review_items`,
`assistant_review_dispositions`, `assistant_review_events`. It reads every source advisory table via
read-only queries and never mutates them.

## Before/after digest checks (`tests/test_review_builder.py`)
`_snapshot(db)` computes a SHA-256 over the full row content of each source table:
`assistant_claims, assistant_context_pack_items, assistant_context_packs, assistant_decision_records,
assistant_preference_records, assistant_open_loop_records, assistant_enrichment_receipts,
assistant_memory_nodes`.

- `test_preview_is_read_only`: preview writes 0 review rows and leaves the source snapshot identical.
- `test_build_apply_idempotent_and_nonmutating`: a second `build --apply` leaves the source snapshot
  identical (digest equality) and creates 0 new review rows.
- `test_claims_and_decisions_remain_candidate`: after build, every `assistant_claims` row stays
  `status=candidate`/`review_state=unreviewed`, and every `assistant_decision_records` row stays
  `status=candidate`/`review_state=unreviewed` — building a review item never accepts the source.

## Disposition nonmutation (`tests/test_review_repository.py`)
- `test_disposition_does_not_mutate_item_columns`: recording a disposition does not change the review
  item's stored columns and (by construction) touches no source table.

## Read-only DB snapshot for MCP (`tests/test_nas_mcp_review.py`)
- `test_snapshot_is_read_only`: the MCP snapshot (`mode=ro&immutable=1` + `PRAGMA query_only=ON`) raises
  `sqlite3.OperationalError` on any `UPDATE assistant_review_items` — physically cannot write.
