# 140 — Phase 09 Prompt 21: Metadata Filter Enforcement

**Status:** Implementation — project/source/date/review/confidence/source-coverage filter enforced before + after retrieval; read-only, fail-closed.
**Schema:** V38 (unchanged; no new table). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `d8758fc`, Prompt 20 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/21-metadata-filter-enforcement.md` (+ `.json`, `metadata-filter-proof.{json,md}`, `validation-outputs-prompt-21/`).
**Builds on:** record 139 (hybrid broker); reuses `RetrievalBroker`/`RetrievalItem`, `ALLOWLISTED_SOURCE_FAMILIES`/`EXCLUDED_FAMILIES`, `apply_context_budget`, and `_assert_no_raw`.

---

## 1. Purpose

A fail-closed metadata-filter layer that constrains retrieval **before** (which allowlisted
families/sources are queried; excluded families rejected) and **after** (drop items outside the requested
project / family / date window / review-tier ceiling / confidence floor; emit source-coverage warnings).
Deterministic source-of-truth discipline is preserved: review tier, confidence class, source references,
and freshness ride through on kept items, and the layer never assembles a final answer.

## 2. Design

### Pure filter module, integrated at the hybrid seam
`retrieval/metadata_filter.py` holds the `MetadataFilter` spec and two pure functions —
`normalize_filter` (pre) and `apply_metadata_filter` (post). `build_hybrid_retrieval` gains an optional
`metadata_filter` param: pre-filter resolves the effective family set + project that constrain the
deterministic broker; post-filter runs on the merged `det + semantic` item list **before**
`apply_context_budget`. The post-filter is the authoritative family gate (the broker defaults to all
families on an empty set, so family enforcement happens post). The module does not import `hybrid_broker`
at module level (the proof imports `build_hybrid_retrieval` function-scoped) — no import cycle.

### Family-aware date filtering
`recency` is a parseable ISO date for the six date-capable families but a non-date for
`cross_source_relationships` (relationship id) and semantic items (`freshness_label`). A date window
applies only to date-capable families; date-incapable families are **kept** with a
`date_filter_not_applicable:{family}` coverage warning, never silently dropped.

### Fail-closed pre-filter
`normalize_filter` raises `MetadataFilterError` when `source_families` explicitly names an
`EXCLUDED_FAMILIES` member (excluded families must never be queried), and on an invalid date window /
tier bound / confidence value. Allowlisted-but-unknown families are dropped with a
`requested_family_not_allowlisted` note. The whole surface is V38-gated via the hybrid broker.

### Read-only, metadata-only
The layer persists nothing (no new table, no migrator change). `apply_metadata_filter` records drops by
reason (`project_mismatch`, `family_not_selected`, `out_of_date_window`, `review_tier_above_max`,
`confidence_below_min`) and emits `no_results_for_family` / `source_coverage_incomplete`. The emitted
summary carries `filter_applied` + `filter_summary` (dropped_by_reason, effective_families, filter_keys)
— never the raw query (only `query_hash`) or any excerpt.

## 3. Contract & seed

`phase_09_metadata_filter_contract.json` (+ `.seed.yaml`): filterable keys, date-capable families,
confidence order (`deterministic > high > medium > low > unknown`), review-tier bounds,
`excluded_families_blocked=true`, drop reasons, coverage-warning codes, forbidden-emitted fields. Registered as `metadata_filter_contract`.

## 4. CLI

`second-brain retrieval metadata-filter status | apply "<q>" [--project] [--source a,b] [--date-from]
[--date-to] [--max-review-tier] [--min-confidence] [--require-coverage] [--mode] | proof`. `apply` is
read-only (no operator-DB write); `proof` runs the offline guard-clean proof.

## 5. Validation

`compileall`/`ruff`/`mypy` (289 files) clean; `pytest -m "not live and not integration and not manual"`
= 3152 passed, 0 failed. The filter proof passes (pre-filter rejects excluded families + constrains
families/project; post-filter drops by project/date/review/confidence with reasons; date-incapable family
kept with a coverage note; hybrid integration ok; raw query not emitted). A real `bge-small` filtered
hybrid query enforced the tier ceiling (3 tier-1 + 3 tier-2, 0 tier-3). Operator DB unmutated (apply
yields 0 results — all operator issue items are tier 3 and the demo capped tier at 2; hybrid tables 0/0;
schema 38). Full matrix in the evidence bundle.

## 6. Deferred

Filtered hybrid adoption by A02/A04; the `generated_outputs` loader; eval sets / benchmarks /
memory-quality review — later Phase 09 prompts.
