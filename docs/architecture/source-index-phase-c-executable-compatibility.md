# Source-Index Phase C — Executable / Database Compatibility & Rollback

Scope: PC-WI-04 (PCR-007) of `GOAL-SOURCE-INDEX-PHASE-C-CLOSURE-001`. This note records the
executable/database compatibility classification and the rollback contract. It is verified by
`tests/source_index/test_phase_c_executable_compatibility.py`, which runs a **prior executable** (pinned
historical SHA `6b57a406`, head V124) via a `git worktree` and performs bounded reads against
representative databases. It does not activate the application, migrate, or touch a production database.

## Exact schema changes V125 → V127 (not "strictly additive")

The head is **not** uniformly additive. The precise post-V124 changes are:

| Version | Change | Additive? |
|---|---|---|
| **V125** `v125_source_index_scan_quarantine` | adds the `source_index_scan_quarantine` table | additive |
| **V126** `v126_source_rename_lineage` | adds source rename-lineage tables/columns | additive |
| **V127** `v127_events_moved_dest_backoff` | **rebuilds `source_intelligence_events`** (`DROP`/recreate via `_rebuild_v127_events`): widens the `event_type` CHECK to accept the governed **`moved`** type and adds the `dest_rel_path` + `next_attempt_at` columns | **NOT additive — a table rebuild** |

The V127 migrator body itself records the code-rollback caveat: after V127, **old application code
cannot read/insert `moved` rows**, and Phase B must not deploy or migrate production because of it.

## Compatibility matrix (from executing the prior V124 executable)

| Executable | Database | Observed (bounded reads under the prior executable) | Classification |
|---|---|---|---|
| Prior (head **V124**, SHA `6b57a406`) | Prior-restored **V124** | `current_version()` → 124; genuine repository DAO `SourceIndexRepository.generated_note_counts()` returns counts; the database carries only event types the prior executable knows (no unknown types) | **PC-AC-041 — rollback combination proven**: the prior executable operates normally against a prior-restored database (rollback = restore + prior executable). |
| Prior (head **V124**) | New **V127** | `current_version()` → 127; the repository DAO `generated_note_counts()` still returns counts (read-only generation-table path); **but** `source_intelligence_events` contains a `moved` event, and `moved` is absent from the prior executable's known `event_type` vocabulary (`created`, `modified`, `deleted`, `reindex_requested`, `rebuild`) | **PC-AC-040 — read-only generation-path compatibility ONLY**: the prior executable can read the generation-table path, but the V127 events rebuild introduces a `moved` semantic the prior executable cannot interpret. This is **not** general forward compatibility. |

### PC-AC-040 — narrow meaning and explicit prohibition

- **Proven:** the prior V124 executable can perform the **read-only generation-table** path against a
  V127 database (`current_version()` and `generated_note_counts()` succeed).
- **Not proven / explicitly prohibited:** the prior V124 executable **must not** process the
  `source_intelligence_events` **queue**, **write** events, or perform **general application operation**
  against a V127 database. V127 rebuilds the events table and adds the `moved` event type; the prior
  executable has no knowledge of `moved` and would misclassify or reject such rows. A newer database
  therefore does not lock out an older executable's one proven read path, but it is **not** safe to run
  the older executable as a general application against a V127 database.

## Rollback contract (no in-place schema downgrade)

Rollback is **restore + prior executable**, never an in-place schema downgrade (governing spec §8):

1. stop use of the migrated database;
2. restore the verified pre-migration backup to a **new** path;
3. verify the restored backup (integrity + logical inventory);
4. run the matching **prior** executable against the restored database;
5. verify read-only service before resuming.

**In-place schema downgrade is unsupported unless separately implemented and approved.** There is no
reverse migration path; the schema head only moves forward (V127 rebuilds `source_intelligence_events`,
which cannot be losslessly reversed). A rollback reverts the *database* (by restoring a prior backup)
and the *executable* (by running the matching prior build) together — it never rewrites a V127 database
down to a prior head.

## Probe honesty and reproduction limitation (disclosed)

The bounded reads are labeled by kind: `current_version()` is the prior migrator's connection-layer
read; `generated_note_counts()` is a genuine prior **repository DAO** operation; the event-type
comparison is a direct read of `source_intelligence_events` against the prior executable's own
`EVENT_TYPE_VALUES` constant. The prior executable is run from a `git worktree` of the pinned SHA under
the **current** virtual environment; its third-party dependencies are not historically pinned. The
probes target the DB-access/repository layer, built on the standard-library `sqlite3` module, so
dependency drift does not affect the compatibility conclusion. If the pinned prior-executable SHA
cannot be checked out, the compatibility result is **INSUFFICIENT EVIDENCE** (fail-closed), never a pass
inferred from static inspection.
