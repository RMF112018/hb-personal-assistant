# 150 — Phase 09 Prompt 30: Memory Quality Review

**Status:** Implementation — read-only advisory evaluation of memory candidates for duplicate/stale/conflicting; fail-closed, metadata-only, no determination, no merge/delete/accept.
**Schema:** V38 (unchanged; reuses the reserved `second_brain_memory_quality_review_runs`). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `04112c5`, Prompt 29 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/30-memory-quality-review.md` (+ `.json`, `memory-quality-review-proof.{json,md}`, `validation-outputs-prompt-30/`).
**Builds on:** records 134–149; reuses `memory/store.py` (read candidates / `write_memory_item`), `memory/curator.py` (`propose_memory_candidate`), `memory/policy.py` (`classify_memory_tier` → `T3_CONFLICT_DETECTED`), the `eval_set.py` persister pattern, and `_assert_no_raw`.

---

## 1. Purpose

Evaluate **proposed** long-term memory candidates (`memory_update_candidates`, status `proposed`) for
**duplicate / stale / conflicting** status against the accepted memory corpus, and **flag** problem
candidates for human review. The surface **never merges, deletes, or accepts** memory and makes **no
determination** — it is an advisory quality review.

## 2. Design

### Detection (deterministic, metadata-only)
Statements are SHA256-hashed (`statement_redacted`), never stored/emitted raw. The evaluator builds
`accepted_hashes` (items `review_status='accepted'`) and `superseded_hashes` (`review_status='superseded'`)
and classifies each proposed candidate:
- **duplicate** — its statement-hash ∈ `accepted_hashes`, or it appears more than once among candidates.
- **stale** — its statement-hash ∈ `superseded_hashes` (restates outdated/superseded memory).
- **conflicting** — its `review_tier_reason_code == "T3_CONFLICT_DETECTED"` (the deterministic conflict
  code stamped by `memory/policy.classify_memory_tier(conflict=True)` — no noisy subject heuristics).
A candidate may carry multiple flags. Returns `reviewed_count`, `flagged_count`, per-category counts, a
`review_tier` summary, `status` (`clean`/`flagged`/`empty`), and **hashed per-candidate flag records**
(`candidate_id_hash`, `statement_hash`, `flags`, `review_tier`) — never raw statement text.

### Read-only, persistence
`build_memory_quality_review` reads candidates + accepted/superseded items via `mode=ro` SQL (zero
writes), evaluates, and returns a metadata-only summary (`makes_determination=false`,
`merges_or_deletes_or_accepts=false`, `routes_flagged_to_review=true`). `emit_receipt=False` by default
(persists nothing); `persist_memory_quality_review_run` writes one guard-clean row to the reserved V38
`second_brain_memory_quality_review_runs` table (run_id, project_key, reviewed_count, flagged_count,
review_tier, status; all 23 `CHECK(=0)` guards 0). **No migrator change** (schema stays V38; contract
table count stays 190).

### Advisory, fail-closed
The surface flags for review; it never decides, merges, deletes, or accepts. Fail-closed on missing
policy / stale schema (V38-gated). Preserves review tier / confidence / source refs. No raw memory
statement text is persisted or emitted (only hashes, counts, review vocabulary).

## 3. Contract & seed

`phase_09_memory_quality_review_contract.json` (+ `.seed.yaml`): the reviewed candidate status
(`proposed`), flag categories (`duplicate`/`stale`/`conflicting`), the conflict reason code, status vocab
(`clean`/`flagged`/`empty`), the run column allowlist, forbidden-emitted fields
(statement/statement_redacted/content/raw/…), and global requirements (advisory-only / no-determination /
no-merge-or-delete-or-accept / route-flagged-to-review; preserve review tier/confidence/source refs;
fail-closed). Registered as `memory_quality_review_contract` (15th Phase-09 contract).

## 4. CLI

`second-brain memory quality-review build [--project] | proof` — a new sub-group under the existing
`memory` group (which already has `candidate`/`review`). Unique Typer var (`memory_quality_review_app`) /
guardrails constant (`_MEMORY_QUALITY_REVIEW_GUARDRAILS`) / command names. `build` is read-only (no
persist; on the operator DB — no proposed candidates — honestly `empty`); `proof` runs the offline
guard-clean proof.

## 5. Validation

`compileall`/`ruff`/`mypy` (298 files) clean; `pytest -m "not live and not integration and not manual"`
green. The proof passes (seeds an accepted item, a superseded item, and four proposed candidates — a
duplicate, a stale restatement, a conflicting one, and a clean one; `flagged_count=3`, each category
detected, the run row guard-clean + metadata-only, `makes_determination=false`, read-only default persists
nothing, no raw statement emitted). Operator DB unmutated (read-only build; schema 38; table-inventory 190
contract / 0 unmapped live). `phase-08b-gates` is a **pre-existing/environmental** failure (reproduces at
clean HEAD `6c43844`, unrelated to this change) — see the evidence bundle. Full matrix in the evidence
bundle.

## 6. Deferred

Memory **consolidation** (clustering duplicates into merge proposals via the reserved
`second_brain_memory_consolidation_candidates` / `_review_items` tables) — a later prompt; executing the
operator review decision on flagged candidates (the existing `memory review` surface); wiring quality
signals (`long_term_memory_quality_signals`) into the freshness/conflict evaluation.
