# Validation Matrix

The local agent must complete and record the following validation.

| Area | Required proof | Evidence file |
|---|---|---|
| Repo state | clean branch from `main`, no dirty tree before implementation | `00-repo-state.md`, `01-branch-state.txt` |
| Schema | schema before/after, no migration unless justified | `02-schema-before-after.json` |
| Daily brief convergence | unified Model Enriched Intelligence object reaches JSON | `05-daily-brief-intelligence-convergence-proof.json` |
| Browser | Model Enriched Intelligence rendered safely | `06-browser-model-enriched-intelligence-proof.html` |
| Obsidian | Model Enriched Intelligence rendered safely | `07-obsidian-model-enriched-intelligence-proof.md` |
| Status | safe counts/metadata only | `08-status-json-proof.json` |
| Scheduler | install preview + status readiness | `09-scheduler-install-preview-proof.json`, `10-scheduler-status-proof.json` |
| Email raw readiness | eligibility counts and skip reasons | `11-email-raw-enrichment-eligibility-proof.json` |
| Email raw dry-run | no writes, would-enrich counts | `12-email-raw-enrichment-dry-run-proof.json` |
| Email raw apply | capped, idempotent, review-safe rows only | `13-email-raw-enrichment-capped-apply-proof.json`, `14-email-raw-enrichment-idempotency-proof.json` |
| Integrated daily-run | one daily-run receipt shows all three candidates converged | `15-daily-run-integrated-proof.json` |
| Fallback | model unavailable preserves deterministic brief | `16-model-unavailable-fallback-proof.json` |
| Safety scan | no forbidden strings | `17-forbidden-string-scan.txt` |
| No writeback | static and runtime proof | `18-no-writeback-proof.md` |
| Guard columns | all relevant guards zero | `19-guard-column-proof.json` |
| DB proof | production DB sha unchanged | `20-production-db-unchanged-proof.txt` |
| Tests | targeted tests + changed-module lint/type/compile | `21-validation-results.md` |
| CLI help | updated help snapshots | `22-cli-help-snapshots.md` |
| Output paths | no repo-contained generated raw outputs | `23-output-path-safety-proof.md` |
| Limitations | real limitations only | `24-known-limitations.md` |
| Final handoff | complete operator handoff | `25-final-handoff.md` |
| Residual audit | no residual package work | `26-residual-work-audit.md` |
