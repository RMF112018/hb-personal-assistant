# 149 — Phase 09 Prompt 29: Hallucination Risk Checks

**Status:** Implementation — read-only advisory measurement of hallucination-risk + overconfidence indicators; fail-closed, metadata-only, no determination.
**Schema:** V38 (unchanged; no table — read-only, no DB writes). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `e4c24b6`, Prompt 28 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/29-hallucination-risk-checks.md` (+ `.json`, `hallucination-risk-checks-proof.{json,md}`, `validation-outputs-prompt-29/`).
**Builds on:** records 134–148; reuses Prompt 28's `detect_and_route_claims` (`retrieval/unsupported_claim_checks.py`, record 148), the deterministic `RetrievalBroker` + `RetrievalEnvelope` (broker.py / models.py), `EXCLUDED_FAMILIES` (`retrieval/policy`), and `_assert_no_raw`.

---

## 1. Purpose

Measure **hallucination risk and overconfidence indicators** over the deterministic retrieval corpus — how
risky the corpus is to present as fact — for human awareness. It **makes no determination and blocks
nothing**; it scores risk signals and bands them. This complements Prompt 28 (which detects + routes
unsupported claims) by aggregating fabrication / ungrounded / overconfident signals into a single
advisory risk band.

## 2. Design

### Read-only advisory measurement
No dedicated risk table exists in V38 and none is reserved, so this surface **persists nothing** (no DB
writes) — the `context_budget` / `*-mart` convention. `assess_hallucination_risk(envelope)` is a pure
function; `build_hallucination_risk_checks` gathers the corpus from
`RetrievalBroker.retrieve(emit_receipt=False)` and returns the assessment. **No migrator change.**

### Hallucination-risk indicators
- **unsupported claims** (fabrication): `unsupported_count` via the reused `detect_and_route_claims` (a
  claim is supported iff it has a `source_ref` + an allowlisted non-`EXCLUDED` `source_family`).
- **tier-3 presented as fact**: `tier3_share` (mandatory-review items).
- **stale / conflict**: items carrying `stale_unknown_flags` / `conflict_flags`.
- **coverage gap**: the envelope's `coverage_warnings`.
- **degradation**: the broker `degradation_mode` (`none`/`narrow_claims`/`blocked`).

### Overconfidence indicators
- **overconfident_count**: items with `confidence_class == "high"` that are also tier-3 OR unsupported OR
  stale/conflict-flagged (high confidence on a weakly-grounded item).
- **high_confidence_tier3_count**: the confidence/tier mismatch.
- **confidence_distribution**.

### Deterministic risk band
`high` if any unsupported claim OR `degradation==blocked` OR overconfidence-rate > the seed threshold;
`medium` if any overconfidence OR tier3-share > threshold OR stale/conflict present OR
`degradation==narrow_claims` OR a coverage gap; else `low`. An `indicators` list names the firing signals.
All rates are emitted as **bucketed bands** (never raw floats) alongside counts; metadata-only — no raw
content/source ref (only family names + flags). `assembles_final_answer` and `makes_determination` are
always False.

## 3. Contract & seed

`phase_09_hallucination_risk_checks_contract.json` (+ `.seed.yaml`): risk bands, indicator names,
forbidden-emitted fields (content/excerpt/source_ref/raw/…), and global requirements (advisory-only /
no-final-answer / no-determination / no-blocking; preserve review tier/confidence/source refs/freshness/
coverage warnings; fail-closed). The seed carries the deterministic risk-band thresholds. Registered as
`hallucination_risk_checks_contract` (14th Phase-09 contract).

## 4. CLI

`second-brain retrieval hallucination-risk build [--project] | proof`. Unique Typer var
(`retrieval_hallucination_risk_app`) / guardrails constant (`_RETRIEVAL_HALLUCINATION_RISK_GUARDRAILS`) /
command names. `build` is read-only (no persist; on the operator DB it reports an honest risk assessment);
`proof` runs the offline guard-clean proof.

## 5. Validation

`compileall`/`ruff`/`mypy` (297 files) clean; `pytest -m "not live and not integration and not manual"`
green. The proof passes (on a synthetic corpus with a clean supported item, an overconfident
high-confidence tier-3 item, an unsupported item, and a conflict-flagged item under a degraded,
coverage-gapped envelope: `risk_band=high`, overconfidence detected, the fabrication + overconfidence
indicators fire, no determination is made, the build path performs no DB writes, no raw emitted). Operator
DB unmutated (read-only; schema 38; table-inventory 190 contract / 0 unmapped live). `phase-08b-gates` is
a **pre-existing/environmental** failure (reproduces at clean HEAD `6c43844`, unrelated to this change) —
see the evidence bundle. Full matrix in the evidence bundle.

## 6. Deferred

Persisting risk receipts (none today — read-only by design); rolling the risk band into the synthesis
evaluation gate (A05); executing/scoring the eval set against the index (`eval_runs`); wiring semantic
context into the default `synthesize_answer` (A04) — later Phase 09 prompts.
