# Phase 09 Review Burden Reduction — Proof

This bundle attests the implementation of the exception-based, two-step review burden policy.

## Summary of change

- Replaced blanket `review_not_performed_blocks_all` (for both advisory and promotion) with separated concerns.
- Two-step classification: source family in allowed_families (necessary) + item impact/risk (decisive). High-impact item from any family (incl. cross_source_relationships, aging_exposure, risk_digest) is Tier C.
- Financial ledger separate (raw ~128k, distinct high; always advisory_only + promotion_blocked; does not create permanent assistant failure for low-risk non-financial).
- High-impact always visible as category summary + totals + only top clusters within operator daily budget (no item spam, no silent hiding of counts).
- top_examples_json strictly limited to 9 hash-safe fields; prohibited fields (text/PII/URLs/titles) rejected in builder/proof/tests.
- Daily brief renders "Review exceptions" (top 3-10) + "Batched/suppressed" + recommended CLI action; capped; not a full review queue/dashboard.
- V39 additive tables (3) with full 23 guards CHECK=0. LATEST=39. All >=38 and <38 checks in Phase 09 surfaces remain correct (39 satisfies >=38). 08D/MCP surfaces re-validated post-bump.
- Package: seed+contract under src/hb_assistant/resources/... ; pyproject updated; loader supports package (installed) + fallback (dev); verified via `pip install -e .` + `review policy-status`.
- Retrieval: hybrid status reports `review_burden_advisory_retrieval_allowed`; low-risk A/B (after two-step + guards) usable as advisory even under review_not_performed; C/D blocked from promotion.
- All no-raw, no-writeback, source-linked, no-final-determination guardrails preserved and attested.

## Key numbers (from repo-truth baseline at implementation time)

- total_distinct_review_items: ~2840
- total_unresolved (raw, dominated by financial ledger): ~129084
- total_high_impact_distinct: ~1313
- After policy: advisory_retrieval_allowed true (for safe low-risk); promotion_blocked_for_high_impact true; blanket_review_block false; operator_visible capped at 10; suppressed_or_batched ~2830; financial separate.

See the accompanying JSON for the exact gate + high_impact_summary + financial breakdown emitted by the proof at cut.

## Two-step examples (enforced in code + tests + docs)

- cross_source_relationships + unclassified/low confidence → Tier B (batch, advisory only, not promoted).
- cross_source_relationships + financial/contractual/claim → Tier C (mandatory before promotion; may appear as advisory warning only).
- aging_exposure_report_items + cost_impact → Tier C (unless only used as advisory warning; still blocked from accepted).
- Approved generated outputs / obsidian apply outputs (low impact, source-linked, metadata) → Tier A when family+impact+guards pass.

## Daily brief output shape (rendered)

```
Review exceptions:
- 4 contractual correspondence clusters require review.
- 3 financial exposure clusters remain advisory only.
- 2 source-conflict clusters need confirmation.

Batched/suppressed:
- 761 calendar/email candidates retained as advisory signals.
- 384 weak candidates suppressed from standard answers.

Recommended: run `hb-assistant second-brain review burden --json` ...
```

No thousands of items; capped; summary first.

## 08D / MCP compatibility after V39

Explicitly executed (and required to pass with no regression):

- hb-assistant second-brain mcp status --json
- hb-assistant second-brain mcp audit --json
- hb-assistant second-brain mcp no-raw-access --json
- hb-assistant second-brain mcp no-writeback --json
- hb-assistant second-brain data-quality phase-08d-gates --json

All must exit with their normal success semantics (proof_passed or equivalent) on a post-V39 schema.

## Package verification

```
python -m pip install -e .
hb-assistant second-brain review policy-status --json
```

Must succeed and report loading the policy from the installed package context (not only source tree).

## Guardrails / no-raw / no-writeback / no-determination

- All V39 burden rows carry the 23 CHECK(...=0) columns.
- top_examples_json builder + proof + tests reject any prohibited field.
- No change to source-system writeback prohibition, Graph/Procore direct calls, raw body/prompt/URL/token persistence, or final determinations.
- Existing 08A/08C/08D no-writeback and no-raw proofs continue to pass.

## Files changed (surgical)

(See the commit for the exact list; only files required for the objective + the required docs/evidence/runbook were touched. Unrelated dirty files from the initial git status were not staged.)

## Deduplication refinement (post-implementation quality)

Within review-burden clusters, `top_examples` (and serialized `top_examples_json`) are now deduplicated using a stable hash-only key (`item_hash` preferred, then `source_ref_hash`, then a safe composite of family+project+impact+confidence+reason+freshness). Each cluster emits `unique_example_count` (the count of distinct examples shown to the operator) in addition to the full `item_count`. Prohibited fields remain strictly absent. An explicit regression test asserts `len(dedup_keys) == len(set(dedup_keys))`. This reduces operator noise without changing policy semantics, counts, or schema. Hash-only contract is unchanged.

## Validation

Full matrix per the implementation plan (compileall, ruff, mypy, pytest -m "not live...", construction-agent validate, all second-brain data-quality/retrieval/status commands, the 5 08D commands, pip -e + review commands, daily brief render checks, etc.). All acceptance criteria (original + the 7 refinements) verified.

## Deferred

- Persisting burden clusters/runs on explicit "apply" from the review CLI (current surfaces are read-only compute + proof).
- Adding the burden clusters table as a queryable family for corpus balance / retrieval evals (future).
- Operator UX beyond the Typer review group (e.g. Obsidian commands or TUI to act on top clusters).

This proof + the architecture note + runbook update + tests + code changes close the Phase 09 review burden objective.
