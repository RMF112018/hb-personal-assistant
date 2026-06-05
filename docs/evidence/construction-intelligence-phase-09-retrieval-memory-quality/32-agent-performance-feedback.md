# Phase 09 Prompt 32 — Agent Performance and Feedback (Evidence)

**Package:** 1.4.0-phase-09 · **Schema:** V39 (live; reuses the reserved V38 `second_brain_agent_performance_feedback_runs` table) · **Repo SHA at build:** `abbb458`
**Objective:** Track per-agent repeated corrections, review burden, weak coverage, and emit advisory policy recommendations for operator awareness. Read-only, advisory — makes no determination.

## What changed

- **New** `construction/second_brain/agent_performance_feedback.py` — `assess_agent_performance` /
  `build_agent_performance_feedback` / `persist_agent_performance_feedback` /
  `build_agent_performance_feedback_proof` (+ `AgentPerformanceFeedbackError`). Reuses the Phase-08A
  agent registry (`agents.loader.load_agent_registry`), the **stable** Phase-08B
  `second_brain_agent_run_receipts` (review tiers), `second_brain_operator_feedback`
  (corrections, never raw `reason_redacted`), `corpus_balance_mart.build_corpus_balance_mart` (weak
  coverage), `financial_review_routing._assert_no_raw`, and the `eval_set.py` persister pattern.
- **New** contract `phase_09_agent_performance_feedback_contract.json` + seed; registered as
  `agent_performance_feedback_contract` (18th Phase-09 contract).
- **New** CLI `second-brain agent-performance build | proof` (sub-group `agent_performance_app`,
  `_AGENT_PERFORMANCE_FEEDBACK_GUARDRAILS`).
- **New** tests `tests/test_phase_09_agent_performance_feedback.py` (5 required paths + proof; 7 tests).
- **No migrator change, adds NO tables** — reuses the reserved V38
  `second_brain_agent_performance_feedback_runs` table (already classified; contract count stays 190).

## Design (why it is safe)

- **Per-agent aggregation (deterministic, metadata-only)** over the 9 registry agents:
  - **review_burden** — from `agent_run_receipts`: `run_count`, `tier3_count`, tier-3 share band.
  - **repeated_corrections** — from `operator_feedback` (`feedback_class IN ('correct','reject')`)
    attributed to the owning agent via the `target_kind` → agent map; count + band. Never emits
    `reason_redacted`.
  - **weak_coverage** — empty/deferred source families from the corpus-balance mart, attributed to the
    coverage owner (`retrieval_source_broker_agent`); count + band.
  - **policy_recommendation** — a deterministic, **advisory** recommendation code
    (`recommend_review_tier_increase` / `recommend_confidence_tuning` / `recommend_source_expansion` /
    `no_action`) derived from thresholds. Never applied.
- **Advisory — makes no determination**: `makes_determination=false`, `advisory_only=true`,
  `recommendations_advisory_only=true`. Recommendations are suggestions for the operator only.
- **Read-only, fail-closed, no raw**: `emit_receipt=False` persists nothing; reads receipts/feedback via
  `mode=ro` SQL; only counts, bucketed bands, agent names, metric names, and recommendation codes are
  emitted (statements/reasons SHA256-hashed or omitted — never raw). Persisted rows (on `emit_receipt`)
  are one `second_brain_agent_performance_feedback_runs` row per (agent, metric), all 23 guards = 0.

## Operator DB outcome (read-only)

`agent-performance build --json` → `status=built`, **9 agents**, 11 signals, `advisory_only=true`,
`makes_determination=false`, `read_only=true`, `receipt_emitted=false` (nothing persisted), schema **39**.
The operator DB is unmutated by this change (read-only default).

## Proof (temp DB)

`agent-performance proof --json` → **`proof_passed=true`**: seeds `agent_run_receipts` (incl. tier-3 runs
→ review burden) + `operator_feedback` (`correct`/`reject` on a `retrieval` target → corrections) for the
broker agent; asserts the four signal categories computed per agent
(`corrections_attributed`, `review_burden_computed`, `weak_coverage_computed`), an advisory
`policy_recommendation` emitted (`recommendation_emitted`, not a determination —
`makes_determination=false`), the per-(agent, metric) rows guard-clean + metadata-only
(`rows_persisted_guard_clean`), read-only default persists nothing (`read_only_default_no_persist`), and
no raw feedback reason emitted (`no_raw_emitted`; regex scan clean).

## Validation matrix

| Check | Result |
|---|---|
| `compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | **2 errors — both PRE-EXISTING in `review_burden_mart.py` (concurrent); my module is CLEAN** ¹ |
| `pytest -m "not live and not integration and not manual"` | **10 failed — all PRE-EXISTING `test_v{26,28,29,30,31,32,33,34,35,37}_table_classified_in_lifecycle_contract`; my 7 new tests pass** ² |
| `construction-agent validate --json` | exit 0 (schema 39) |
| `data-quality table-inventory --json` | schema 39; contract 190; **3 unmapped — all concurrent review_burden tables** ² |
| `data-quality no-writeback-proof --json` | exit 0 |
| `second-brain data-quality phase-08a-gates --json` | exit 0 |
| `second-brain data-quality phase-08b-gates --json` | exit 1 — pre-existing/environmental (`automation_executor.py:1485`), not this change |
| `second-brain financial data-quality phase-08c-gates` | **SKIPPED** (mutates operator DB ~1,299 ledger rows/call) |
| `second-brain data-quality phase-08d-gates --json` | exit 0 |
| `second-brain mcp no-raw-access --json` | exit 0 |
| `second-brain mcp no-writeback --json` | exit 0 |
| `second-brain agent-performance build --json` | exit 0 — built (9 agents), read-only, no persist |
| `second-brain agent-performance proof --json` | exit 0 — proof_passed=true |
| `test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof` | pass |

¹ ² **The 2 mypy errors, 10 pytest failures, and 3 unmapped tables are ALL pre-existing regressions from
the concurrent review_burden Phase-09 work (`3759a0a` / `abbb458`)**, which added
`second_brain_review_burden_runs` / `_clusters` / `_policy_evals` **without classifying them in the
lifecycle contract** (and with 2 type errors in `review_burden_mart.py`). The failing tests are
`test_v{26,28,29,30,31,32,33,34,35,37}_table_classified_in_lifecycle_contract`, which assert
`in_db_not_in_contract == []`. **None are caused by this change** — Prompt 32 adds no tables, touches no
classification contract, and the V38 feedback-runs table it reuses is already classified; its 7 new tests
all pass and `mypy` reports its module clean. These belong to the review_burden owner.

## Concurrency note

Built on a heavily concurrent working tree (HEAD `abbb458`, a concurrent review_burden follow-up). This
commit stages **only** the isolated agent-performance files; the `contracts.py` change is exactly one
added registry line (`agent_performance_feedback_contract`). No concurrent-agent src/tests were touched.

## Deferred

Wiring advisory recommendations into a unified operator review queue; applying a recommendation (operator
review → policy change) — a later prompt; trend/time-series of per-agent burden across runs.
