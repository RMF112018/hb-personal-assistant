# 148 — Phase 09 Prompt 28: Unsupported Claim Checks + Review Routing

**Status:** Implementation — dedicated unsupported-claim detection + review routing; advisory, read-only, fail-closed, metadata-only.
**Schema:** V38 (unchanged; reuses `second_brain_retrieval_unsupported_claim_checks`). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `f33ada0`, Prompt 27 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/28-unsupported-claim-checks.md` (+ `.json`, `unsupported-claim-checks-proof.{json,md}`, `validation-outputs-prompt-28/`).
**Builds on:** records 134–147; reuses the structural support rule from `synthesis/semantic_output_evaluation` (Prompt 23, record 142), the deterministic `RetrievalBroker` (broker.py), the review-tier→status mapping (`synthesis/reasoning`), `EXCLUDED_FAMILIES` (`retrieval/policy`), and `_assert_no_raw`.

---

## 1. Purpose

Promote the binary unsupported-claim check embedded in Prompt 23's output evaluation into a **dedicated
surface that detects unsupported claims AND routes them to human review**. Each retrieved item presented
as context is a **claim**; an unsupported claim (one lacking source support) must never be presented as
fact — it is routed to review. The surface makes **no** claim or entitlement determination; it is
advisory and routes to a human.

## 2. Design

### Detection (structural support rule)
A claim (a `RetrievalItem`) is **supported** iff it carries a `source_ref` **and** an allowlisted,
non-`EXCLUDED` `source_family` — the same rule as Prompt 23's `_unsupported_claim_check` (re-implemented
in the new module to keep it self-contained and richer). Otherwise it is **unsupported**.

### Review routing
`detect_and_route_claims(items)` routes each non-clean claim using the canonical review-tier→status
mapping (`1→auto_advisory`, `2→review_recommended`, `3→review_required`):
- **unsupported** → `review_required` (tier 3), reason `unsupported_no_source_link` or
  `unsupported_excluded_family`.
- **supported but tier-3 / stale / conflict-flagged** → routed at its tier's status
  (`review_required` for tier 3, `review_recommended` for tier 2), reason `supported_review_flagged`.
- **clean supported** (tier ≤ 2, no flags) → not routed.

It returns `claim_count`, `unsupported_count`, `routed_count`, `status`
(`clean`/`review_routed`/`blocked` — **`blocked`** iff any unsupported claim, the zero-tolerance signal),
a routing breakdown (`by_review_status`, `by_reason`), and **hashed per-claim routing records**
(`source_ref_hash`, `source_family`, `review_tier`, `review_status`, `reason`) — never raw claim
text/excerpt/source ref.

### Builder + persistence
`build_unsupported_claim_checks(db_path, *, project_key, families, emit_receipt)` gathers claims from the
deterministic broker (`retrieve(..., emit_receipt=False)`), runs detection + routing, and returns a
metadata-only summary (`assembles_final_answer=false`, `claim_determination_made=false`,
`routes_unsupported_to_review=true`). `emit_receipt=False` by default (persists nothing);
`persist_unsupported_claim_check` writes one guard-clean row to the V38
`second_brain_retrieval_unsupported_claim_checks` table (check_id = `sha256(run_id:claim)[:48]`,
claim_count, unsupported_count, status; all 23 `CHECK(=0)` guards 0 — including
`claim_or_entitlement_decision_performed` and `unsupported_claim_performed`). **No migrator change.**

### Advisory, fail-closed, no determination
The surface never decides a claim is true/false/entitled — it routes to review. `assembles_final_answer`
and `claim_determination_made` are always False; the `claim_or_entitlement_decision_performed` /
`unsupported_claim_performed` guards stay 0. Fail-closed on missing policy / stale schema (V38-gated).
Preserves review tier / confidence / source refs (hashed) / coverage warnings.

## 3. Contract & seed

`phase_09_unsupported_claim_checks_contract.json` (+ `.seed.yaml`): the support rule, review statuses,
reason codes, status vocab (`clean`/`review_routed`/`blocked`), the check column allowlist,
forbidden-emitted fields (claim/content/excerpt/source_ref/raw/…), and global requirements (advisory-only
/ no-final-answer / no-claim-or-entitlement-determination / route-unsupported-to-review; preserve review
tier/confidence/source refs/freshness/coverage warnings; fail-closed). Registered as
`unsupported_claim_checks_contract` (13th Phase-09 contract).

## 4. CLI

`second-brain retrieval claim-checks build [--project] | proof`. Unique Typer var
(`retrieval_claim_checks_app`) / guardrails constant (`_RETRIEVAL_CLAIM_CHECKS_GUARDRAILS`) / command
names. `build` is read-only (no persist; on the operator DB it reports an honest detection + routing
summary); `proof` runs the offline guard-clean proof.

## 5. Validation

`compileall`/`ruff`/`mypy` (296 files) clean; `pytest -m "not live and not integration and not manual"`
green. The claim-checks proof passes (on synthetic claims: a clean supported claim is not routed; an
unsupported claim routes to `review_required`; a supported tier-2 conflict-flagged claim routes to
`review_recommended`; no claim/entitlement determination is made; the persisted receipt is guard-clean +
metadata-only; the read-only default persists nothing; no raw claim text emitted). Operator DB unmutated
(read-only build; schema 38; table-inventory 190 contract / 0 unmapped live). `phase-08b-gates` is a
**pre-existing/environmental** failure (reproduces at clean HEAD `6c43844`, unrelated to this change) —
see the evidence bundle. Full matrix in the evidence bundle.

## 6. Deferred

Routing claim-check signals into a unified review queue / promotion gate (the financial review table is
domain-specific; this surface routes advisorily via metadata + the receipt); executing/scoring the eval
set against the index (`eval_runs`); wiring semantic context into the default `synthesize_answer` (A04) —
later Phase 09 prompts.
