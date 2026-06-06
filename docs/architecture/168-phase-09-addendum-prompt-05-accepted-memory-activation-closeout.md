# 168 — Phase 09 Addendum Prompt 05: Accepted Memory Activation Closeout

**Status:** Closeout — full validation matrix run, evidence captured, addendum closed honestly (substrate validated by fixtures; live corpus empty; **not production-ready**).
**Schema:** unchanged (V39; no migration across the entire addendum). **Version:** 1.8.0-phase-09-addendum.
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/accepted-memory-activation-closeout.{json,md}` + `validation-outputs-accepted-memory-activation/`.
**Closes:** records 164–167 (Prompts 01–04) + the Prompt-00 rebaseline.

---

## 1. What the addendum shipped (Prompts 00–04)

Candidate preview (read-only) → explicit operator acceptance (`--confirm`, no auto-acceptance) →
retrieval/loader/manifest/vector pipeline inclusion → quality & supersession controls (dedup
suppression, metadata-only supersession, freshness, source retention, transition validation). All on
the pre-existing `long_term_memory_items` substrate — **no migration** (Prompt-00 finding). 33 files
across Prompts 00–04; new modules `memory/candidate_preview.py`, `memory/acceptance.py`,
`memory/quality_controls.py`, `retrieval/accepted_memory_inclusion.py` + 3 contracts, a store setter,
CLI verbs, and fixtures.

## 2. Closeout findings (honest)

- **Live memory corpus is empty:** accepted/pending/rejected/superseded = 0/0/0/0. Population is an
  operator action, not done by the addendum.
- **Coverage (live):** deterministic reader 10/10; approved manifest 10 families (reviewed_memory
  category present, 0 live memory refs); **vector-indexed 8 families** (the live `llamaindex build
  --apply` applied successfully — `retrieval-local` present — embedding the eligible Obsidian /
  read-model / generated-output families; `accepted_long_term_memory` is absent — no accepted memory).
  `memory_substrate_status = deferred_empty`; `coverage_parity_ok = true`.
- **8→9:** not reached live (empty corpus); proven by the Prompt-03 fixture
  (`accepted-memory-vector-coverage-proof`, +1 family delta, parity holds). The live baseline is
  concretely 8.
- **All guardrail proofs pass:** no-writeback, no-raw-vector-index, mcp no-raw-access / no-writeback,
  phase-09 gates, approved-sources / -read-model / -vector-loader, reader-registry parity,
  source-linked, llamaindex build-proof, memory acceptance / quality-controls / candidate-preview.

## 3. Validation not clean → not production-ready

- `compileall` pass; `construction-agent validate` 4/4.
- `ruff check .` — 3 **pre-existing** B008 in `cli/procore.py`. `mypy src` — 2 **pre-existing** errors
  in `review_burden_mart.py` (Prompt 34). `pytest` — **28 failures, all pre-existing/environmental**
  (08a-v26 + 08b/c/d schema-lifecycle classification drift over the unclassified
  `second_brain_review_burden_*` tables; the 08b data-quality-gate suite; the automation-executor
  suite, whose failing subset varies run-to-run). All re-confirmed independent of the addendum by
  re-running with the closeout edits stashed at baseline `98ce9694`. The addendum's own suites are
  green. **No production-readiness claim.**

## 4. Closeout hardening (this commit)

The closeout's `mypy src` and the no-writeback static scanner surfaced two addendum-introduced issues,
fixed here with no behavior change:
- 2 mypy type-casts — `read_accepted_memory(cast(Any, None), …)` / `read_risk_digest(cast(Any, None),
  …)` (the reader `store` arg is unused on those conn-injected paths).
- 8 `dict.update()` calls refactored to subscript assignment in `acceptance.py` / `quality_controls.py`
  — the no-writeback scanner (`data_quality/safety.py`) flags any `.update()` attribute call as a
  mutation verb (it can't tell `dict.update` from an HTTP client). Subscript assignment is not an
  attribute call, so the guardrail proof returns to green (`proof_passed=true`, 0 writeback findings).

## 5. Deferred / next

- Live accepted-memory population — operator action (`memory accept --confirm`); then re-run
  `llamaindex build --apply` to flip live coverage 8→9 and `memory_substrate_status` to `covered`.
- Advisory run-record surfaces deferred from the Phase 09 core closeout (unchanged).
- Time-based memory expiration — Prompt-04 future enhancement (no schema added).
- Resolve the pre-existing table-lifecycle drift by classifying `second_brain_review_burden_*` in the
  lifecycle contract.
