# CPM Observability Deferred

Phase 1 preserves and proves commit-time CPM recompute. It does not add new CPM observability schema.

Deferred items:
- Explicit persisted CPM input snapshot table for activity/relationship counts.
- Rich CPM provenance linking each run stage to package file IDs and canonical merge version.
- UI-facing CPM observability surfaces beyond existing schedule health/project schedule surfaces.

Phase 1 proof uses committed canonical DB counts plus commit-returned CPM computed activity counts. The proof script records canonical relationship input counts from the same current relationship table consumed by CPM graph services.
