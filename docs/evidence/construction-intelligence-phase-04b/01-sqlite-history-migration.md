# Phase 04B Prompt 01 — SQLite Historical Memory Migration (V7)

**Date:** 2026-05-29 · **Migration:** `v7_procore_history_and_enrichment` ·
**File:** `src/hb_assistant/store/migrator.py`.

## Summary

Additive, idempotent **V7** migration adding historical-memory, cross-cutting enrichment, and
inspection-projection tables so later Phase 04B prompts can populate snapshots, field-level change
events, timeline events, and entity/edge/signal projections. **Schema only** — no population, no live
calls, no changes to existing V1–V6 tables. DDL transcribed from the package design source
`resources/sql/phase_04b_schema_additions.sql` into the repo's `V*_STATEMENTS` convention
(`apply()` execs each statement under a transaction, then registers version 7 in `schema_migrations`).
`SQLiteMigrator.apply()` now returns **7**.

## Table inventory (18 tables + 2 views)

### History (4)
| table | PK | key columns | guardrails |
|---|---|---|---|
| `procore_live_record_state_index` | `record_key` | project/endpoint/parent/record ids, current_canonical_hash, current_text_hash, first/last_seen, last_changed | `CHECK(raw_body_persisted=0)`, `CHECK(redaction_applied=1)` |
| `procore_live_record_snapshots` | `snapshot_id` | record_key, observed_at_utc, canonical_hash, canonical_json_redacted, change_summary_json; `UNIQUE(record_key, canonical_hash)` | `CHECK(raw_body_persisted=0)`, `CHECK(redaction_applied=1)` |
| `procore_live_record_change_events` | `change_event_id` | record_key, detected_at_utc, field_path, old/new_value_redacted+hash, change_type/category, importance | `CHECK(raw_body_persisted=0)` |
| `procore_record_timeline_events` | `timeline_event_id` | record_key, event_time_utc, event_type, summary_redacted, actor/target_entity_key | `CHECK(raw_body_persisted=0)` |

### Cross-cutting enrichment (8)
`procore_people_entities` (CHECK raw_body=0), `procore_company_entities`, `procore_location_entities`,
`procore_attachment_refs` (CHECK raw_body=0; url stored as `url_path_redacted`/`url_hash`,
`download_eligibility` default `metadata_only`), `procore_custom_field_values`
(`UNIQUE(record_key, custom_field_key)`), `procore_record_edges`, `procore_action_signals`,
`procore_text_intelligence` (CHECK raw_body=0; `UNIQUE(record_key, source_field_path, text_hash)`).

### Inspection projection (6)
`procore_inspection_records` (`UNIQUE(project_key, inspection_id)`), `procore_inspection_sections`,
`procore_inspection_items` (`UNIQUE(project_key, item_id)`), `procore_inspection_response_sets`,
`procore_inspection_response_options`, `procore_inspection_evidence_rules`.

### Views (2)
`v_procore_open_action_signals`, `v_procore_inspection_unanswered_items`.

## Indexes

Record-history lookups by `record_key` + observed/detected time:
`ix_procore_snapshots_record_observed`, `ix_procore_change_events_record_detected`,
`ix_procore_timeline_record_time`. Project lookback by `project_key` + event time:
`ix_procore_snapshots_project_endpoint`, `ix_procore_change_events_project_detected`,
`ix_procore_timeline_project_time`, `ix_procore_state_index_project_endpoint`,
`ix_procore_action_signals_project_status`. Plus `ix_procore_change_events_category`,
`ix_procore_record_edges_{from,to_record,to_entity}`, `ix_procore_attachment_refs_source`,
`ix_procore_action_signals_type`, `ix_procore_inspection_items_project_status`.

## Guardrails

- **No raw bodies:** `raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0)` on
  state_index, snapshots, change_events, timeline_events, people_entities, attachment_refs,
  text_intelligence. **Always redacted:** `redaction_applied ... CHECK(redaction_applied = 1)` on
  state_index + snapshots. Attachment URLs are stored path-only/hashed (no signed-URL query strings).
- **Additive + idempotent:** every statement is `CREATE … IF NOT EXISTS`; version 7 is registered once;
  re-running `apply()` is a no-op. **No V1–V6 table is dropped or rewritten.**

## Tests (`tests/test_procore_history_migration_v7.py`)

- all 18 tables exist; required history + project indexes exist; both views exist;
- idempotent (`apply()` → 7 twice; one v7 row in `schema_migrations`);
- `CHECK` rejects `raw_body_persisted=1` (snapshots) and `redaction_applied=0` (state_index) via
  `IntegrityError`;
- existing migrations still run from an empty DB (V1 `source_records` + V6 `procore_live_records`
  present alongside the V7 tables).

Adjacent tests updated for the new max version: `test_construction_store_repositories.py`
idempotency assertions `6 → 7`; `test_procore_repositories_v6.py` `procore_live_%` exact-set check
relaxed to a subset (V7 adds `procore_live_record_*` tables sharing that prefix).

## Validation

```
python -m pytest -q --no-header   # full suite green (2 pre-existing skips)
ruff check .                      # All checks passed
mypy .                            # Success: no issues found in 188 source files
python -m compileall src tests    # OK
```
Confirmed `SQLiteMigrator(tmp).apply() == 7` from an empty DB and idempotent on re-apply.
