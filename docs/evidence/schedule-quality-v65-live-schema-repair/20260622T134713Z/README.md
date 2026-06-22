# Schedule Quality V65 Live Schema Repair — 2026-06-22

Live Application Support DB repair and TWNU18 quality re-validation after V65 derived-finish-float schema drift correction and quality-engine normalization fixes.

## Target

- **DB:** `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- **SVK:** `tropical|TWNU18|2026-05-26T08:00:00`
- **Source:** `~/Downloads/schedule-xml-files.zip` → `TWNU18.xml` (SHA256 `26b4661029d955d08212d166d8295844fb964af7b6577885d7a4e45a0701a8e2`)

## Artifacts

| File | Contents |
|------|----------|
| `02-schema-after.json` | Schema v66 + V65 physical column/metric CHECK readiness |
| `03-twnu18-canonical-before-rerun.json` | Pre-rerun committed import + V65 field population |
| `04-twnu18-reimport.json` | Supersede re-import commit receipt |
| `04-twnu18-canonical-after.json` | Post-import canonical counts + derived-float population |
| `05-metrics-before.json` | Quality metrics before parser/engine fixes rerun |
| `06-quality-rerun.json` | Manual quality rerun queue + process receipt |
| `06-metrics-after.json` | Key DCMA metrics after fix (float, logic, relationship types, cost loading) |
| `07-downstream-readiness-after.json` | Downstream readiness posture |
| `08-stop-condition-checks.json` | Operator stop-condition gate (all passed) |

## Stop conditions (all passed)

- `schedule_v65_physical_ready: true` despite `schema_migrations >= 65`
- Derived-float fields populated on canonical activity rows (`with_float_hours: 677`)
- `dcma_resources_cost_loading` not passed on cost-code/`"none"` alone (`schedule_posture: not_cost_loaded`)
- `cost_weighting: ready_with_quality_penalty` (not blocked)
- `true_cost_loaded_analytics: unavailable_not_cost_loaded`
- `dcma_relationship_types` shows real distribution (FS=2235, FF=1357, SS=125, SF=1) — not `0/3718`

## Pre-merge frontend build proof

`frontend/src/lib/errorCopy.ts` is **absent on `origin/main`** (`16631869`) while 11 files import it. Clean `npm ci && npm run build` on an isolated main worktree reproduces the same `TS2307` failure (`09-main-clean-build-failure.log`). PR #90 does not touch `errorCopy` imports; the only build-log delta vs main is removal of a pre-existing unused `waitFor` import in `ScheduleQualityPage.test.tsx` (`10-pr90-build-regression-check.json`).

## Branch

`feature/v65-schema-quality-repair` (worktree `schedule-derived-finish-float-v65`)