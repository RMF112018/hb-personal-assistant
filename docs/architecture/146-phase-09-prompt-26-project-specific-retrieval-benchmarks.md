# 146 — Phase 09 Prompt 26: Project-Specific Retrieval Benchmarks + Coverage Reports

**Status:** Implementation — per-project deterministic/semantic/hybrid benchmarks paired with per-project coverage reports; advisory, read-only, fail-closed, metadata-only.
**Schema:** V38 (unchanged; reuses `second_brain_retrieval_benchmark_runs`). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `6c43844`, Prompt 25 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/26-project-specific-retrieval-benchmarks.md` (+ `.json`, `project-retrieval-benchmark-proof.{json,md}`, `project-retrieval-coverage-report.json`, `validation-outputs-prompt-26/`).
**Builds on:** records 134–144 (and 145, the concurrent daily-brief prompt); reuses the Prompt 25 benchmark (`retrieval/benchmark.py`, record 144), the corpus-balance coverage mart (`corpus_balance_mart.py`), the deterministic `RetrievalBroker` (record 134), and `_assert_no_raw`.

---

## 1. Purpose

Scope the global deterministic-vs-semantic-vs-hybrid benchmark (Prompt 25) **per project**, and pair each
project with a **coverage report** (which approved source families are present/empty/deferred). Answers,
per project: "is the retrieval corpus complete, and does semantic/hybrid add value over the deterministic
baseline?" It is an **orchestration leaf** — it assembles no answer and never routes semantic context
into an answer / Research Packet / Evaluation path.

## 2. Design

Pure orchestration over two shipped, tested builders — it adds no new retrieval logic.

### Project enumeration
`_enumerate_projects` reads the deterministic approved corpus once
(`RetrievalBroker.retrieve(project_key=None)`) and returns the distinct `RetrievalItem.project_key`s
(readers set them from `obsidian_index_entries` / `long_term_memory_items`). An explicit `--project`
scopes to one key; a requested key absent from the corpus is skipped with a hashed
`requested_project_absent:*` warning. The set is capped at `max_projects` (seed, 25) with a surfaced
`project_cap_applied:*` warning — no silent truncation.

### Per-project benchmark + coverage
For each project P:
- **Benchmark** — `build_retrieval_benchmark(db, project_key=P, …, emit_receipt=…)` (Prompt 25,
  unchanged). It gathers P's approved nodes, runs the deterministic baseline + advisory semantic per
  probe, derives a project-distinct `bmk_<hash>` / `eval_set_id`, and persists P's seven bucketed
  `benchmark_runs` rows **iff** `emit_receipt`.
- **Coverage** — `build_corpus_balance_mart(db, project_key=P)` (unchanged): per-allowlisted-family
  `coverage_status` (`covered`/`empty`/`deferred_no_reader`), `total_corpus_rows`, `dominant_family`,
  and coverage warnings (`no_read_model:…`, `empty_family:…`). **Read-only — never persisted** (the
  established `*-mart` convention). Raw/excluded families never appear (the mart iterates only
  `ALLOWLISTED_SOURCE_FAMILIES`).

A cross-project rollup reports `projects_with_semantic_available`, `projects_coverage_complete`, and
`projects_with_empty_families`.

### Read-only, fail-closed, no-bypass, metadata-only
`build_project_retrieval_benchmarks` defaults `emit_receipt=False` (persists nothing); persistence flows
only through the reused Prompt-25 builder per project. `assembles_final_answer=false` and the
`semantic_retrieval_bypassed_policy` guard stays 0. Fail-closed on missing policy / stale schema
(V38-gated). The summary carries no raw probe/query/content/source ref — only hashes, bands, counts,
plaintext `project_key`s (a non-sensitive config identifier, as the existing marts/snapshots emit), and
family names. **No migrator/schema change** (schema stays V38; contract table count stays 190).

## 3. Contract & seed

`phase_09_project_retrieval_benchmark_contract.json` (+ `.seed.yaml`): approved-outputs source families,
`benchmark_modes`, `coverage_statuses`, `max_projects`, project enumeration source, forbidden-emitted
fields (raw query/probe/content/source_ref/…), and global requirements (advisory-only / no-final-answer /
no-semantic-bypass; preserve review tier/confidence/source refs/freshness/coverage warnings; approved
outputs only; fail-closed). Registered as `project_retrieval_benchmark_contract` (11th Phase-09 contract).

## 4. CLI

`second-brain retrieval project-benchmark build [--project P] [--name NAME] | proof`. Unique Typer var
(`retrieval_project_benchmark_app`) / guardrails constant (`_RETRIEVAL_PROJECT_BENCHMARK_GUARDRAILS`) /
command names. `build` is read-only (no persist; on the operator DB — no projects — honestly `empty`);
`proof` runs the offline guard-clean proof (per-project benchmarks persisted + guard-clean, per-project
coverage present, read-only-default no-persist, unsafe families excluded from coverage).

## 5. Validation

`compileall`/`ruff`/`mypy` (294 files) clean; `pytest -m "not live and not integration and not manual"`
green (project-benchmark proof: ≥1 project enumerated from the ALPHA/BETA fixture; per-project
`benchmark_runs` rows persisted + guard-clean; coverage reports present + advisory; raw/excluded families
absent from coverage; `assembles_final_answer=false`; bypass guard 0; read-only default persists nothing).
Operator DB unmutated (`benchmark_runs` 0; schema 38; table-inventory 190 contract / 0 unmapped live).
Full matrix in the evidence bundle.

## 6. Deferred

Executing/scoring the eval set against the index (`eval_runs` + pass/fail); wiring semantic context into
the default `synthesize_answer` (A04 — must route via Research Packet / Evaluation if adopted); the
`generated_outputs` (research-packet) loader; memory-quality / consolidation review — later Phase 09
prompts.
