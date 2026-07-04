# N2 · 03 — Schema-Drift Fix

Timestamp (UTC): 20260703T151646Z

## Change 1 — the fix (one line)

`src/hb_assistant/store/migrator.py:17`

```diff
-LATEST_SCHEMA_VERSION = 97
+LATEST_SCHEMA_VERSION = 98
```

Rationale: the migrator already applies and records v98; this aligns the single source of truth with
the actual recorded head. Migration semantics untouched. No existing test asserts a literal `97`, so
this repairs the ~13 equality tests broken by the drift without editing any of them (see `04`).

## Change 2 — regression guard test (new)

`tests/test_schema_version_head_consistency.py` (5 tests, scratch-DB only). Pins the invariant that
drifted so it cannot silently recur:

- `test_fresh_db_migrates_to_latest_constant` — `apply() == LATEST_SCHEMA_VERSION`.
- `test_recorded_head_equals_latest_constant` — `MAX(schema_migrations.version) == LATEST_SCHEMA_VERSION` (the exact quantity that drifted).
- `test_v98_migration_row_present` — `schema_migrations` row `version=98, name='v98_project_schedule_review_dispositions'`.
- `test_apply_is_idempotent` — double `apply()` returns the same head and does not error (pins the v98 version-guard).
- `test_health_reports_schema_ready_equality` — `/health` on a migrated scratch DB reports `schema_version == schema_expected == LATEST_SCHEMA_VERSION` and `schema_ready is True`, run with `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1`; DB is an explicit `tmp_path` path so it can never resolve to the live PathPolicy DB (conftest `isolated_hb_pa_config` also FS-isolates).

## Change 3 — test-bundle maintenance

`scripts/test-schedule.sh` — added `"tests/test_schema_version_head_consistency.py"` to the target
allowlist (alphabetically last). Per `CLAUDE.md`, a new schema/migrator test must be added to the
schedule bundle (the cross-domain migrator canary) or it is silently uncovered by focused validation.
Verified: `bash -n` OK; `--collect-only` resolves the new target (5 tests).

## Explicitly NOT changed (bounded scope)

- `docs/implementation/project-schedule-controls/baseline-repo-truth.md:140` (`= 94`, separately
  stale) — noted in `02`, not edited per operator instruction.
- No migration SQL, no `>=` health operator, no other test, no doc.

## Files changed by N2 (intended)

| File | Change |
|---|---|
| `src/hb_assistant/store/migrator.py` | `LATEST_SCHEMA_VERSION` 97 → 98 (1 line) |
| `tests/test_schema_version_head_consistency.py` | new regression guard (5 tests) |
| `scripts/test-schedule.sh` | +1 allowlist entry |
| `docs/evidence/nas-safe-db-migration-n2/20260703T151646Z/**` | this evidence package |

A test **side-effect** (not an intended change) regenerated
`docs/evidence/construction-intelligence-phase-08b-automation-hardening/phase-08b-final-no-writeback-proof.md`
during the bundle run (stamps the live DB head; committed value was a stale `schema_version=63`). It
was reverted to the committed state and is **not staged** — see `04` and `09`.
