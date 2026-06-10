# Repo-Truth Audit — Procore Expansion (Prompt 06)

## Existing surfaces (very mature)

| Concern | Location | State |
|---|---|---|
| Live sync | `procore/live_sync.py` `run_live_sync` | Canonical `procore_live_*` persistence; fail-closed live gate (`HB_PROCORE_LIVE=1`). |
| Endpoint registry | `procore/endpoints.py` `list_all/list_verified` | 59 endpoints; 56 live-verified, 3 unverified (`live_verified=False`). |
| Freshness read-model | `store/procore_freshness.py` `build_freshness_report` | Per-endpoint current/stale/never_synced/fail_closed + recommended sync command. Read-only. |
| Digest consumer | `…/local_ai/procore_digest.py` `build_procore_action_digest` | Deterministic action-signal digest → `daily_brief_action_candidates` (dry-run default). |
| CLI | `procore live status/coverage/stale/digest/…` | Rich but **scattered** across many commands. |

## Gap (Prompt requirement 3)

The pieces for "is Procore data healthy enough to trust the brief's Procore section" existed but were
spread across `status` / `stale` / `coverage` / endpoint registry — there was no single read-model
combining endpoint-contract status + per-project refresh health + a degraded-honest verdict that
daily-brief Procore intelligence can consume.

## Decision (surgical)

Add `procore_monitor.py` (`build_procore_monitoring_report` + renderer) composing the endpoint
registry contract status + `build_freshness_report` per project into one read-only, degraded-honest
report (verdict: healthy / partial_stale / stale / no_data, with degraded reasons + next actions), and
a `procore live monitor` CLI verb. No live HTTP, no writeback, no schema change. Complements (does not
duplicate) the existing brief Procore digest.
