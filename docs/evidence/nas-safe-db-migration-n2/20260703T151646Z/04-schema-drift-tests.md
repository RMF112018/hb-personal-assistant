# N2 · 04 — Schema-Drift Tests

All tests ran against `tmp_path` scratch SQLite DBs only. No live/production DB, secrets, network, or
NAS production path was touched. Python 3.14.5 (`.venv`), pytest 9.0.3.
`PYTHONPATH=src:subrepos/construction-financial-review/src` (worktree src wins over the editable install).

## 1. Empirical drift confirmation (pre-fix, scratch DB)

```
LATEST_SCHEMA_VERSION (constant) = 97
apply() landed version           = 98
MAX(schema_migrations.version)   = 98
v98 row                          = (98, 'v98_project_schedule_review_dispositions')
DRIFT (apply != constant)        = True
```

## 2. Red → green proof (the fix repairs a live breakage)

With `LATEST_SCHEMA_VERSION` reverted to **97** (fix stashed), three equality tests **FAIL**:

```
tests/test_phase_10_schema.py::test_migration_idempotent_and_preserves_prior_versions  → AssertionError: assert 98 == 97 (apply())
tests/test_phase_10_schema.py::test_schema_status_ready                                 → assert 98 == 97
tests/test_schema_version_head_consistency.py::test_recorded_head_equals_latest_constant → assert 98 == 97 (MAX(schema_migrations.version))
```

With the fix restored (**98**), all three pass. This confirms the drift was breaking the suite on the
base branch, and the one-line fix repairs it.

## 3. Targeted run (with fix) — PASS

```
pytest tests/test_schema_version_head_consistency.py tests/test_phase_10_schema.py \
       tests/test_migrator_v76_project_staffing.py tests/test_phase_09_schema_status.py \
       tests/test_fastapi_analytics_app_shell.py
→ 41 passed (1 StarletteDeprecationWarning, unrelated)
```

Includes the 5 new guard tests and representative previously-broken equality tests, plus the
`/health` shell tests.

## 4. Cross-domain bundles (required for `store/migrator.py` edits, per CLAUDE.md) — PASS

| Bundle | Command | Result |
|---|---|---|
| Schedule (migrator/schema canary + new guard test) | `scripts/test-schedule.sh` | **328 passed, 2 deselected**, exit 0, 612.95s |
| Forecasting | `scripts/test-forecasting.sh` | **1166 passed, 3 deselected**, exit 0, 1585.90s |

The new `tests/test_schema_version_head_consistency.py` is in the schedule bundle allowlist and passed
there. `bash -n scripts/test-schedule.sh` OK; `--collect-only` resolves the new target (5 tests).

## 5. NAS scaffold test — 1 PRE-EXISTING failure (unrelated to schema drift)

```
pytest tests/test_nas_runtime_scaffold.py
→ test_dockerignore_excludes_config_db_and_secrets FAILED
  (asserts '**/security/' and '**/auth/' in .dockerignore)
```

**Pre-existing, not caused by N2.** Commit 581ad598's own N1C fix deliberately removed `**/security/`
and `**/auth/` from `.dockerignore` (they were excluding the real `src/hb_assistant/{auth,security}/`
source packages and broke the container import); the test was not updated to match. My N2 diff touches
neither `.dockerignore` nor this test (`git diff --name-only` = `scripts/test-schedule.sh`,
`src/hb_assistant/store/migrator.py`). Documented in `09`; recommended fix in `11` (N2B). Not fixed in
N2 (bounded scope + operator instruction to not edit unrelated stale assets).

## 6. Lint

`ruff check tests/test_schema_version_head_consistency.py src/hb_assistant/store/migrator.py` →
**All checks passed** (no `ruff format` run — avoided to prevent unrelated reformat churn).

## 7. Test side-effects reverted (not staged)

The forecasting/schedule bundles regenerated 8 tracked evidence artifacts as side-effects (1 under
`…phase-08b-automation-hardening/`, 7 under `…phase-08c-financial-readiness/`) — fresh timestamps/
run_ids/gate lines; the 08b one also stamped the live DB head (98 vs a stale committed 63). These are
pre-existing test-writes-tracked-file behavior, **not** N2 changes. All were reverted
(`git checkout --`); final tracked diff is exactly `scripts/test-schedule.sh` +
`src/hb_assistant/store/migrator.py`. See `09`.

## Not run (out of scope / would need live resources)

Full `pytest` suite (reserved for release validation); anything requiring the live Mac DB, secrets,
Procore `live`, network, or NAS production paths.
