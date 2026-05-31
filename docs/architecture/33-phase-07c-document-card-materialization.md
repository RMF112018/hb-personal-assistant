# 33 — Phase 07C: Document Card Materialization

**Phase:** 07C (Document Intelligence Promotion) — Prompt 04.
**Status:** Implemented and applied to the live store at this record's commit.
**Evidence:** `docs/evidence/construction-intelligence-phase-07c-document-intelligence/04-document-card-materialization-proof.json`.

Populates `construction_document_cards` from the indexed drive-item layer using **safe fields only** —
the core 07C step that clears the `document_card_population_status` blocker. No schema change (V24 already
present); Graph stays read-only (reads already-indexed inventory; no token, no Graph call).

## Source and rules

Source: `construction_drive_item_inventory` (the populated Phase 06A file layer). Per
07_DOCUMENT_CARD_MATERIALIZATION_PLAN: **one card per active file-like drive item**; folders are source
context only; deleted rows (`status != 'active'`) produce no card; **scope-non-compliant sources are
blocked** (via `non_compliant_source_keys` from Prompt 03); cards materialize as **review-required
candidates** (document type / project match / extraction are deferred to Prompts 05–08 — no auto-promotion).

## Worker + command

`construction/document/card_materializer.py` `materialize_document_cards(store, *, apply=False, registry=None,
policy=None)` iterates `distinct_inventory_source_keys()` → `list_inventory(source_key)`, skipping
folders / deleted / unknown-source / blocked-source rows (each counted), and for each active file-like
compliant row derives the safe card fields and (when `apply`) upserts. Counts are computed regardless of
`apply`; writes happen only when `apply=True`. Surfaced by `hb-assistant graph files
materialize-document-cards [--apply] --json` (dry-run default, matches the `graph files sources` --apply
template).

### Safe-field derivation (no raw value ever stored)
Reuses `normalize/redaction.py`: `hash_value` = `sha256[:16]` (the same scheme calendar uses for project
numbers), `redact_subject(name)` → `[redacted:<hash16>]`. Per card:
`document_card_id = hash_value("{source}|{drive}|{item}")` (stable → idempotent), `card_id =
document_card_id`; `drive_id_hash` / `drive_item_id_hash` / `title_hash` / `source_path_hash` = `hash_value(...)`;
`source_path_token_hashes_json` = JSON of per-token hashes; `title_redacted` = `[redacted:<hash>]`;
`file_extension` parsed; `mime_type` from a small ext→MIME map; `size_class` bucketed via the file-ingestion
thresholds; `last_modified_datetime` carried; `source_reference_json` = hashes only (no URL/path);
`project_key` = source.project_key and `project_number_hash` = `hash_value(source.project_number)`
(deterministic source context, not a model match). Review state: `document_type='unknown'`,
`confidence_class='unknown'`, `extraction_eligibility='not_evaluated'`, `review_status='pending'`,
`review_required=1`, reasons `["unclassified_document_type"]`. The six guard columns stay `0`.

The card upsert (`repositories.py:upsert_document_card`) was extended additively to write the V24 columns
(legacy callers unaffected); `get_document_card` now returns the full row; `count_document_cards()` and
`distinct_inventory_source_keys()` were added.

## Live result

`--apply` against the live store: **283 review-required candidate cards** from the single compliant
SharePoint project-drive source (401 inventory rows → 118 folders + 0 deleted + 0 blocked skipped; 4
OneDrive sources blocked at the registry level have no inventory). Idempotent (re-apply → still 283).
`document_card_population_status` → **pass**, 07C `blocked_by` → `[]`. `raw_content_leakage_scan`,
`external_writeback_scan`, and `data-quality no-writeback-proof` stay green; a scan of all 283 card rows
found **0** URL/email/iCal patterns. `meeting_prep_readiness.ready` remains **False** (blocked by
`review_required_routing_presence`, `auto_readiness_allowed=False`) — card population is real progress,
nothing overstated.

## Guardrails / deferrals
No raw text / paths / URLs / signed-download URLs / tokens / secrets in SQLite, evidence, or vault — only
hashed/redacted/bounded fields; guard CHECK columns enforce `0`. Idempotent upserts; no external writeback.
Classification (05), project matching (06), controlled extraction (07), relationship candidates (08), and
no-writeback-proof coverage of the V24 card tables (12) remain deferred.
