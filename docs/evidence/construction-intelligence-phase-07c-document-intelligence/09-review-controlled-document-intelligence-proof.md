# Phase 07C — Prompt 09: Review-Controlled Document Intelligence Proof

- **phase:** construction-intelligence-phase-07c-document-intelligence
- **prompt:** 09-review-controlled-document-intelligence
- **generated_utc:** 2026-05-31
- **repo_sha_parent:** `95b0a06342bb4ee2881afeecf04faccf7017ef8f`
- **schema_version:** 24 (no migration; previews table created by V24)
- **package_version:** 1.3.0
- **command:** `hb-assistant graph files build-document-previews --apply --json`
- **mode:** apply
- **exit_code:** 0
- **ok:** true
- **deterministic:** verified identical summary across `PYTHONHASHSEED` 1/2/3

> **leak_safe:** counts/status only + gate statuses. `preview_redacted` and `warnings_json` carry aggregate
> counts and safe keys (project_key, document/source counts, enum distributions) — no per-card identifiers, and no
> raw filenames, paths, web URLs, excerpts, tokens, or secrets. No legal/claim/financial/personnel/safety
> conclusion.

## Project rollup (live: `tropical`)

- **previews written:** 1 (one per project; `preview_kind=project_document_intelligence`, `document_card_id`
  NULL)
- **confidence_class:** `weak_heuristic` (classified_fraction = 67/283 ≈ 0.24)
- **review_required:** 1

| dimension | counts |
| --- | --- |
| documents | 283 (small 176, medium 73, large 29, oversize 5) |
| classification | 67 classified (deterministic 42, high_heuristic 25), 216 unknown_needs_review |
| project match | 283 deterministic |
| extraction eligibility | manual_approval_required 273, metadata_only 5, blocked 5, eligible 0 |
| relationships | 23 (procore; contract 12, rfi 8, change_order 2, daily_log 1) |
| review pending | 283 documents + 261 candidate items |
| sources | 1 indexed source |

## Idempotency

Re-running `--apply` produced 1 preview (unchanged); the row is keyed by
`preview_id = hash("{project_key}|project_document_intelligence")`.

## Guardrails

| guardrail | value |
| --- | --- |
| external_systems | read_only |
| graph_calls | none |
| model_invoked | false |
| deterministic_first | true |
| raw_document_text_persisted | false |
| raw_path_or_url_persisted | false |
| external_writeback | false |
| auto_promotion | false |
| card_mutated | false |
| high_impact_conclusions | false |

## Post-apply gates

| gate | status |
| --- | --- |
| document_card_population_status | pass |
| raw_content_leakage_scan | pass |
| external_writeback_scan | pass |
| graph files no-writeback-proof | passed |
| meeting_prep_readiness.ready | false |

## Leak / safety scan (live `construction_document_intelligence_previews`)

- rows scanned: 1
- URL / token pattern hits: **0**
- guard CHECK columns (raw_document_text / raw_prompt / raw_response / external_writeback) all 0: **true**
- confidence_class within the six-value vocabulary (deterministic / high_heuristic / moderate_heuristic /
  weak_heuristic / model_proposed / unknown): **true**

## Deferred disclosure

The V24 satellite tables (incl. previews) remain outside the no-writeback-proof static-scan scope; that coverage
is deferred to Prompt 12 and is not claimed here.

## Outcome

One project-level document-intelligence preview was written for project `tropical`, rolled up deterministically
from the document cards + classification / project-match / relationship candidates + extraction dispositions. The
preview is a bounded, counts-only redacted summary with a `weak_heuristic` confidence class (67/283 documents
classified), visible review state (283 documents + 261 candidate items pending), a required source reference, and
a warnings list — no raw content, no unsafe identifier, and no high-impact conclusion. Read-only; no card
mutation, no auto-promotion, no external writeback. No readiness overstated (meeting-prep still blocked).
