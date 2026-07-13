# Phase C — C0 Execution-Time Repository Truth

**Stage:** Phase C Stage 1 (foundation). **Disposition authority:** none (planning/implementation
only; never `GO`). **Governance:** AEOS.

This artifact records the execution-time repository state and reconciles the approved Phase C
objective (from `AUDIT-NAS-SOURCE-INDEX-FULL-REMEDIATION-REPORT.md`) against current `origin/main`,
per the plan's C0 step and stop conditions. Raw captures accompany this narrative:
`git-state.txt`, `environment.txt`, `schema-head-probe.txt`.

## 1. Repository state

- Repository: `RMF112018/hb-personal-assistant` (origin over HTTPS).
- Working branch for Stage 1: **`phase-c-source-index-migration-assurance-stage1`**, created from
  `origin/main`.
- `origin/main` = `d110c54fa295e9e683afb780d5d0c48728325f5c` (merge commit for PR #311; parents
  `77cf87da` + `c914be4d`).
- Phase B head `c914be4d…` **is an ancestor of** `origin/main` (Phase B fully merged) — verified via
  `git merge-base --is-ancestor`.
- Stale local `main` ref (`77cf87da…`) was **not** used; the branch was based on `origin/main`.
- Tracked working tree at branch creation: **clean** (0 staged, 0 unstaged). Untracked Phase B
  evidence exports and pre-existing foreign churn are present in the tree and were **not** disturbed,
  staged, or deleted.

## 2. Environment

- Platform: Darwin 27.0.0 arm64.
- Runtime interpreter: **`.venv/bin/python` = Python 3.14.5** (SQLite lib **3.53.1**).
  - **Correction:** an earlier reconnaissance note inferred "Python 3.12" from a stale
    `.venv/lib/python3.12` path. The actual runtime is 3.14.5. The migrator's
    `[tool.ruff] target-version = py312` / `[tool.mypy] python_version = 3.12` are *static-analysis*
    targets, not the runtime.
- `sqlite3` connection default `isolation_level` = `''` (legacy transaction control). Under legacy
  control, DDL statements participate in the surrounding transaction (no implicit commit since
  CPython 3.6), which is the precondition for the single-atomic-transaction migration claim (§4).
- Gate-equivalent invocation convention: `PYTHONPATH="src:subrepos/construction-financial-review/src"`
  with `.venv/bin/python -m pytest` (the committed gate's bare `pytest` resolves to a broken system
  interpreter on this machine — see plan PCR-003).

## 3. Schema head and migration ledger (empirical)

Proven by applying the migrator to a disposable scratch DB (`schema-head-probe.txt`):

- `LATEST_SCHEMA_VERSION` constant = **127** (`src/hb_assistant/store/migrator.py:17`).
- `SQLiteMigrator(db_path=…).apply()` returns **127** (`SELECT MAX(version) FROM schema_migrations`).
- Ledger has **127 rows, versions 1…127, no gaps, no duplicates**.
- Source-index-relevant ledger names (execution-time truth):

  | Ver | `schema_migrations.name` |
  |-----|--------------------------|
  | 115 | v115_source_structure_layered_index |
  | 116 | v116_source_structure_overrides |
  | 117 | v117_source_index_bootstrap |
  | 119 | v119_source_index_bootstrap_runs |
  | 122 | v122_source_index_scan_generations |
  | 123 | v123_drop_narrow_relpath_index |
  | 124 | v124_index_metadata_fts_rowid |
  | 125 | v125_source_index_scan_quarantine |
  | 126 | v126_source_rename_lineage |
  | 127 | v127_events_moved_dest_backoff |

  V118/V120/V121 are tool-manifest migrations (`v118_tool_manifest_semantic_payload`,
  `v120_manifest_entry_classification`, `v121_manifest_gateway_allowlist`), **not** source-index —
  but because the ledger is monolithic, an origin "at V121" simply means `MAX(version)=121`, i.e. the
  **pre-V122** source-index state the audit calls for.

## 4. Migration transaction model (single atomic transaction)

- `apply()` opens one connection and wraps the entire V1→V127 body in a single
  `with transaction(conn):` block (`migrator.py:7638-7641`).
- `transaction()` commits once on success and rolls back on any exception, never closing the
  borrowed connection (`connection.py:150-162`).
- Therefore there are **no per-migration commits**. Any interruption during `apply()` rolls the DB
  back to the origin head; `schema_migrations` never exposes a partially-applied version set. This
  replaces the original plan's C6 "between-versions committed" failure taxonomy, which does not exist.
- V127 self-hardens the events contract on **every** apply: `_events_schema_current` re-validates the
  structural contract and `_rebuild_v127_events` raises `v127_events_invalid_existing_rows` (rolling
  back the whole transaction) rather than coercing queued rows
  (`migrator.py:9285-9289`, `9405-9418`).

## 5. Objective reconciliation (V125 → V127)

The approved audit's Phase C objective targets a **V125** head with **V121/V124** origins; it
predates V126/V127. Current repo truth is a **V127** head. Per CLAUDE.md authority order (current
repository/runtime evidence is highest), Stage 1 advances the objective to:

- **Head:** V127.
- **Origins:** V121 (≡ pre-V122), V124, V125, V126, plus `head` (idempotency) and `fresh`.

This is recorded as an **approved-objective reconciliation**, not a silent redesign. The audit's
qualitative requirements (production-shaped fixture, PRAGMA parity, no-downgrade, 800k+ scale, WAL)
carry forward unchanged.

**Identifier note:** the audit uses `IDX-###` finding IDs; the `PB-010`/`PB-012` identifiers cited in
the session handoff come from a separate Phase B working doc and are not load-bearing for Phase C.

## 6. Stop-condition check

None of the plan's stop conditions are triggered: worktree tracked-clean and unambiguous; Phase B
lineage present in `origin/main`; schema head matches the plan (V127); migration architecture
unchanged; no production/NAS resources required; no conflict between the approved objective and repo
truth beyond the recorded V125→V127 reconciliation.

**C0 result:** repository truth supports the Stage 1 plan. Proceed to C1.
