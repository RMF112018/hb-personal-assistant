# Source-Index Phase C — Migration & Rollback Proof (durable specification)

**Status:** Stage 1 (foundation) implemented; Stages 2–3 specified, not implemented.
**Governance:** AEOS. **Production / deployment / NAS authority:** none.
**Approved objective source:** `AUDIT-NAS-SOURCE-INDEX-FULL-REMEDIATION-REPORT.md` (Phase C), as
reconciled to current repository truth in `docs/evidence/source-index-phase-c/preflight/00-c0-repository-truth.md`.

This document is the reconciled, repository-truth-aligned contract for Phase C. It supersedes the
version numbers in the original audit (which is stale at schema V125) and in the original
`PLAN-SOURCE-INDEX-PHASE-C-001` where they conflict with the code. It is the authoritative reference
for the fixture framework, the inventory/parity engine, and all downstream proof work.

---

## 1. Objective

Prove that representative legacy source-index SQLite databases can be inspected, backed up, migrated
to the current schema head, validated for schema and data integrity, restored independently, used
with supported executable/database combinations, and recovered after interruption — **without
migrating, repairing, reindexing, or activating the production source-index database.**

## 2. Execution-time truth (from C0)

- **Schema head:** V127 (`LATEST_SCHEMA_VERSION`, `src/hb_assistant/store/migrator.py:17`), proven by
  applying the migrator to a scratch DB (127-row ledger, versions 1..127, no gaps/duplicates).
- **Migration engine:** `SQLiteMigrator(db_path=…).apply()` runs the entire V1→V127 body in **one**
  `with transaction(conn)` block (`migrator.py:7638-7641`; `connection.py:150-162`). No per-migration
  commits. Interruption during `apply()` rolls back to the origin head atomically.
- **Runtime:** Python 3.14.5, SQLite 3.53.1, `sqlite3` legacy transaction control
  (`isolation_level=''`) — DDL participates in the transaction.
- **V127 self-hardening:** `_events_schema_current` revalidates the events contract on every apply;
  `_rebuild_v127_events` raises `v127_events_invalid_existing_rows` (whole-transaction rollback)
  rather than coercing queued rows.

## 3. Supported origins and head

The ledger is monolithic (one `schema_migrations` table across all domains). An "origin at version N"
means `MAX(version)=N`.

| Origin | Meaning | Rationale |
|--------|---------|-----------|
| **V121** | pre-V122 source-index state | the audit's "pre-V122 layout"; oldest supported origin |
| **V124** | has V122 generations + V123 index fix + V124 fts index | audit-named origin |
| **V125** | + quarantine | post-audit intermediate |
| **V126** | + rename lineage | post-audit intermediate |
| **V127** | head (idempotency origin) | reapply-at-head must be a no-op |
| **fresh** | apply from empty → head, **no legacy seeding** (empty source tables) | baseline forward path; a distinct fixture identity (`origin="fresh"`), not overloaded onto an integer |

Head for every migration path = **V127**. V123 introduces no positive source-index *object* delta
observable on a from-head fixture (the narrow `idx_si_sources_relpath` it drops is already absent by
V99 < V121), so V123 is discriminated only by its `schema_migrations` row, not a schema object.

## 4. Source-index object deltas (the discriminator contract)

The independent fixture oracle (`tests/support/source_index_expected_inventory.py`) is authored from
this table, derived by **reading** the migrator source (not by running it). It shares no code path
with the fixture builder.

