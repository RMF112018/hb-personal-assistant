# Final Handoff — Procore Endpoint Workflow Remediation

## 1. Branch / HEAD
- Branch: `fix/procore-endpoint-contracts-and-persistence`
- HEAD: `7351000a` (+ this handoff/architecture commit on top)

## 2. Base branch and relevant prior branch comparison
- Base: `main` @ `f8439ca4` (clean, ff-only, includes the prior live-refresh fix merge #9).
- `fix/procore-live-refresh-degradation`: fully merged into `main` (0 commits ahead). No newer unmerged Procore/scheduler branch.

## 3. Commit list
```
7fe6c7ac docs(procore): capture endpoint contract failure evidence
6eb69ceb fix(procore): route daily source-refresh through canonical endpoint adapters
373864a4 fix(source-refresh): classify Procore endpoint statuses and surface actionable receipts
f845bb54 fix(procore): reconcile persistence path and add canonical operator status
655990d8 fix(procore): align downstream consumers to canonical procore_live_* path
635e0242 test(procore): cover daily-refresh plan, taxonomy, persistence, and guardrails
7351000a docs(procore): record live validation safe evidence (0 failures)
+ docs(procore): architecture record + final handoff
```

## 4. Files changed (vs main)
- `src/hb_assistant/procore/daily_refresh_plan.py` (new) — plan + taxonomy
- `src/hb_assistant/source_refresh/orchestrator.py` — `_procore_stage` canonical routing + receipts
- `src/hb_assistant/cli/procore.py` — `procore live status` operator surface
- `src/hb_assistant/construction/manifests/service.py` — project-card repointed to canonical
- `tests/test_procore_daily_refresh_plan.py` (new), `tests/test_sources_refresh.py`, `tests/test_construction_manifests.py`
- `docs/evidence/procore-endpoint-workflow-remediation/00..10`, `docs/architecture/237-*.md`

## 5. Architecture/evidence docs added
- `docs/architecture/237-procore-endpoint-contracts-and-canonical-persistence.md`
- `docs/evidence/procore-endpoint-workflow-remediation/00..10`

## 6. Endpoint failure matrix before/after
| Endpoint | Before | After |
| --- | --- | --- |
| list-projects | 400 missing scope | `projects` ✓ (company, once) |
| list-change-events | 400 missing scope | `change-events` ✓ |
| list-invoices (7th) | 400 missing scope | `subcontractor-invoices` ✓ |
| list-daily-logs | 400 missing date window | `daily-log-*` ✓ (bounded dates) |
| list-punch-items | 404 stale route | `punch-items` ✓ (flat v1.1) |
| list-prime-contracts | 404 stale route | `prime-contracts` ✓ (flat) |
| list-drawings | 404 | `skipped_tool_not_enabled` (no adapter) |
| **Totals** | **28 failures / run** | **0 failures; 73 succeeded** |

## 7. Seventh endpoint resolution
`list-invoices` — resolved from safe receipt evidence (HTTP 400 across all 4 pilots in run57). Not guessed.

## 8. Persistence-path decision
Canonical = `procore_live_records` / `procore_live_sync_runs` / `procore_live_sync_watermarks`. `procore_sync_*` retired from the daily refresh (manual `procore sync run` only). Documented in `procore live status` (`table_roles`).

## 9. Run-tracking decision
`procore_sync_runs` retired (DB count 0 — never written). `procore_live_sync_runs` is the canonical endpoint run ledger; `assistant_runs` remains the global scheduler ledger.

## 10. Downstream consumer alignment
All operational read-models / daily-brief / analytics / issue-history / obsidian_operational already read `procore_live_*` (now fed by the scheduler). `manifests/service.py` repointed to canonical. `obsidian.py` / `validate.py` remain legacy/compat readers (documented).

## 11. Validation commands and results
- `python -m compileall src tests` → OK
- `ruff check` / `ruff format --check` / `mypy` on changed modules → clean
- `pytest tests -k "procore and (endpoint or sync or live or source_refresh or scheduler)"` (deselecting one env-config test) → exit 0
- `pytest tests -k "no_writeback or secret or redaction or guardrail"` → exit 0
- `pytest tests/test_scheduler_degraded_surfacing.py tests/test_procore_live_apply_fix.py tests/test_procore_daily_refresh_plan.py` → passed
- `pytest tests/test_procore_daily_refresh_plan.py tests/test_sources_refresh.py` → 43 passed
- Pre-existing/environmental (not introduced here): local-config-driven `test_launcher_scheduler` production-default tests + 1 fastapi test (pass with shipped default); repo-wide ruff `B008`/format debt; `review_burden_mart.py` mypy. See `08`.

## 12. Live validation result
**Success.** Bobby-approved production run (run58, 2026-06-09): status `ok`, `failure_count 0` (was 28), 73 endpoint executions succeeded, 0 contract-bug, 0 externally blocked. DB backup created + size-verified before the run.

## 13. Safe DB table counts/latest timestamps
- `procore_live_records`: 30059 (latest 2026-06-09T17:29:52Z)
- `procore_live_sync_runs` today: 73× `success` (0 error/partial); 73 watermarks advanced
- Previously-failing endpoints refreshed today: projects(21), change-events(195), subcontractor-invoices(220), prime-contracts(5), punch-items(4), daily-log-weather(127)
- Legacy (retired, untouched): `procore_synced_entities`=1185, `procore_sync_runs`=0, `procore_sync_errors`=0

## 14. No-writeback/no-secret proof
- `procore live no-writeback-proof` → `proof_passed: true`; GET-only client; `raw_body_persisted=0` across all 73 runs; no M365 writeback; no cloud LLM.
- No-secret scan over `docs/evidence/.../` + `src` + `tests`: zero secret-shaped hits in evidence; `src` hits are the redaction keyword list + the `sensitive_scan` detector only.

## 15. Known follow-ups
- Repo-wide pre-existing lint/format/mypy debt (documented in `08`) — out of scope here.
- `config/config.yml` local-config drift causes `test_launcher_scheduler` production-default tests to fail locally; consider routing those tests through `isolated_hb_pa_config` (separate change).
- `daily-log-manpower` showed no new rows in the bounded 7-day window — expected; widen `DAILY_LOG_LOOKBACK_DAYS` if deeper backfill is desired.

## 16. Exact command Bobby can run next
```
hb-assistant procore live status --json
```
(Inspect the canonical path, freshness, and table roles. Re-run the refresh any time with
`hb-assistant scheduler run daily-source-refresh --environment production --json`.)
