# 237 — Procore Endpoint Contracts & Canonical Persistence

Status: Implemented (2026-06-09) · Branch: `fix/procore-endpoint-contracts-and-persistence`
Supersedes the daily-refresh portion of [236 — Procore live refresh degradation surfacing](236-procore-live-refresh-degradation-surfacing.md).

## Problem

The scheduled `daily-source-refresh` read Procore through the legacy
`procore/sync.py` (`run_sync`) path against the stale
`procore_endpoint_contract.seed.yaml`. That builder formatted only
`{company_id}`/`{project_id}` into the URL and passed only `updated_after`, with
no company/project scoping header and stale routes. Result: 28 endpoint failures
per scheduled run (7 endpoints × 4 pilots) — `list-projects`/`list-change-events`/
`list-invoices` (HTTP 400 "Missing Project or Company ID"), `list-daily-logs`
(400 "Start/End Date required"), `list-drawings`/`list-punch-items`/
`list-prime-contracts` (404). It also wrote `procore_sync_*`, while every
operational read-model, the daily brief, analytics, and issue-history read the
richer `procore_live_*` tables — so the scheduler fed tables nobody read.

## Decision

1. **Route the daily refresh through the canonical `EndpointAdapter` registry**
   (`procore/endpoints.py`) via `procore/live_sync.py::run_live_sync`, writing the
   canonical `procore_live_*` tables. (Preferred architecture #1 from the
   remediation package.)
2. **`procore_live_*` is the single canonical Procore read/write path.**
   `procore_sync_*` is retired from the scheduled refresh (legacy/compat for the
   manual `procore sync run` CLI only). `procore_sync_runs` was never written
   (DB count 0) and is retired rather than revived; `procore_live_sync_runs` is
   the canonical endpoint run ledger.

## Design

- **`procore/daily_refresh_plan.py`** (new, pure): maps the daily-refresh
  endpoint set onto canonical adapter ids, classifies scope (company-level
  run-once vs per-project), computes a bounded daily-log date window
  (`DAILY_LOG_LOOKBACK_DAYS=7`), and translates `run_live_sync` receipts to an
  operator status taxonomy (`success` / `skipped_*` / `blocked_*` /
  `contract_bug_*` / `transport_*` / `normalizer_missing` / `projection_error` /
  `unknown_degraded`). HTTP rules: 400→contract bug, 403→permission-limited,
  404→tool-not-enabled, 429→rate-limited, 5xx→retryable.
- **`source_refresh/orchestrator.py` `_procore_stage`**: dry-run emits a plan
  only (no live read — `run_live_sync` would fail-closed before any HTTP); apply
  executes `run_live_sync` per endpoint/project (company-level once), aggregates
  receipts into a per-endpoint/per-project summary + `by_status` histogram,
  reports `persistence_path=procore_live` + `tables_written`, and a Procore
  `next_operator_action`.
- **`cli/procore.py` `procore live status`** (new): read-only operator surface —
  live gate, auth readiness, canonical vs retired-legacy table roles + counts,
  per-pilot freshness, next action. Safe fields only.
- **`construction/manifests/service.py`**: project-card Procore totals repointed
  from legacy to canonical tables.
- `list-drawings` has no canonical adapter → classified
  `skipped_tool_not_enabled` (not a generic error).

## Mapping (legacy → canonical)

`list-projects`→`projects` (company, once) · `list-change-events`→`change-events` ·
`list-invoices`→`subcontractor-invoices` · `list-prime-contracts`→`prime-contracts` ·
`list-punch-items`→`punch-items` (flat + `project_id` query) ·
`list-daily-logs`→`daily-log-*` (11 subtypes, date-windowed) ·
`list-rfis`/`list-submittals`/`list-commitments`→`rfis`/`submittals`/`commitment-contracts`.

## Guardrails (unchanged)

GET-only Procore (`_require_get`), fail-closed live gate (`HB_PROCORE_LIVE` armed
only per-run), `raw_body_persisted=0`, redaction, no M365 writeback, no
destructive migration (no schema change — canonical tables exist since V6/V7).

## Validation

Live production run 2026-06-09 (run58): **status ok, 0 failures** (was 28),
73 endpoint executions succeeded, `procore_live_sync_runs` 73× success, 73
watermarks advanced. Evidence: `docs/evidence/procore-endpoint-workflow-remediation/`.
