# 144 — Phase 09 Prompt 25: Deterministic vs Semantic Benchmark

**Status:** Implementation — comparative deterministic/semantic/hybrid retrieval benchmark; advisory, read-only, fail-closed, metadata-only.
**Schema:** V38 (unchanged; reuses `second_brain_retrieval_benchmark_runs`). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `28853e6`, Prompt 24 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/25-deterministic-vs-semantic-benchmark.md` (+ `.json`, `retrieval-benchmark-proof.{json,md}`, `validation-outputs-prompt-25/`).
**Builds on:** records 134–143; reuses the deterministic `RetrievalBroker` (broker), the advisory `_semantic_query` + `_latest_applied_vector_index_run` (hybrid_broker, record 135), `_gather_approved_nodes` (vector_index), `ALLOWLISTED_SOURCE_FAMILIES`/`EXCLUDED_FAMILIES` (policy), and `_assert_no_raw`.

---

## 1. Purpose

Answer "does the semantic/hybrid path add retrieval value over the deterministic baseline?" by
**benchmarking the three retrieval modes against each other** over the approved-outputs corpus and
emitting **comparative, bucketed, metadata-only metrics**. The benchmark is a measurement leaf — it
assembles no answer and never routes semantic context into an answer / Research Packet / Evaluation path.

## 2. Design

### Three modes, one corpus
- **Deterministic** — `RetrievalBroker.retrieve(...)`, the authoritative, query-free corpus baseline,
  computed once (identical for every probe).
- **Semantic** — one advisory `_semantic_query` per runtime probe over the applied vector index
  (floored at review tier 2, source-linked to `vector_index_items`, re-validated no-raw). Fail-closed:
  when the optional LlamaIndex SDK or an applied index is absent it degrades to a `blocked`
  `semantic_status`; the deterministic baseline is unaffected.
- **Hybrid** — deterministic + **net-new** advisory semantic. Because semantic items carry the *hashed*
  source ref (disjoint from the deterministic raw-ref space), every admitted semantic match is net-new
  in the merge — so the hybrid surface is `deterministic + semantic_max` and the `semantic_lift` metric
  measures the added advisory context.

### Runtime-only probes
`_build_probes` derives one probe per approved node from its already-redacted excerpt; a node is admitted
iff it carries a `source_ref`, a redacted excerpt, and an allowlisted (non-`EXCLUDED`) `source_family`.
The probe text is used **in-memory only** as the semantic query and is **never persisted or emitted**.
Probes are capped at `max_probes` (50) with a surfaced `probe_cap_applied:*` warning — no silent
truncation.

### Bucketed, metadata-only metrics
A run emits seven `(metric, mode)` rows — `result_count:{deterministic,semantic,hybrid}`,
`semantic_hit_rate:hybrid`, `semantic_lift:hybrid`, `tier_floor:semantic`, `semantic_status:hybrid` —
each a `(metric_name, metric_value_label)` band (`_count_band` / `_rate_band`). `persist_retrieval_benchmark`
writes them to `benchmark_runs` (`run_id = bmk_<hash>:<metric_slug>`, `eval_set_id = res_<hash>` for
linkage, `config_snapshot_id` = applied-index run id or `none`), all 23 `CHECK(=0)` guards 0. The status
is `built` (semantic available) / `blocked` (corpus present, semantic unavailable) / `empty` (no probes).

### Read-only, fail-closed, no-bypass
`build_retrieval_benchmark` defaults `emit_receipt=False` (persists nothing); receipt persistence is
exercised only in the proof on a temp DB. `assembles_final_answer=false` and the
`semantic_retrieval_bypassed_policy` guard stays 0. Fail-closed on missing policy or stale schema
(V38-gated).

## 3. Contract & seed

`phase_09_retrieval_benchmark_contract.json` (+ `.seed.yaml`): approved-outputs source families,
`benchmark_modes`, the seven `metric_names`, the `benchmark_run` column allowlist, status vocab
(`built`/`empty`/`blocked`), forbidden-emitted fields (raw query/probe/content/source_ref/…), `max_probes`,
and global requirements (advisory-only / no-final-answer / no-semantic-bypass; preserve review
tier/confidence/source refs/freshness; approved outputs only; fail-closed). Registered as
`retrieval_benchmark_contract`.

## 4. CLI

`second-brain retrieval benchmark build [--project] [--name NAME] | proof`. Unique Typer var
(`retrieval_benchmark_app`) / guardrails constant (`_RETRIEVAL_BENCHMARK_GUARDRAILS`) / command names.
`build` is read-only (no persist; on the operator DB it is honestly `empty`); `proof` runs the offline
guard-clean proof (applied-index path + blocked-semantic fail-closed path + unsafe-node exclusion).

## 5. Validation

`compileall`/`ruff`/`mypy` (293 files) clean; `pytest -m "not live and not integration and not manual"`
= 3180 passed, 0 failed. The benchmark proof passes (3 probes; all three modes compared; semantic
available + floored tier 2; guard-clean metadata-only `benchmark_runs` receipts; blocked-semantic
fail-closed path; unsafe nodes excluded; no raw emitted; `assembles_final_answer=false`; bypass guard 0).
A real `bge-small` smoke compared all three modes end-to-end (dim 384). Operator DB unmutated
(`benchmark_runs` 0; schema 38; table-inventory 190 contract / 0 unmapped live). Full matrix in the
evidence bundle.

## 6. Deferred

Executing/scoring the eval set against the index (`eval_runs` + pass/fail); wiring semantic context into
the default `synthesize_answer` (A04 — must route via Research Packet / Evaluation if adopted); the
`generated_outputs` (research-packet) loader; memory-quality / consolidation review — later Phase 09
prompts.
