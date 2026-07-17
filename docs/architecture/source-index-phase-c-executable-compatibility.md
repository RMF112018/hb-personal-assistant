# Source-Index Phase C — Executable / Database Compatibility & Rollback

Scope: PC-WI-04 (PCR-007) of `GOAL-SOURCE-INDEX-PHASE-C-CLOSURE-001`. This note records the
executable/database compatibility classification and the rollback contract. It is verified by
`tests/source_index/test_phase_c_executable_compatibility.py`, which runs a **prior executable** (pinned
historical SHA, head V124) via a `git worktree` and performs bounded DAO reads against representative
databases. It does not activate the application, migrate, or touch a production database.

## Compatibility matrix

The migrator schema is **strictly additive** (V1…V127; existing tables are never rewritten). The
compatibility classification below reflects that contract and is confirmed by executing the prior
executable's own connection/migrator read layer, not by static inspection.

| Executable | Database | Observed (bounded DAO read) | Classification |
|---|---|---|---|
| Prior (head **V124**, SHA `6b57a406`) | Prior-restored **V124** | `current_version()` → 124; representative source-index table read succeeds | **PC-AC-041 — rollback combination proven**: the prior executable operates normally against a prior-restored database (rollback = restore + prior executable). |
| Prior (head **V124**) | New **V127** | `current_version()` → 127; the V124-known source-index table is still readable (additive schema) | **PC-AC-040 — forward-read-compatible for known objects**: the prior executable opens and reads the newer additive database at the DB-access layer and does **not** fail-closed on the higher head; it cannot use V125+ tables/columns it has no knowledge of. |

Meaning of PC-AC-040: a newer database does not corrupt or lock out an older executable's known read
paths, because migrations are additive. It does **not** mean the older executable gains V125+
functionality. Operators must not rely on an older executable to interpret newer schema features.

## Rollback contract (no in-place schema downgrade)

Rollback is **restore + prior executable**, never an in-place schema downgrade (governing spec §8):

1. stop use of the migrated database;
2. restore the verified pre-migration backup to a **new** path;
3. verify the restored backup (integrity + logical inventory);
4. run the matching **prior** executable against the restored database;
5. verify read-only service before resuming.

**In-place schema downgrade is unsupported unless separately implemented and approved.** There is no
reverse migration path; the schema head only moves forward. A rollback therefore reverts the *database*
(by restoring a prior backup) and the *executable* (by running the matching prior build) together — it
never rewrites a V127 database down to a prior head.

## Reproduction limitation (disclosed)

The prior executable is run from a `git worktree` of the pinned SHA under the **current** virtual
environment; its third-party dependencies are not historically pinned. The probe targets the DB-access
layer, which is built on the standard-library `sqlite3` module, so dependency drift does not affect the
compatibility conclusion. If the pinned prior-executable SHA cannot be checked out, the compatibility
result is **INSUFFICIENT EVIDENCE** (fail-closed), never a pass inferred from static inspection.
