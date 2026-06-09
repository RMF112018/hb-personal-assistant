# Evidence — Procore Live Source-Refresh Degradation Fix

Date: 2026-06-09 · Branch `fix/procore-live-refresh-degradation` · schema V44 (no migration)
Local-only · GET-only Procore · no writeback · all values below are safe counts/statuses/reason
codes (no tokens, no raw payloads).

## Symptom (original)

`scheduler run daily-source-refresh --environment production --json` →
`orchestrator_status: degraded`, `counts: {failed: 4, planned: 0, inserted: 0}`, but receipt
`status: ok` (masked). Failure reasons not persisted.

## Root causes (each exposed by fixing the one above)

| Layer | Reason (redacted) | Fix |
| --- | --- | --- |
| Status masking | wrapper `status="ok"` for degraded; `failures[]` discarded; `write_evidence` never called | persist evidence + receipt `failures[]`; honest status; manual exit 2 |
| Expired token | cached access token `expires_in ≈ -192156s`; presence-only gate passed | `procore auth refresh` (refresh token valid) |
| Bad env | `ValueError: Unknown environment: prod` ×4 projects (coordinator default `"prod"`) | default → `"production"`; normalize `"prod"` |
| No transport | `transport_not_injected` ×40 (client built without `live_enabled`) | `live_enabled=live_env_active()` |
| Endpoint honesty | `counts.failed>0` but `status=ok` | endpoint errors now set `degraded` + surfaced |

## Live proof (production DB, backed up)

Backup: `/tmp/hb-personal-assistant-before-procore-sync-<ts>.sqlite` (created before any apply).

Progressive runs (manual, `--environment production`):

| Run | Result | Meaning |
| --- | --- | --- |
| run55 | degraded, exit 2, `failures[]`= `ValueError: Unknown environment: prod` ×4 | diagnosability fix exposed the real reason |
| run56 | `ok`→counts.failed 40 (pre endpoint-honesty fix) | env fixed; transport error surfaced |
| probe (temp DB copy) | `total_items_normalized: 887`; 3 success / 6 not-eligible / 7 API errors | transport fix → data flows |
| run57 (final) | **degraded, exit 2, `inserted: 1185`, `failed: 28`, `failure_count: 4`** | end-to-end sync persists; remaining endpoint errors visible |

Production DB after run57 (all timestamped 2026-06-09):

| Table | Evidence |
| --- | --- |
| `procore_synced_entities` | **1185** rows synced today (tropical 887, alton-hilltop-pbg 167, pga-modern-garage 131) |
| `procore_sync_watermarks` | **12** advanced today @ 14:45 (list-rfis / list-submittals / list-commitments × 4 projects) |
| guardrail | GET-only; no writeback; no secrets in receipt/evidence |

Final receipt fields (safe): `status=degraded`, `orchestrator_status=degraded`,
`stages={preflight:ok, procore:degraded, graph:partial_local_only, rebuild:ok}`,
`evidence_summary_path=…/evidence/scheduled/source-refresh-production-2026-06-08-run57.json`.

## Remaining (documented, not masked)

- 7 endpoints/project return HTTP 400/404 (missing project/company/date params, or unavailable):
  `list-projects`, `list-change-events`, `list-daily-logs` (400); `list-drawings`,
  `list-punch-items`, `list-prime-contracts` (404). Endpoint-contract parameterization follow-up.
- The orchestrator writes `procore_sync_*` tables; the `procore_live_*` tables (last updated
  2026-06-03) are a **separate** `live_sync.py` path the orchestrator does not call. Operators
  monitoring `procore_live_*` will not see daily-refresh changes — reconcile the two paths (follow-up).

## Validation

- `pytest tests/test_scheduler_degraded_surfacing.py tests/test_procore_live_apply_fix.py` (10 pass).
- Full scheduler/source_refresh/procore suite with isolated config: pass except one pre-existing
  mtime ordering flake (`test_snapshot_copy_source_unmutated_and_confirm_gate`, unrelated).
- ruff + mypy clean on changed modules.
- Pre-existing test-env note: a developer's machine-local `config/config.yml` (live-read flags)
  pollutes `resolve_profile("production")` in the suite, flipping production tests to live_source;
  these tests pass once that file is isolated. `config/config.yml` is now gitignored.

## Commands (safe)

```bash
hb-assistant procore auth status            # presence + token expiry (no live call)
hb-assistant procore auth refresh           # mint a fresh access token (OAuth only; no DB/data write)
hb-assistant scheduler status --environment production --json   # gates + last run status/failures
hb-assistant scheduler run daily-source-refresh --environment production --json   # exits 2 if degraded
```
