# 01 — Model & schema decision (Phase 10 · 252)

## Decision: render-model-first, then a minimal additive read model

Per the reviewer's "avoid schema-first overbuild" correction, the in-memory render model
(`DailyBriefChangeEvent`) was built and proven first; only the normalized, safe, source-linked fields
needed for repeatability/evidence are persisted.

## In-memory model

`new_today_digest.DailyBriefChangeEvent` (dataclass) — deterministic business facts authoritative:
`event_id`, `brief_date`, refresh window, `source_family`, `source_record_id`, `source_refs`
(hash-only), `project_key` + `project_display_name`, `actor_display_name` / `actor_company`,
`event_type`, `event_timestamp`, business-record `type` / `number` / `title` / `status`, `amount`,
`due_date`, meeting start/end/mode, `summary_text` / `why_it_matters` / `recommended_action`,
`attention_class`, `confidence`, `enrichment_status`, and `model_*` linkage.

## Schema: migration V54 (additive, append-only)

`LATEST_SCHEMA_VERSION` bumped 53 → 54. Two tables, both carrying the full 13-column `_P10_GUARDS`
(`CHECK(col = 0)`):

- **`daily_brief_change_events`** — one raw-free row per New Today item. Redacted / title-only /
  hash-linked columns only; the model layer is referenced solely by hash-only `model_run_receipt_id`.
- **`daily_brief_change_event_refs`** — hash-only `(change_event_id, source_table, source_ref_hash)`
  source linkage.

`CREATE IF NOT EXISTS` so re-apply is a no-op; V1–V53 untouched. Writers in
`ConstructionStore.insert_daily_brief_change_event` / `insert_daily_brief_change_event_ref` accept
**only** redacted/hash fields (no parameter can carry a raw body, payload, prompt, response, URL,
token, or path); the 13 guard columns are pinned to literal 0.

## Why a new table (vs reusing candidates)

The existing `daily_brief_action_candidate` model is candidate/section-shaped (the exact thing the
reviewer said New Today must NOT be built from). A business-event read model with per-record
number/vendor/amount/status/actor + hash-only source refs has no existing home, so a minimal additive
table is the correct fit. It is a read model the digest can rebuild deterministically; the in-memory
render works with zero persisted rows (dry-run is the default).
