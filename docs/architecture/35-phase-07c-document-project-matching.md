# 35 — Phase 07C: Document Project Matching

**Phase:** 07C (Document Intelligence Promotion) — Prompt 06.
**Status:** Implemented and applied to the live store at this record's commit.
**Evidence:** `docs/evidence/construction-intelligence-phase-07c-document-intelligence/06-document-project-match-proof.json`.

Records *which project* each of the 283 materialized document cards belongs to **deterministic-signals-first**,
writing advisory candidate rows to `construction_document_project_match_candidates` (V24). No model, no Graph
call, no re-parse of raw paths/names. No schema change (V24 already created the table; `LATEST_SCHEMA_VERSION`
stays 24).

## Matcher

`construction/document/project_matcher.py` `match_document_projects(store, *, apply=False, registry=None)`.
The card already carries a deterministic project binding from materialization (`project_key` from the
scope-compliant source location + `project_number_hash`), so the matcher consumes that binding rather than
re-deriving from raw drive items (it does **not** reuse `graph/file_project_matcher.py`, which re-parses raw
paths/names). Per card, with `project_hash = {p.project_key: hash_value(p.project_number)}` built from the
project registry (`load_source_registry`, `hash_value` = `sha256[:16]`):

1. **source key + full project-number hash** — `project_key` present and the card's `project_number_hash`
   equals the registry hash for that key → `candidate_type="deterministic"`, `confidence_class="deterministic"`,
   `confidence=0.95`, `deterministic=True`, `review_required=False`.
2. **conflict** — `project_number_hash` present but disagrees with the registry hash →
   `candidate_type="conflict"`, `confidence_class="weak_heuristic"`, `confidence=0.3`, `deterministic=False`,
   `review_required=True` (honors "no auto-promotion for conflicts").
3. **source key only** — no corroborating number hash available → `candidate_type="deterministic"`,
   `confidence_class="deterministic"`, `confidence=0.9`, `deterministic=True`, `review_required=False`.
4. **no project key** — `project_key` is falsy → `unmatched_skipped` (the candidate table requires a non-null
   project_key; such cards await source/project resolution). No candidate written.

`list_document_cards` was extended to also select `project_number_hash` (additive; other consumers read by
key and are unaffected). One candidate per matchable card (`matcher_name="deterministic_v1"`, stable
`candidate_id = hash_value("{document_card_id}|deterministic_v1|{project_key}")`,
`promotion_status='candidate'`), written via the new
`repositories.upsert_document_project_match_candidate` (guard CHECK columns never set). `signals_json` carries
only the matcher name and the named signal list (`source_location_project_key`, `full_project_number_hash`,
`project_number_hash_conflict`) — never a raw path/name/URL/project number. The card is **not mutated**
(candidates-only; promotion deferred to the Review prompt 09). Surfaced by
`hb-assistant graph files match-document-projects [--apply] --json` (dry-run default).

## Live result

`--apply`: 283 candidates — all 283 `deterministic` bound to project `tropical` via the source key corroborated
by the full project-number hash; 0 conflict, 0 review-required, 0 unmatched/skipped. Idempotent (re-apply →
283). Determinism verified identical `by_project_key`/`by_confidence_class`/`by_candidate_type` across
`PYTHONHASHSEED` 1/2/3. Gates unchanged: `document_card_population_status` pass; `raw_content_leakage_scan` /
`external_writeback_scan` / `graph files no-writeback-proof` / `data-quality no-writeback-proof` green; a scan
of all 283 candidate rows found 0 URL/email/iCal/token patterns and the guard CHECK columns
(`raw_document_text_persisted`, `external_writeback_performed`) all 0; `meeting_prep_readiness.ready` stays
**False** (blocked on `review_required_routing_presence`; project matching is not a prerequisite).

## Guardrails / deferrals

Deterministic-first; model advisory-only and not invoked. No raw text/paths/URLs/project-numbers/tokens/secrets
persisted; candidate guard CHECK columns stay 0; conflicts and any non-deterministic class → review; no
auto-promotion; no high-impact determination. The V24 candidate tables (incl. project_match) are **not yet** in
the no-writeback-proof static-scan scope — that coverage is deferred to Prompt 12 and is not claimed here.
Controlled extraction (07), relationship candidates (08), card/match promotion (09), Obsidian document outputs
(10), and the data-quality gate suite for project matching (11) remain deferred.
