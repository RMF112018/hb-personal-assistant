# Schedule Intelligence V62 Live Cutover Evidence

- captured: `2026-06-22T09:47:45.279840+00:00`
- branch: `feature/forecast-ui-live-config-promotion-orphan-fix`
- commit: `33fd116ca9438eb84437686b84494c1f8ade83db`
- status: **pass**
- schema version: `62` (expected `62`)
- table count: `412` (expected `412`)

## Artifacts

- `live_preflight.json` — pre-migration read-only audit
- `backup_receipt.json` — backup metadata only (`backups/*.sqlite` is local-only; never commit)
- `copied_live_rehearsal_proof.json` — migration + GMA smoke on copy (`work/*.sqlite` is local-only; never commit)
- `live_apply_receipt.json` — live migration receipt (if applied)
- `post_migration_certification.json` — post-apply certification
- `schedule_tests.log` — pytest output

