# 163 — Phase 09: Reader / Manifest / Vector Coverage-Parity Proof Surfaces

## Context

Builds on doc 162 (approved-family coverage expansion). That work made all 10 allowlisted retrieval
families reader-backed, added the `approved_read_models` manifest category, the `read_model_loader`,
and a `coverage_layers` block. This run brings the three coverage planes into **explicit, provable
parity** with dedicated proof surfaces, the objective's exact reporting fields, and committed evidence —
without weakening no-raw / no-writeback / advisory-only / review-control guardrails.

## Coverage planes (runbook)

Three distinct planes are now reported separately (never conflated, never overstated):

- **Deterministic reader coverage** — families with a registered reader in
  `retrieval/readers.py::READER_REGISTRY`. **All 10** allowlisted families
  (`retrieval/policy.py::ALLOWLISTED_SOURCE_FAMILIES`) are reader-backed:
  `phase_07d_source_evidence_trails`, `cross_source_relationships`, `project_issue_history_items`,
  `project_risk_digest_items`, `aging_exposure_report_items`, `meeting_prep_brief_sections`,
  `review_controlled_correspondence_context`, `approved_obsidian_generated_outputs`,
  `generated_outputs`, `accepted_long_term_memory`. `missing_reader_families == []`.
- **Approved-manifest coverage** — families the approved-source manifest admits across enabled
  categories (`generated_outputs`, `approved_obsidian_outputs`, `reviewed_memory`,
  `approved_read_models`). `approved_read_models` admits the safe, redacted, source-linked,
  non-review-required, `review_tier <= 2` deterministic items from the seven read-model families.
- **Vector-index coverage** — families actually present in the latest **applied** vector index
  (`second_brain_retrieval_vector_index_items`). Before this work: 2
  (`approved_obsidian_generated_outputs`, `generated_outputs`). After (post `llamaindex build --apply`
  with the retrieval-local toolchain): **8** — the 2 plus `cross_source_relationships`,
  `phase_07d_source_evidence_trails`, `project_issue_history_items`, `project_risk_digest_items`,
  `meeting_prep_brief_sections`, `review_controlled_correspondence_context`.
- **Deferred** — `accepted_long_term_memory` (memory substrate empty → `memory_substrate_status:
  deferred_empty`), reported deferred, never fabricated. `aging_exposure_report_items` indexes only
  when eligible (non-review-required, deterministic/strong) rows exist.

`coverage_parity_ok` is **reader-plane parity only** (`missing_reader_families == []`); empty
manifest / vector / memory families are deferred signals, not parity failures (no readiness
overstatement).

## Coverage-parity report (exact fields)

`corpus_balance_mart.build_coverage_parity_report(db_path)` (thin wrapper over the corpus-balance mart;
cheap — no live manifest build in the hot path) emits:
`deterministic_allowlisted_family_count`, `deterministic_reader_family_count`,
`deterministic_reader_families`, `missing_reader_families`, `approved_manifest_category_count`,
`approved_manifest_categories`, `approved_manifest_family_count`, `approved_manifest_families`,
`vector_indexed_family_count`, `vector_indexed_families`, `empty_approved_families`,
`deferred_families`, `memory_substrate_status`, `coverage_parity_ok`. This block (`coverage_parity`)
is surfaced by the corpus-balance mart, the source-linked proof, operator-status, and the
data-quality gates.

## Proof surfaces (new) + CLI

Each follows the established `build_X_proof(*, evidence_dir=None, write_evidence=True)` pattern
(JSON+MD to the phase-09 evidence dir; `_assert_no_raw` over the serialized output; controlled temp
DBs; planted-unsafe cases for non-vacuity):

- `retrieval/coverage_parity.py::build_reader_registry_parity_proof` — allowlist ↔ registry parity
  (`missing_reader_families == []`, no non-allowlisted reader). CLI:
  `second-brain retrieval reader-registry-parity-proof`.
- `retrieval/source_manifest.py::build_approved_read_model_manifest_proof` — `approved_read_models`
  populated with eligible, metadata-only, guard-clean entries; planted high-impact / review-required /
  excluded / raw-shape candidates rejected; persisted manifest row metadata-only. CLI:
  `second-brain retrieval approved-read-model-manifest-proof`.
- `retrieval/read_model_loader.py::build_read_model_vector_loader_proof` — loader bridges eligible
  items into safe, in-memory-only nodes (≥5 families), excludes review-required/high-impact, rejects
  raw/excluded candidates, persists nothing to SQLite. CLI:
  `second-brain retrieval read-model-vector-loader-proof`.
- `retrieval/coverage_parity.py::build_coverage_parity_closeout` — aggregates the report + the three
  proofs into a closeout (`closeout_ok`). CLI: `second-brain retrieval coverage-parity-closeout`.

Evidence: `reader-registry-parity-proof.{json,md}`, `approved-read-model-manifest-proof.{json,md}`,
`read-model-vector-loader-proof.{json,md}`, `coverage-parity-closeout.{json,md}` under
`docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/`.

## Why the guardrails remain intact

- **No raw**: readers/manifest/nodes carry only `*_redacted` excerpts + hashes; every node is
  re-validated by `embedding_policy.validate_embedding_candidate`; every evidence artifact passes
  `_assert_no_raw`. Vectors/text never persist to SQLite (vectors live on the filesystem under
  Application Support); the no-raw-vector-index proof passes post-apply.
- **No writeback / no direct external access**: proofs are read-only over controlled temp DBs; no MCP
  surface change; no Graph/Procore/source-system writeback. The phase-09 no-writeback proof passes
  (note: set members are accumulated with `.add()` so the source scanner does not false-positive).
- **Review-control**: the read-model eligibility filter (`review_required is False`,
  `review_tier <= 2`) keeps every review-required / high-impact / tier-3 item out of the manifest and
  the vector index — proven by the planted-rejection cases.
- **Advisory-only**: no financial/legal/claim/payment/safety determination is produced; readiness is
  not overstated (memory + empty families reported deferred).

## Validation

`compileall`, `ruff check .` (3 pre-existing `cli/procore.py` B008 only), `mypy src` (2 pre-existing
`review_burden_mart.py` only), `pytest -m "not live and not integration and not manual"` (only the 10
pre-existing phase-08 schema-lifecycle failures). Full CLI matrix green: `construction-agent validate`
4/4; phase-09 gates ok; operator-status `advisory_ready`; phase-09 + MCP no-writeback / no-raw pass;
approved-sources approved (1696 refs); source-linked has no `no_read_model` for the three families;
`llamaindex build` dry-run `indexed_family_count=8`; `--apply` applied (retrieval-local present);
reader-registry-parity / approved-read-model-manifest / read-model-vector-loader proofs + coverage
closeout all pass.
