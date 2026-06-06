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

V39 is additive (3 new tables for review burden; 22 tables total, full 23 guards on all). Phase 09 surfaces use >=38 checks (V39 satisfies; schema status reports >=39 as ready). 08D/MCP must be re-validated after the bump with the explicit commands:

- second-brain mcp status/audit/no-raw-access/no-writeback --json
- second-brain data-quality phase-08d-gates --json

All must pass with no regression vs pre-V39. (See Prompt 40 readiness consolidation for explicit categories in operator-status; population of tables like manifests/vectors/review is now reflected without blocking ready status.)

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

## Accepted memory activation (addendum, Prompts 00–05)

The accepted-memory-activation addendum turns the long-term memory substrate into an operator-driven
flow. **No migration** (schema V39); all surfaces are local-first, metadata-only, fail-closed.

Operator flow:

1. **Preview** safe candidates (read-only; never accepts):
   `second-brain memory candidates build --json`
2. **Persist** a chosen candidate to the safe candidate store:
   `second-brain memory candidate --statement "…" --origin-id … --source-refs "family:ref" --emit --json`
3. **Accept** it explicitly (dry-run without `--confirm`; duplicates are suppressed with block
   `DUPLICATE_ACCEPTED`): `second-brain memory accept --candidate-id <id> --confirm --json`
4. **Reject / defer / supersede a candidate**:
   `second-brain memory reject --candidate-id <id> --reason "…" [--decision rejected|deferred|superseded] --confirm --json`
5. **Supersede an accepted item** with a newer accepted one (metadata-only; the old item becomes
   `superseded` and stops loading into retrieval):
   `second-brain memory supersede --old-id <a> --new-id <b> --confirm --json`
6. **List** by status: `second-brain memory list --status accepted --json`

Proofs (all `--no-evidence --json` to avoid evidence churn):
`memory candidates proof`, `memory proof` (acceptance), `memory quality-controls-proof`,
`retrieval accepted-memory-loader-proof`, `retrieval accepted-memory-vector-coverage-proof`.

After an accepted item exists, re-run `retrieval llamaindex build --apply` then
`retrieval coverage-parity-closeout`: the vector-indexed family count rises **8 → 9**
(`accepted_long_term_memory`) and `memory_substrate_status` flips `deferred_empty → covered`.

**Deferred:** the live memory corpus is empty until an operator accepts an item (the substrate is
validated by fixtures only); time-based memory expiration is a documented future enhancement (no schema
added). See `accepted-memory-activation-closeout.md` — **not a production-readiness claim**.

## Evidence location

`docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/`

- review-burden-reduction-proof.json
- review-burden-reduction-proof.md
- (plus the per-prompt proofs for the other Phase 09 items)

## Known deferred

- Persist of burden clusters from the review CLI (current is read-only compute + proof).
- Using the clusters table as an additional corpus family.
- Richer operator UX (Obsidian commands, TUI) over the Typer review group.
- Full production readiness (see phase-09-operator-status / gates / schema-status for explicit categories: safe_advisory_readiness, semantic_retrieval_readiness, vector_apply_readiness, production_readiness=false, deferred_limitations list). External embedding providers, full synthesis determinations, MCP dispatch, and certain high-impact flows remain deferred.
- (Prompt 40) Schema/gates now report V39/22 tables + row counts without forcing all_rows_zero for "ready" (legitimate population of manifests/vector/review after apply is advisory-ok). See evidence/.../validation-outputs-prompt-40/ for matrix outputs (phase-09-schema-status, corpus-balance, approved-sources, llamaindex/hybrid, review, 08D/MCP gates).

## Review burden clusters: deduplicated examples

The `second-brain review clusters` (and `burden`) outputs include per-cluster `unique_example_count` and a deduplicated `top_examples` list (hash-only keys only: prefer item_hash, then source_ref_hash, safe composite otherwise). This is a quality refinement; policy, schema (V39), and guardrails are unchanged. The CLI human output uses `len(top_examples)` which now reflects uniques. See the architecture note + evidence for examples and the regression test asserting no repeated dedup keys.
