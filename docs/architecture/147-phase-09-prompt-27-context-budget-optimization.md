# 147 — Phase 09 Prompt 27: Context Budget Optimization

**Status:** Implementation — additive advisory best-effort context packer (vs the baseline `apply_context_budget`); read-only, fail-closed, metadata-only.
**Schema:** V38 (unchanged; no table). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `4c2645d`, Prompt 26 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/27-context-budget-optimization.md` (+ `.json`, `context-budget-optimization-proof.{json,md}`, `validation-outputs-prompt-27/`).
**Builds on:** records 134–146; reuses `apply_context_budget` + `load_context_budget` + `ContextBudget` (`retrieval/policy.py`), the deterministic broker gather (`broker.py`), `READER_REGISTRY`, `ALLOWLISTED_SOURCE_FAMILIES`/`EXCLUDED_FAMILIES`, and `_assert_no_raw`.

---

## 1. Purpose

The baseline deterministic packer `apply_context_budget` (`policy.py:183`) fills the model-bound context
in priority order (review tier → recency → confidence → source_ref) but **`break`s at the first item
that would overflow**. Because each excerpt is capped at `max_item_chars` (1800) within a
`max_context_chars` (24000) budget, the cumulative sum can stop with hundreds of chars of headroom while
a small lower-priority item that *would* fit is silently dropped. Prompt 27 **optimizes context packing**
with an additive best-effort fill that recovers that wasted budget — **while preserving source and
warning metadata**.

## 2. Design

### Additive, not a replacement
`apply_context_budget` is consumed by `broker.py` (2×), `hybrid_broker.py`, and asserted in
`tests/test_retrieval_policy.py`. It is **not modified** — `optimize_context_packing` is a new, advisory
function (capability + measurement). Adoption into the authoritative broker is **deferred** (as semantic
adoption into A04 was). `authoritative_packer_unchanged` is asserted in the proof.

### `optimize_context_packing(items, budget)`
Same staged ordering as the baseline (tier → recency desc → confidence → source_ref) and the same
`max_item_chars` truncation, but a **best-effort fill**: process in priority order; keep an item if it
fits, else record it `oversized_skipped` and **continue** (do not `break`). It **never exceeds**
`max_context_chars`; every kept item retains full metadata (only the excerpt is length-bounded,
identically to the baseline); and **every drop is surfaced** as `budget_dropped:<family>` +
`budget_dropped_tier{N}:<family>` coverage warnings — so a sacrificed higher-tier item is never silently
lost. Same `none`/`narrow_claims`/`blocked` degradation vocabulary.

### `build_context_budget_optimization(db_path, *, project_key, families)`
Gathers the **pre-budget** corpus by mirroring the broker's gather loop (allowlist iteration; excluded /
unknown / no-reader families denied with coverage warnings), then reports a metadata-only
**baseline-vs-optimized** comparison: kept counts, char-utilization %, `items_recovered`, preserved
per-mode tier distribution, `metadata_preserved`, `within_budget`,
`all_drops_have_coverage_warnings`, and the union of coverage + budget-drop warnings. `read_only=True`,
`assembles_final_answer=false`; **persists nothing** (no DB writes). Fail-closed on missing policy /
stale schema (V38-gated).

## 3. Contract & seed

`phase_09_context_budget_optimization_contract.json` (+ `.seed.yaml`): honored budget fields, degradation
modes, drop-warning prefixes, forbidden-emitted fields (content/excerpt/source_ref/raw/…), and global
requirements (advisory-only / no-final-answer / deterministic-packing / never-exceed-budget /
no-silent-drops; preserve review tier/confidence/source refs/freshness/coverage warnings; fail-closed).
Registered as `context_budget_optimization_contract` (12th Phase-09 contract).

## 4. CLI

`second-brain retrieval context-budget build [--project] | proof`. Unique Typer var
(`retrieval_context_budget_app`) / guardrails constant (`_RETRIEVAL_CONTEXT_BUDGET_GUARDRAILS`) / command
names. `build` is read-only (no persist; on the operator DB it reports an honest small/empty comparison);
`proof` runs the offline guard-clean proof.

## 5. Validation

`compileall`/`ruff`/`mypy` (295 files) clean; `pytest -m "not live and not integration and not manual"`
green. The optimization proof passes (on a crafted set the baseline keeps N and breaks at an overflowing
item; the optimizer skips it and keeps a tiny lower-priority item → ≥1 item recovered, never exceeds the
budget, all metadata preserved, every drop surfaced as a coverage warning, priority preserved, the
authoritative packer left unchanged, the build path performs no DB writes, no raw emitted). Operator DB
unmutated (no writes; schema 38; table-inventory 190 contract / 0 unmapped live). `phase-08b-gates` is a
**pre-existing/environmental** failure (reproduces at clean HEAD `6c43844`, unrelated to this change) —
see the evidence bundle. Full matrix in the evidence bundle.

## 6. Deferred

Adopting `optimize_context_packing` into the authoritative broker / hybrid context budget (deferred —
would change `apply_context_budget` consumers and their tests); executing/scoring the eval set against
the index (`eval_runs`); wiring semantic context into the default `synthesize_answer` (A04) — later
Phase 09 prompts.
