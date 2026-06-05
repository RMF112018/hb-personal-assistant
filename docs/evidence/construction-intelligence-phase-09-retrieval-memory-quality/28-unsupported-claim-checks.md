# Phase 09 Prompt 28 — Unsupported Claim Checks + Review Routing (Evidence)

**Package:** 1.4.0-phase-09 · **Schema:** V38 (unchanged) · **Repo SHA at build:** `f33ada0`
**Objective:** Implement unsupported claim detection and review routing — each retrieved item is a claim; unsupported claims (lacking source support) are detected and routed to human review, never presented as fact. Advisory only — no claim/entitlement determination.

## What changed

- **New** `retrieval/unsupported_claim_checks.py` — `detect_and_route_claims` /
  `build_unsupported_claim_checks` / `persist_unsupported_claim_check` /
  `build_unsupported_claim_checks_proof` (+ `UnsupportedClaimCheckError`). Reuses the structural support
  rule (Prompt 23), the deterministic `RetrievalBroker` corpus, the review-tier→status mapping, and
  `EXCLUDED_FAMILIES`.
- **New** contract `phase_09_unsupported_claim_checks_contract.json` + seed; registered as
  `unsupported_claim_checks_contract` (13th Phase-09 contract).
- **New** CLI `second-brain retrieval claim-checks build | proof`
  (`retrieval_claim_checks_app`, `_RETRIEVAL_CLAIM_CHECKS_GUARDRAILS`).
- **New** tests `tests/test_phase_09_unsupported_claim_checks.py` (5 required paths + proof).
- **No migrator change** — reuses the existing V38 `second_brain_retrieval_unsupported_claim_checks`
  table. Schema stays 38, contract table count stays 190.

## Design (why it is safe)

- **Detection**: a claim (`RetrievalItem`) is supported iff it has a `source_ref` + an allowlisted
  non-excluded `source_family`; else unsupported.
- **Review routing**: unsupported → `review_required` (tier 3, reason `unsupported_no_source_link` /
  `unsupported_excluded_family`); supported-but-tier-3/stale/conflict → routed at its tier status
  (`review_required` tier 3, `review_recommended` tier 2, reason `supported_review_flagged`); clean
  supported → not routed. Canonical mapping `1→auto_advisory`, `2→review_recommended`,
  `3→review_required`. Status `clean`/`review_routed`/`blocked` (**blocked** iff any unsupported claim —
  zero tolerance: an unsupported claim must not be presented as fact).
- **Advisory only — no determination**: `assembles_final_answer=false`, `claim_determination_made=false`;
  the `claim_or_entitlement_decision_performed` + `unsupported_claim_performed` guards stay 0. It routes
  to a human; it never decides a claim is true/false/entitled.
- **Read-only, metadata-only**: `emit_receipt=False` persists nothing; the receipt (one guard-clean row)
  carries only hashes, counts, family names, review vocabulary, and reasons — never raw claim
  text/excerpt/source ref (per-claim routing records hold a `source_ref_hash`, not the raw ref).

## Operator DB outcome (real result; pristine)

`claim-checks build --json` → `status=clean`, **408 claims**, **0 unsupported**, 0 routed, `read_only`.
On the real operator corpus all 408 retrieved claims are source-supported — an honest demonstration that
the deterministic corpus is well source-linked. Direct check:
`second_brain_retrieval_unsupported_claim_checks` = **0 rows**, schema **38** — `operator_db_mutated=false`.

## Proof (synthetic + receipt)

`claim-checks proof --json` → **`proof_passed=true`**: on synthetic claims (a clean supported claim not
routed; an unsupported claim → `review_required`; a supported tier-3 claim → `review_required`; a
supported tier-2 conflict-flagged claim → `review_recommended`), `unsupported_count=1`, status `blocked`,
`unsupported_routed_to_review_required=true`, `flagged_routed_to_review_recommended=true`,
`claim_determination_made=false`, `receipt_guard_clean=true`,
`claim_or_entitlement_decision_performed=0`, `unsupported_claim_performed=0`,
`read_only_default_no_persist=true`, `no_raw_emitted=true`.

## Validation matrix

| Check | Result |
|---|---|
| `compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | Success — 296 source files |
| `pytest -m "not live and not integration and not manual"` | 3209 passed, 0 failed |
| `construction-agent validate --json` | 4/4 (schema 38) |
| `data-quality table-inventory --json` | schema 38; contract 190; 0 unmapped live |
| `data-quality no-writeback-proof --json` | ok=true, proof_passed=true |
| `second-brain data-quality phase-08a-gates --json` | ok=true |
| `second-brain data-quality phase-08b-gates --json` | **exit 1 — PRE-EXISTING / ENVIRONMENTAL (not this change)** ¹ |
| `second-brain financial data-quality phase-08c-gates` | **SKIPPED** (mutates operator DB ~1,299 ledger rows/call) |
| `second-brain data-quality phase-08d-gates --json` | proof_passed=true, ok=true |
| `second-brain mcp no-raw-access --json` | proof_passed=true |
| `second-brain mcp no-writeback --json` | proof_passed=true |
| `second-brain retrieval claim-checks build --json` | exit 0 — 408 claims, status=clean, read-only, no persist |
| `second-brain retrieval claim-checks proof --json` | exit 0 — proof_passed=true |
| `test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof` | pass (in the full suite) |

¹ **`phase-08b-gates` is a pre-existing/environmental failure, not caused by this prompt** (no automation
code touched). It is an `AssertionError` (`assert failed_count >= 1`) in
`automation_executor.build_automation_execution_proof` (`automation_executor.py:1485`) that **reproduces
on a pristine checkout of clean HEAD `6c43844`** in an isolated git worktree (verified in Prompt 26) —
operator Application-Support automation-state drift; the proof is not fully temp-isolated. The full pytest
suite passes (fixtures redirect `PathPolicy` to a temp root).

## Deferred

Routing claim-check signals into a unified review queue / promotion gate (the financial review table is
domain-specific; this surface routes advisorily via metadata + the receipt); executing/scoring the eval
set against the index (`eval_runs`); wiring semantic context into the default `synthesize_answer` (A04).
