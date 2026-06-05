# Phase 09 Prompt 26 — Project-Specific Retrieval Benchmarks + Coverage Reports (Evidence)

**Package:** 1.4.0-phase-09 · **Schema:** V38 (unchanged) · **Repo SHA at build:** `6c43844`
**Objective:** Scope the Prompt 25 deterministic/semantic/hybrid benchmark **per project** and pair each with a **per-project coverage report** — advisory (`assembles_final_answer=false`), read-only by default, fail-closed, metadata-only.

## What changed

- **New** `retrieval/project_benchmark.py` — `build_project_retrieval_benchmarks` /
  `build_project_retrieval_benchmarks_proof` (+ `ProjectRetrievalBenchmarkError`). Pure orchestration:
  per project it reuses `benchmark.build_retrieval_benchmark(project_key=P)` (Prompt 25) and the read-only
  `corpus_balance_mart.build_corpus_balance_mart(project_key=P)`; projects are enumerated from the
  deterministic `RetrievalBroker` corpus. No new retrieval logic.
- **New** contract `phase_09_project_retrieval_benchmark_contract.json` + seed; registered as
  `project_retrieval_benchmark_contract` (11th Phase-09 contract).
- **New** CLI `second-brain retrieval project-benchmark build | proof`
  (`retrieval_project_benchmark_app`, `_RETRIEVAL_PROJECT_BENCHMARK_GUARDRAILS`).
- **New** tests `tests/test_phase_09_project_retrieval_benchmark.py` (5 required paths + proof).
- **No migrator change** — per-project benchmark metrics reuse the existing V38
  `second_brain_retrieval_benchmark_runs` table; coverage reports are read-only evidence (never
  persisted). Schema stays 38, contract table count stays 190.

## Design (why it is safe)

- **Per project**: a benchmark (deterministic authoritative + advisory semantic + hybrid, from Prompt 25)
  paired with a coverage report (per-allowlisted-family `covered`/`empty`/`deferred_no_reader`, shares,
  coverage warnings). Raw/excluded families never appear (the mart iterates only
  `ALLOWLISTED_SOURCE_FAMILIES`).
- **Orchestration leaf**: `assembles_final_answer=false` and the `semantic_retrieval_bypassed_policy`
  guard stays 0 — semantic context never reaches an answer / Research Packet / Evaluation path.
- **Read-only by default**: `emit_receipt=False` persists nothing; per-project benchmark persistence
  flows through the reused Prompt-25 builder (project-distinct `bmk_<hash>` run ids). Coverage is always
  read-only. `project_key` is a non-sensitive config identifier emitted in plaintext (as the existing
  marts/snapshots do); no raw query/probe/content/source ref is created or stored.

## Operator DB outcome (pristine)

`project-benchmark build --json` → `status=built`, **1 project** enumerated, `read_only`, **no persist**.
The deterministic broker corpus enumerates one project on the operator DB; that project's approved-node
benchmark is honestly empty/blocked (no approved Obsidian/reviewed-memory outputs). Direct check:
`second_brain_retrieval_benchmark_runs` = **0 rows**, schema **38** — `operator_db_mutated=false`.

## Proof (temp DB)

`project-benchmark proof --json` → **`proof_passed=true`**: status `built`, **2 projects** (ALPHA/BETA
from the `_proof_db` fixture), `per_project_benchmarks_persisted=true`, `per_project_coverage_present=true`,
`rows_persisted_guard_clean=true`, `semantic_retrieval_bypassed_policy=0`, `assembles_final_answer=false`,
`read_only_default_no_persist=true`, `no_raw_emitted=true`, `coverage_excludes_raw_families=true`.
Sample coverage report: `validation-outputs-prompt-26/project-retrieval-coverage-report.json` (ALPHA/BETA,
each benchmark `built` + semantic available, 1 covered family, coverage incomplete).

## Validation matrix

| Check | Result |
|---|---|
| `compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | Success — 294 source files |
| `pytest -m "not live and not integration and not manual"` | 3194 passed, 0 failed |
| `construction-agent validate --json` | 4/4 (schema 38) |
| `data-quality table-inventory --json` | schema 38; contract 190; live 186; 0 unmapped live |
| `data-quality no-writeback-proof --json` | ok=true, proof_passed=true |
| `second-brain data-quality phase-08a-gates --json` | ok=true |
| `second-brain data-quality phase-08b-gates --json` | **exit 1 — PRE-EXISTING / ENVIRONMENTAL (not this change)** ¹ |
| `second-brain financial data-quality phase-08c-gates` | **SKIPPED** (mutates operator DB ~1,299 ledger rows/call) |
| `second-brain data-quality phase-08d-gates --json` | proof_passed=true, ok=true |
| `second-brain mcp no-raw-access --json` | proof_passed=true |
| `second-brain mcp no-writeback --json` | proof_passed=true |
| `second-brain retrieval project-benchmark build --json` | exit 0 — 1 project, read-only, no persist |
| `second-brain retrieval project-benchmark proof --json` | exit 0 — proof_passed=true (2 projects) |
| `test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof` | pass (in the full suite) |

¹ **`phase-08b-gates` is a pre-existing/environmental failure, not caused by this prompt.** It is an
`AssertionError` (`assert failed_count >= 1`) in `automation_executor.build_automation_execution_proof`
(`automation_executor.py:1485`) — automation code this prompt does not touch. It **reproduces on a
pristine checkout of clean HEAD `6c43844`** in an isolated git worktree, so it is independent of both this
prompt and the concurrent daily-brief working-tree changes. It passed in the Prompt-25 CLI matrix minutes
earlier, indicating shared operator Application-Support automation state drifted (the proof is not fully
temp-isolated; the full pytest suite passes because pytest fixtures redirect `PathPolicy` to a temp root).
Documented as pre-existing per operator decision.

## Concurrency note

During this session a parallel agent's uncommitted changes appeared in the same working tree (a different
**"Prompt 26 — Daily Brief Approved Source Population"**: `daily_brief/output.py`, `research/store.py`,
daily-brief tests, `docs/architecture/68`, and an untracked
`145-phase-09-prompt-26-daily-brief-approved-source-population.md`). To avoid entangling the two tasks,
this commit stages **only** the isolated project-benchmark retrieval files; the other agent's changes were
left untouched (not staged, not restored). This prompt's architecture record was renumbered **145 → 146**
to avoid the doc-number collision (the concurrent task owns 145).

## Deferred

Executing/scoring the eval set against the index (`eval_runs`); wiring semantic context into the default
`synthesize_answer` (A04 — must route via Research Packet / Evaluation if adopted); the `generated_outputs`
(research-packet) loader.
