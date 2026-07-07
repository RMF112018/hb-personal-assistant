# 07 — Idempotency & digest proof

## Deterministic review item id
`review_item_id = sha256(target_kind | target_id | target_digest | review_type | "review-queue-v1")[:24]`.
`target_digest` folds the target's content digest AND state digest, so a review item is one snapshot per
target state.

- `test_review_repository.py::test_review_item_id_deterministic`: same inputs → same id; changed
  `target_digest` → different id.
- `test_upsert_idempotent`: upserting the same row twice → `created` then `reused`, count stays 1.

## Lineage-scoped supersede (changed digest)
On a changed `target_digest`, the new id supersedes ONLY prior items of the SAME
`(target_kind, target_id, review_type)` lineage that are still un-disposed
(`review_state ∈ {unreviewed, needs_review}` and `superseded=0`); disposed items are protected so operator
decisions are never overwritten.

- `test_changed_digest_supersedes_prior_same_lineage`: prior item flagged `superseded=1`/
  `review_state='superseded'`; active listing returns only the new item; a `marked_superseded` event is
  logged.
- `test_independent_targets_coexist`: different target ids never supersede each other (2 items coexist).

## Build idempotency + nonmutation
- `test_review_builder.py::test_build_apply_idempotent_and_nonmutating`: a second `build --apply` creates
  0 new items and leaves every source table's content digest unchanged (see 08).
