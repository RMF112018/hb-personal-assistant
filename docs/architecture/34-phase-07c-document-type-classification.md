# 34 — Phase 07C: Document Type Classification

**Phase:** 07C (Document Intelligence Promotion) — Prompt 05.
**Status:** Implemented and applied to the live store at this record's commit.
**Evidence:** `docs/evidence/construction-intelligence-phase-07c-document-intelligence/05-document-classification-proof.json`.

Classifies the 283 materialized document cards into construction document types **deterministic-signals-first**,
writing advisory candidate rows to `construction_document_classification_candidates` (V24). Model output is
advisory-only and **not invoked** (deterministic-first; offline-safe). No schema change; Graph read-only.

## Policy (new seeds)

`resources/config/document_type_classification_policy.seed.yaml` (`classification_order`, `document_types`
keyword vocabulary, `review_required_types`) and `resources/config/review_required_document_rules.seed.yaml`
(`review_required_when` {document_type, confidence_class, flags}; no-auto-promotion rules), loaded by
`construction/policy/document_classification.py` (mirrors the document-source policy loader; no-auto-promotion
booleans `Literal`-locked).

## Classifier

`construction/document/classifier.py` `classify_document_cards(store, *, apply=False, ...)`. Per card:
hydrate the inventory row via `(source_id, drive_item_id)`, derive **normalized token hashes** (lowercase,
split on `[\W_]+`, len≥2, plus a de-pluralized variant so `RFIs`/`Drawings` match the singular vocabulary;
`hash_value` = `sha256[:16]`), and apply signals in order:

1. **record_number** — RFI/CO·PCO/SUB/PAYAPP·G702/INSP/addenda patterns → type (`deterministic`).
2. **folder_token_hashes** — folder token hash ∈ hashed vocabulary → type (`deterministic`).
3. **filename_token_hashes** — filename token hash ∈ vocabulary → type (`deterministic`/`high_heuristic`).
4. **extension_mime** — unambiguous ext (dwg/dxf→drawings, png/jpg/…→photo_media, mpp→schedule).
5. else → `unknown_needs_review` (`heuristic`/`unknown`).

**Determinism:** when a name/folder matches keywords of more than one type, the winner is chosen by stable
policy-order rank (`_best_match` + `type_rank`), not set-iteration order — verified identical across
`PYTHONHASHSEED` 1/2/3. Multiple distinct matched types set a `conflicting_type_signals` flag → review.

**Review routing:** `review_required` = (type ∈ `review_required_types`: contract/change_order/pay_application/
inspection_report/warranty_closeout/unknown) OR (confidence_class ∈ moderate/weak/model/unknown) OR a
sensitivity match from the reused `ReviewPolicyEvaluator` (folder/name → `PROTECTED_CATEGORIES`). Reasons +
flags captured in `signals_json` (policy vocabulary + extension + hashes only — never a raw token/name/path).

One candidate per card (`classifier_name="deterministic_v1"`, stable `candidate_id`, `promotion_status='candidate'`),
written via the new `repositories.upsert_document_classification_candidate` (guard CHECK columns never set).
The card is **not mutated** (candidates-only; promotion deferred to the Review prompt 09). Surfaced by
`hb-assistant graph files classify-document-cards [--apply] --json` (dry-run default).

## Live result

`--apply`: 283 candidates — 67 deterministic (drawings 26, contract 12, schedule 9, rfi 8, addenda 7,
change_order 2, photo_media 2, daily_report 1), 216 `unknown_needs_review`; 236 review-required. Idempotent
(re-apply → 283). Gates unchanged: `document_card_population_status` pass; `raw_content_leakage_scan` /
`external_writeback_scan` / `no-writeback-proof` green; a scan of all 283 candidate rows found 0 URL/email/iCal
patterns; `meeting_prep_readiness.ready` stays **False**. Cards still `document_type='unknown'`.

## Guardrails / deferrals
Deterministic-first; model advisory-only and not invoked. No raw text/prompt/response/paths/URLs/tokens/secrets
persisted; candidate guard CHECK columns stay 0; sensitive/high-impact + weak/unknown → review; no
auto-promotion; no high-impact determination. Project matching (06), controlled extraction (07), relationship
candidates (08), card promotion (09), and no-writeback-proof coverage of the V24 candidate tables (12) remain
deferred.
