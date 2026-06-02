# 79 — Phase 08B: Source / Runtime / Retrieval Freshness Observability (Prompt 07)

**Status:** Implemented (additive). Schema **V30 unchanged** (no new table); package stays `1.3.0`.
**Baseline:** atop `1dabcd7` (08B Prompt 06; 08A closeout `954a518` is ancestor).
**Scope:** A read-only, deterministic observability surface — source freshness, runtime health,
retrieval freshness — plus a new proof-backed `freshness_observability` gate. `automation_execution`
stays the only deferred 08B gate.

## Context

Prompts 03–06 built the automation-health agent, launchd scheduling, the run registry + no-overlap
lock, and retry/recovery. None of them answered "is the *data* the automation runs on fresh?" This
prompt adds that observability layer, reading existing per-domain sync watermarks + index/retrieval
timestamps — no new persistence beyond an optional emit-gated receipt.

## Design

New module `construction/second_brain/freshness.py` (read-only SELECTs, table-existence guarded,
injected `now`/`db_path`):

- **Source freshness** (`evaluate_source_freshness`) — one signal per ingestion domain from the
  latest successful-sync watermark: `construction_source_sync_state.last_successful_sync_utc`
  (drive), `email_sync_state.last_successful_sync_utc` (mail),
  `calendar_sync_state.last_successful_sync_utc` (calendar),
  `procore_live_sync_watermarks.last_success_at_utc` (procore). `SOURCE_FRESH` (age ≤
  `source_max_age_hours`), `SOURCE_STALE` (age >), `SOURCE_FRESHNESS_UNKNOWN` (never synced / table
  absent). Unknown is **not** a failure — a fresh install with nothing synced is `ok`.
- **Runtime health** (`evaluate_runtime_health`) — COMPOSES `evaluate_automation_health`
  (path/store/schema/handoff) and maps it to `RUNTIME_HEALTH_OK` / `RUNTIME_HEALTH_DEGRADED`. No
  re-implementation of those checks.
- **Retrieval freshness** (`evaluate_retrieval_freshness`) — `obsidian_index_manifests.generated_utc`
  vs `MAX(obsidian_index_entries.modified_utc)` (notes modified after the index → `RETRIEVAL_STALE`),
  index age vs `retrieval_max_age_hours`, and the latest `retrieval_query_receipts.created_utc` +
  `stale_unknown_count`. `RETRIEVAL_INDEX_MISSING` when no manifest exists.
- **Combined** (`evaluate_observability`) — `OBSERVABILITY_OK` iff all three sub-evaluators are ok,
  else `OBSERVABILITY_DEGRADED`. `run_observability(emit_receipt=...)` optionally persists a
  metadata-only V28 `agent_run_receipt` (`agent_id='freshness_observability_agent'`) — the only
  apply-capable path, off by default.
- **`build_freshness_observability_proof()`** drives the gate (temp DB): empty install → OK with
  unknown sources + missing index reported; then seed a fresh drive watermark + a stale mail
  watermark to exercise `SOURCE_FRESH`/`SOURCE_STALE` and the degraded combined snapshot;
  values-only no-raw scan.

### Gate / policy / CLI

- `data_quality.py`: new `freshness_observability` proof-gate → **pass**; added to
  `PHASE_08B_GATE_NAMES` + the gates contract `required_fields`. `automation_execution` stays
  deferred. phase-08b-gates → **10 pass / 0 warning / 0 fail / 1 deferred**.
- Policy seed: new `freshness` section (`source_max_age_hours: 48`, `retrieval_max_age_hours: 168`,
  reason codes), mirrored in the automation-policy + data-quality-gates contracts.
- CLI `second-brain automation`: `source-freshness`, `retrieval-freshness` (read-only),
  `observability` (read-only; `--emit-receipt` off by default). All exit 0 on ok, 3 on attention.

## Guardrails

No schema change (V30/147 unchanged); the observability receipt reuses the V28 table (already in
the no-writeback scan scope). All evaluators are read-only SELECTs; the only write is the emit-gated
metadata-only V28 receipt (off by default = dry-run posture). No external writeback/delivery; no raw
email/document/calendar/prompt/response/URL content (the proof scans values, not schema names).
Phase 08A guardrails preserved (phase-08a-gates 8/1/0/3; no-writeback proof passes).

## Known limitations / next

- `automation_execution` stays deferred — the final executor (weekend execution, local-only alerting
  emission, morning-pipeline wiring) consuming health + freshness + retry + recovery + registry/lock.
- Source freshness keys off the per-domain *latest* watermark (a coarse roll-up), not per-source-id
  rows; per-source granularity can be added later if needed.
- Thresholds are global (per-domain not yet differentiated) and live in the policy seed.
