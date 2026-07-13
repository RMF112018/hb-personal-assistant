# Phase C — Stage 1 Implementation Report

**Disposition:** `STAGE 1 COMPLETE — READY FOR INDEPENDENT AUDIT`
**Scope authorized:** AEOS "APPROVE WITH REQUIRED CHANGES — Stage 1 only" (C0 evidence, C1 durable
spec, C2 fixture framework + independent oracle, C3 read-only inventory engine). No `GO`. Phase C
remains **INCOMPLETE** (Stages 2–3 and the 800k+ rehearsal are unauthorized/unrun).

## 1. Repository, branch, base

- Branch: `phase-c-source-index-migration-assurance-stage1`, based on `origin/main`
  `d110c54fa295e9e683afb780d5d0c48728325f5c` (PR #311 merge; Phase B `c914be4d` is an ancestor).
- Runtime: Python 3.14.5, SQLite 3.53.1 (`.venv`). Full C0 detail:
  `docs/evidence/source-index-phase-c/preflight/00-c0-repository-truth.md`.
- Only tracked edit: `pyproject.toml` (+2 lines — one mypy strict override, PCR-004). All other
  Stage 1 content is new files. Pre-existing untracked foreign churn was not staged, edited, or
  deleted (`preflight/changed-files.txt`).

## 2. What Stage 1 delivered

| Part | Artifact |
|------|----------|
| C0 | `preflight/00-c0-repository-truth.md`, `git-state.txt`, `environment.txt`, `schema-head-probe.txt` |
| C1 | `docs/specs/source-index-phase-c-migration-rollback-proof.md` (reconciled spec + 55-criterion matrix) |
| C2 oracle | `tests/support/source_index_expected_inventory.py` (frozen, independent of the builder) |
| C2 builder | `tests/support/source_index_migration_fixture.py` (deterministic V121/V124/V125/V126/V127 fixtures) |
| C2 tests | `tests/source_index/test_phase_c_fixture.py` |
| C3 engine | `src/hb_assistant/store/source_index_migration_assurance.py` (read-only inventory + logical hash) |
| C3 tests | `tests/source_index/test_phase_c_inventory.py` |

## 3. Key implementation facts (reconciled to repo truth)

- **Head V127** proven empirically (127-row ledger, no gaps/dupes; `schema-head-probe.txt`).
- **Single atomic transaction**: `apply()` wraps V1→V127 in one `transaction(conn)`; the spec's
  interruption model (Stage 2) is atomic-rollback, not per-version — the plan's original "between
  versions committed" taxonomy was corrected.
- **Fixtures are apply-to-head-then-revert** (mirroring `test_migrator_v127_moved_event.py`), seeded
  origin-aware with synthetic data. The **independent oracle** (hand-authored from the migrator
  source, no shared code path) validates each fixture's present/absent delta objects + ledger head.
- Corrected version semantics baked into the spec/oracle: V119 = `source_index_bootstrap_runs`
  (pass trail); source cards = V93 `source_intelligence_generated_notes`; V126 = `renamed_from_source_id`;
  V127 = moved-event queue (`dest_rel_path`/`next_attempt_at`, `'moved'` CHECK).

## 4. Tests and static analysis (exact commands)

- Phase C suite: `PYTHONPATH="src:subrepos/construction-financial-review/src" .venv/bin/python -m pytest tests/source_index/`
  → **29 passed** (`preflight/regression-migrator-and-phase-c.txt`).
- Migrator-canary regression (v117/v123/v126/v127 + `moved_drain`) co-run with the Phase C suite →
  **114 passed, exit 0** (`regression-migrator-and-phase-c.txt`). Confirms PC-AC-046 for the migrator
  canaries + no interference from the additions.
- Ruff (new engine, `--no-force-exclude` to defeat the `store/` default exclude) → **All checks
  passed**; ruff on support+test modules → **All checks passed**.
- Strict mypy (new engine, explicit; venv interpreter) → **Success: no issues found**.
  See `preflight/static-analysis.txt`. (`.venv/bin/mypy` and bare `pytest` shims are broken on this
  box — Python-3.12 interpreter trap; the venv `python -m` form is used, PCR-003.)

## 5. Required-changes conformance (PCR-001 … PCR-009)

- **PCR-001 / PCR-008** — all fixture/evidence DB writes go under a caller-provided rehearsal root;
  the builder rejects destinations outside the root, symlinked roots, missing roots, unmarked
  pre-existing DBs, and refuses the configured application DB; fixtures carry a disposable marker +
  manifest. Negative tests present. (PC-AC-054 verified.)
- **PCR-002** — independent oracle in a separate module; corruption negative test proves it rejects a
  V121 fixture with a stray V125 object. (PC-AC-051 verified.)
- **PCR-003** — committed gate untouched; local evidence uses the venv interpreter. No `.venv`
  hard-coding added to any committed script.
- **PCR-004** — new production engine explicitly Ruff- and strict-mypy-covered; one mypy override
  added. (PC-AC-052/053 verified.)
- **PCR-005 / PCR-006 / PCR-007** — recorded in the durable spec §9 as Stage 2/3 requirements; not
  implemented in Stage 1. 800k remains a hard completion gate (PC-AC-048 NOT VERIFIED; PC-AC-055).
- **PCR-009** — this disposition + the Stage 2 delta proposal (§7).

## 6. Acceptance-criteria status (Stage 1 subset)

VERIFIED this stage: PC-AC-001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 045
(fixture-side), 047, 051, 052, 053, 054. PC-AC-013 generator VERIFIED / large run NOT VERIFIED.
PC-AC-046 spot-verified (migrator canaries). PC-AC-043/044 hold (no production/NAS/watcher/parser
touched). All Stage 2/3 criteria remain **NOT VERIFIED** by design.

## 7. Stage 2 delta proposal (returns for a new AEOS review)

1. `store/sqlite_backup.py` — online backup via `Connection.backup()` over a read-only source URI;
   receipt shaped like `startup_schema_policy.py`; rehearsal-root destinations only.
2. Migration matrix: `build_fixture(origin) → apply() → assert head + parity` for
   V121/V124/V125/V126/head/fresh, using `collect_inventory` pre/post logical-hash diff + the three
   PRAGMA checks + idempotent rerun (PC-AC-014..029).
3. Interruption/recovery under the **single-atomic-transaction** model with a **deterministic
   barrier** (PCR-005) — no timing sleeps.
4. Backup/restore round-trip + representative `SourceIndexRepository` reads on the restored DB
   (PC-AC-030..039).

## 8. Known gaps / unverified

- Fixtures are reconstructed by reverting the current migrator, not sampled from a real deployed DB
  (RISK-PC-001); mitigated by the independent oracle but not eliminated — a sanitized production
  schema-inventory comparison remains a separately-authorized cross-check.
- No backup/restore, migration-forward, interruption, compatibility, or 800k evidence exists yet
  (out of Stage 1 scope).
- V123 has no positive object discriminator on a from-head fixture; it is validated only via the
  ledger head (documented in the spec).

**Recommended next AEOS gate:** Stage 2 plan review (backup/migration/recovery proof), reconciled to
this implementation.

## 9. Independent-review package (response to `INSUFFICIENT EVIDENCE`)

A self-contained review package is provided under `review-package/` so the actual source can be
inspected/reconstructed without any commit, push, or PR:

| Audit gap | Resolution |
|-----------|------------|
| S1-AUD-001 (implementation absent) | `review-package/phase-c-stage1.patch` contains every Stage 1 file's full source |
| S1-AUD-002 (no diff/patch) | binary patch: `pyproject.toml` as a diff vs `origin/main`, each new file as a `/dev/null` addition; **verified `git apply --check` applies cleanly onto a pristine `origin/main`** |
| S1-AUD-003 (test identity) | `review-package/test-identity.txt`: exact command, 29 Phase C vs 85 canary node counts (=114), function enumeration, 0 skipped/deselected/warnings |
| S1-AUD-004 (exit capture) | `preflight/static-analysis.txt`: explicit `RUFF_ENGINE_EXIT=0`, `RUFF_SUPPORT_EXIT=0`, `MYPY_ENGINE_EXIT=0` (the earlier blank was a zsh word-split artifact, now corrected) |
| S1-AUD-005 (uncommitted identity) | `review-package/content-manifest.txt`: `git hash-object` blob SHA + SHA-256 for every file and the patch |

The work remains **uncommitted**. An authorized local evidence commit + `git bundle` can be produced
on request (procedure in `review-package/README.md`); it will not be pushed until the audit passes.

## 10. Corrective round (response to `FAIL — BLOCKERS REMAIN`, S1-AUD-006 … S1-AUD-013)

Corrective implementation applied in place (still uncommitted). Full suite now **135 passed, exit 0**
(85 migrator canaries + 50 Phase C tests), ruff + strict mypy clean.

| Finding | Resolution |
|---------|------------|
| **S1-AUD-006** V121 retains a "V123 index" | **Repo-truth correction + faithful modeling.** `idx_si_sources_root_relpath` is a **V93** object (present at all origins), *not* introduced by V123 — proven empirically (head has only the root-scoped index, created by the V93 base DDL; V123 only `DROP`s the narrow index). The real gap was fidelity: a genuine pre-V123 deployed DB carried the **narrow** unique `idx_si_sources_relpath (source_kind, rel_path)`. Pre-V123 fixtures now install it (globally-unique paths, no cross-root dupes); V123+ omit it (cross-root dupes present). The oracle asserts narrow present **iff origin < 123** plus **exact SQL** for both indexes; corruption negatives (inject narrow at V124 / remove narrow at V121) both rejected. |
| **S1-AUD-007** no column/constraint inventory | Engine now emits a full **structural signature**: ordered columns (`table_xinfo`: type/nullability/default/pk), foreign keys (`foreign_key_list`), index detail (`index_info` + uniqueness/partial + canonical SQL), triggers, views, normalized DDL — folded into the logical hash. Mutation tests: added column / dropped index / index-uniqueness change each flips the hash. |
| **S1-AUD-008** read-only can create a DB | `_open_readonly` is **fail-closed**: requires an existing regular file, opens `mode=ro&immutable=1` (no `-wal`/`-shm`/journal creation), **no** read-write fallback. Tests: missing path raises + creates nothing; non-file raises; inspection creates no sidecar. |
| **S1-AUD-009** hash omits text/FTS | Logical hash now includes `source_intelligence_text`/chunks/relationships/summaries and **FTS linkage parity** (matched / dangling / orphan vs the kind-appropriate FTS table). Corruption tests: deleted FTS row, stale `fts_rowid`, changed excerpt, missing source text, orphan FTS row — all detectable. |
| **S1-AUD-010** fresh origin absent | Distinct `origin="fresh"` fixture (empty DB migrated to head, no legacy seeding), not an overloaded integer; test asserts head schema + empty source tables. |
| **S1-AUD-011** app-DB refusal untested | Added a test monkeypatching `PathPolicy.get_db_path()` to the fixture destination → rejection proven; the `except` is narrowed to `(OSError, RuntimeError, ValueError)`. |
| **S1-AUD-012** `reconcile_pending` missing | Seeded on a third generation-only root (`nas-archive`); the head fixture now carries **all six** generation states, one active per root across three roots. |
| **S1-AUD-013** archive identity mismatch | Evidence package regenerated; the exact delivered archive SHA-256 is reported in the handoff message and `review-package/README.md`, and the README's contents list matches the archive byte-for-byte. |

**PC-AC updates:** PC-AC-006 now "all six generation states"; added PC-AC-056 (narrow-index exact-SQL),
PC-AC-057 (fail-closed read-only), PC-AC-058 (structural + FTS parity in hash), PC-AC-059 (fresh
fixture). All remain within the Stage 1 boundary — no C4/backup, migration-forward, compatibility, or
800k work was performed.

## 11. Corrective round 2 (response to round-2 `FAIL`, S1-AUD-014 … S1-AUD-016)

Applied in place (still uncommitted). Full suite now **140 passed, exit 0** (85 canaries + 55 Phase C);
ruff + strict mypy clean.

| Finding | Resolution |
|---------|------------|
| **S1-AUD-014** immutable read ignores committed WAL | `_open_readonly` now **rejects a non-empty `-wal`** (`uncheckpointed_wal_present`) before opening `immutable=1`; it never checkpoints. Test proves rejection + unchanged DB/WAL hashes + no new sidecar; empty/absent WAL accepted (fixtures truncate WAL). → PC-AC-060 |
| **S1-AUD-015** same-rowid FTS content undetected | Added **per-row FTS content digests** — `sha256(table ∥ rowid ∥ text ∥ rel_path ∥ aux)` for both FTS tables — folded into the logical hash. Seeded obsidian_note sources so `obsidian_note_fts` is populated. Tests: same-rowid text corruption (parity unchanged, hash changes), path/aux corruption, and `obsidian_note_fts` corruption all detected. → PC-AC-061 |
| **S1-AUD-016** structural scope incomplete | `_STRUCTURAL_TABLES` now = all 16 inventoried source-index tables **+ both FTS virtual tables**. Test: a schema change to a previously-omitted table (`source_structure_folders`) flips the hash. Stale oracle docstring corrected. → PC-AC-062 |
| **S1-AUD-013** package provenance | The **patch is the canonical identity anchor** (the auditor confirmed it reconstructs all files and matches `content-manifest.txt`). The archive is a convenience wrapper; its exact bytes/SHA-256 are reported at delivery and its README describes the true layout. Any hash mismatch at the auditor's end indicates a stale upload, not a package defect. |

No Stage 2/3 or 800k work was performed. Stage 1 boundary intact.
