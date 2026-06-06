# 162 — Phase 09: Approved-Family Retrieval Coverage Expansion

## Context

Phase 09 closed at `0c226208`. The retrieval substrate was operational and the vector index applied,
but coverage was narrow:

- The deterministic source-linked proof still emitted `no_read_model` warnings for `generated_outputs`,
  `meeting_prep_brief_sections`, and `review_controlled_correspondence_context` — three allowlisted
  families with no registered reader.
- Five allowlisted families that *did* have readers (`phase_07d_source_evidence_trails`,
  `project_issue_history_items`, `project_risk_digest_items`, `aging_exposure_report_items`,
  `cross_source_relationships`) were never bridged into the vector index — only the Obsidian, reviewed
  memory, and generated-output node loaders fed `_gather_approved_nodes`.

**Objective:** Expand approved-family coverage without weakening the no-raw / no-writeback /
review-control guardrails.

## Decisions

- **Three new deterministic readers** registered in `retrieval/readers.py::READER_REGISTRY`:
  `read_generated_outputs` (accepted research packets + apply-mode source-linked daily briefs),
  `read_meeting_prep_brief_sections` (via `ConstructionStore.list_meeting_prep_brief_sections`; the
  table is not project-scoped, so a project-scoped call returns nothing rather than leaking rows), and
  `read_review_controlled_correspondence_context` (a bounded single-query read of the redacted
  `email_thread_summaries` read model via `ConstructionStore.list_email_thread_summaries(limit=500)`;
  one item per thread, `summary_redacted` excerpt, `thread_key` source ref, tier floored at 2 / tier 3
  when review-required). All 10 allowlisted families are now reader-backed.

  Note: the correspondence reader reads the redacted thread summaries directly rather than running the
  heavier Phase 07D `CorrespondenceContextBuilder` relationship-join projection. The builder issues
  several `list_*(limit=100000)` calls (many unclosed WAL connections) per broker retrieve — too costly
  for the retrieval hot path, and its global SQLite-state churn destabilized an unrelated fragile
  file-size test (`test_phase_09_llamaindex_config`). The direct read uses the same real correspondence
  substrate, is bounded, and matches the single-connection pattern of every other deterministic reader.
- **Both meeting-prep and correspondence are made vector-embeddable** (added to
  `phase_09_embedding_vector_policy.seed.yaml::embeddable_source_families`). Only eligible items are
  ever indexed (see eligibility below), so review-required / tier-3 correspondence and meeting content
  never reaches the vector store.
- **New module `retrieval/read_model_loader.py`** bridges eligible deterministic read-model items into
  safe vector nodes. Served families = `embeddable_families(seed) ∩ READER_REGISTRY` minus the
  dedicated-loader families (`approved_obsidian_generated_outputs`, `accepted_long_term_memory`,
  `generated_outputs`) → the 5 long-standing families plus meeting-prep + correspondence. **Eligibility:**
  non-empty redacted excerpt, non-empty source ref, allowlisted family, `review_required is False`, and
  `review_tier <= 2`. Nodes carry only `content_excerpt_redacted` (as `text_redacted`) + hashes/labels;
  every node is re-validated with the Prompt 14 `validate_embedding_candidate` no-raw guard.
- **New approved-source manifest category `approved_read_models`** (`source_manifest.py` + contract +
  seed) sourced from the *same* `load_approved_read_model_nodes` output, so manifest coverage exactly
  matches what the vector gather will index. Entries carry hashes/metadata only (the excerpt text is a
  forbidden manifest entry field).
- **`vector_index._gather_approved_nodes`** appends the read-model nodes (de-duplicated by `node_id`)
  and the dry-run plan reports `indexed_family_count` / `read_model_family_count`.

## Coverage-layer distinction

`corpus_balance_mart.build_retrieval_coverage_layers(db_path)` (a thin wrapper over the corpus-balance
mart) distinguishes four layers, surfaced in the corpus mart, the source-linked proof, operator-status,
and the data-quality gates output:

- `deterministic_reader_families` — all reader-backed allowlisted families (now 10).
- `approved_manifest_categories` — manifest categories with ≥1 approved ref (best-effort, guarded).
- `vector_indexed_families` — distinct families in the latest applied `vector_index_items` receipts.
- `deferred_families_no_reader` (now empty) + `deferred_memory_substrate` (long-term memory
  consolidation remains deferred).

The corpus mart counts the new reader-backed families via dedicated branches: generated outputs
(accepted packets + apply briefs), correspondence (the `email_thread_summaries` anchor count), and
meeting-prep (its V25 table). Coverage-layer computation is deliberately cheap — it derives manifest
categories from the seed and counts correspondence from the anchor table rather than re-running the
readers.

## Guardrail note — empty-family coverage warning

Registering readers for previously-unbacked families removed their `no_read_model` warnings, which the
output-evaluation `coverage_warnings_surfaced` check had *coincidentally* relied on to detect coverage
gaps. The deterministic broker (and the context-budget mirror) now emit `empty_read_model:<family>`
when a backed family returns no rows — an honest, explicit coverage-gap signal that keeps the
evaluation gate sound (a missing family is never silently treated as full coverage). The daily-brief
context-builder proof and query-tool surfaces were updated accordingly (meeting-prep is now
reader-backed; a project-scoped brief degrades to empty, not `no_read_model`).

## Guardrails preserved

No raw email/document/calendar/Procore payload, prompt, response, signed/download URL, token, or secret
enters any node — only `*_redacted` excerpts + hashes. The `review_required is False` / `review_tier <= 2`
eligibility filter guarantees no high-impact / review-required item is vector-indexed. Vectors remain
outside SQLite; receipts are metadata-only; everything is read-only and fail-closed. No MCP surface
change, no source-system writeback, and no new financial/legal/claim/payment/safety determination.

## Validation

`python -m compileall src tests`, `ruff check .` (3 pre-existing `cli/procore.py` B008 errors only),
`mypy src` (2 pre-existing `review_burden_mart.py` errors only), and
`pytest -m "not live and not integration and not manual"`. New tests:
`tests/test_phase_09_read_model_coverage.py` (readers, loader eligibility/node validation, manifest
category, ≥5 indexed families, coverage layers, source-linked has no `no_read_model` for the three
families). Acceptance CLI: `second-brain retrieval source-linked build` (no `no_read_model` warnings),
`llamaindex build` (≥5 `per_family_node_count` on an eligible DB), `llamaindex build --apply` (still
fail-closed without `retrieval-local` deps / eligible nodes), and the no-raw-vector-index, phase-09
no-writeback, and MCP no-raw/no-writeback proofs.
