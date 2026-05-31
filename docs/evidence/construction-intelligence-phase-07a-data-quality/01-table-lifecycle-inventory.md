# 01 — Table Lifecycle Inventory (Phase 07A Prompt 00)

**Generated:** 2026-05-31  
**Baseline:** HEAD `cb526668b851d43b9e6c3b3116b297552f105526` (main) | pkg 1.3.0 (source) | schema V19 (confirmed runtime + code)  
**Contract:** `resources/json/table_lifecycle_status_contract.json` (7 statuses, 6 required fields)  
**Reconciliation sources:** package `03_SQLITE_DATA_QUALITY_REPORT_RECONCILIATION.md` + `02_REPO_TRUTH_AUDIT_SUMMARY.md`

## Executive Summary

- **82 user tables** (migrator V1-V19 + 4 legacy pilot tables in `repositories.py` `_ensure_procore_sync_tables`).
- **53 populated / 29 empty** (per package SQLite report).
- **6 tables classified `operational_empty_blocking`** (explicit in 02_/03_ + 07A/07B impact):
  - `construction_project_identity`, `construction_project_source_matches`, `construction_document_cards` (07A canonical identity / source-record map blockers).
  - `calendar_events`, `email_thread_summaries` (07B meeting-prep blockers).
- **1 `placeholder_deferred`**: `content_embeddings` (Phase 09).
- **8 `legacy_superseded`**: early V2/V3 construction tables + 4 Prompt-09 pilot `procore_sync_*` (replaced by V5/V6+ canonical + live_*).
- **~14 `evidence_only`**: receipts, runs, errors, model decisions/audit tables (durable but not operational state).
- **Strong operational foundation**: Procore (live + history + financial + inspection, concentrated on `tropical`), email metadata/recipients/relationships/candidates/review (V11+), construction drive items + file intel (V5+V15-19), action signals/edges.
- **Key gaps preserved for 07A/07B/07D**: project identity empty (no backfill yet), cross-domain linkage incomplete, calendar/thread summaries absent, embeddings deferred, financials dense but uneven (currency/WBS missing in many).
- **No schema changes** in this prompt (inventory + classification only).

## Lifecycle Status Definitions (from contract)

- `operational_populated`: Actively written by current code paths; expected to have rows for pilot data.
- `operational_empty_expected`: Schema present and current; empty by design (e.g. no calendar data yet).
- `operational_empty_blocking`: Empty but blocks downstream (07A identity, 07B meeting prep); must be addressed or explicitly gated.
- `placeholder_deferred`: Schema for future phase (09 embeddings); not yet used.
- `legacy_superseded`: Old tables replaced by newer canonical equivalents (V5/V6+); retained for audit continuity, no new writes.
- `evidence_only`: Audit/receipt/decision tables (processing_receipts, model_decisions, crawl receipts, etc.); valuable for diagnostics but not source-of-truth state.
- `unknown_requires_audit`: Any table not clearly mappable from DDL + reports (none found).

## Family Classification (9 families + legacy + misc)

