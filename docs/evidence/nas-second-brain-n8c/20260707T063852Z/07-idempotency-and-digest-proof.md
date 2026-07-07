# 07 — Idempotency & Digest Proof

## Deterministic identity (`intelligence_projection_models.py`)

- `projection_id   = sha256(projection_type | scope_json | filter_policy_json | budget_json | input_digest | "intel-projection-v1")[:24]`
- `input_digest    = sha256(sorted (review_item_id, effective_state, target_digest) signals + filter_policy_json + budget_json)`
- `projection_item_id = sha256(projection_id | target_kind | target_id | review_item_id | effective_state | target_digest)[:24]`
- `projection_receipt_id = sha256(projection_id | input_digest | output_digest | "intel-projection-v1")[:24]`
- `output_digest   = sha256(sorted included projection_item_ids)`

`effective_state` folds into both `input_digest` and `projection_item_id`, so a new disposition (changed
effective state) changes the digests → a new `projection_id`.

## Idempotency & lineage supersede (repository)

`upsert_projection(header, items, receipt, conn=)`:
- Same `projection_id` already present → **reuse no-op** (`reused=True`, `created=False`); no duplicate row.
- Different `input_digest` for the same `(projection_type, IFNULL(scope_json,''))` lineage → the prior
  `draft`/`built` projection is marked `superseded` (+ `marked_superseded` event) and the new one inserted.
- Different scope lineage → coexists (never supersedes across lineages).
- **Supersede/stale only ever touches projection-owned rows** — never a source-advisory or review record.

## Tests (green)

`tests/test_intelligence_projection_repository.py`:
- `test_ids_deterministic` — same inputs → same ids; changed `input_digest` → different `projection_id`;
  changed `effective_state` → different `projection_item_id`; receipt id stable.
- `test_upsert_idempotent` — re-upsert → `reused=True`, `count()==1`, one item.
- `test_changed_input_supersedes_prior_same_type_scope` — prior → `status=superseded`, new → `status=built`.
- `test_independent_scope_coexists` — two scopes → `count()==2` (no cross-lineage supersede).
- `test_mark_stale_if_needed` — a changed current `input_digest` marks the projection `stale`.

`tests/test_intelligence_projection_builder.py::test_build_apply_idempotent` — a second `apply=True` build
with unchanged inputs returns `reused=True`, `created=False` (no duplicate projection).
