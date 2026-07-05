# 07 — Recent Changes & Related Proof

## Recent changes
New read-only repo primitive `SourceIndexRepository.list_recent_events` (the only reader added — no
"recent changes" reader existed) over `source_intelligence_events`, newest-first, bounded, optional
`event_type` filter by **bound parameters** (no SQL interpolation).

`tests/test_obsidian_source_navigation.py::test_recent_changes_shape_and_order`:
- inserts two events (`2026-07-01` created, `2026-07-05` modified);
- `recent_changes(limit=1)` returns the newest (`e2`) first and `truncated=True` (more existed).
- envelope shape `{changes, count, limit, truncated}`.

## Related sources
`get_related_sources` wraps `repo.list_relationships` (outgoing edges).
`test_get_related_sources`: after recording a `mentions` relationship sid_a→sid_b, `related` has one
edge with `dst_ref=sid_b`, `count=1`.

## Result
Both pass. Recent-changes ordering + bounding proven; related lookup returns outgoing edges only.
