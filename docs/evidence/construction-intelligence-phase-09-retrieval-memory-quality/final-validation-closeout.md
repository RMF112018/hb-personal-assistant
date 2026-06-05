# Phase 09 — Final Validation Closeout (Prompt 39)

**Date:** 2026-06-05 · **Baseline HEAD:** `eac150b8` (concurrent multi-agent `main`; this closeout
commit follows) · **Package Manifest:**
`HB_Construction_Intelligence_Phase_09_Retrieval_Memory_Quality_Implementation_Package/00_PACKAGE_MANIFEST.md`
v1.4.0-phase-09-planning · **Schema:** V39

Final validation closeout for Phase 09 (Retrieval / Memory / Quality). This prompt **operationalizes
the semantic-retrieval substrate against the live operator DB** — building a real local vector index
over the approved corpus and proving working semantic retrieval — then records the full validation
matrix, confirms the no-raw / no-writeback guard proofs still pass **after** the live mutation, and
closes the phase **honestly**: the retrieval substrate is operational; the advisory run-record and
memory surfaces remain explicitly deferred. **Repository truth is authoritative; readiness is not
overstated.**

> **Concurrency reconciliation.** Work spanned concurrent `main` commits `f4a5c916` → `eac150b8`
> (a concurrent agent's **Prompt 40**, "consolidate Phase 09 readiness reporting", landed mid-flight
> and modified `phase_09_gates.py` / `phase_09_operator_status.py` / `phase_09_schema.py` / the
> operator-status seed / `cli/second_brain.py` — not README.md or this runbook). After `eac150b8`
> became HEAD, the gate/operator-status/validate/table-inventory numbers below were **re-verified** and
> are unchanged: schema **V39**, gates **14 pass / 9 deferred / 0 fail_blocking**, operator-status
> `advisory_ready`, table-inventory 190/189; the Phase-09 gate + operator-status tests pass under
> Prompt 40's code. The `pytest` tally was captured at `f4a5c916` (pre-Prompt-40); its 12 failures are
> the same pre-existing categories.

> **Toolchain note.** The Phase-09 retrieval surfaces require the optional `retrieval-local`
> dependencies (`llama-index-core`, `llama-index-embeddings-huggingface`, `sentence_transformers`,
> `torch`), which are installed only under `.venv/bin/python3.12`. The `hb-assistant` console script
> targets `.venv/bin/python` (an empty Python 3.14) and reports those deps absent. Every
> operationalization and matrix command below was run via `.venv/bin/python3.12 -m hb_assistant.cli.main`.

## Operationalization (new in Prompt 39 — live operator DB)

The operator authorized building a **real** vector index against the live operator DB. The approved
corpus already held indexable, source-linked content (1 apply-mode Obsidian manifest → 5 entries, 7
applied daily-briefs, 1 approved-source-manifest row); only the vector index had never been built.

- **`second-brain retrieval llamaindex build --apply`** → `status=applied`,
  `run_id=vir_apply_537b5e90de1c3ecded10e95eed04136a`. Embedded **8 approved nodes**
  (`approved_obsidian_generated_outputs`=1, `generated_outputs`=7; 0 rejected) with genuine
  **384-dim BAAI/bge-small-en-v1.5** local embeddings. Vectors written to the Application Support
  filesystem (`retrieval/vector_store/vir_apply_…/`), **never to SQLite**; metadata-only receipts
  persisted: `second_brain_retrieval_vector_index_runs`=1, `…_vector_index_items`=8.
  `no_raw_attested=true`, `vectors_persisted_to_sqlite=false`. (First run performed the one-time
  HuggingFace model download; all embedding computation is local.)
- **`second-brain retrieval hybrid proof`** → `proof_passed=true`, `semantic_count=3`,
  `semantic_source_linked=true`, `deterministic_authoritative=true`, `assembles_final_answer=false`,
  `raw_query_not_persisted=true`, `semantic_retrieval_bypassed_policy=0` — the semantic path is
  **proven operational** over the applied index, guard-clean.
- **`second-brain retrieval hybrid search "<approved-topic query>"`** runs a real merged retrieval
  (`result_count=408`, all deterministic-authoritative; advisory semantic admitted only as
  non-duplicate of deterministic, so net semantic admission was 0 for this query — an honest runtime
  outcome, not a failure). `assembles_final_answer=false`; only the query hash is recorded.

## Validation matrix (run after the live mutation)

