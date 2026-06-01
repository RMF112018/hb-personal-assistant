# 47 — Phase 07D Relationship Normalization & Promotion (Prompt 04)

**Status:** Implemented (Phase 07D Prompt 04). Additive; no schema change. **Scope:** extend the
Prompt-03 substrate engine with the remaining source arms, cross-family `project_key` alignment,
and policy-gated deterministic promotion; run the first live substrate population.

## Why

Prompt 03 shipped the substrate machinery and seeded it from the three edge-shaped candidate
tables. Prompt 04 completes coverage — the **Procore-native edge graph** (the largest source,
1,671 live edges) and the Phase 07A **relationship_resolution_queue** — wires
`source_system_record_map` for `project_key` alignment, and promotes the deterministic subset into
a confirmed-relationship layer.

## The five source arms (`_ADAPTERS`)

| Adapter | Source table | Edge shape | Class source |
| --- | --- | --- | --- |
| `_document_edges` | `construction_document_relationship_candidates` (V24) | document → procore record | flags/score |
| `_meeting_email_edges` | `meeting_email_relationship_candidates` (V23) | calendar event ↔ email thread | flags/score |
| `_email_edges` | `email_relationship_candidates` (V11) | email → project/procore/calendar | flags/score |
| `_procore_edges` | `procore_record_edges` (V7) | procore record → record / entity | deterministic (conf≥0.999) |
| `_resolution_queue_edges` | `relationship_resolution_queue` (V20) | canonical → canonical | `confidence_class` carried verbatim |

`NormalizedEdge.confidence_class_override` lets a source that already classifies an edge (the
resolution queue) carry its class through; `_confidence_class` honors a valid override before the
flag/score fallback. Procore record→entity edges (where `to_record_key` is null) map to a
`procore_entity` target family using the already-hashed `to_entity_key`.

## project_key alignment

`build()` backfills a missing `project_key` from `source_system_record_map` via
`resolve_source_record_project_key(source_family, source_record_ref)` **before** the project
filter, so an alignable edge is not wrongly skipped. Alignment never changes `candidate_id` (the
identity hash excludes `project_key`), so dedup is unaffected. The map is empty in the live DB
today, so alignment is a counted no-op until Phase 07A's map is populated.

## Deterministic promotion (`promote()` + `relationships promote`)

Gated by `cross_source_relationship_policy.seed.yaml`: promotion runs only when
`deterministic.allow_local_promotion` is true, and a candidate is promoted into
`cross_source_relationships` only if `confidence_class == 'deterministic'` **and** not
`sensitive_high_impact` **and** not `review_required`. `relationship_id = hash("rel|"+candidate_id)`
makes it idempotent; `promoted_by = 'deterministic'`. Weak/strong/model/sensitive/high-impact are
**never** auto-promoted (the hard guardrail). Promotion writes the confirmed layer only; it does
not mutate candidate rows. Dry-run is the default; `--apply` is required to write.

## First live population

`relationships build --apply` → 1,880 candidates + 1,880 evidence trails (procore 1,671 / calendar
117 / email 69 / document 23). `relationships promote --apply` → 1,671 deterministic Procore edges
promoted; 209 non-deterministic skipped; 0 sensitive/review promoted. Both no-writeback proofs pass
over the populated tables.

## Invariants (unchanged from 46, reaffirmed)

No raw content (refs are local IDs / hashes; `metadata_json` / `evidence_redacted` free-text never
read into substrate rows; guard CHECK columns stay 0); deterministic-hash idempotency; advisory
only; promotion strictly deterministic + policy-gated.

## Related records
- `45` — V25 schema + contracts.
- `46` — substrate engine + `relationships build`/`status` (Prompt 03).