| Δ at | Object | Kind |
|------|--------|------|
| V122 | `source_index_scan_generations` (+ `idx_source_index_scan_generations_active`/`_root`/`_status`) | table + indexes |
| V122 | `source_intelligence_sources.last_seen_generation` / `last_seen_at` / `last_indexed_fingerprint` | columns |
| V122 | `source_intelligence_metadata.extraction_disposition` / `content_indexed_at` | columns |
| V122 | `source_index_bootstrap_runs.generation_id` | column |
| V122 | `idx_si_sources_last_seen_gen` | index |
| V124 | `idx_si_metadata_fts_rowid` | index |
| V125 | `source_index_scan_quarantine` (+ `idx_source_index_scan_quarantine_active`/`_root_state`) | table + indexes |
| V126 | `source_intelligence_sources.renamed_from_source_id` (+ `idx_si_sources_renamed_from`) | column + index |
| V127 | `source_intelligence_events.dest_rel_path` / `next_attempt_at`; `event_type` CHECK accepts `'moved'` | columns + constraint |

**Relpath uniqueness indexes (S1-AUD-006) — two distinct objects, do not conflate:**
- `idx_si_sources_root_relpath` (root-scoped, `(source_kind, source_root_key, rel_path)`) is a **V93**
  object present at **every** origin. It is NOT introduced by V123. The oracle asserts its **exact**
  canonical SQL at all origins.
- `idx_si_sources_relpath` is the historical **narrow** unique index `(source_kind, rel_path)` that
  omits the root. The current migrator never creates it (grep: only V99/V123 `DROP` statements), but a
  real **pre-V123 deployed** database carried it — which is precisely why it blocked cross-root
  duplicate rel_paths. Pre-V123 fixtures (origin < 123) install it with exact SQL and seed
  globally-unique paths; V123 drops it, enabling cross-root duplicates at V124+. The oracle asserts it
  **present iff origin < 123** with exact SQL. V123 is therefore a real discriminator (the narrow-index
  drop), not merely a ledger row.

**Base objects present at every origin (≥V121)** include the V93 core
(`source_intelligence_sources`/`_metadata`/`_text`/`_chunks`/`_relationships`/`_generated_notes`/
`_events` [pre-V127 shape]/`_state`), V94 `_summaries`, the two FTS5 tables
(`source_intelligence_fts`, `obsidian_note_fts`), the V115 `source_structure_*` layer + V116
`_overrides`, the V117 `source_index_bootstrap_state`/`_reconciliation_runs`, and the V119
`source_index_bootstrap_runs` (without `generation_id`).

## 5. Parity classification model

Every inventory field is classified for cross-version comparison:

- **exact** — must be identical pre/post (e.g. `source_id` values, root-scoped uniqueness).
- **monotonic** — may only increase (e.g. `MAX(schema_migrations.version)` origin→head).
- **migration-transformed** — a defined, expected change (e.g. events table gains `dest_rel_path`).
- **allowed-difference** — legitimately variable (e.g. SQLite page layout / whole-file byte hash).
- **informational** — recorded, not asserted (e.g. file size, WAL size, timings).

Logical-inventory hashing (a canonical, order-independent digest of logical content) is used **in
addition to** whole-file hashes, because SQLite page layout may legitimately change while logical
content is preserved.

## 6. Data invariants the fixtures must carry (origin-aware)

Seeded only into tables that exist at the fixture's origin version:

- duplicate relative paths under **two different roots** → distinct `source_id`s (root folded into
  the identity hash); root-scoped uniqueness intact.
- source rows with **FTS present** and rows with **FTS intentionally missing** (`fts_rowid` NULL) —
  distinguishable from data loss (rebuildable from `source_intelligence_text.text_excerpt`).
- V93 `source_intelligence_generated_notes` (source cards) with `not_generated`/`generated`/`stale`.
- V119 `source_index_bootstrap_runs` (pass trail) with distinct run identities.
- **V122+ only:** `source_index_scan_generations` in `running`/`partial`/`failed`/`abandoned`/
  `completed` states, incl. one active per root (partial-unique honored).
- **V125+ only:** `source_index_scan_quarantine` unresolved rows (root-level trust blocker).
- **V126+ only:** `renamed_from_source_id` lineage (new row → prior `source_id`; old row `deleted`).
- **V127 only:** `source_intelligence_events` including a governed `'moved'` event with
  `dest_rel_path` + `next_attempt_at`; pre-V127 origins carry only legacy event types.

