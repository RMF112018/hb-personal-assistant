# 166 — Phase 09 Addendum Prompt 03: Accepted Memory Pipeline Inclusion

**Status:** Implementation — integrated end-to-end proof that one accepted memory item flows through all seven Phase 09 retrieval stages; the wiring pre-existed, this adds the integration proofs + evidence + tests.
**Schema:** unchanged (V39; no migration). **Version:** 1.8.0-phase-09-addendum.
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/accepted-memory-loader-proof.{json,md}`, `accepted-memory-vector-coverage-proof.{json,md}`.
**Builds on:** records 136 (reviewed-memory loader), 135 (approved manifests), 137–139 (vector dry-run/apply), the read-model loader, no-raw-vector proof, and coverage-parity closeout; records 164–165 (candidate preview, acceptance).

---

## 1. Purpose

Wire accepted long-term memory through the full retrieval pipeline: deterministic reader → reviewed-
memory loader → approved-source manifest → vector node generation → vector dry-run → vector apply →
coverage-parity closeout. **Repo finding: the wiring already existed** — `accepted_long_term_memory` is
a first-class family on every plane (`readers.read_accepted_memory` in the reader registry,
`memory_loader.load_reviewed_memory_nodes`, the enabled `reviewed_memory` manifest category,
`vector_index._gather_approved_nodes` calling the reviewed-memory loader, and
`coverage_parity.build_coverage_parity_closeout`). It reported `deferred_empty` only because no
accepted memory existed. So this prompt adds the **integrated proof** that one accepted item flows
through every stage (and non-accepted memory is excluded), plus evidence and tests. **No pipeline code
change, no migration, no new contract** — every pipeline function already accepts `db_path`.

## 2. Design

New module `retrieval/accepted_memory_inclusion.py` orchestrates the existing functions over a
deterministic fixture (`SQLiteMigrator` + `memory.store.write_memory_item`):

- **`build_accepted_memory_loader_proof`** — seeds one accepted item + one each `pending_review` /
  `rejected` / `superseded` (note: `deferred` is a *candidate* decision — deferred candidates never
  become memory items, so exclusion is by construction). Asserts the accepted item appears in
  `read_accepted_memory` (family `accepted_long_term_memory`, only the accepted ref), in
  `load_reviewed_memory_nodes` / `build_reviewed_memory_loader_report` (`loaded_count==1`, `status=
  'loaded'`), and in `build_approved_source_manifest` (`reviewed_memory` `approved_count>=1`); the node
  is redacted + bounded (≤280), source-linked (`source_ref_count>=1`), carries `confidence_class` +
  `freshness_label`; non-accepted excluded everywhere. Writes `accepted-memory-loader-proof.{json,md}`.
- **`build_accepted_memory_vector_coverage_proof`** — seeds an apply-mode Obsidian fixture as the
  non-empty baseline, applies it (mock writer), then adds one accepted item (+ a non-accepted one) and
  re-runs the pipeline. Asserts: `accepted_long_term_memory` enters the vector **dry-run** plan
  (`per_family_node_count`) only after the item is added; **apply** (via `vector_index._mock_vector_
  writer`, the offline path used by the apply proof) includes it in `per_family_item_count` with
  `vectors_persisted_to_sqlite is False`; `build_no_raw_vector_index_proof` still passes; the
  **coverage-parity closeout** flips `memory_substrate_status` `deferred_empty→covered`, adds the family
  to `vector_indexed_families` (count +1: 1→2 in the fixture), keeps `coverage_parity_ok`/`closeout_ok`
  true (deferred families still listed — no readiness overstatement). A `live_baseline_note` records
  that the eight already-applied live families make this same +1 an **8→9** increase. Writes
  `accepted-memory-vector-coverage-proof.{json,md}`.

CLI: `second-brain retrieval accepted-memory-loader-proof` and
`second-brain retrieval accepted-memory-vector-coverage-proof` (`--evidence/--no-evidence`,
`--json/--no-json`; exit 0/3).

## 3. The 8→9 mechanism

`coverage_parity` derives `vector_indexed_families` from DISTINCT families across **applied** vector-
index receipts (`second_brain_retrieval_vector_index_items` JOIN `_runs WHERE status='applied'`). The
fixture proves the additive mechanism with a real N→N+1 (Obsidian baseline 1 → +memory 2); the live
baseline of eight eligible families therefore becomes nine. `memory_substrate_status` is `covered` when
`long_term_memory_items WHERE review_status='accepted'` has rows. `coverage_parity_ok` depends only on
reader-registry parity (all ten allowlisted families have readers); empty manifest/vector/memory
families are reported deferred, never as failures.

## 4. Existing proofs — confirmed, not changed

The per-stage proofs already seed accepted memory and pass unchanged
(`build_reviewed_memory_loader_proof`, `build_accepted_memory_seed_proof`,
`build_approved_source_manifest_proof`, `build_approved_read_model_manifest_proof`,
`build_read_model_vector_loader_proof`, `build_vector_index_dry_run_proof`,
`build_vector_index_apply_proof`, `build_no_raw_vector_index_proof`, `build_coverage_parity_closeout`).
Confirmed green via their regression test files.

## 5. Validation

`ruff`/`mypy` clean on the new module + CLI; `tests/test_phase_09_accepted_memory_inclusion.py` (11
tests) green plus the retrieval + memory regression suites. Pre-existing, unrelated phase-08b/c/d
schema-lifecycle and data-quality-gate failures remain out of scope.

## 6. Deferred

Populating the operator's live DB with accepted memory (an operator action via the Prompt-02 `memory
accept` workflow, not this proof); exercising vector apply with the real local embedding backend
(`retrieval-local`) instead of the mock writer.
