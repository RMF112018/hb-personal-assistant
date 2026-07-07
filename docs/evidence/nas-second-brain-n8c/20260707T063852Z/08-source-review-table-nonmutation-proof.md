# 08 — Source + Review Table Non-Mutation Proof

The builder READS the review overlay and advisory records and WRITES only the four projection tables. Two
tests prove this with before/after snapshot digests across **preview, dry-run, and apply**.

## Snapshot set (`_PROTECTED`)

Both the review overlay and the upstream source-advisory tables are digested:
```
assistant_review_items, assistant_review_dispositions, assistant_review_events,
assistant_claims, assistant_context_pack_items, assistant_decision_records,
assistant_preference_records, assistant_open_loop_records, assistant_memory_nodes,
assistant_enrichment_receipts
```
`_snapshot(db)` = `{table: sha256(repr(SELECT * ORDER BY 1))}` for each.

## Proof 1 — full protected set unchanged (`test_preview_and_dryrun_and_apply_do_not_mutate_review_or_source`)

```
before = _snapshot(db)
preview_intelligence_projection(...)                        ; assert _snapshot(db) == before
build_intelligence_projection(..., apply=False)             ; assert _snapshot(db) == before
res = build_intelligence_projection(..., apply=True)        ; assert _snapshot(db) == before
assert res["applied"] and res["created"]                    # projection persisted
assert irepo.count() == 1                                   # ... into projection tables only
```
Every protected table's digest is identical before and after all three operations, while the projection
was still persisted — proving the writes landed only in the projection tables.

## Proof 2 — disposition + event ledgers specifically unchanged (`test_dispositions_and_events_unchanged_by_apply`)

An explicit before/after over the two append-only ledger tables specifically:
```
before = (repr(SELECT * FROM assistant_review_dispositions ORDER BY 1),
          repr(SELECT * FROM assistant_review_events ORDER BY 1))
build_intelligence_projection(..., projection_type=TRUSTED_CONTEXT, apply=True)
assert (dispositions, events) == before
```
This directly satisfies clarification #8: the projection never writes back a disposition or a review event.

## Repository-level guarantee

`IntelligenceProjectionRepository` issues INSERT/UPDATE only against
`assistant_intelligence_projections` / `_items` / `_receipts` / `_events`. Its supersede/stale logic
(file 07) updates only projection-owned rows. All read methods are `conn=`-threaded so they can run against
the MCP read-only snapshot (`mode=ro&immutable=1` + `PRAGMA query_only=ON`).