All fixture data is **synthetic** — no production absolute paths, secrets, or real source content.

## 7. Safety contracts preserved from Phase A/B

Migration and all Phase C proof work must preserve: certified-complete-scan-before-delete (A1);
fail-closed root trust with **unresolved quarantine as a blocker** (A4 / `source_root_trust`);
canonical structure-root mapping (A3); root-scoped source identity (no collapse of multi-root
uniqueness into global path uniqueness); thin move lineage (no alias table); event ownership by
claim-generation (`attempts`), not a fabricated owner column.

## 8. Rollback definition (no schema downgrade)

Rollback is **restore + prior executable**, never an in-place schema downgrade:

1. stop use of the migrated database; 2. restore the verified pre-migration backup to a **new** path;
3. verify the restored backup (integrity + logical inventory); 4. run the matching **prior**
executable; 5. verify read-only service before resuming. Schema downgrade is unsupported unless
separately implemented and approved.

---

## 9. Staging and boundaries

- **Stage 1 (this increment) — foundation.** C0 evidence; this spec; the fixture framework +
  independent oracle; the read-only inventory/parity engine. **No** backup/restore, migration-matrix,
  atomicity, lock, compatibility, gate, or 800k work.
- **Stage 2 — proof.** Backup/restore harness (`Connection.backup()` over a read-only source URI;
  never a raw copy while WAL is active); migration matrix (V121/V124/V125/V126/head/fresh → V127);
  interruption/recovery under the **single-atomic-transaction** model.
- **Stage 3 — compatibility, gate, evidence.** Compatibility/rollback matrix + runbook; CI-gate
  wiring; redacted evidence bundle.

Each stage returns for a **new AEOS review** before it begins. Stage 1 may not begin C4 backup work.

### Deferred requirements recorded now (do not lose)

- **Deterministic atomicity barrier (PCR-005, Stage 2):** the kill-mid-`apply()` proof must use a
  deterministic barrier (test-only migration progress callback / injectable hook / SQLite trace
  signal), **never** a timing sleep. The test must: start from a validated legacy fixture; wait for
  the barrier; terminate the child; reopen with a fresh connection; allow WAL/journal recovery;
  verify origin `MAX(version)` + logical inventory unchanged; run all integrity checks; rerun
  migration successfully.
- **Backup mechanism (Stage 2):** SQLite online backup via `Connection.backup()` over a read-only
  source URI; emit a receipt shaped like `store/startup_schema_policy.py`'s validated receipt;
  destinations under the caller's rehearsal root only (never `path_policy.get_db_backups_dir()`).
- **Compatibility prerequisites (PCR-007, Stage 3):** pre-define exact historical SHAs, dependency
  reproduction, worktree authorization, whether the probe is executable-startup vs bounded DAO reads,
  and result meanings. If historical execution cannot be reproduced → `INSUFFICIENT EVIDENCE`, never
  static inspection relabeled as compatibility proof.
- **800k+ rehearsal (PCR-006):** the configurable generator (Stage 1) and any bounded CI run are
  **not** the audit's production-shaped proof. Until an authorized 800k+ rehearsal is run with raw
  evidence: `PC-AC-048 = NOT VERIFIED` and **Phase C = INCOMPLETE**. Generator existence must never be
  reported as `PASS` for the large-scale requirement.

### Rehearsal-root isolation (PCR-001 / PCR-008)

Every fixture/backup/restore/WAL/evidence database file lives under a **caller-provided temporary
rehearsal root**. Production path-policy functions may be inspected for naming/receipt conventions
only — they must never determine a destination. Commands reject destinations outside the rehearsal
root, reject symlinked roots, refuse the configured application DB by default, and only rebuild a
target proven disposable (fixture marker/manifest present).

---

## 10. Acceptance criteria

