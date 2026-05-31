# 38 — Phase 07C: Review-Controlled Document Intelligence (Project Previews)

**Phase:** 07C (Document Intelligence Promotion) — Prompt 09.
**Status:** Implemented and applied to the live store at this record's commit.
**Evidence:** `docs/evidence/construction-intelligence-phase-07c-document-intelligence/09-review-controlled-document-intelligence-proof.md`.

Produces one **project-level** document-intelligence preview per project, rolled up from the already-populated
document cards + classification / project-match / relationship candidates + extraction dispositions, into the V24
table `construction_document_intelligence_previews` (`preview_kind="project_document_intelligence"`,
`document_card_id` NULL). Read-only, counts-only, review-controlled. No schema change
(`LATEST_SCHEMA_VERSION` stays 24).

## Rollup / confidence / warnings

`construction/document/preview_builder.py` `build_document_intelligence_previews(store, *, apply=False)`. It reads
`list_document_cards()`, `list_document_classification_candidates()`, and the new
`list_document_project_match_candidates()` / `list_document_relationship_candidates()`, groups every candidate to
its project via the card's `document_card_id → project_key`, and per project aggregates **counts only**:
documents by `size_class` / `extraction_eligibility` / review state; classification classified-vs-unclassified by
`confidence_class`; project-match count; relationship count by `target_record_type`; distinct source count.

- **confidence_class rollup** (deterministic): `classified_fraction = classified / total` →
  `>=0.8 high_heuristic`, `>=0.5 moderate_heuristic`, `>=0.2 weak_heuristic`, else `unknown`. (The table's
  `confidence_class` is free-text; the worker only emits the card CHECK vocabulary.)
- **`preview_redacted`**: a bounded, fixed-shape multi-line summary of those counts — never a raw name, path,
  URL, or excerpt.
- **`warnings_json`**: `{warnings: [...], source_reference: {project_key, document_count, distinct_sources},
  review: {documents_pending_review, candidate_items_pending_review}}`. Warnings are safe count/category strings
  (unclassified backlog, extraction disposition split, relationship-candidate note + email/calendar deferral, and
  an explicit "advisory; no auto-promotion; no legal/claim/financial/personnel/safety conclusions" line).
- **`review_required`** is set whenever any document or candidate in the project is review-required.

Persisted via the new `repositories.upsert_document_intelligence_preview` (idempotent by
`preview_id = hash_value("{project_key}|project_document_intelligence")`; guard CHECK columns never set).
Surfaced by `hb-assistant graph files build-document-previews [--apply] --json` (dry-run default).

## Live result

`--apply`: 1 preview (project `tropical`) — 283 documents (small 176, medium 73, large 29, oversize 5);
classification 67 classified (deterministic 42, high_heuristic 25) / 216 unknown_needs_review; project-match 283;
extraction 273 manual_approval_required / 5 metadata_only / 5 blocked / 0 eligible; relationships 23 (contract 12,
rfi 8, change_order 2, daily_log 1); 283 documents + 261 candidate items pending review; 1 indexed source.
`classified_fraction = 67/283 ≈ 0.24 → confidence_class = weak_heuristic`; `review_required = 1`. Idempotent
(re-apply → 1). Determinism verified identical summary across `PYTHONHASHSEED` 1/2/3. A live scan confirmed 0
URL/token patterns, the four guard CHECK columns all 0, and `confidence_class` within the six-value vocabulary.
Gates unchanged: `document_card_population_status` pass; `raw_content_leakage_scan` / `external_writeback_scan` /
`graph files no-writeback-proof` green; `meeting_prep_readiness.ready` stays **False**.

## Guardrails / deferrals

No legal/claim/financial/personnel/safety conclusions — the preview is pure counts/status with advisory framing.
Review states visible (review_required + pending counts); source references required (`source_reference` in
`warnings_json`). No raw document text / path / URL / token / secret persisted — `preview_redacted` /
`warnings_json` carry counts + safe keys only. No external-system writeback; read-only. No card mutation; no
auto-promotion. The V24 satellite tables (incl. previews) remain outside the no-writeback-proof static-scan scope
(deferred to Prompt 12; not claimed here). Obsidian document outputs (10) and the document data-quality gate suite
(11) remain deferred.
