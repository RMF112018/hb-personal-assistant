# 05 — Persistence-Path Reconciliation Decision

Prompt: `05_PERSISTENCE_PATH_RECONCILIATION.md`.

## Decision

**The canonical downstream Procore read/write path is `procore_live_*`:**

```
procore_live_records          # canonical operational read model
procore_live_sync_runs        # canonical endpoint run ledger
procore_live_sync_watermarks  # canonical per-endpoint watermarks
+ family projection / action-signal / text-intelligence tables
```

The legacy `procore_sync_*` path is **retired from the daily source-refresh** and
documented as a legacy/compat staging path used only by the manual
`hb-assistant procore sync run` CLI.

## Why (validated against repo + DB truth)

- The daily source-refresh now writes `procore_live_*` (Phase B: it routes through `run_live_sync`). The legacy `sync.py`/`procore_sync_*` path is no longer on the scheduled path.
- Downstream consumers already read `procore_live_*`: `store/procore_operational.py`, `procore_freshness.py`, `procore_history.py`, `procore_cost_exposure.py`, `procore_schedule_exposure.py`, `procore_project_health.py`, `procore_action_queue.py`, `procore_relationship_quality.py`; `construction/issue_history`, `construction/analytics`, `construction/data_quality`, `construction/second_brain/daily_brief`; `procore/obsidian_operational.py`. (Full inventory in `07`.)
- The live path has richer endpoint metadata, request classification, query-param + date-window handling, run tracking, watermarks, and projection hooks.
- Migrating consumers onto `procore_synced_entities` would regress the Phase 04A/04B/05/06B projection + operational design.

## Inventory (writers / readers)

| Path | Writer | Readers |
| --- | --- | --- |
| `procore_live_*` (canonical) | `procore/live_sync.py::run_live_sync` (now invoked by the daily refresh + manual `procore live sync`) | operational/freshness/history/cost/schedule/health/action-queue read models; issue-history; analytics; data-quality; daily-brief enrichment; obsidian_operational |
| `procore_sync_*` (legacy) | `procore/sync.py::run_sync` (manual `procore sync run` only) | `procore/obsidian.py` receipts; `procore/validate.py`; `construction/manifests/service.py` |

## DB proof (safe counts, production DB)

| Table | Count | Role |
| --- | --- | --- |
| `procore_live_records` | 30035 | canonical operational read model |
| `procore_live_sync_runs` | 508 | canonical run ledger |
| `procore_live_sync_watermarks` | 160 | canonical watermarks |
| `procore_synced_entities` | 1185 | legacy staging (manual only) |
| `procore_sync_watermarks` | 12 | legacy watermarks |
| `procore_sync_runs` | **0** | legacy run ledger — never written (retired) |
| `procore_sync_errors` | **0** | legacy error ledger — never written |

## Implementation

- Daily source-refresh moved onto `live_sync.py` / `procore_live_*` (Phase B). **No bridge** is required — the canonical tables are written directly, idempotently, with `raw_body_persisted=0` and redaction preserved.
- No destructive migration; no schema change (canonical tables exist since V6/V7).
- Operator-facing roles are surfaced by the new `hb-assistant procore live status` command (`table_roles` + `canonical_counts` + `legacy_counts`).
- DB proof commands for both paths are documented in `VALIDATION_COMMANDS.md` and reproduced by `procore live status`.

## Guardrails honored

No destructive migration; additive-only (none needed); existing `procore_live_*`
projections preserved; no raw payloads copied; `raw_body_persisted=0` and
redaction invariants intact.
