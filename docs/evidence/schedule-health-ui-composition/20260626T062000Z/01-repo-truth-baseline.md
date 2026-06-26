# Repo Truth Baseline

## Fetch / Ref

`git fetch origin --prune` advanced `origin/main` from V74 to V75:

```text
185de7ff feat(schedule): add import health foundation (#151)
```

Remote refs included:

```text
origin/HEAD -> origin/main
origin/fix/schedule-import-health-foundation-20260626
origin/main
```

## V75 Gate

Confirmed on `origin/main` before implementation:

```text
src/hb_assistant/store/migrator.py: LATEST_SCHEMA_VERSION = 75
src/hb_assistant/store/migrator.py: v75_schedule_import_health_foundation
src/hb_assistant/construction/analytics/api.py: GET /api/schedules/versions/{schedule_version_key}/health-data
```

No schema, parser, persistence, import workflow, or backend computation files were changed in this UI branch.

## Worktree

```text
/Users/bobbyfetting/hb-personal-assistant-worktrees/schedule-health-ui-composition
```

Branch:

```text
fix/schedule-health-ui-composition-20260626000000
```
