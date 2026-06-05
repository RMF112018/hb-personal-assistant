# Phase 09 Prompt 29 — Hallucination Risk Checks (Evidence)

**Package:** 1.4.0-phase-09 · **Schema:** V38 (unchanged) · **Repo SHA at build:** `e4c24b6`
**Objective:** Measure hallucination risk and overconfidence indicators over the deterministic retrieval corpus — a read-only advisory measurement (how risky the corpus is to present as fact). Makes no determination and blocks nothing.

## What changed

- **New** `retrieval/hallucination_risk.py` — `assess_hallucination_risk` /
  `build_hallucination_risk_checks` / `build_hallucination_risk_checks_proof`
  (+ `HallucinationRiskError`). Reuses Prompt 28's `detect_and_route_claims` (fabrication signal), the
  deterministic `RetrievalBroker` + `RetrievalEnvelope` (degradation / coverage / stale / conflict + tier
  distribution), and `EXCLUDED_FAMILIES`.
- **New** contract `phase_09_hallucination_risk_checks_contract.json` + seed; registered as
  `hallucination_risk_checks_contract` (14th Phase-09 contract).
- **New** CLI `second-brain retrieval hallucination-risk build | proof`
  (`retrieval_hallucination_risk_app`, `_RETRIEVAL_HALLUCINATION_RISK_GUARDRAILS`).
- **New** tests `tests/test_phase_09_hallucination_risk_checks.py` (5 required paths + proof).
- **No migrator change, no DB writes** — read-only advisory measurement (no dedicated risk table exists or
  is reserved in V38). Schema stays 38, contract table count stays 190.

## Design (why it is safe)

- **Hallucination-risk indicators**: unsupported claims (fabrication, via the reused detector), tier-3
  items presented as fact, stale/conflict items, coverage gaps, degradation mode.
- **Overconfidence indicators**: high confidence on weakly-grounded items (tier-3 / unsupported /
  stale-or-conflict); `high_confidence_tier3` mismatch count; confidence distribution.
- **Deterministic risk band** (low/medium/high) from these, with an `indicators` list of firing signals;
  rates emitted as **bucketed bands** (never raw floats).
- **Advisory measurement**: `assembles_final_answer=false`, `makes_determination=false`,
  `blocks_nothing=true`. It **persists nothing** (no DB writes). Metadata-only — counts, bands,
  distributions, family names, indicator flags; no raw content/source ref.

## Operator DB outcome (real result; pristine)

`hallucination-risk build --json` → `status=built`, **408 claims**, **`risk_band=medium`**,
`indicators=[coverage_gap, degradation]`, **0 overconfident**, **0 unsupported**, `read_only`. The operator
corpus is well source-grounded (no fabrication / no overconfidence — consistent with Prompt 28's 0
unsupported), but a coverage gap and a degraded retrieval mode fire → an honest, nuanced **medium** risk.
The build performs **no DB writes** — `operator_db_mutated=false`, schema **38**.

## Proof (synthetic)

`hallucination-risk proof --json` → **`proof_passed=true`**: on a synthetic corpus (a clean supported
tier-1 high-confidence item; an overconfident high-confidence tier-3 item; an unsupported item; a
conflict-flagged item, under a degraded + coverage-gapped envelope), `risk_band=high`, `unsupported_count=1`,
`overconfident_count=1`, the fabrication + overconfidence indicators fire, `makes_determination=false`,
`assembles_final_answer=false`, `build_path_no_db_writes=true`, `no_raw_emitted=true`.

## Validation matrix

| Check | Result |
|---|---|
| `compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | Success — 297 source files |
| `pytest -m "not live and not integration and not manual"` | 3220 passed, 0 failed |
| `construction-agent validate --json` | 4/4 (schema 38) |
| `data-quality table-inventory --json` | schema 38; contract 190; 0 unmapped live |
| `data-quality no-writeback-proof --json` | ok=true, proof_passed=true |
| `second-brain data-quality phase-08a-gates --json` | ok=true |
| `second-brain data-quality phase-08b-gates --json` | **exit 1 — PRE-EXISTING / ENVIRONMENTAL (not this change)** ¹ |
| `second-brain financial data-quality phase-08c-gates` | **SKIPPED** (mutates operator DB ~1,299 ledger rows/call) |
| `second-brain data-quality phase-08d-gates --json` | proof_passed=true, ok=true |
| `second-brain mcp no-raw-access --json` | proof_passed=true |
| `second-brain mcp no-writeback --json` | proof_passed=true |
| `second-brain retrieval hallucination-risk build --json` | exit 0 — 408 claims, risk_band=medium, read-only, no writes |
| `second-brain retrieval hallucination-risk proof --json` | exit 0 — proof_passed=true |
| `test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof` | pass (in the full suite) |

¹ **`phase-08b-gates` is a pre-existing/environmental failure, not caused by this prompt** (no automation
code touched). It is an `AssertionError` (`assert failed_count >= 1`) in
`automation_executor.build_automation_execution_proof` (`automation_executor.py:1485`) that **reproduces
on a pristine checkout of clean HEAD `6c43844`** in an isolated git worktree (verified in Prompt 26) —
operator Application-Support automation-state drift; the proof is not fully temp-isolated. The full pytest
suite passes (fixtures redirect `PathPolicy` to a temp root).

## Deferred

Rolling the risk band into the synthesis evaluation gate (A05); executing/scoring the eval set against the
index (`eval_runs`); wiring semantic context into the default `synthesize_answer` (A04).
