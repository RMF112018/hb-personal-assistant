# Phase 04B Prompt 03 — Generic Entity / Edge / Attachment / Custom-Field Framework

**Date:** 2026-05-29 · **Module:** `src/hb_assistant/store/procore_enrichment.py`.

## Summary

Cross-endpoint enrichment primitives that extract and persist people / company / location entities,
attachment refs, typed custom-field values, relationship edges, action signals, and text intelligence
into the V7 enrichment tables. Self-contained store module (no `hb_assistant.procore` import,
mirroring `procore_history.py`); **framework + unit tests + evidence only** — per-endpoint wiring into
the live-sync orchestrator is a deliberate follow-up (this prompt has no sync-flow-update section).

## Extractor inventory

| function | target table | returns | key/id |
|---|---|---|---|
| `extract_people_refs(people, ...)` | `procore_people_entities` | `person_entity_key[]` | `hash(procore_user_id \| login_hash)` |
| `extract_company_refs(companies, ...)` | `procore_company_entities` | `company_entity_key[]` | `hash(procore_company_id \| name_hash)` |
| `extract_location_refs(locations, project_key, ...)` | `procore_location_entities` | `location_entity_key[]` | `hash(project_key, procore_location_id)` |
| `extract_attachment_refs(attachments, source_record_key, source_endpoint_id, ...)` | `procore_attachment_refs` | `attachment_ref_id[]` | `hash(source_record_key, attachment_id)` |
| `extract_custom_field_values(custom_fields, record_key, ...)` | `procore_custom_field_values` | `custom_field_value_id[]` | `hash(record_key, custom_field_key)` |
| `emit_record_edge(from_record_key, edge_type, ...)` | `procore_record_edges` | `edge_id` | `hash(project, from, to_record, to_entity, edge_type)` |
| `emit_action_signal(record_key, signal_type, ...)` | `procore_action_signals` | `action_signal_id` | `hash(project, record_key, signal_type)` |
| `emit_text_intelligence(source_field_path, text, ...)` | `procore_text_intelligence` | `text_intelligence_id \| None` | `hash(record_key, field_path, text_hash)` |

## Custom-field type policy

| data_type | handling | column populated |
|---|---|---|
| boolean, integer, decimal, datetime | **preserve verbatim** | `value_json_redacted` |
| lov_entry | preserve + label | `value_json_redacted`, `value_label_redacted` (label) |
| lov_entries | preserve + labels | `value_json_redacted`, `value_label_redacted` (comma-joined labels, ≤120) |
| string, rich_text, login_information, prostore_files, unknown (+ any unrecognised) | **hash only** | `value_hash` (no `value_json_redacted`) |

## Attachment policy

Captured: `procore_attachment_id`, `filename_hash` (filename never stored raw → `filename_redacted` NULL),
`url_hash` + `url_path_redacted` (path-only, from first of `url`/`share_url`/`viewable_url`/`download_url`),
`content_type`, `size_bytes`, `download_eligibility='metadata_only'`, `sensitivity`, `source_endpoint_id`,
`source_record_key`. **Signed-URL query strings (tokens / `company_id` / `prostore_file_id`) are never
persisted** — only the path component and a hash.

## Redaction & idempotency guarantees

- Personal PII (person `login`/`name`) is reduced to a SHA-256 prefix (`login_hash`); names are never
  stored. Organisation/place labels (company / location names) are kept verbatim (not personal PII).
- Free text → `emit_text_intelligence` stores `text_hash` + `text_length` only; `excerpt_redacted` is
  always NULL — raw text never persists.
- URLs everywhere reduced to path + hash; no query strings.
- All enrichment rows carry `raw_body_persisted = 0` (schema CHECK where present).
- Deterministic keys/ids + conflict-upsert (entities/edges/signals; entity `source_count` increments)
  or `INSERT OR IGNORE` (custom fields / text intelligence) → every extractor is **idempotent**:
  re-extracting identical data records no duplicate rows.

## Tests (`tests/test_procore_enrichment.py`)

People (PII hashed, names absent, dedup + source_count); company (org name kept, dedup incl. nested
`company` ref); location (nested payload); attachment (query strings stripped — asserts no `?` /
`company_id` / `prostore_file_id` / `token=` in the row); custom fields across all 11 data types
(preserve vs hash); `emit_record_edge` idempotency; `emit_action_signal` row + idempotent;
`emit_text_intelligence` hash-only (raw text absent) + idempotent + empty-text → None.

## Validation

```
python -m pytest -q --no-header   # full suite green (1 pre-existing skip)
ruff check .                      # All checks passed
mypy .                            # Success: no issues found in 191 source files
python -m compileall src tests    # OK
```

## Follow-up

Wiring these extractors into `live_sync.run_live_sync` per endpoint (mapping each endpoint's
people/company/location/attachment/custom-field fields to the extractors and emitting the
record→entity edges + action signals) is left for a subsequent prompt; the primitives here are the
reusable foundation.
