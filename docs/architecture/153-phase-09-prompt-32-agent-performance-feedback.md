# 153 — Phase 09 Prompt 32: Agent Performance and Feedback

**Status:** Implementation — read-only, advisory per-agent performance tracker; aggregates repeated corrections, review burden, weak coverage; emits advisory policy recommendations; fail-closed, metadata-only, no determination.
**Schema:** V39 (live; reuses the reserved `second_brain_agent_performance_feedback_runs` table added at V38). **Version:** 1.4.0-phase-09. **HEAD (audited):** `abbb458` (a concurrent review-burden follow-up).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/32-agent-performance-feedback.md` (+ `.json`, `agent-performance-feedback-proof.{json,md}`, `validation-outputs-prompt-32/`).
**Builds on:** records 134–152; reuses the Phase-08A agent registry (`agents.loader.load_agent_registry`), the STABLE Phase-08B `second_brain_agent_run_receipts`, `second_brain_operator_feedback`, `corpus_balance_mart.build_corpus_balance_mart`, the `eval_set.py` persister pattern, and `_assert_no_raw`.

---

## 1. Purpose

Give the operator a single **advisory** read on how each Phase-08A agent is performing, aggregating four
signal categories per agent:

- **repeated_corrections** — operator feedback of class `correct`/`reject`, attributed to the owning agent.
- **review_burden** — the agent's run review tiers (tier-3 share = high burden).
- **weak_coverage** — empty/deferred source families, attributed to the retrieval coverage owner.
- **policy_recommendation** — a deterministic, advisory recommendation code derived from thresholds.

It **makes no determination**: recommendations are suggestions for operator awareness only, never applied.
This complements the per-surface quality signals (claim checks, hallucination risk, memory review) with a
per-*agent* rollup.

## 2. Design

### Pure assessor (deterministic, metadata-only)
`assess_agent_performance(receipts, feedback, coverage, *, agents, seed)` computes, per registry agent:

- **review_burden** — from `agent_run_receipts`: `run_count`, `tier3_count`, and a tier-3 share band.
- **repeated_corrections** — from `operator_feedback` filtered to `correction_feedback_classes`
  (`correct`/`reject`), attributed to the owning agent via the `target_kind` → agent map; count + band.
  A correction on an unmapped `target_kind` counts to no agent (no crash). Never emits `reason_redacted`.
- **weak_coverage** — empty/deferred source families from the corpus-balance mart, attributed to the
  `coverage_owner_agent` (`retrieval_source_broker_agent`); count + band (0 for other agents).
- **policy_recommendation** — a deterministic advisory code: `recommend_review_tier_increase` (corrections
  ≥ `high_corrections_count`), `recommend_confidence_tuning` (tier-3 share ≥ `high_tier3_share`),
  `recommend_source_expansion` (weak coverage > 0), else `no_action`.

Returns per-agent signal records (counts + bucketed bands + recommendation codes) + a `signal_count` total
+ a `status` (`built`/`empty`). Only counts, bands, agent names, metric names, and recommendation codes —
no raw feedback reason text.

### Read-only builder + metadata-only persistence
`build_agent_performance_feedback(db_path=None, *, project_key=None, emit_receipt=False)` runs
`_schema_ready` (V38 + the feedback-runs table) and loads the contract/seed (all fail-closed), reads
receipts + feedback via `mode=ro` SQL and coverage via `build_corpus_balance_mart`, enumerates the 9
registry agents, calls the assessor, derives `run_id`, and returns a metadata-only summary
(`makes_determination=false`, `advisory_only=true`, `recommendations_advisory_only=true`, `read_only`,
policy/contract versions). `emit_receipt=False` by default (persists nothing).
`persist_agent_performance_feedback` writes one `second_brain_agent_performance_feedback_runs` row per
(agent, metric) — `agent_name`, `signal_count`, `metric_name`, `metric_value_label`, `status` — with the
PK `run_id` sharing the logical-run prefix (`<run_id>:<agent_hash>:<metric>`) so a run groups its rows; all
23 `CHECK(=0)` guards 0. **No migrator change**; reuses the already-classified reserved V38 table, so the
contract table count stays 190.

### Advisory, fail-closed, no raw
The surface makes **no determination** — recommendations are advisory suggestions only. Fail-closed on
missing policy/contract or stale (pre-V38) schema. No raw feedback reason / prompt / response is persisted
or emitted; `_assert_no_raw` + a regex scan in the proof enforce this.

## 3. Contract, seed, CLI

- Contract `phase_09_agent_performance_feedback_contract.json` (registered as
  `agent_performance_feedback_contract`, the 18th Phase-09 contract): `signal_categories`,
  `recommendation_codes`, `target_kind_to_agent`, `correction_feedback_classes`, `status_values`, the run
  column allowlist, `forbidden_emitted_fields`, `global_requirements`.
- Seed `phase_09_agent_performance_feedback.seed.yaml`: `high_corrections_count` (3),
  `high_tier3_share` (0.50), `correction_feedback_classes`, the `target_kind_to_agent` map,
  `coverage_owner_agent`.
- CLI `second-brain agent-performance build | proof` (sub-group `agent_performance_app`,
  `_AGENT_PERFORMANCE_FEEDBACK_GUARDRAILS`, `_emit_08c`, exit 0/3).

## 4. Proof

`build_agent_performance_feedback_proof` seeds a temp migrated DB with `agent_run_receipts` (incl. tier-3
runs) + `operator_feedback` (`correct`/`reject` on a `retrieval` target) for the broker agent, runs
`emit_receipt=True`, and asserts: the four signal categories computed; an advisory `policy_recommendation`
emitted (not a determination — `makes_determination=false`); the per-(agent, metric) rows guard-clean +
metadata-only; read-only default persists nothing; no raw feedback reason emitted (regex scan). Writes
`agent-performance-feedback-proof.{json,md}`. **`proof_passed=true`.**

## 5. Validation & concurrency

Full matrix in the evidence bundle. My module is `ruff`/`mypy`-clean; its 7 new tests pass; `build` reads
the operator DB read-only (9 agents, no persist); `proof_passed=true`; table-inventory stays 190 contract.
The 2 mypy errors, 10 `test_v*_table_classified_in_lifecycle_contract` failures, and 3 unmapped tables are
**pre-existing regressions from the concurrent review_burden Phase-09 work** (`3759a0a`/`abbb458`) — not
this change (Prompt 32 adds no tables and touches no classification contract). `phase-08b-gates` exit 1 is
the pre-existing/environmental `automation_executor.py:1485` failure. This commit stages only the isolated
agent-performance files; the `contracts.py` change is exactly one added registry line.

## 6. Deferred

- Wiring advisory recommendations into a unified operator review queue.
- Applying a recommendation (operator review → policy change) — a later prompt.
- Trend/time-series of per-agent burden across runs.
