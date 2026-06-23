# Schedule XER Import Commit FK Repair — 2026-06-22

Repairs live SQLite FK drift where schedule child tables referenced orphan `schedule_file_imports_v66` while commits inserted into canonical `schedule_file_imports`.

## Root cause

- Live `procore_ep_schedule_*` FK targets: `schedule_file_imports_v66(import_id)`
- Application inserts: `schedule_file_imports`
- Result: `IntegrityError` on activity bulk insert; partial `committed` parent with zero children (`import_id=984adf7e43f5`)

## Fix summary

| Area | Change |
|------|--------|
| V69 migration | Merge orphan parents, rebuild six child tables with FK → `schedule_file_imports`, drop `schedule_file_imports_v66`, mark partial commits `failed` |
| Commit path | Single SQLite transaction for version row, import parent, and subgraph |
| API errors | `schedule_import_persistence_failed` / `schedule_project_mismatch` → HTTP 409 |
| UI | Preview-bound `project_key`; clear preview on picker change |
| XER metadata | `source_project_*` columns stored separately from operator `project_key` |

## Artifacts

| File | Contents |
|------|----------|
| `01-live-fk-before.json` | Pre-repair FK inventory (from diagnosis) |
| `02-partial-commit-before.json` | Partial commit row counts before repair |
| `03-migration-v69-proof.txt` | Post-V69 schema version, FK list, `foreign_key_check` |
| `08-backend-tests.log` | Targeted backend pytest gate |
| `09-frontend-tests.log` | ScheduleImports/Routes/QualityPage vitest |
| `10-build.log` | `npm run build` |

## Validation gates (passed)

```bash
pytest tests/test_schedule_import_api.py tests/test_schedule_project_association.py tests/test_schedule_critical_path_quality.py tests/test_migrator_v69_schedule_import_fk_repair.py
pytest tests/test_schedule_*.py tests/test_schedule_project_association.py
cd frontend && npm test -- ScheduleImports ScheduleRoutes ScheduleQualityPage && npm run build
```

## Post-repair live posture

- Schema version: 69
- Orphan `schedule_file_imports_v66`: dropped
- Partial import `984adf7e43f5`: `import_status=failed`