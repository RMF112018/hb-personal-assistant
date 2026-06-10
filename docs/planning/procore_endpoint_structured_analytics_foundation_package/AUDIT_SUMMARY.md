# Audit Summary — Procore Structured Analytics Foundation

## Context correction

This package supersedes the earlier daily-brief-centered framing. The Procore data layer is not simply a feedstock for the local daily-brief agent/model. It must become a durable, local, analytics-grade source of truth that can support future reporting, trend analysis, cost/schedule/quality analytics, local model retrieval, operator drill-down, and daily-brief projections.

Daily brief and local-model consumption are downstream consumers. They must not define the storage design.

## DB audit package findings incorporated

A private DB usefulness audit package was provided as additional reference. The package included a safe audit report, row counts, schema inventory, and a copied SQLite DB. The audit was based on a timestamped SQLite `.backup` copy and reported both `integrity_check` and `quick_check` as `ok`.

Safe findings incorporated into this implementation package:

- Schema version: `45`.
- `procore_live_records`: `30,059` rows.
- `procore_live_record_snapshots`: `27,963` rows.
- `procore_live_record_change_events`: `29,738` rows.
- `procore_live_record_state_index`: `27,464` rows.
- `procore_record_timeline_events`: `27,479` rows.
- `procore_record_edges`: `30,912` rows.
- `procore_text_intelligence`: `4,409` rows.
- `procore_financial_amount_facts`: `85,525` rows.
- `procore_action_signals`: `5,866` rows.
- `daily_brief_action_candidates`: `0` rows.
- `candidate_source_refs`: `0` rows.
- `raw_content_model_context_packets`: `4` rows.
- `retrieval_context_refs`: `6,528` rows.
- `calendar_event_raw_content`: `117` rows.
- `email_message_raw_content`: `1` row.

The audit verdict classified Procore as `blocked_by_ranking`, but for the revised objective the more important data-foundation finding is this: Procore has high-volume normalized/read-model tables, but no equivalent durable, structured Procore raw-content table family comparable to the existing raw calendar/email content tables.

## Current Procore storage posture

Current Procore tables are useful but not analytics-complete:

- `procore_live_records` stores `canonical_json_redacted`, status, redacted title, timestamps, source URL redacted, and stable endpoint/project identifiers.
- `procore_live_record_snapshots` stores redacted canonical JSON, canonical hash, text hash, optional raw payload hash, and snapshot/change metadata.
- `procore_live_record_change_events` stores redacted field-level deltas and hashes.
- `procore_action_signals` stores derived signals, not endpoint facts.
- `procore_financial_*` and `procore_inspection_*` tables contain typed projections, but they do not preserve endpoint-complete raw business payloads in endpoint-family tables.

This means the DB can support some operational read models today, but it is not yet a durable analytics foundation for future detailed analysis across Procore endpoint families.

## Endpoint-volume evidence from DB audit

High-volume endpoint families already present:

- `subcontractor-invoice-contract-detail-items`: `12,223` live records.
- `inspection-items`: `3,484` live records.
- `daily-log-dcrs`: `2,604` live records.
- `meeting-topics`: `2,472` live records.
- `activities`: `1,609` live records.
- `budget-detail-rows`: `1,182` live records.
- `daily-log-manpower`: `962` live records.
- `subcontractor-invoice-change-order-items`: `909` live records.
- `rfis`: `603` live records.
- `submittals`: `445` live records.
- `commitment-line-items`: `299` live records.
- `budget-change-history`: `229` live records.
- `subcontractor-invoices`: `220` live records.
- `observations`: `210` live records.
- `change-events`: `195` live records.

These volumes justify typed endpoint-family tables now. A generic JSON-only sink would repeat the current problem under a different name: technically captured data, but not sufficiently queryable for analytics.

## Action-signal usefulness evidence from DB audit

The audit found:

- `5,866` open Procore signals.
- `0` due-soon Procore signals.
- `1,888` recent signals.
- `3,592` aggregate-sludge signals.
- Large stale/aggregate groups such as inspection unanswered/requires-observation, meeting topics, closed observations, budget postings, critical/zero-float activities, and unpaid change orders.

Signal volume is not the same as operator usefulness. The implementation must distinguish analytics storage from daily-brief projection:

- Analytics storage should preserve structured endpoint facts even when they are historical or aggregate-heavy.
- Daily-brief projection should suppress stale aggregate backlog and surface only ranked, source-linked, current/operator-actionable records.

## Key correction to the previous package

The previous package leaned too heavily toward a generic raw payload table plus daily-brief gates. This revised package changes the design priority:

1. Create an analytics-grade local Procore data foundation.
2. Persist endpoint-complete business payloads locally in structured endpoint-family tables.
3. Preserve a governed raw payload landing/snapshot layer for reprocessing and lossless traceability.
4. Build typed projections and analytics marts from those structured tables.
5. Treat daily brief, local model context, and candidate generation as downstream projections with strict redaction and usefulness gates.

## Recommended implementation strategy

Implement a local layered model:

- **Capture/control layer:** capture runs, endpoint contracts, page receipts, source request fingerprints, endpoint coverage reports.
- **Raw landing/snapshot layer:** one governed `procore_endpoint_raw_payloads` table for lossless local reprocessing, payload hashes, current flags, and retention/safety metadata.
- **Structured bronze layer:** endpoint-family tables such as RFIs, submittals, observations, inspections, meetings, daily logs, commitments, change events, budget rows, invoices, line items, payments, attachments, companies, people, locations, and schedule activities. These tables preserve endpoint business fields in typed columns and keep raw payload linkage.
- **Silver projection layer:** normalized business facts, clean dimensions, relationship edges, due/owner/status/materiality facts, cost and schedule analytics facts.
- **Gold/read-model layer:** ranked operator signals, project risk/health marts, daily brief candidates, local-model context packets, and CLI/report surfaces.

## Non-goals

- Do not make the daily brief the storage target.
- Do not store only aggregate signals.
- Do not store only redacted summaries.
- Do not rely on live Procore calls for reprocessing.
- Do not commit payload data, DB copies, tokens, signed URLs, or private endpoint content.
- Do not perform any external writeback.