All criteria begin at `NOT VERIFIED`. The "Stage" column marks where each is exercised. Stage 1
criteria are the only ones an agent may move off `NOT VERIFIED` in this increment.

| ID | Criterion | Stage |
|----|-----------|-------|
| PC-AC-001 | Execution-time schema head and supported legacy origins recorded | 1 |
| PC-AC-002 | Deterministic **V121/pre-V122 monolithic** fixture generated **and validated against an independent historical object inventory**; inability to reconstruct is a Stage 1 blocker requiring plan review | 1 |
| PC-AC-003 | Deterministic V124 fixture generated | 1 |
| PC-AC-004 | Fixtures for each post-audit version through head (V125, V126, V127) | 1 |
| PC-AC-005 | Production-shaped fixture includes duplicate relative paths under multiple roots | 1 |
| PC-AC-006 | Fixture includes ALL six generation states — running/partial/reconcile_pending/completed/failed/abandoned — one active per root across three roots (V122+) | 1 |
| PC-AC-007 | Fixture includes FTS-present and intentionally FTS-missing source rows | 1 |
| PC-AC-008 | Fixture includes V93 `source_intelligence_generated_notes` (where applicable) **and** V119 `source_index_bootstrap_runs`, distinct identities preserved | 1 |
| PC-AC-009 | Fixture includes V125 quarantine state (V125+) | 1 |
| PC-AC-010 | Fixture includes V126 rename/move lineage (V126+) | 1 |
| PC-AC-011 | Fixture includes pre-V127 **and** V127 `source_intelligence_events` forms, incl. moved-event `dest_rel_path`/`next_attempt_at` and representative `attempts` | 1 |
| PC-AC-012 | Fixtures run in WAL mode | 1 |
| PC-AC-013 | CI-size fixture and separately-invoked production-shaped profile available | 1 (generator) / 3 (run) |
| PC-AC-014 | Every supported origin migrates to exactly the execution-time head | 2 |
| PC-AC-015 | After atomic `apply()`, the ledger contains every expected version exactly once, no gaps/duplicates | 2 |
| PC-AC-016 | Reapplying the migrator at head produces no schema/protected-data change | 2 |
| PC-AC-017 | Post-migration DDL/indexes/triggers/views match current canonical definitions | 2 |
| PC-AC-018 | Source-row counts satisfy parity rules | 2 |
| PC-AC-019 | Duplicate relative paths under different roots remain valid and distinct | 2 |
| PC-AC-020 | Source-to-FTS parity satisfies the approved rules | 2 |
| PC-AC-021 | Generation state and current-generation authority preserved | 2 |
| PC-AC-022 | Unresolved quarantine preserved | 2 |
| PC-AC-023 | Rename/move lineage remains valid and acyclic | 2 |
| PC-AC-024 | Event statuses, attempt generations, ownership-relevant fields preserved | 2 |
| PC-AC-025 | Source cards and pass links satisfy parity rules | 2 |
| PC-AC-026 | Representative queries use acceptable indexes / query plans | 2 |
| PC-AC-027 | `PRAGMA quick_check` succeeds after migration | 2 |
| PC-AC-028 | `PRAGMA integrity_check` succeeds after migration | 2 |
| PC-AC-029 | `PRAGMA foreign_key_check` returns no unexpected violations | 2 |
| PC-AC-030 | Consistent backup created from the pre-migration fixture | 2 |
| PC-AC-031 | Backup has a durable hash and receipt | 2 |
| PC-AC-032 | Backup restores to an independent location | 2 |
| PC-AC-033 | Restored DB passes integrity and logical-inventory validation | 2 |
| PC-AC-034 | Representative read-only repository ops succeed against the restored DB | 2 |
| PC-AC-035 | An interrupted backup cannot be mistaken for a valid backup | 2 |
| PC-AC-036 | Migration lock/busy behavior is bounded | 2 |
| PC-AC-037 | Interruption during atomic `apply()` leaves the origin DB logically unchanged after SQLite recovery, or the test fails closed | 2 |
| PC-AC-038 | A recoverable interruption reruns without duplicated migrations or corruption | 2 |
| PC-AC-039 | An unrecoverable integrity failure blocks completion | 2 |
| PC-AC-040 | Old-executable / new-database compatibility explicitly tested or classified | 3 |
| PC-AC-041 | Prior-executable / prior-restored-database rollback combination proven | 3 |
| PC-AC-042 | Docs state schema downgrade is unsupported unless separately implemented | 3 |
| PC-AC-043 | No Phase C command requires production database access | 1–3 |
| PC-AC-044 | No Phase C test activates watchers/parsers/reindexing/reconciliation/pruning | 1–3 |
| PC-AC-045 | No committed fixture/evidence contains production absolute paths, secrets, or source content | 1–3 |
| PC-AC-046 | Existing Phase A/B source-index gate remains green | 1–3 |
| PC-AC-047 | Phase C CI-profile tests run deterministically | 1 |
| PC-AC-048 | Production-shaped rehearsal emits timing/size/WAL/migration/backup/restore/compat evidence (**requires authorized 800k+ run**) | 3 |
| PC-AC-049 | Every implementation claim maps to raw evidence tied to base/head SHAs | 1–3 |
| PC-AC-050 | Final report identifies deviations, known gaps, unverified areas | 1–3 |
| PC-AC-051 | Every legacy fixture matches an **independent** expected schema inventory | 1 |
| PC-AC-052 | Every new production module receives explicit Ruff coverage | 1 |
| PC-AC-053 | Every new typed production module receives explicit strict mypy coverage | 1 |
| PC-AC-054 | All fixture/backup/restore/evidence writes remain beneath a disposable rehearsal root | 1–3 |
| PC-AC-055 | The 800k+ rehearsal remains required for final Phase C completion | 3 |
| PC-AC-056 | Pre-V123 fixtures carry the historical narrow index with exact SQL; V123+ omit it; oracle asserts both (S1-AUD-006) | 1 |
| PC-AC-057 | Inventory engine is fail-closed read-only: missing/non-file paths raise and create nothing; inspection creates no `-wal`/`-shm`/journal sidecar (S1-AUD-008) | 1 |
| PC-AC-058 | Inventory captures structural signature (columns/FK/constraints/DDL/index detail) and source-text/FTS linkage parity, folded into the logical hash; mutations are detectable (S1-AUD-007/009) | 1 |
| PC-AC-059 | A distinct `fresh` fixture (empty DB migrated to head, no legacy seeding) is supported (S1-AUD-010) | 1 |
| PC-AC-060 | Inventory rejects a non-empty `-wal` (`uncheckpointed_wal_present`) so immutable read cannot ignore committed WAL state; rejection mutates/creates nothing (S1-AUD-014) | 1 |
| PC-AC-061 | Per-row FTS content digests (both `source_intelligence_fts` and `obsidian_note_fts`) are folded into the logical hash; same-rowid content/path/aux corruption is detectable (S1-AUD-015) | 1 |
| PC-AC-062 | Structural signature covers **all** inventoried source-index tables + FTS virtual tables; a schema change to any flips the hash (S1-AUD-016) | 1 |

---

## 11. Stage 1 dispositions

Stage 1 concludes with exactly one of: `STAGE 1 COMPLETE — READY FOR INDEPENDENT AUDIT` /
`STAGE 1 COMPLETE WITH NON-BLOCKING GAPS` / `STAGE 1 PARTIAL — BLOCKED` /
`STAGE 1 NOT STARTED — PREFLIGHT CONFLICT` / `STAGE 1 INSUFFICIENT EVIDENCE`, plus a Stage 2 delta
proposal. No agent may issue `GO`, and Phase C remains `INCOMPLETE` until the deferred requirements
(§9) are satisfied under separate authorization.
