# 48 — Phase 07D: Meeting-Prep Prerequisite Gates

**Status:** Implemented (Phase 07D Prompt 05). Additive over schema **V25** (no migration).
**Scope:** Wire the 07D meeting-prep prerequisite gate set into the existing
`construction-agent data-quality gates` evaluator so `meeting_prep_readiness` honestly reflects
relationship, review, safety, and source-scope readiness — and never overstates readiness when
the V25 substrate is empty or upstream gates are deferred.

## Problem

Phase 07D Prompts 02–04 built and populated the V25 cross-source relationship substrate
(`cross_source_relationship_candidates`, `source_evidence_trails`, `cross_source_relationships`).
The `data-quality gates` command already computed a `meeting_prep_readiness` block, but its
prerequisites came only from the **07B manifest** (`phase_07b_data_quality_gates.json` →
`meeting_prep_prerequisites`): calendar / email / document / orphan / safety gates. It did **not**
evaluate the 07D substrate, the weak/model/sensitive review-routing on V25 candidates, or a
meeting-prep–specific source-scope prerequisite. Readiness could therefore be claimed without any
relationship substrate in place.

## Design

Five new `GateEvaluator` methods in `construction/data_quality/gates.py`, all tagged
`future_phase="07D"`, named to match the `phase_07d_data_quality_gates.json` required-field ids.
Each reads the V25 substrate through existing read-only `ConstructionStore` methods, wrapped so an
empty or partial DB degrades to a status rather than raising. Because `_classify`'s `is_boolean`
path only yields `pass`/`deferred_not_blocking`, the genuine-violation branches apply a
post-`_classify` override to `fail_blocking` (the same hard-fail pattern `_classify` already uses
for `deterministic_orphan_rate`).

| Gate | Reads | pass | deferred_not_blocking | fail_blocking |
|---|---|---|---|---|
| `cross_source_relationship_candidate_coverage` | `count_cross_source_relationship_candidates()` | candidates > 0 | candidates == 0 | — |
| `deterministic_relationship_quality` | `list_cross_source_relationship_candidates()` | deterministic edges present, none malformed | no deterministic edges | a deterministic edge lacks the `deterministic` class or is flagged `sensitive_high_impact` |
| `evidence_trail_completeness` | candidate vs evidence-trail counts | trails ≥ candidates (> 0) | candidates == 0 | trails < candidates |
| `weak_model_sensitive_review_routing_accuracy` | `list_cross_source_relationship_candidates()` | every model/sensitive/weak candidate is `review_required` | no weak/model/sensitive candidates | any such candidate not review-routed |
| `meeting_prep_prerequisite_status` (source-scope 3-way) | `evaluate_source_scope_compliance()` + `_card_count()` | OneDrive in scope, no implicit-root block, `all_compliant` | no OneDrive sources in scope **or** no document-card inputs | an in-scope OneDrive source is implicit-root / ambiguous / missing-allowlist |

### Source-scope 3-way

`meeting_prep_prerequisite_status` reuses the existing Phase 07C scope evaluator
(`construction/document/source_scope.py::evaluate_source_scope_compliance`) — which already treats
an **explicit all-folders opt-in** (`allow_all_folders=True` + policy
`allow_explicit_all_folders=True` on a recognized OneDrive root) as **compliant** and implicit
root-wide as blocked. The only new logic is the `deferred_not_blocking` branch the prompt requires:
no enabled OneDrive sources (`by_system["onedrive"] == 0`) **or** no document-card inputs
(`_card_count == 0`). The gate must NOT block solely because all-folders scope is explicitly
selected — satisfied by reusing the evaluator unchanged.

### Wiring & readiness

The five gates run in `run()` after `_gate_external_writeback()`; persistence is unchanged
(idempotent `insert_data_quality_gate_result`, PK `{run_id}:{gate_name}`).
`meeting_prep_readiness` now merges the 07B manifest prerequisites with the 07D constant
`_MEETING_PREP_07D_PREREQUISITES` (de-duped, order-preserving). A `deferred_not_blocking` 07D gate
still keeps readiness blocked (the `!= "pass"` test is preserved), so an empty substrate cannot be
mistaken for readiness. `auto_readiness_allowed` stays `False`. A new additive
`prerequisite_categories` key breaks readiness down by
calendar / email / document / relationship / review / safety / source_scope. Existing keys
(`ready`, `blocked_by`, `prerequisites`, `auto_readiness_allowed`) are preserved.

`meeting_prep_readiness_claim` gains an honest `needs_07d_data` value: `blocked` (any 07B/07C
`fail_blocking`) → `needs_07b_07c_data` (any 07B/07C not pass) → `needs_07d_data` (07B/07C all pass
but a 07D prerequisite unmet) → `ready` (all pass). `ready` reflects prerequisite readiness only;
`auto_readiness_allowed=False` still gates any downstream auto-action.

### Decisions

- **07D prereq list is a constant, not derived from the contract.** The contract's 12
  `required_fields` are a superset spanning Prompts 06–11 (brief / issue / risk / aging / obsidian);
  deriving would add `blocked_by` names with no gate method. A test asserts the constant ⊆ contract.
- **Existing `data-quality gates` command extended; no new `phase-07d-gates` command.** The
  validation matrix references `data-quality phase-07d-gates`, but that is the home for the full
  12-field 07D surface and lands in the later 07D gates-wiring prompt; adding it now would emit a
  half-populated report. Meeting-prep prerequisites are validated today through `data-quality gates`.

## Guardrails

Local-first, read-only. No schema change, no store mutation, no auto-promotion. Gates copy only
counts, enum classes, boolean flags, and registry source-keys into results — never decoded
`signals_json`/`source_reference_json` free-text (enforced by a no-raw-content regex test over the
serialized report). The review-routing gate only reports misrouting; it never sets `review_required`
or promotes.

## Files

- `src/hb_assistant/construction/data_quality/gates.py` — 5 gate methods; `_MEETING_PREP_07D_PREREQUISITES`,
  `_WEAK_CONFIDENCE_CLASSES`, `_DETERMINISTIC_CONFIDENCE_CLASS`, `_MEETING_PREP_CATEGORY_MAP` constants;
  `run()` wiring; readiness + claim block.
- `tests/test_data_quality_meeting_prep_gates.py` (new, 15 tests); claim-whitelist widening in
  `tests/test_data_quality_gates.py`, `tests/test_phase07b_gates.py`.
- Reused unchanged: `construction/document/source_scope.py`, `construction/store/repositories.py`,
  `construction/relationships/contracts.py`.

See `docs/evidence/construction-intelligence-phase-07d-cross-source-meeting-prep/05-meeting-prep-prerequisite-gates.md`.
