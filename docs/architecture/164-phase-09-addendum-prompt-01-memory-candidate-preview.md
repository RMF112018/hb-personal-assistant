# 164 — Phase 09 Addendum Prompt 01: Memory Candidate Preview

**Status:** Implementation — read-only advisory preview that *surfaces possible* long-term memory candidates from already-redacted, source-linked records; never accepts/persists memory; fail-closed, metadata-only, deterministic.
**Schema:** unchanged (V39; no migration — accepted-memory substrate already sufficient, see record 120/163). **Version:** 1.8.0-phase-09-addendum.
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/accepted-memory-candidate-preview.{json,md}` (+ `accepted-memory-candidate-preview-proof.{json,md}`).
**Builds on:** records 136 (reviewed-memory loader), 150 (memory quality review), 152 (consolidation preview); clones their advisory/read-only `build_* + build_*_proof` pattern and reuses `_assert_no_raw`, `memory/store.read_operator_preferences` shape, `retrieval/readers.read_risk_digest`, and `memory/store.upsert_operator_preference`.

---

## 1. Purpose

Identify possible long-term memory candidates **without accepting or persisting them as accepted
memory**. The surface is read-only and advisory: every candidate is `review_status='pending_review'`
and is never auto-accepted. It is the proposal-side preview that precedes the existing explicit
`memory review` acceptance gate (record 66) and the reviewed-memory loader (record 136).

## 2. Design

### Candidate sources (already-redacted, never raw records)
- `system_config_fact` — durable, non-sensitive facts enumerated deterministically from live constants
  (`store.migrator.LATEST_SCHEMA_VERSION`, local-first/no-write-back posture). Guarantees a non-empty,
  deterministic preview even against an empty operator DB.
- `operator_preference` / `workflow_preference` / `retrieval_preference` / `team_context` — **repeated**
  operator preferences (`signal_count >= min_signal_count`, default 2) from
  `second_brain_operator_preference_profiles` (redacted values only). Type is chosen by `scope=='entity'`
  (→ `team_context`) then `preference_key` prefix (`workflow*` / `retrieval*` / else).
- `project_context` — stable redacted `project_risk_digest_items` via `readers.read_risk_digest`
  (conn-injected read-only); review-required / tier-3 items are excluded as non-durable.

### Validation / rejection (deterministic, per-input)
`_evaluate_input` rejects an input (recording a metadata-only `reason_code`, never surfacing it) when:
unsourced (`REJECTED_UNSOURCED`), empty statement (`REJECTED_EMPTY_STATEMENT`), raw-content-shaped
(`REJECTED_RAW_SHAPED`, via `_assert_no_raw`), or implying a final determination
(`REJECTED_DETERMINATION`, seed `determination_terms`). Review tier 3 is **surfaced** marked
`non_acceptance_preview_only` (this is an explicit non-acceptance preview); a future acceptance-mode
caller (`preview_only=False`) would reject tier 3 (`REJECTED_REVIEW_TIER_3`).

### Candidate shape & determinism
Each candidate carries the contract's required fields: `candidate_id` (`mcp_` + SHA256 of
`source_family:source_ref:statement_hash`), `memory_type`, bounded `statement_redacted` (≤ seed
`statement_max_chars`), `source_family`, `source_ref`, `source_ref_hash`, nullable `project_key`,
`confidence_class`, `review_tier`, `review_status='pending_review'`, `reason_code`, `durability_class`
(`stable|durable|volatile`), `freshness_label`, `created_utc`, and the three no-raw guard flags all
`false`. Identity/content is hash-derived; candidates are sorted by `candidate_id`; only `generated_utc`
is wall-clock (not part of the candidate set).

### Read-only, no acceptance
`build_memory_candidate_preview` reads via `mode=ro` SQL (zero writes), enumerates safe inputs,
validates, and returns a metadata-only envelope (`read_only=true`, `writes_accepted_memory=false`,
`accepted_memory_written=0`, `deterministic=true`). It never touches `long_term_memory_items`.

### Evidence (metadata-only)
`write_evidence` emits candidate **summaries** (drop `statement_redacted` and `source_ref`; keep
`statement_hash` + `statement_len`) — mirroring `memory_loader._node_summary` — guarded by
`_assert_no_raw`. The committed preview/proof artifacts are generated from the deterministic proof
fixture (synthetic preferences), not from the operator's live DB, so they are reproducible and
non-personal.

## 3. Contract & seed

`phase_09_memory_candidate_preview_contract.json` (`required_candidate_fields`, `allowed_memory_types`,
`allowed_durability_classes`, `fixed_review_status='pending_review'`, `rejection_reason_codes`,
`evidence_forbidden_fields`, global requirements: local-first / fail-closed / no-raw / no-writeback /
read-only / no-acceptance / source-linked-only / bounded / deterministic). Registered as
`memory_candidate_preview_contract`. Seed `phase_09_memory_candidate_preview.seed.yaml`
(`min_signal_count`, `statement_max_chars`, `preview_only`, `candidate_types`, `determination_terms`).

## 4. CLI

`second-brain memory candidates build [--project] [--evidence] | proof [--evidence]` — a new
`candidates` sub-group under the existing `memory` group, with a unique Typer var
(`memory_candidates_app`) and guardrails constant (`_MEMORY_CANDIDATE_PREVIEW_GUARDRAILS`). `build` is
read-only against the operator DB (honestly system-facts + any repeated preferences); `proof` runs the
offline fixture proof. Exit 0 on success; 3 fail-closed.

## 5. Validation

`ruff`/`mypy` clean on the new module + CLI; `tests/test_phase_09_memory_candidate_preview.py` (14
tests) green, plus the memory regression suite. The proof seeds repeated operator preferences
exercising safe surfacing (workflow/retrieval/team types), raw-shaped + determination rejection, a
tier-3 non-acceptance surface, and a not-repeated exclusion; asserts `long_term_memory_items` unchanged
(0→0), evidence metadata-only, and no raw emitted.

## 6. Deferred

Acceptance of previewed candidates (the existing explicit `memory review` decision surface); wiring
additional candidate sources from the prompt's list (accepted research-packet summaries, daily-brief
handoff items) beyond the conservative starting set; per-source freshness/conflict signals.
