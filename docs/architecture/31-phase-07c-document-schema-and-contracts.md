# 31 — Phase 07C: Document Schema (V24) and Card Contracts

**Phase:** 07C (Document Intelligence Promotion) — Prompt 02.
**Status:** Implemented at this record's commit.
**Evidence:** `docs/evidence/construction-intelligence-phase-07c-document-intelligence/02-schema-and-contract-proof.md`.

Adds the **additive** schema and machine-readable contracts that later 07C prompts build on. No
materialization, classification, extraction, or CLI surface — those are Prompts 04+. Schema 23 → **24**.

## Additive migration V24

The package reference DDL assumed a greenfield `construction_document_cards` (`document_card_id` PK), but
the repo already has an **empty V5** `construction_document_cards` (`card_id` PK) with a materializer +
tests; `CREATE TABLE IF NOT EXISTS` would silently no-op on it. V24 therefore **extends** the existing
table rather than recreating it (additive-only guardrail; matches the Prompt 00/01 evidence commitment):

- **Card extension** — `migrator.py` `V24_CARD_COLUMNS` ALTERs the existing table with the 07C fields:
  the canonical identity `document_card_id` (+ `UNIQUE INDEX ux_document_cards_document_card_id`), hashed/
  redacted identity fields (`drive_id_hash`, `drive_item_id_hash`, `project_number_hash`, `title_hash`,
  `title_redacted`, `source_path_hash`, `source_path_token_hashes_json`), safe metadata (`file_extension`,
  `mime_type`, `size_class` CHECK, `last_modified_datetime`, `source_reference_json`), review/extraction/
  confidence state (`review_status` CHECK, `review_required`, `review_reasons_json`,
  `extraction_eligibility` CHECK, `confidence_class` CHECK, `guardrail_flags_json`), and the six hard guard
  columns `raw_document_text_persisted` / `raw_payload_persisted` / `signed_url_persisted` /
  `download_url_persisted` / `source_file_copied_to_vault` / `external_writeback_performed`
  (`INTEGER NOT NULL DEFAULT 0 CHECK(... = 0)`). The legacy `card_id` PRIMARY KEY is **retained untouched**;
  the Prompt 04 materializer will set `card_id = document_card_id`. Hash/id columns are nullable on the
  empty table (SQLite ALTER cannot add NOT NULL without a default); the contract `required_fields` +
  materializer enforce presence.
- **Five satellite tables** (`V24_STATEMENTS`, `CREATE IF NOT EXISTS`): `…_classification_candidates`,
  `…_project_match_candidates`, `…_relationship_candidates`, `construction_document_intelligence_previews`,
  `construction_document_projection_runs` — each FK→`construction_document_cards(document_card_id)`, each
  carrying its no-raw-text / no-raw-prompt / no-raw-response / no-external-writeback CHECK guards, plus the
  four reference indexes.
- **apply()** records v24 once (gated on `schema_migrations` version 24 absent, like V22). The card ALTERs
  are per-column `PRAGMA table_info` guarded → idempotent. V1–V23 untouched.

### Identity decision
`card_id` (legacy V5 PK, retained) and `document_card_id` (V24 canonical 07C identity, UNIQUE-indexed,
FK target). Keeping both is the additive-faithful way to adopt the package contracts verbatim while not
rewriting the V5 PK; the materializer keeps them equal.

## Contracts

Five identifier/enum-only contracts shipped under `resources/json/` (auto-packaged via the
`resources/json/*.json` glob): `document_card_contract`, `document_classification_contract`,
`document_project_match_contract`, `document_relationship_candidate_contract`,
`controlled_extraction_contract` (all `version: phase07c-v1`). They encode required/safe/forbidden fields,
guardrail columns, document-type and signal taxonomies, confidence/review classes, target systems/record
types, and the controlled-extraction policy (`download_default=false`, `persist_full_text=false`,
`auto_promotion_allowed=false`). New package `construction/document/` (`contracts.py`) loads them via the
importlib→filesystem→empty pattern (`load_document_contract` / `load_all_document_contracts`) — the single
entry point for downstream 07C prompts. No expansion of `construction-agent validate` (it does not
enumerate contracts).

## Lifecycle contract
The five satellites are registered in `table_lifecycle_status_contract.json` (family
`document_intelligence_v24`, `phase_owner=07C`, `operational_empty_expected`); `table_count` 105 → 110.
Live `table-inventory` reports `contract=110`, `in_db_not_in_contract=[]`.

## Guardrails / deferrals
Additive only; no raw-text/URL columns; only hashed/redacted/bounded fields + `*_persisted=0` CHECKs. Cards
remain 0 rows → `document_card_population_status` stays `deferred_not_blocking`; meeting-prep/risk-digest
stay `blocked` (no readiness overstated). The new (empty) V24 tables are **not yet** in the
`data-quality no-writeback-proof` scan scope — that integration is deferred to **Prompt 12** (07C no-raw
proof), consistent with the Prompt 01 scope-disclosure posture.
