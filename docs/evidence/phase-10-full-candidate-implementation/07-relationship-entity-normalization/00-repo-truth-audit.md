# Repo-Truth Audit — Relationship / Entity Normalization (Prompt 07)

## Existing surfaces (mature)

| Concern | Location | State |
|---|---|---|
| Unified substrate | `relationships/cross_source_substrate.py`; `cross_source_relationship_candidates` (V25) | Merges document/calendar/email/procore edges; deterministic-hash ids; never promotes; 8 guard columns. |
| Relationship scan | `…/local_ai/relationship_candidates.py` `build_relationship_candidates` | Deterministic email↔calendar scorer; dry-run + `--max-persist` cap → `phase10_relationship_candidates`; hashed refs only. |
| Entity tables | `procore_people/company/location_entities` | Redacted names + `source_count` dedup signal. |
| Project identity | `construction_project_identity` (V5) | Stable project keys / aliases. |
| CLI | `relationship-candidates scan`, `phase-10 relationship-candidates`, `data-quality relationship-quality` | Scan + quality mart; no consolidated review report. |

## Gap (Prompt requirement 2)

The substrate held rich candidates but there was no single **review-safe report grouped by operator
category** (alias/project, relationships, likely-duplicate entities, low-confidence needs-review,
rejected/not-actionable) with confidence reasons + source refs.

## Decision (surgical)

Add `relationship_entity_report.py` (`build_relationship_entity_report` + classifier + renderer)
that groups the V25 candidates deterministically by stable enums (relationship_type / confidence_class
/ promotion_status / review_required), plus a `relationship-candidates report` CLI verb. Read-only —
persists nothing, promotes nothing; a promotion-safety check proves no unreviewed/model-proposed
inference is in an accepted state. Deterministic-first (no model grouping). No schema change.
