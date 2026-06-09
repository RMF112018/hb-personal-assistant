# 07 — Downstream Consumer Alignment

Prompt: `07_DOWNSTREAM_CONSUMER_ALIGNMENT.md`.

## Consumer classification

Grep: `grep -RIn "procore_synced_entities|procore_sync_|procore_live_records|procore_live_sync_" src tests`.

### Canonical live-path consumers (read `procore_live_*`) — no change needed
Already on the canonical path; now fed directly by the scheduled refresh (Phase B):

- `store/procore_operational.py`, `procore_freshness.py`, `procore_history.py`, `procore_cost_exposure.py`, `procore_schedule_exposure.py`, `procore_project_health.py`, `procore_action_queue.py`, `procore_relationship_quality.py`
- `construction/issue_history/issue_history_builder.py`, `construction/analytics/service.py`, `construction/data_quality/*`, `construction/document/relationship_builder.py`
- `construction/second_brain/daily_brief/enrichment.py` (`source_family="procore_live_records"` + `procore_action_signals`)
- `procore/obsidian_operational.py`

### Legacy-sync-path consumers (read `procore_sync_*`)

| Module | Disposition |
| --- | --- |
| `construction/manifests/service.py` (project-card Procore totals) | **REPOINTED to canonical** (`procore_live_records` + `procore_live_sync_watermarks`) — it was active and would otherwise freeze stale once the scheduler stopped writing the legacy tables. |
| `procore/obsidian.py` (legacy sync receipts) | **Legacy/compat** — only renders receipts for the manual `procore sync run` path. Left intact; documented as legacy. |
| `procore/validate.py` (legacy schema validation) | **Reference** — validates legacy table presence. Left intact. |
| `resources/json/table_lifecycle_status_contract.json` | **Reference-only** lifecycle metadata. |

## Daily brief / digest alignment

- The previously latent misalignment — *digest/daily-brief read `procore_live_*` while the scheduler wrote `procore_sync_*`* — is **resolved by Phase B**: the scheduler now writes `procore_live_*`, the same path these consumers read.
- Daily-brief Procore sections already **degrade explicitly**: `enrichment.py` builds a section with an explicit `count`/`reason` when no fresh records exist (no false-empty success), and tags `source_family` so the source is traceable. `procore live status` + `procore live stale` expose canonical freshness so an operator can see staleness directly.

## Change made

`construction/manifests/service.py`: project-card Procore summary now reads
`procore_live_records` (count + `review_required`) and `procore_live_sync_watermarks`
(`last_success_at_utc`) instead of the legacy `procore_synced_entities` /
`procore_sync_watermarks`. Output keys (`procore_entities_total`,
`procore_review_required_total`, `procore_watermark_count`,
`procore_last_watermark_fp`) are unchanged. Test
`tests/test_construction_manifests.py::test_project_card_includes_procore_sync_summary_totals`
updated to seed the canonical tables (full V6 rows; `raw_body_persisted=0`).

## Tests

- `tests/test_construction_manifests.py` — green (project-card reads canonical).
- Fresh-canonical-populates vs stale-only-degrades fixtures + bridge idempotency: the canonical read-models are covered by the existing `test_procore_live_sync_*` / freshness suites; the daily-brief degrade-explicit path is exercised in `tests/test_sources_refresh.py` (daily-brief packet stage). Additional coverage in Phase F (`08`).