| # | Command | Result |
| --- | --- | --- |
| 1 | `python -m compileall src tests` | **pass** (exit 0) |
| 2 | `ruff check .` | **pre-existing** (exit 1) — 3× B008 in `cli/procore.py` (696/1074/1715); no code files changed this prompt |
| 3 | `mypy src` | **pre-existing** (exit 1) — 2× `review_burden_mart.py` (169/171); 308 files checked (concurrent agent's) |
| 4 | `pytest -m "not live and not integration and not manual"` | **3279 passed / 12 failed / 0 skipped** (3291 collected); all 12 pre-existing/not-mine (see below) |
| 5 | `construction-agent validate --json` | **pass** (exit 0) — 4/4, schema **V39** |
| 6 | `construction-agent data-quality table-inventory --json` | **pass** (exit 0) — 190 contract / 189 live, schema V39 |
| 7 | `construction-agent data-quality no-writeback-proof --json` | **pass** (exit 0) |
| 8 | `second-brain data-quality phase-08a-gates --json` | **pass** (exit 0, ok=true, readiness_overstated=false) |
| 9 | `second-brain data-quality phase-08b-gates --json` | **pre-existing** (exit 1) — `automation_executor.py:1485` AssertionError |
| 10 | `second-brain financial data-quality phase-08c-gates --json` | **intentionally skipped** — mutates operator DB; out of scope |
| 11 | `second-brain data-quality phase-08d-gates --json` | **pass** (exit 0, proof_passed=true, readiness_overstated=false) |
| 12 | `second-brain mcp no-raw-access --json` | **pass** (exit 0, proof_passed=true) |
| 13 | `second-brain mcp no-writeback --json` | **pass** (exit 0, proof_passed=true) |
| 14 | `second-brain data-quality phase-09-no-writeback-proof --json` | **pass** (exit 0, proof_passed=true) |
| 15 | `second-brain retrieval no-raw-vector-index-proof --json` | **pass** (exit 0, proof_passed=true) — 6/6 gates, 0 findings, 464 evidence files, after the real index build |
| 16 | `second-brain data-quality phase-09-gates --json` | **pass** (exit 0, ok=true) — 14 pass / 9 deferred / 0 fail_blocking |
| 17 | `second-brain data-quality phase-09-operator-status --json` | **pass** (exit 0) — `advisory_ready`, readiness_overstated=false |

(The package matrix lists commands 11–13 under a `second-brain mcp data-quality …` path; the
registered surfaces are `second-brain data-quality phase-08d-gates` and `second-brain mcp
no-raw-access` / `mcp no-writeback`, mirroring the 08C/08D closeout path notes.)

### Pre-existing test failures (none introduced by this prompt — 0 test files added)

- **10× `test_v{26,28,29,30,31,32,33,34,35,37}_*_classified_in_lifecycle_contract`** — fail because
  3 unmapped `second_brain_review_burden_*` tables (`…_clusters`, `…_runs`, …) are not yet classified
  in the lifecycle contract. Owned by the concurrent review-burden agent.
- **`test_phase_09_embedding_policy::test_normal_path`** (`assert 8 == 7`) — a concurrent change
  raised `embeddable_family_count` to 8 without updating the test. Deterministic, pre-existing.
- **`test_phase_09_llamaindex_config::test_status_does_not_mutate_db_and_report_clean`** — **passes in
  isolation**; its full-suite failure is collection-order pollution from a concurrent agent's test.
  That it passes in isolation *after* this prompt's live `--apply` build confirms the build did not
  break the no-mutation contract.

## Phase 09 data-quality gate status (`phase-09-gates-proof` / `B-phase-09-gates.json`)

- `ok`: **true** · `proof_passed`: **true** · `readiness_overstated`: **false**
- `status_counts`: **14 pass · 0 warning · 0 fail_blocking · 9 deferred_not_blocking**
- **Moved this prompt:** `vector_index` (deferred → **pass**) via the real `--apply` build, joining the
  already-passing `approved_source_manifest`.
- **Pass (14):** `phase_09_schema_present`, `phase_09_guard_columns_clean`, `no_raw_vector_content`,
  `no_external_writeback_posture`, `no_semantic_retrieval_bypass`, `gates_contract_loaded`,
  `lifecycle_contract_loaded`, `embedding_vector_policy`, `approved_source_manifest`, `vector_index`,
  `metadata_filter`, `context_budget_optimization`, `hallucination_risk_checks`,
  `no_raw_vector_index_proof`.
- **Deferred_not_blocking (9), honestly:**
  - **7 advisory run-record surfaces** — `llamaindex_config`, `hybrid_retrieval`, `retrieval_eval_set`,
    `retrieval_benchmark`, `unsupported_claim_checks`, `agent_performance_feedback`,
    `source_linked_retrieval_proof`. Every Phase-09 retrieval CLI command is documented and built to
    **persist nothing to the operator DB** (proofs run against a throwaway temp DB); their run-record
    tables are populated only by internal `persist_*` APIs that no CLI exposes. These were **not**
    force-persisted via internal APIs — doing so would violate the read-only design contract those
    surfaces advertise.
  - **2 memory surfaces** — `memory_quality_review`, `memory_consolidation_preview`. Deferred because
    `long_term_memory_items`=0 and 0 accepted research packets; these gates cannot truthfully pass
    without operator-reviewed memory, which was not fabricated.

## Readiness honesty

Readiness is not overstated. The substrate is genuinely operational (real index built; semantic
retrieval proven `proof_passed=true` with `semantic_count=3`, source-linked), so `vector_index` is
truthfully `pass`. The remaining 9 gates are honestly `deferred_not_blocking` — 7 because the advisory
CLI persists nothing to the live DB by design, 2 because no operator-reviewed memory exists yet —
rather than reported as pass. `phase-09-operator-status` is `advisory_ready` (not "ready"),
`readiness_overstated=false`.

## Guard honesty (attested, post-mutation)

All guard proofs pass **after** the live operationalization: `no-raw-vector-index-proof`
(`proof_passed=true`, 6/6 gates, 0 findings across the DB + 464 evidence files),
`phase-09-no-writeback-proof`, `mcp no-raw-access`, `mcp no-writeback`, and the construction-agent
`no-writeback-proof` all `proof_passed=true`. No raw vector content / raw prompt/response / token /
signed-or-download URL / PEM is persisted; vectors live on the Application Support filesystem, never in
SQLite; only metadata-only receipts are written; no Graph/Procore/email/calendar/source-system
writeback; advisory only — no final determinations; deterministic retrieval remains the authoritative
source of truth and semantic results are floored to review tier 2.

## Stop conditions (checked — none tripped)

No raw-content persistence; no writeback; no-raw/no-writeback proofs present and passing; only the
approved manifest's loader nodes were embedded (0 rejected — no unapproved content indexed); semantic
retrieval is advisory and does not bypass Research Packet / Evaluation (`assembles_final_answer=false`,
deterministic authoritative).

## Evidence target audit (Phase 09 bundle)

`docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/`: the per-prompt bundles
(`00-*`…`38-*`), the canonical proof companions (`no-raw-vector-index-proof`, `hybrid-retrieval-proof`,
`source-linked-retrieval-proof`, `phase-09-gates-proof`, `phase-09-no-writeback-proof`,
`phase-09-operator-status`, retrieval/memory/agent proofs), the vector-index apply/dry-run proofs, and
**new in this prompt**: `39-final-validation-closeout.{json,md}`, `final-validation-closeout.md`, and
`validation-outputs-prompt-39/` (compileall, ruff, mypy, pytest, `C5`–`C15` gate/proof JSONs, the
`A1`–`A3` operationalization captures, and the `B-*` gates/operator-status snapshots).

## Closeout decision

**Phase 09 (Retrieval / Memory / Quality) — CLOSED; retrieval substrate operational, memory substrate
deferred.** A real local vector index is built and persisted over the approved corpus; semantic
retrieval is proven functional and guard-clean; the `vector_index` gate is `pass`; the full validation
matrix was re-run after the live mutation with only documented pre-existing failures; every no-raw /
no-writeback guard proof passes; `readiness_overstated=false`. The advisory run-record surfaces (no
live-persist CLI by design) and the memory surfaces (no accepted content) remain explicitly deferred
and are **not** overstated. The README phase ledger is flipped to Closed only now that validation
passes.

## Handoff to future

- **Memory substrate:** `memory_quality_review` / `memory_consolidation_preview` flip to pass once the
  operator reviews/accepts long-term memory (`long_term_memory_items` currently 0).
- **Advisory run-record tables:** `hybrid_query_runs` / `eval_sets` / `benchmark_runs` /
  `unsupported_claim_checks` / `agent_performance_feedback_runs` / `source_linked_proof_runs` /
  `llamaindex_config_snapshots` populate when a future automation layer wires the internal `persist_*`
  APIs; the read-only CLI deliberately persists nothing to the operator DB.
- **Carry-forward (unchanged):** 08C's deferred-external Procore forecast dependency.
- **Out of scope:** `phase-08c-gates` (operator-DB mutation); remote embedding providers
  (deferred/policy-gated); fixing concurrent agents' pre-existing regressions (review-burden
  lifecycle/mypy, `cli/procore.py` B008, `phase-08b` AssertionError, `embedding_policy` 8≠7).
