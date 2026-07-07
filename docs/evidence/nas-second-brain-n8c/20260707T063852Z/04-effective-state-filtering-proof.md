# 04 — Effective-State Filtering Proof

Effective review state is READ from the N8C-9 overlay (`review_repository.get_effective_state`) and mapped
to an `inclusion_state` by `classify_inclusion_state(effective_state, budget)` in
`intelligence_projection_models.py`. **No projection ever converts a candidate into accepted truth.**

## State → (inclusion_state, policy-included-when-allowed)

| effective_state | inclusion_state | included (trusted_context) | included (review_aware_context) |
|---|---|---|---|
| `accepted` | `trusted` | ✅ yes | ✅ yes |
| `candidate` (default when undisposed) | `candidate` | ❌ no | ✅ yes (labeled) |
| `deferred` | `deferred` | ❌ no | policy (`include_deferred`, default off) |
| `stale` | `stale` | ❌ no | policy (`include_stale`, default off) |
| `rejected` | `excluded` | ❌ no | ❌ no |
| `not_required` | `not_required` | ❌ no | ❌ no |
| `superseded` | `superseded` | ❌ no | ❌ no |

`accepted` is always trusted+included; `rejected`/`not_required`/`superseded` are always excluded regardless
of policy; `candidate`/`deferred`/`stale` are policy-gated per projection type.

## Tests (green)

`tests/test_intelligence_projection_repository.py::test_classification_by_effective_state` asserts each row
of the table above, including the pivotal:
```
classify_inclusion_state("candidate", trusted_budget) == ("candidate", False)   # excluded in trusted
classify_inclusion_state("candidate", review_budget)  == ("candidate", True)    # included+labeled review
classify_inclusion_state("accepted", trusted_budget)  == ("trusted", True)
classify_inclusion_state("rejected", trusted_budget)  == ("excluded", False)
```

`tests/test_intelligence_projection_builder.py`:
- `test_trusted_excludes_candidates_until_accepted` — a `trusted_context` preview has `included_count == 0`
  while everything is undisposed; after `record_disposition(rid, "accept")` the same pack yields
  `counts["trusted"] == 1`, the trusted item carries `effective_state == "accepted"` and preserves its
  `review_item_id` linkage. This proves acceptance is driven by the operator's disposition in the review
  ledger, not fabricated by the projection.
- `test_review_aware_includes_and_labels_candidates` — every undisposed item is included AND labeled
  `inclusion_state == "candidate"` (never silently promoted to trusted).
- `test_excluded_items_minimized` — a rejected item classifies to `excluded`, `included == 0`,
  `effective_state == "rejected"`, `exclusion_reason == "rejected"`.
