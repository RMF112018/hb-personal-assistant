# 12 — Risk & defer list

## Deferred (intentional, narrow-scope)
- **`assistant_review_batches`** (optional grouping of review builds): DEFERRED as YAGNI. The three core
  tables (items / dispositions / events) satisfy the queue + ledger + effective-state contract. Add later
  only if reproducible batch grouping is needed — must stay a review-overlay table, not a job system.
- **Global / `--all` (non-pack-scoped) build**: DEFERRED. Pack-scoped build is the mandatory default to
  keep the queue bounded; a global mode would need separate approval + explicit bounding.

## Watch items
- **Schema-head test drift (low)**: future migrations (V106+) will break `test_review_v105_migration.py::
  test_head_is_105` and `test_source_identity_v99_migration.py::test_latest_schema_version_is_105`. The
  established pattern is to relax the prior layer's exact head-equality to
  `>= N` + a "V-N migration row present" check (already applied here for V104).
- **Enrichment scoping (low)**: enrichment review items are pack-scoped by filtering the derived list to
  the pack's `source_ids` (bounded by `limit`). If a pack references many sources with large enrichment
  histories, some enrichment items beyond `limit` may not surface in one build; re-running or raising
  `--limit` covers them. Documented; not a correctness issue for the overlay.
- **Decision-family pack filter (low)**: decision/preference/open-loop review items are found by reading
  candidate records and filtering `pack_id == pack` in Python (bounded by `limit`). Consistent with the
  pack-scoped contract; a dedicated pack-indexed read could be added later if volumes grow.
- **`construction/analytics/api.py` pre-existing ruff backlog (informational)**: unchanged by N8C-9
  (1 pre-existing finding at HEAD and now; N8C-9 added zero in-scope findings). Do not "fix" as part of
  this slice.
