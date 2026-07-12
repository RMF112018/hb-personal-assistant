# 15 — Final cumulative validation

Seven separately-named validation runs, each with its own command, exact scope, branch HEAD, JUnit totals,
failing node IDs, and baseline comparison. Raw per-run artifacts are under `final-runs/`. All runs were
executed on branch HEAD (the FINAL checkpoint working tree) with
`PYTHONPATH="src:subrepos/construction-financial-review/src" .venv/bin/python -m pytest -p no:cacheprovider`
(the repo's custom terminal reporter suppresses the text tally, so totals are read from `--junit-xml`).

## Results

| Run | Scope | tests | fail | err | Artifact |
|---|---|---:|---:|---:|---|
| `phase-a-authored-tests` | the 5 new + 4 modified Phase-A test files | **164** | 0 | 0 | `final-runs/phase-a-authored-tests.txt` |
| `phase-a-cross-checkpoint` | A1+A3+A2+A4 new suites + FINAL lifecycle, run together | **113** | 0 | 0 | `final-runs/phase-a-cross-checkpoint.txt` |
| `source-index-client-surface` | connector service, NAS connector, connector-eval, trust, health, manifest freshness + parity | **103** | 0 | 0 | `final-runs/source-index-client-surface.txt` |
| `source-index-generation-and-recovery` | generation hardening, quarantine, lifecycle, watcher ×4, metadata bootstrap/generation | **227** | 0 | 0 | `final-runs/source-index-generation-and-recovery.txt` |
| `source-index-migrations` | the 3 (corrected) schema-version tests + `migrator_v117`/`v123` | **13** | 0 | 0 | `final-runs/source-index-migrations.txt` |
| `source-index-broad-regression` | the CI gate's full pytest target set (`ci_source_index_gate.sh`) | **384** | 0 | 0 | `final-runs/source-index-broad-regression.txt` |
| `repository-static-checks` | ruff check (clean set) + ruff format --check (new formatted files) + mypy (new modules) | n/a | 0 | 0 | `final-runs/repository-static-checks.txt` |

**Zero failures across all seven runs.** These are separate executions with distinct scopes — none is a
relabeled "superset" of another; overlaps (e.g. the schema tests appear in both `migrations` and
`generation-and-recovery`) are intentional scope membership, not double-counting within a single run.

## Baseline comparison

- The **5 new** Phase-A test files do not exist on `origin/main`; the **4 modified** files' pre-existing tests
  pass on `origin/main`. → no baseline failures introduced.
- The **3 schema-version tests** (`test_v122_fresh_and_incremental_migration`,
  `test_v119_migration_idempotent_and_additive`, `test_v120_migration_idempotent_and_additive`) failed on a
  pristine `origin/main` worktree (`scratchpad/origin-baseline`, `9c27839b`) with `124 == 123`; they were
  corrected to `== LATEST_SCHEMA_VERSION` (drift-proof, isolated, justified — `08`) and now pass.
- The only source-index failures that survive anywhere are the pre-existing `08` baseline failures #4/#5/#6,
  each reproduced on pristine `origin/main`; #6 is `--deselect`-ed from the gate with justification. None is
  Phase-A-authored; none was ever absorbed into a prove-red set.

## A4 trust-integration lifecycle (item 3)

`tests/test_source_index_quarantine_lifecycle.py` (in `phase-a-authored-tests`,
`phase-a-cross-checkpoint`, and `source-index-generation-and-recovery`) exercises the full sequence through the
**real shared authority**, not isolated mocks:

- `test_quarantine_lifecycle_blocks_serving_and_reconcile_then_recovers` — a REAL scan drives a poison file to
  a blocking quarantine (generation `failed`+`quarantine_unresolved`); then `load_root_trust`/`evaluate_root_trust`
  → blocked (+`quarantine_unresolved` reason), `search`/`list`/`read` → fail-closed envelopes, the next
  `begin_generation_pass` → blocked sentinel (reconciliation suspended). Operator `retry_quarantine` resolves
  the path; the root **remains non-authoritative** (serving still blocked, no completed generation). A normal
  validating pass completes → trust `safe`, serving answers again, the next pass is no longer blocked.
- `test_quarantine_toggles_watcher_activation_via_shared_authority` — `evaluate_root_trust` on fully
  watcher-ready inputs flips `safe_for_watcher_activation` True→False on the unresolved-quarantine count alone.
- `test_quarantined_root_fails_watcher_start_closed` — a real `SourceWatcher.start()` on a quarantined root
  degrades (never `watchdog`/`polling`).

(The end-to-end "watcher activation succeeds" terminal step is proven via the shared-authority predicate;
`SourceWatcher.start()` full activation additionally requires the `watchdog` backend, which is absent in this
local venv — see `10`. The quarantine integration into watcher activation is proven independent of that.)

## Migration & retention (items 4, 5)

- Migration precision (`06`, `a4-migration-precise.txt`): fresh V125; **REAL V124 fixture** (built by the
  origin-baseline migrator) upgraded to V125; idempotent rerun; table/index DDL; `PRAGMA foreign_key_check`
  (no FKs — intentional), `quick_check`, `integrity_check` all ok; rollback coexistence (older V124 migrator
  ignores the additive V125 table without error). No schema downgrade claimed.
- Retention (`a4-retention-evidence.txt`): unresolved quarantine survives generation pruning; `generation_id`
  nulled while `origin_generation_id` retained; root blocking does not depend on a retained generation row;
  cleanup cannot remove an unresolved record; retention cannot flip an unsafe root to safe.

## Full-branch audit (item 7)

Two independent read-only audits over the complete diff `9c27839b..HEAD` (+ evidence set):
- **Branch-diff scope audit** — CLEAN across all 10 categories (no unrelated changes; no absolute/personal
  paths; no secrets; no stale artifacts; V125 migration wired; no dead duplicate mapping/trust logic; no remote
  exposure of quarantine mutation; no contradictory client fields; checksum generated canonically; no
  source-file write/delete capability).
- **Security/secrets audit** — CLEAN (no secrets, tokens, credentials, or genuine PII/path leaks in the diff or
  evidence; synthetic scratch fixtures only).

## CI gate (item 6)

`.github/workflows/source-index-gate.yml` + `scripts/ci_source_index_gate.sh` — YAML parses, script passes
`bash -n`, and the gate's pytest target set is 384/0 (`source-index-broad-regression`). See `10-ci-gate.md`
for triggers, scope, the recommended required-check name, and the branch-protection recommendation (not applied).

## Disposition

**`PR_READY`** — see `12-pr-readiness.md`.
