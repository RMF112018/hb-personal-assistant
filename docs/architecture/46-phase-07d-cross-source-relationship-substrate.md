# 46 — Phase 07D Cross-Source Relationship Substrate (Prompt 03)

**Status:** Implemented (Phase 07D Prompt 03). Additive; no schema change (V25 tables created
in Prompt 02). **Scope:** the substrate store layer, a normalization engine, and the
`construction-agent relationships` build/status CLI.

## Why

07D needs one unified relationship surface to drive meeting-prep briefs, issue history, risk,
and aging. The per-source candidate tables (document V24, calendar↔email V23, email V11) stay
authoritative; the substrate **normalizes** them into `cross_source_relationship_candidates`
with consistent confidence classes, review routing, and compact evidence trails — without
replacing or mutating the sources.

## 03/04 split

Prompt 04 explicitly owns normalizing "document, email, calendar, **Procore, and
source-record-map** candidates" + cross-family `project_key` alignment + promotion. So Prompt 03:
- Ships the **machinery** (store methods + engine + CLI) and seeds from the three existing
  **edge-shaped relationship-candidate** tables.
- Leaves to Prompt 04: Procore-native edges (`procore_record_edges`), `source_system_record_map`
  / `relationship_resolution_queue` arms, `project_key` backfill/alignment, cross-family dedup,
  and **policy-gated promotion** into `cross_source_relationships`.
- `build` writes **candidates + evidence trails only** — it never promotes, so the
  "never auto-promote weak/model/sensitive" guardrail is structurally satisfied.

## Engine (`construction/relationships/cross_source_substrate.py`)

- **`NormalizedEdge`** (`extra="forbid"`) — the source-agnostic edge shape produced by adapters.
- **Adapters** (read-only via store `list_*`): `_document_edges`, `_meeting_email_edges`,
  `_email_edges`. Refs come straight from the sources' local IDs / existing hashes
  (`document_card_id`+`target_record_key_hash`, `event_index_id`+`thread_key_hash`,
  `message_id`+`target_key` with a hash fallback when null).
- **`CrossSourceRelationshipSubstrateBuilder.build(dry_run, project_filter, max_edges)`** — counts
  computed regardless of `dry_run`; writes only when applying.

### Confidence-class mapping (source → unified V25 enum)

| Source signal | Unified class |
| --- | --- |
| `model_proposed` flag set | `model_proposed` |
| `deterministic` flag set | `deterministic` |
| score ≥ 0.80 | `strong_heuristic` |
| otherwise | `weak_heuristic` |

### Review / sensitive routing

Driven by `review_required_relationship_rules.seed.yaml`:
`review_required = confidence_class ∈ {weak_heuristic, model_proposed, stale_or_unresolved}`
`OR sensitive_high_impact OR origin_review_required`. `sensitive_high_impact` = the source's own
flag OR a sensitive-category keyword (legal/contractual/claim/safety/personnel/financial) hit on
the edge's relationship/record types.

## Invariants

1. **Idempotent.** `candidate_id = hash(source_family|source_record_ref|target_family|target_record_ref|relationship_type)`
   matches the table UNIQUE edge key → re-runs upsert, never duplicate. `evidence_trail_id =
   hash("evt|"+candidate_id)`.
2. **No raw content.** `source_reference_json` / `signals_json` / `source_refs_json` hold only
   hashes, local IDs, enum names, and booleans. The eight V25 guard CHECK columns stay 0
   (never written).
3. **No auto-promotion.** Every candidate is `promotion_status='candidate'`;
   `cross_source_relationships` is untouched by `build` (its `upsert_*` ships for Prompt 04).
4. **Advisory only.** Substrate seeded ≠ meeting-prep ready; `meeting_prep_readiness` is unaffected.

## Store (`construction/store/repositories.py`)

`upsert_cross_source_relationship_candidate` / `upsert_source_evidence_trail` /
`upsert_cross_source_relationship` (+ `count_*` / filtered `list_*`), plus
`list_document_relationship_candidates_full` for the document adapter. All mirror the existing
`upsert_document_relationship_candidate` pattern.

## CLI

`construction-agent relationships build` (`--apply` default dry-run, `--project`, `--json`) and
`relationships status` (`--project`, `--json`). Names match `phase_07d_validation_matrix.json`.

## Related records
- `45` — V25 schema + contracts (Prompt 02; this substrate's tables).
- `30–42` — Phase 07C document intelligence (a source of edges).
- `43`–`44` — 07D remediation + local PDF extraction.
