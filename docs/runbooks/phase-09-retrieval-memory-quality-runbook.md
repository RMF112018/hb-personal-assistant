# Phase 09 Retrieval & Memory Quality Runbook

(Extended with review burden reduction policy.)

## Review burden policy (two-step, exception-based)

### Commands

- `hb-assistant second-brain review policy-status --json`
  - Loads packaged (or fallback) seed + contract.
  - Shows two-step rules, high-impact cats (decisive), allowed families (necessary), financial separate, hash-only example fields, budgets, guards.
  - Must succeed after `pip install -e .` using the installed package data.

- `hb-assistant second-brain review burden --json [--project KEY]`
  - Full mart + gate: counts by tier after two-step, financial_review_burden (separate), high_impact_summary (categories + totals always; visible_top_clusters capped), operator_visible_count, suppressed_noise_count, advisory_retrieval_allowed, blanket_review_block=false.
  - High-impact is summarized + top clusters only (within daily budget); never full item list or silent hide.

- `hb-assistant second-brain review queue --top N --json`
  - Top operator-visible clusters (high-impact/C first, then by count), hash-only examples only.

- `hb-assistant second-brain review clusters --json`
  - Complete clustered view for the current DB (all groups, hash-only examples).

- Legacy (still works, now richer):
  - `hb-assistant second-brain data-quality review-load --json`
    - Emits the old mart + legacy promotion gate (compat) + the new review_burden_policy fields (advisory_retrieval_allowed, financial separate, high_impact_summary, operator/suppressed counts, blanket=false).

### Daily brief

Daily brief no longer dumps the full review queue. It renders a capped "Review exceptions" section (top from Tier-C / mandatory) + "Batched/suppressed" counts + recommended CLI action. See the architecture note for the exact target text shape.

Use the review CLI commands above for the actionable clustered view.

### Two-step rule (operator mental model)

- Family in the policy allowed list? Necessary for Tier A consideration.
- Item's impact/risk category high (financial, contractual, claim, schedule, safety, legal, payment, cost, entitlement)? Decisive → Tier C (mandatory before promotion), even from an "allowed" family.
- Example: cross_source_relationships + financial/claim → C. Same family + unclassified/low → B (batch, advisory only).
- High-impact categories + totals are always visible in summaries. Only top clusters (budget-capped) are shown for action.

### Financial ledger

Huge raw append-only volume is expected and tracked separately. It is always advisory_only + promotion_blocked. It does not cause the assistant to be "permanently unusable" for safe low-risk non-financial metadata advisory use.

### Hash-only examples

Any surfaced top_examples contain only: source_family, project_key, item_hash, source_ref_hash, confidence_class, review_reason_code, impact_category, freshness_bucket, count.

If you see subject/body/title/email/URL/raw in an example, that is a bug (report + treat as guard violation).

### V39 schema + 08D/MCP compatibility

V39 is additive (3 new tables, full 23 guards). Phase 09 surfaces use >=38 checks (V39 satisfies). 08D/MCP must be re-validated after the bump with the explicit commands:

- second-brain mcp status/audit/no-raw-access/no-writeback --json
- second-brain data-quality phase-08d-gates --json

All must pass with no regression vs pre-V39.

### Package / install

The seed (yaml) and contract (json) are under the package (src/hb_assistant/resources/...). After any change:

```
python -m pip install -e .
hb-assistant second-brain review policy-status --json
```

If this fails to load the policy, the globs in pyproject.toml or the loader fallback need fixing.

### Validation after changes

Run the full matrix listed in the implementation plan / architecture 151 (compile, lint, type, pytest safe subset, all the hb-assistant second-brain ... --json commands including the new review ones + the 08D ones, pip -e + review policy-status, daily brief render checks, etc.).

## Other Phase 09 surfaces (llamaindex, hybrid, approved sources, etc.)

See the sibling runbooks and the per-prompt architecture notes (120–150 range) for their specific commands and proofs.

## Evidence location

`docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/`

- review-burden-reduction-proof.json
- review-burden-reduction-proof.md
- (plus the per-prompt proofs for the other Phase 09 items)

## Known deferred

- Persist of burden clusters from the review CLI (current is read-only compute + proof).
- Using the clusters table as an additional corpus family.
- Richer operator UX (Obsidian commands, TUI) over the Typer review group.

## Review burden clusters: deduplicated examples

The `second-brain review clusters` (and `burden`) outputs include per-cluster `unique_example_count` and a deduplicated `top_examples` list (hash-only keys only: prefer item_hash, then source_ref_hash, safe composite otherwise). This is a quality refinement; policy, schema (V39), and guardrails are unchanged. The CLI human output uses `len(top_examples)` which now reflects uniques. See the architecture note + evidence for examples and the regression test asserting no repeated dedup keys.
