# 36 — Phase 07C: Controlled Extraction Eligibility

**Phase:** 07C (Document Intelligence Promotion) — Prompt 07.
**Status:** Implemented and applied to the live store at this record's commit.
**Evidence:** `docs/evidence/construction-intelligence-phase-07c-document-intelligence/07-controlled-extraction-eligibility-proof.md`.

Decides, **before any content download or parse**, the extraction disposition of each of the 283 document cards
and persists it to the card's `extraction_eligibility` column (V24). **Deterministic-only**: the decision is
computed from card metadata + the existing V18 file-ingestion policy + document review rules; no Graph call, no
model, no content read, no text persistence. No schema change (`LATEST_SCHEMA_VERSION` stays 24; V24 created no
extraction satellite table — the disposition is a card column).

## Eligibility ladder

`construction/document/extraction_eligibility.py` `evaluate_extraction_eligibility(store, *, apply=False, ...)`.
Per card, with `ext` normalized (lowercased, leading dot stripped) and the extension dispositions from
`load_file_ingestion_policy()` (`eligible` = pdf/docx/doc/xlsx/xls/csv/txt/rtf; `metadata_only` = CAD/image/
archive/video kinds; `blocked` = exe/dll/…), the review-required document types from
`load_document_review_rules()`, and the `controlled_extraction_contract.json` for attestation, the ladder is
(first match wins):

1. no extension → **skipped** (`no_extension`)
2. `ext ∈ blocked` → **blocked** (`policy_disallowed_extension`)
3. `size_class == 'oversize'` → **blocked** (`oversize`)
4. `ext ∈ metadata_only` → **metadata_only** (`metadata_only_extension`)
5. `review_required` OR `review_status ∈ {pending, blocked}` OR `document_type ∈ review_required_types`
   → **manual_approval_required** (`review_required`)
6. `ext ∉ eligible` → **metadata_only** (`unparseable_extension`)
7. not deterministically project-bound (`project_key`/`project_number_hash` missing)
   → **manual_approval_required** (`low_project_confidence`)
8. else → **eligible** (`eligible`)

**Precedence rationale:** dangerous/oversize kinds are dispositioned first; non-text-parseable kinds become
`metadata_only` regardless of review because they can never yield extracted text; text-parseable review-required
cards route to `manual_approval_required` (honoring "review-required files cannot extract"). `eligible` means a
card *may* be extracted on a later **explicit, separately-gated** request — never an automatic download. On
`--apply`, the disposition is written via the new `repositories.update_document_card_extraction_eligibility`
(a targeted `UPDATE` of only `extraction_eligibility` + `updated_utc`; guard/raw columns untouched). The CHECK
constraint enforces the six-value enum. `list_document_cards` was extended (additive) to also return
`extraction_eligibility` and `size_class`. Surfaced by
`hb-assistant graph files evaluate-extraction-eligibility [--apply] --json` (dry-run default).

## Live result

`--apply`: 283 cards dispositioned — **blocked 5** (oversize), **metadata_only 5** (CAD/image kinds),
**manual_approval_required 273**, **eligible 0** (all 283 cards are currently `review_required`, so none can be
eligible). Idempotent (re-apply → identical). Determinism verified identical `by_eligibility`/`by_reason_code`
across `PYTHONHASHSEED` 1/2/3. A live scan confirmed every `extraction_eligibility` value is within the six-value
enum, **0** review-required cards are marked `eligible`, the six guard CHECK columns are all 0, and 0 URL/token
patterns. Gates unchanged: `document_card_population_status` pass; `raw_content_leakage_scan` /
`external_writeback_scan` / `graph files no-writeback-proof` green; `meeting_prep_readiness.ready` stays **False**.

## Guardrails / deferrals

No download by default (no download/parse occurs at all). Review-required cards cannot be `eligible`. No raw
text/paths/URLs/tokens/secrets persisted — only the enum column is written (this is the first 07C prompt to
mutate a card column, and it mutates **only** `extraction_eligibility`). No model; deterministic-only. No
auto-promotion (a disposition label, not a candidate promotion). The V24 satellite tables remain outside the
no-writeback-proof static-scan scope (deferred to Prompt 12; not claimed here). The actual controlled download +
bounded redacted extraction, the document relationship candidates (08), card/match promotion (09), Obsidian
document outputs (10), and the document data-quality gate suite (11) remain deferred.
