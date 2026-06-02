# 66 — Phase 08A: Long-Term Memory Curator (A07) + Operator Preference (A08) Agents (Synthesized Prompt 10)

Status: implemented (Phase 08A Synthesized Prompt 10). Builds on records 57–65.
Deterministic, local-first, read-only over external systems, no-writeback, no new SQLite
tables.

## Purpose

Implements the **Memory Curator Agent (A07)** and **Operator Preference Agent (A08)**:
source-linked, review-controlled long-term memory that compounds with auditable quality
signals, plus reviewable presentation-only operator preferences.

- Memory candidates carry `origin_id` + source refs + review tier + quality signals.
  **Sensitive/high-impact material routes to Tier 3** (mandatory review, never
  auto-accepted). Promotion to accepted memory happens **only via an explicit operator
  review** — no silent acceptance.
- Operator preferences are reviewable, presentation-only records (never auto-accepted;
  sensitive → Tier 3). **Accepted preferences can never override safety policy /
  review-tier routing / guardrails** (enforced by `apply_operator_preferences`).

**No new tables / no migration** (schema stays V26 / 141). Metadata-only; no raw content.

## Repo-truth reconciliation

- **Schema already exists (V26).** `long_term_memory_items`, `long_term_memory_source_refs`,
  `long_term_memory_quality_signals`, `memory_update_candidates`, `memory_update_reviews`,
  `second_brain_operator_feedback`, `second_brain_operator_preference_profiles` all ship in
  V26 with `CHECK(raw_*_persisted = 0)` guards. The models map 1:1 to these columns
  (repo-authoritative over the package's fuller proposed candidate fields).
- **Contracts already registered + repo-authoritative.** `long_term_memory_contract`,
  `memory_update_candidate_contract`, `memory_quality_signal_contract`,
  `operator_preference_profile_contract`, `operator_feedback_contract`,
  `review_tier_contract` (Prompt 02). No contract / `test_phase_08a_contracts` change.
- **Sensitive set is authoritative from `review_tier_contract.mandatory_review_for`** (+
  the memory seed's `tier_3_always`). Agents A07/A08 were already registered.

## Seeds

`resources/config/phase_08a_memory_policy.seed.yaml` (candidate posture + sensitive/
high-impact categories + `tier_3_always`) and `phase_08a_operator_preference_policy.seed.yaml`
(allowed presentation types, sensitive types, `never_overrides` incl. safety_policy +
review_tier_routing). Loaded deterministically (no contract).

## Code (`construction/second_brain/memory/`, strict-mypy)

- `models.py` — `MemoryCandidate`, `MemoryReview`, `MemoryItem`, `QualitySignal`,
  `OperatorFeedback`, `OperatorPreference` (all 1:1 with V26 columns; source-ref validator
  rejects forbidden raw fields).
- `policy.py` — `classify_memory_tier` (sensitive/unsupported/model-only/conflict → Tier 3;
  high→1, medium→2, else 3), `classify_preference` (sensitive → Tier 3; always
  pending_review), `apply_operator_preferences` (applies only accepted, allowlisted
  presentation keys; drops anything safety-affecting — tier/review/safety/suppress/bypass/
  guardrail tokens), `sensitive_high_impact_categories`, `validate_memory_policy`.
- `curator.py` (A07) — `propose_memory_candidate` (never auto-accepts),
  `review_memory_candidate` (explicit decision; 'accepted' promotes to
  `long_term_memory_items` + source refs + origin/quality signals),
  `build_memory_curator_agent_proof`, `build_long_term_memory_proof`.
- `preference.py` (A08) — `capture_preference`, `record_operator_feedback`,
  `build_operator_preference_proof`.
- `store.py` — metadata-only writers for all tables (guard columns 0); preference upsert on
  `UNIQUE(scope, scope_key, preference_key)` increments `signal_count`;
  `read_memory_candidate` (ensures schema before read).

## CLI

`second-brain memory candidate` (propose; sensitive → Tier 3; dry-run default),
`second-brain memory review --candidate-id --decision` ('accepted' promotes),
`second-brain preference capture` (reviewable; never overrides safety). All dry-run unless
`--emit`.

## Guardrails

Local-first; external systems read-only; no writeback; no raw content persisted (model
validators + DB CHECK guards); **sensitive/high-impact memory → Tier 3 (never
auto-accepted); no silent acceptance (promotion only via explicit review); accepted
preferences never override safety / review-tier routing / guardrails**; dry-run default.

## Evidence

`long-term-memory-proof.json`, `memory-curator-agent-proof.json`,
`operator-preference-proof.json` (all `proof_passed: true`);
`10-long-term-memory-and-operator-preferences-proof.md`.

## Deferred

Daily brief (Prompt 13) — will consume accepted memory + preferences; scheduling /
validation matrix / 08A no-writeback proof arm (later prompts). Memory retrieval priority
influence is gated to accepted memory only (existing `read_accepted_memory` reader).
