# N2B — Scaffold Test-Drift Fix (NAS `.dockerignore` safety test)

Timestamp (UTC): 20260703T160919Z · Phase: **N2B** (narrow cleanup/hardening before commit).
Follows N2 ([[docs/evidence/nas-safe-db-migration-n2]]); closes the pre-existing finding recorded in
N2 `09-risk-and-stop-conditions.md` and `11-next-phase-n2b-or-n3-plan.md`.

## Root cause of the scaffold test drift

Commit `581ad598` (N1B+N1C) shipped an **internally contradictory** pair:

- The **N1C `.dockerignore` fix** deliberately **removed** the broad directory globs `**/auth/` and
  `**/security/`. Those globs had been excluding the *real source packages*
  `src/hb_assistant/auth/` and `src/hb_assistant/security/` from the build context, so the non-root
  container booted into `ModuleNotFoundError: hb_assistant.auth`. The fix narrowed exclusions to secret
  **files** and documented (in a `.dockerignore` NOTE) that `auth/`/`security/` dirs must stay.
- The **test** `tests/test_nas_runtime_scaffold.py::test_dockerignore_excludes_config_db_and_secrets`
  was **not updated** in the same commit — it still asserted `**/security/` and `**/auth/` must be
  *present* in `.dockerignore`. So the committed test contradicted the committed fix and failed:

  ```
  AssertionError: .dockerignore missing safety exclusion: **/security/
  ```

This was a test-vs-code drift local to the scaffold branch, **unrelated to the N2 schema-version
drift**. N2 diagnosed and deferred it (bounded scope); N2B fixes it.

## Exact test fix

`tests/test_nas_runtime_scaffold.py` — the test now asserts the **intended** N1C behaviour:

1. `test_dockerignore_excludes_config_db_and_secrets` — the required-present list drops the two wrong
   directory globs and asserts the real secret/config/DB/env **file** exclusions actually present in
   `.dockerignore`:
   `config/config.yml`, `**/.env`, `**/*.sqlite`, `**/*.db`, `**/*.key`, `**/*.pem`,
   `**/msal-token-cache*.bin`, `**/text-vault.key`.
2. **New** `test_dockerignore_does_not_exclude_source_packages` — asserts (on comment-stripped content,
   so the explanatory NOTE is ignored) that `.dockerignore` does **not** exclude the source packages
   via `**/auth/`, `**/security/`, `src/hb_assistant/auth`, or `src/hb_assistant/security`. This pins
   the N1C intent so the drift cannot recur in either direction.

`.dockerignore` itself is **unchanged** — the N1C fix is preserved, and nothing was broadened (no new
directory-level globs; only file-pattern exclusions are asserted). No change to the Docker image.

## Test results

Python 3.14.5 (`.venv`), pytest 9.0.3, `PYTHONPATH=src:subrepos/construction-financial-review/src`.
Scratch `tmp_path` DBs only.

| Suite | Command | Result |
|---|---|---|
| NAS scaffold | `pytest tests/test_nas_runtime_scaffold.py` | **19 passed** (was 18 with 1 failing; +1 new negative test) |
| Schema guard | `pytest tests/test_schema_version_head_consistency.py` | **5 passed** |
| Schedule bundle | `scripts/test-schedule.sh` | **328 passed, 2 deselected**, exit 0 (591.44s) |
| Forecasting bundle | `scripts/test-forecasting.sh` | **1166 passed, 3 deselected**, exit 0 (1561.23s) |
| Lint | `ruff check` (scaffold test, schema test, migrator) | **All checks passed** |

## Boundary attestation

No live DB copied/opened/migrated (scratch `tmp_path` DBs only). No secrets, MSAL/Procore creds,
Text-Vault, or vault touched. No NAS commands (no SSH). No backend/container started. No sudo. Not
pushed.

## Files changed by N2B

| File | Change |
|---|---|
| `tests/test_nas_runtime_scaffold.py` | fix drifted `.dockerignore` assertions + add negative source-package guard |
| `docs/evidence/nas-scaffold-test-hardening-n2b/20260703T160919Z/**` | this evidence |

`.dockerignore` and `deploy/nas/**` unchanged; N1C fix preserved.
