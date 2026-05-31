# 37 — Phase 07C: Document→Record Relationship Candidates

**Phase:** 07C (Document Intelligence Promotion) — Prompt 08.
**Status:** Implemented and applied to the live store at this record's commit.
**Evidence:** `docs/evidence/construction-intelligence-phase-07c-document-intelligence/08-document-relationship-candidate-proof.json`.

Writes conservative, source-linked advisory candidates connecting each document card to the Procore records it
belongs with, into the V24 table `construction_document_relationship_candidates` (FK → document_card_id).
**Candidates only** — no card mutation, no auto-promotion, no external writeback, no raw content read. No schema
change (`LATEST_SCHEMA_VERSION` stays 24; V24 already created the table + `ix_document_relationship_candidates_target`).

## Signals / alignment

`construction/document/relationship_builder.py` `build_document_relationship_candidates(store, *, apply=False, ...)`.
The only safe, project-aligned link available today is **document → Procore record type**: every document card
and every `procore_live_records` row share `project_key`, so a card whose **classified** document type aligns to
a Procore record type gets one heuristic, review-required candidate. Per card with a `project_key`:

- Resolve the card's document type from its classification candidate
  (`store.list_document_classification_candidates()`; the card's own `document_type` is `unknown` until review).
- Map via a static table `document_type → (Procore endpoint_id, contract target_record_type)`:
  rfi→rfis/`rfi`, submittal→submittals/`submittal`, change_order→prime-change-orders/`change_order`,
  inspection_report→inspections/`inspection`, daily_report→daily-log-dcrs/`daily_log`,
  contract→commitment-contracts/`contract`, pay_application→subcontractor-invoices/`commitment`. Unaligned types
  (drawings/schedule/addenda/photo_media/unknown_needs_review) produce no candidate.
- Gate on Procore presence: `store.count_procore_live_records(project_key, endpoint_id) > 0` (a read-only count;
  no raw Procore payload is read). If the project has none of that record type, skip.
- Emit one candidate: `target_system="procore"`, `target_record_type`,
  `target_record_key_hash = hash_value("{project_key}|procore|{endpoint_id}")` (a project-scoped record-type
  reference — bucket-level, not a specific record), `relationship_type="project_document_type_alignment"`,
  `candidate_type="heuristic"`, `confidence=0.55`, `confidence_class="moderate_heuristic"`, `review_required=True`.
  `signals_json`/`source_reference_json` carry only hashes + safe enums/keys (project_key, document_type,
  target_record_type) — never a raw name/path/URL/record body.

Persisted via the new `repositories.upsert_document_relationship_candidate` (idempotent by `candidate_id =
hash_value("{document_card_id}|deterministic_v1|procore|{target_record_type}")`; guard CHECK columns never set).
Surfaced by `hb-assistant graph files build-document-relationships [--apply] --json` (dry-run default).

## Live result

`--apply`: 23 heuristic candidates — `contract` 12, `rfi` 8, `change_order` 2, `daily_log` 1; all
`target_system=procore`, `confidence_class=moderate_heuristic`, `review_required=1`; 260 cards skipped
(unaligned type, or no Procore records of the aligned type, or no project). Idempotent (re-apply → 23).
Determinism verified identical `by_target_record_type`/`by_candidate_type` across `PYTHONHASHSEED` 1/2/3. A live
scan confirmed 0 URL/token patterns, the four guard CHECK columns all 0, every `candidate_type` within the
contract enum, and every row `review_required`. Gates unchanged: `document_card_population_status` pass;
`raw_content_leakage_scan` / `external_writeback_scan` / `graph files no-writeback-proof` green;
`meeting_prep_readiness.ready` stays **False**.

## Guardrails / deferrals

Candidates only (`heuristic`, `review_required`, `promotion_status='candidate'`); no auto-promotion, no
high-impact/final determination. Procore is read-only (a count of canonical records); no raw record payload,
document text, path, or URL persisted. No card mutation.

**Email and calendar targets are deferred.** Procore is the only target system whose live records are
project-key-aligned to the documents; `calendar_event_index.project_key` is currently all NULL and `email_messages`
carry `project_number_detected` (mostly NULL) with no `project_key` column, so emitting email/calendar candidates
would be speculative. Their prerequisite is project_key alignment on those records (a 07D/future step); the
builder is structured so those arms are a small additive extension. **Record-level deterministic linking**
(a document's record number ↔ a specific Procore record number) is also deferred — cards persist no raw record
number, so no safe record-level identifier match exists; the current link is project+type bucket-level.

The V24 satellite tables (incl. relationship) remain outside the no-writeback-proof static-scan scope (deferred to
Prompt 12; not claimed here). Card/match promotion (09), Obsidian document outputs (10), and the document
data-quality gate suite (11) remain deferred.
