# Phase 07C — Prompt 07: Controlled Extraction Eligibility Proof

- **phase:** construction-intelligence-phase-07c-document-intelligence
- **prompt:** 07-controlled-extraction-eligibility
- **generated_utc:** 2026-05-31
- **repo_sha_parent:** `016acb4dc759aaeae301e0ddaec4972d8b7047cf`
- **schema_version:** 24 (no migration; `extraction_eligibility` is an existing V24 card column)
- **package_version:** 1.3.0
- **contract:** `controlled_extraction_contract` (version `phase07c-v1`)
- **command:** `hb-assistant graph files evaluate-extraction-eligibility --apply --json`
- **mode:** apply
- **exit_code:** 0
- **ok:** true
- **deterministic:** verified identical `by_eligibility` / `by_reason_code` across `PYTHONHASHSEED` 1/2/3

> **leak_safe:** counts by eligibility / reason code + gate statuses only; no per-card identifiers, and no raw
> filenames, paths, web URLs, project numbers, tokens, secrets, or document text. The only value written to the
> store is the six-value `extraction_eligibility` enum on each card. No content was downloaded or parsed.

## Summary (283 cards)

| extraction_eligibility | count |
| --- | --- |
| blocked | 5 |
| metadata_only | 5 |
| manual_approval_required | 273 |
| eligible | 0 |

| reason_code | count |
| --- | --- |
| oversize | 5 |
| metadata_only_extension | 5 |
| review_required | 273 |

- **eligible:** 0
- **review_required_held_from_extraction:** 283 (every review-required card was withheld from extraction)

## Idempotency

Re-running `--apply` produced an identical distribution (blocked 5 / metadata_only 5 / manual_approval_required
273); no card changed disposition on the second pass.

## Guardrails

| guardrail | value |
| --- | --- |
| external_systems | read_only |
| graph_calls | none |
| model_invoked | false |
| deterministic_first | true |
| download_performed | false |
| parse_performed | false |
| raw_document_text_persisted | false |
| raw_path_or_url_persisted | false |
| auto_promotion | false |
| card_columns_mutated | ["extraction_eligibility"] |
| card_eligibility_updated | true |

## Post-apply gates

| gate | status |
| --- | --- |
| document_card_population_status | pass |
| raw_content_leakage_scan | pass |
| external_writeback_scan | pass |
| graph files no-writeback-proof | passed |
| meeting_prep_readiness.ready | false |

## Leak / safety scan (live `construction_document_cards`)

- rows scanned: 283
- all `extraction_eligibility` values within the six-value enum: **true**
- review-required cards marked `eligible`: **0**
- guard CHECK columns (raw_document_text / raw_payload / signed_url / download_url / source_file_copied_to_vault /
  external_writeback) all 0: **true**
- URL / token pattern hits: **0**

## Deferred disclosure

The V24 satellite tables (classification / project-match / relationship candidates, previews, projection runs)
remain outside the no-writeback-proof static-scan scope; that coverage is deferred to Prompt 12 and is not
claimed here.

## Outcome

283 document cards received a controlled-extraction disposition computed deterministically from card metadata +
the file-ingestion policy + document review rules — with no content download, parse, or text persistence. Because
all 283 cards are currently review-required, **0** are `eligible`; 273 route to `manual_approval_required`, 5 are
`blocked` (oversize), and 5 are `metadata_only` (CAD/image kinds). Only the `extraction_eligibility` column was
written; every guard column stayed 0; no raw content or unsafe identifier was persisted; and no readiness was
overstated (meeting-prep still blocked).
