# N8C-20 — no upstream mutation (clarification #7)

The critical guardrail: `quality build --apply` may change ONLY the five `assistant_quality_*` tables. Every
other N8C table — feedback, action-stage, workflow-derived, source, review, draft, packet, context-pack,
projection, decision, preference, open-loop — must be byte-for-byte unchanged. Snapshot-before/after tests in
`test_quality_evaluator.py` prove all three postures over a realistically seeded DB (feedback record + action
stage built via the real builders):

- **`test_preview_mutates_nothing`** — a full content-hash snapshot of EVERY table (including the quality
  tables) is identical before and after `preview_quality(...)`. Preview persists nothing at all.
- **`test_dry_run_mutates_nothing`** — same full-snapshot equality after `build_quality(..., apply=False)`.
- **`test_apply_changes_only_quality_tables`** — a content-hash snapshot of every NON-quality table is
  identical before and after `build_quality(..., apply=True)`; the quality tables gain exactly one run. Proves
  the writer's blast radius is the five quality tables only.
- **`test_apply_is_idempotent`** — a second `apply` of the same unchanged target produces an identical full
  snapshot (reused, no duplicate row, no new lineage).

## Why this holds structurally

- `QualityRepository` is the sole writer and only ever `INSERT`s into the five quality tables (module
  docstring + `_insert`/`_insert_event` restricted to quality table names; `test_upsert_writes_only_quality_
  tables` corroborates at the repository level).
- The evaluator issues no SQL of its own (`test_evaluator_never_calls_source_file_read` asserts no
  `INSERT/UPDATE/DELETE` in the evaluator source); it reads upstream repositories through their read-only
  methods (`get_*`/`list_*`), never their writers.
- Supersede is lineage-scoped to prior quality runs of the same `(target_kind, target_id, policy_json)` — it
  flips a quality run's own `status` to `superseded`, never an upstream record's state.
