# Phase 09 Prompt 25 — Deterministic vs Semantic Benchmark (Evidence)

**Package:** 1.4.0-phase-09 · **Schema:** V38 (unchanged) · **Repo SHA at build:** `28853e6`
**Objective:** Benchmark deterministic vs semantic vs hybrid retrieval over the approved corpus — comparative, bucketed, **metadata-only** metrics. Advisory (`assembles_final_answer=false`), read-only by default, fail-closed.

## What changed

- **New** `retrieval/benchmark.py` — `build_retrieval_benchmark` / `persist_retrieval_benchmark` / `build_retrieval_benchmark_proof` (+ `RetrievalBenchmarkError`). Reuses the deterministic `RetrievalBroker.retrieve`, the advisory `hybrid_broker._semantic_query`, `_gather_approved_nodes`, `_latest_applied_vector_index_run`, `_assert_no_raw`, and the `ALLOWLISTED_SOURCE_FAMILIES`/`EXCLUDED_FAMILIES` policy.
- **New** contract `phase_09_retrieval_benchmark_contract.json` + seed `phase_09_retrieval_benchmark.seed.yaml`; registered as `retrieval_benchmark_contract` (10th Phase-09 contract).
- **New** CLI `second-brain retrieval benchmark build | proof` (`retrieval_benchmark_app`, `_RETRIEVAL_BENCHMARK_GUARDRAILS`).
- **New** tests `tests/test_phase_09_retrieval_benchmark.py` (5 required paths + proof).
- **No migrator change** — reuses the existing V38 `second_brain_retrieval_benchmark_runs` table; schema stays 38, contract table count stays 190.

## Design (why it is safe)

- **Deterministic is authoritative** (query-free corpus baseline, computed once). **Semantic is advisory** — one `_semantic_query` per runtime probe over the applied vector index, floored at review tier 2, source-linked, re-validated no-raw, and **fail-closed**: when the LlamaIndex SDK or an applied index is absent the semantic side degrades to a `blocked` `semantic_status` and the deterministic baseline is unaffected.
- **Probes are runtime-only.** `_build_probes` derives one probe per approved node from its already-redacted excerpt; the probe text is used in-memory only as a semantic query and is **never persisted or emitted**. Probes are capped at `max_probes` (50) with a surfaced `probe_cap_applied:*` warning — no silent truncation.
- **Metadata-only metrics.** Seven bucketed `(metric, mode)` rows — `result_count:{deterministic,semantic,hybrid}`, `semantic_hit_rate:hybrid`, `semantic_lift:hybrid`, `tier_floor:semantic`, `semantic_status:hybrid` — stored to `benchmark_runs` (`run_id`, `eval_set_id` linkage, `config_snapshot_id`, `metric_name`, `metric_value_label`), all 23 `CHECK(=0)` guards 0.
- **Measurement leaf.** `assembles_final_answer=false` and the `semantic_retrieval_bypassed_policy` guard stays 0; semantic context never reaches an answer / Research Packet / Evaluation path from here.
- **Read-only by default.** `emit_receipt=False` persists nothing; receipt persistence is exercised only in the proof on a temp DB.

## Operator DB outcome (pristine)

`benchmark build --json` → `status=empty`, 0 probes, 0 metric rows, `warnings=["no_approved_outputs"]` (no approved outputs → honestly empty; `emit_receipt` defaulted False → no persist). Direct check: `second_brain_retrieval_benchmark_runs` = **0 rows**, schema **38** — `operator_db_mutated=false`.

## Proof (temp DB)

`benchmark proof --json` → **`proof_passed=true`**: status `built`, 3 probes, **7** metric rows, `all_three_modes_compared=true`, `semantic_available=true`, `semantic_floored_tier_2=true`, `assembles_final_answer=false`, `rows_persisted_guard_clean=true`, `semantic_retrieval_bypassed_policy=0`, `no_raw_emitted=true`, `semantic_blocked_path_status=blocked` (corpus present but no applied index → fail-closed), `unsafe_node_excluded=true`.

Real-model smoke (`validation-outputs-prompt-25/real-huggingface-benchmark-smoke.json`): the real LlamaIndex + HuggingFace `bge-small` pipeline embedded dim-384 vectors and the benchmark compared all three modes (status `built`, semantic `available`, 7 metric rows).

## Validation matrix

| Check | Result |
|---|---|
| `compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | Success — 293 source files |
| `pytest -m "not live and not integration and not manual"` | 3180 passed, 0 failed |
| `construction-agent validate --json` | 4/4 (schema 38) |
| `data-quality table-inventory --json` | schema 38; contract 190; live 186; 0 unmapped live (`in_db_not_in_contract=[]`) |
| `data-quality no-writeback-proof --json` | ok=true, proof_passed=true |
| `second-brain data-quality phase-08a-gates --json` | ok=true, readiness_overstated=false |
| `second-brain data-quality phase-08b-gates --json` | ok=true, readiness_overstated=false |
| `second-brain financial data-quality phase-08c-gates` | **SKIPPED** (mutates operator DB ~1,299 ledger rows/call) |
| `second-brain data-quality phase-08d-gates --json` | proof_passed=true, ok=true |
| `second-brain mcp no-raw-access --json` | proof_passed=true |
| `second-brain mcp no-writeback --json` | proof_passed=true |
| `second-brain retrieval benchmark build --json` | exit 0 — operator DB empty, no persist |
| `second-brain retrieval benchmark proof --json` | exit 0 — proof_passed=true |
| `test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof` | pass |

Captured stdout/JSON for every command is under `validation-outputs-prompt-25/`.

## Deferred

Executing/scoring the eval set against the index (`eval_runs` + pass/fail); wiring semantic context into the default `synthesize_answer` (A04 — must route via Research Packet / Evaluation if adopted); the `generated_outputs` (research-packet) loader.