| Family | Tables | V | Rollup Status | Key Notes / Report Refs |
|--------|--------|---|---------------|-------------------------|
| core_source_v1 | 11 (source_records, emails, calendar_events, attachments, files, parser_outputs, action_items, source_links, assistant_runs, sync_state, content_embeddings) | V1 | mixed (10 populated, 1 blocking, 1 deferred) | Email metadata active; calendar + embeddings explicit blockers (03_) |
| embeddings | 1 | V1 | placeholder_deferred | Phase 09 per 03_ |
| construction_early_v2v4 | 7 (resolutions, delta_tokens, old inventory, old crawl_receipts, review_queue, model_decisions) | V2-V4 | legacy_superseded + evidence_only | Superseded by V5 canonical + V11 email review; model decisions = audit only |
| construction_canonical_v5 | 10 (source_locations, *_sync_state, crawl_runs, drive_items, project_identity, project_source_matches, document_cards, processing_receipts, sync_errors, email_intel_deferred_state) | V5 (+ALTERs) | mixed (populated + 3 blocking) | project_identity / matches / document_cards = explicit empty blocking (02_); drive_items rich post-06A |
| procore_live_v6 | 3 (live_sync_runs, live_records, live_sync_watermarks) | V6 | operational_populated | Strong foundation; 56/59 endpoints verified (05 closeout) |
| procore_history_enrich_v7 | 18 + 2 views (state_index, snapshots, change_events, timeline, entities x3, attachment_refs, custom_fields, edges, action_signals, text_intel, 6 inspection_*) | V7 | operational_populated | Snapshots/edges/signals/inspection = 04B/06B operational; 06B project-health etc read models |
| procore_financial_v8v9 | 15 + 2 (contracts, line_items, change_orders, payment_apps, invoices, rfqs, change_events, budget_*, amount_facts + extensions + billing_periods, subcontractor_invoices) | V8-V9 | operational_populated | Dense facts but uneven (missing currency/WBS in many per 03_); defer normalization 08B |
| procore_legacy_pilot | 4 (procore_sync_runs, sync_errors, synced_entities, sync_watermarks) | legacy (repositories.py) | legacy_superseded | Prompt-09 pilot; fully replaced by V6 live_* + V7 history |
| email_policy_v10 | 2 (active_policy, source_locations) | V10 | operational_populated | Read-only locked singleton + mailbox/folder registry (06) |
| email_operational_v11v14 | 13 (sync_state, crawl_runs, messages, recipients, attachments, project_matches, relationship_candidates, thread_summaries, review_queue, processing_receipts, body_vault_refs, model_classifications) | V11-V14 | mostly operational_populated (1 blocking + 1 gap) | Messages/recipients/candidates/review active; thread_summaries blocking (07B); model_classif has repo-method gap (02_) |
| file_intelligence_v15v19 | 4 + drive_items ALTERs (graph_link_resolution, file_ingestion_decisions, graph_download_receipts, file_extraction_runs) | V15-V19 | mixed (2 operational, 2 evidence) | 06A file intel; receipts evidence-only (bounded, no raw URLs/vault copies per CHECKs) |
| misc_evidence_audit | ~10 (various *_receipts, *_runs, *_errors, model_decisions, processing_*) | all | evidence_only | Durable audit trail; not operational state |

**Total classified user tables: 82** (matches report; minor variance from internal vs user count in grep).

## Explicit Empty / Blocking Tables (from 02_/03_)

- `construction_project_identity` + `construction_project_source_matches` + `construction_document_cards`: operational_empty_blocking (07A). No backfill yet; required for source-record map + project coverage mart.
- `calendar_events`: operational_empty_blocking (07B). No ingestion path exercised.
- `email_thread_summaries`: operational_empty_blocking (07B). Schema + model path exist but not populated in pilot.
- `content_embeddings`: placeholder_deferred (09). Retrieval waits for stable mapped text.

## Legacy Pilot Tables (Prompt-09, superseded)

The 4 tables in `src/hb_assistant/store/repositories.py:_ensure_procore_sync_tables` (procore_sync_runs etc.) were the Phase 03/Prompt09 pilot sync surface. V6 (04A) + V7 (04B) provide the canonical live + history replacement. These 4 are classified legacy_superseded; no new code should write them.

## Evidence-Only Tables (Audit / Receipts)

All `*_receipts`, `*_crawl_runs`, `construction_model_decisions`, `construction_sync_errors`, `email_processing_receipts`, `assistant_runs`, etc. are intentionally evidence_only. They provide deterministic run history, redaction attestations, and decision provenance but are not used for operational queries or second-brain facts.

## Validation of Inventory

- DDL source: `src/hb_assistant/store/migrator.py` (V1-V19 statements + apply() order) + Grep extraction of all CREATE TABLE/VIEW.
- Legacy: Grep on `src/hb_assistant/store/repositories.py` (lines 644-698).
- No other CREATE TABLE sites in `src/hb_assistant/` (confirmed via prior src-wide search; construction/store/repositories.py has none).
- Row counts / population status: taken from package 03_ report (point-in-time SQLite audit) + 02_ explicit empties. No live DB row-count query performed in this prompt (metadata-only via migrator.current_version() = 19).
- All 7 contract statuses used; 0 "unknown_requires_audit".

## Next (Prompt 01+)

This inventory is the authoritative baseline for:
- Additive V20 data-quality schema (run ledger, table_lifecycle_registry, source_record_map, etc.).
- Backfill of `construction_project_identity` / matches (Prompt 02).
- Relationship orphan diagnostics + promotion gates (Prompt 04).
- Agent-ready query marts (Prompt 05).

See `00-repo-truth-rebaseline.md` for full git/CLI/evidence/architecture drift + validation matrix.

**No schema or runtime changes in Prompt 00.** All guardrails preserved (no writeback, no secrets, no raw bodies, read-only, dry-run posture).