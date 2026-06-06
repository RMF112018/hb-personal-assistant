# Accepted Memory Activation — Repo-Truth Rebaseline & Memory Substrate Audit

**Phase 09 Addendum · Prompt 00**

This is a repo-truth audit performed *before* any accepted-memory activation work. It confirms what
the memory substrate already provides and records the decision on whether an additive schema
migration is required. **No code changes are made.**

## Baseline

- **HEAD:** `f87c9cb53bb0dc6cb17802632557a64ea03bc54e` (`f87c9cb5`) — exactly the required baseline.
- **Branch:** `phase-09-approved-family-coverage-expansion`.
- **Schema:** `LATEST_SCHEMA_VERSION = 39` (`src/hb_assistant/store/migrator.py:17`).
- **Working tree:** 27 pre-existing dirty files at audit start are regenerated evidence JSON/MD
  unrelated to this audit. They are left untouched and **not** staged with this audit.

## Memory schema (already activation-ready)

The canonical accepted-memory corpus is `long_term_memory_items`, introduced at **V26**
(`src/hb_assistant/store/migrator.py:3080-3097`). It already carries every field accepted-memory
activation needs:

| Concern | Column / constraint | Notes |
| --- | --- | --- |
| Review gate | `review_status TEXT NOT NULL CHECK(... IN ('accepted','pending_review','rejected','superseded'))` | `'accepted'` is the activation state |
| No-raw guards | `raw_prompt_persisted`, `raw_response_persisted`, `retrieved_context_persisted` | each `NOT NULL DEFAULT 0 CHECK(... = 0)` — fail-closed |
| Project scoping | `project_key TEXT` | indexed with review_status |
| Confidence | `confidence_class TEXT NOT NULL` | |
| Provenance | `origin_id`, `provenance_class` | source linkage via `long_term_memory_source_refs` |
| Supersession | `supersedes_memory_id TEXT` | stale/superseded chain |
| Index | `ix_long_term_memory_items_project (project_key, review_status)` | fast accepted-by-project filtering |

Supporting tables (V26): `long_term_memory_source_refs`, `long_term_memory_quality_signals`,
`memory_update_candidates`, `memory_update_reviews`. Quality-review and consolidation receipt tables
were added at **V38** (`migrator.py:4340+`).

## Loader (already activates accepted memory)

`load_reviewed_memory_nodes` (`src/hb_assistant/construction/second_brain/retrieval/memory_loader.py:102`):

- Opens the DB **read-only** (`?mode=ro`); fail-closed when schema version `< 38` or the table is
  absent.
- Strict activation gate: `SELECT ... FROM long_term_memory_items WHERE review_status = 'accepted'`
  (`memory_loader.py:127-133`), with optional `project_key` filter.
- Emits **metadata-only** nodes (`source_family='accepted_long_term_memory'`), each passed through
  the embedding no-raw guard (`validate_embedding_candidate`). Unreviewed statuses
  (`pending_review`, `rejected`, `superseded`) are never loaded.

## Coverage — memory is already a first-class family on all three planes

- **Deterministic reader:** `read_accepted_memory` (`retrieval/readers.py:278`); family
  `accepted_long_term_memory` is in `ALLOWLISTED_SOURCE_FAMILIES` (`retrieval/policy.py:34`).
- **Approved manifest:** category `reviewed_memory` (`retrieval/source_manifest.py`), eligible on
  `review_status='accepted'`.
- **Vector index:** reviewed-memory nodes are gathered via `_gather_approved_nodes`
  (`retrieval/vector_index.py`).
- **Parity reporting:** `memory_substrate_status` is reported as `"covered"` (any accepted memory
  exists) or `"deferred_empty"` (`corpus_balance_mart.py` / `coverage_parity.py`).

CLI, tests, contracts, and evidence for the substrate already exist (`second-brain memory
candidate|review`, `memory quality-review`, `memory consolidation-preview`, `retrieval
memory-loader status|proof`; `tests/test_phase_09_memory_loader.py`, `tests/test_memory_curator.py`,
`tests/test_memory_policy.py`, `tests/test_phase_09_memory_quality_review.py`,
`tests/test_phase_09_memory_consolidation_preview.py`, `tests/test_second_brain_memory_cli.py`,
`tests/test_phase_09_read_model_coverage.py`).

## Decision

**Existing schema is SUFFICIENT — no additive migration required.**

`long_term_memory_items.review_status` plus the loader's `review_status='accepted'` gate already
*is* accepted-memory activation, with guard columns, project key, confidence, provenance, source-ref
linkage, and supersession all present. Introducing a new migration would be redundant and would
violate the "no migration unless repo truth forces it" constraint. Accordingly this audit makes **no
code changes** and adds evidence only.

Because no code or schema changed, the conditional architecture-doc update (`docs/architecture/`)
does not apply.

## Acceptance criteria

- **Clear decision:** schema sufficient; `migration_required = false` — recorded here and in the JSON.
- **No code changes:** only these two evidence files are added.
- **No fabricated memory / no raw content:** this audit is metadata-only — table/column names,
  file:line citations, and structural facts; no memory statements, source refs, or row data.
