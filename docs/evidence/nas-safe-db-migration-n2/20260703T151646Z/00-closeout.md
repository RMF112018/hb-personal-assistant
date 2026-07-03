# N2 — Closeout · Safe DB Migration Planning + Schema Drift Audit

Timestamp (UTC): 20260703T151646Z · Local start: Fri Jul 3 11:16 EDT 2026

## Coordinates

- Branch: `fix/nas-schema-drift-n2-20260703T151646Z`
- Worktree: `/Users/bobbyfetting/hb-personal-assistant-worktrees/fix/nas-schema-drift-n2-20260703T151646Z`
- Base branch/commit: `feature/nas-runtime-scaffold-n1b-20260703T123726Z` @ `581ad598` (N1B+N1C scaffold, 1 ahead of `origin/main`)
- HEAD commit: `581ad598` (N2 changes are **uncommitted** on top)
- Python: 3.14.5 (`.venv`); venv activated / used via explicit path
- Evidence dir: `docs/evidence/nas-safe-db-migration-n2/20260703T151646Z/`

## Files changed (intended N2 diff)

| File | Change |
|---|---|
| `src/hb_assistant/store/migrator.py` | `LATEST_SCHEMA_VERSION` 97 → 98 (1 line) |
| `tests/test_schema_version_head_consistency.py` | **new** regression guard (5 tests) |
| `scripts/test-schedule.sh` | +1 allowlist entry (new test → schedule bundle) |
| `docs/evidence/nas-safe-db-migration-n2/20260703T151646Z/**` | this evidence package (00–11 + local-sensitive/README) |

Final `git status`: exactly the two tracked edits above + the two untracked additions (evidence dir,
new test). 8 test-regenerated evidence artifacts (08b/08c) were reverted and are **not staged**.

## Tests run / results

- Empirical drift confirm (scratch DB): apply()=98, constant=97, v98 row present → **DRIFT true**.
- Red→green: at 97, 3 equality tests fail `98==97`; at 98 they pass.
- Targeted (with fix): **41 passed**.
- Schedule bundle: **328 passed, 2 deselected**, exit 0 (incl. new guard test).
- Forecasting bundle: **1166 passed, 3 deselected**, exit 0.
- `ruff check` on changed Python: **passed**.
- NAS scaffold test: **1 pre-existing failure** (`test_dockerignore_excludes_config_db_and_secrets`),
  unrelated to schema drift — see `04`/`09`/`11`.

## Boundary attestations

- NAS commands run: **none** (no SSH this phase; repo/scratch-DB only).
- DB copied / opened / migrated: **none live/production**. Only disposable `tmp_path` scratch DBs.
- Live Mac DB / secrets / MSAL / Procore / Text-Vault / vault touched: **none**.
- sudo used: **no**.
- Backend / container started: **no**.
- Committed: **no**. Pushed: **no**.

## Findings

- **Schema drift (root cause):** migrator defines/applies/records **v98**
  (`v98_project_schedule_review_dispositions`) but `LATEST_SCHEMA_VERSION` stayed **97**;
  `apply()`/`current_version()` = `MAX(schema_migrations.version)` = 98 disagreed with the constant.
  Masked by `/health` `>=`; exposed by `automation_health` `==` and ~13 equality tests.
- **Fix applied:** `migrator.py:17` → 98. Repairs the broken equality tests; no test/doc edits needed.
  Guard test added so it cannot silently recur.
- **Migration plans:** SQLite backup-API copy (`05`), live-DB quiesce (`06`), copied-DB smoke (`07`),
  secrets/Text-Vault (`08`) — all **plan-only**, none executed. Copy script **not** implemented per
  operator instruction.
- **Pre-existing issues surfaced (not schema-related):** scaffold `.dockerignore` test contradicts its
  own N1C fix (fix in N2B); several tests write tracked evidence files (reverted, follow-up noted).

## Remaining gates before copied-DB smoke

auth/security ACL hardening (0777) · public-exposure confirmation · runtime-user/admin split — all
external/operator, still **WARN/OPEN** (N1D). Copied-DB smoke = **NO**; production cutover = **NO**.

## N2 final result: **PASS**

Schema drift fixed and proven; all migration/planning documents complete; work left uncommitted pending
authorization. Recommended next: **N2B** (schema-fix closeout + security-gate completion), then **N3**
(safe copied-DB by backup API) only after gates clear and the operator authorizes. **Copied-DB smoke
and production cutover remain prohibited unless explicitly authorized later.**
