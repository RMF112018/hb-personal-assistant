# 165 — Phase 09 Addendum Prompt 02: Explicit Memory Acceptance Workflow

**Status:** Implementation — explicit operator acceptance that promotes a vetted candidate into an accepted `long_term_memory_items` row; strict fail-closed gate, explicit `--confirm`, no auto-acceptance.
**Schema:** unchanged (V39; no migration — `long_term_memory_items` already sufficient, per records 120/163/164). **Version:** 1.8.0-phase-09-addendum.
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/accepted-memory-acceptance-proof.{json,md}`.
**Builds on:** records 66 (long-term memory + curator), 136 (reviewed-memory loader), 164 (candidate preview). Reuses `memory/curator.review_memory_candidate`, `memory/store` (`read_memory_candidate`, `write_memory_item`, `set_candidate_status` via the curator's `emit`), and `candidate_preview` (`_is_raw_shaped`, `_implies_determination`, `load_memory_candidate_preview_seed`).

---

## 1. Purpose

Convert a vetted candidate from the durable safe candidate store (`memory_update_candidates`) into an
accepted `long_term_memory_items` row. **Acceptance requires explicit operator action — there is no
automatic acceptance.** This is the acceptance gate between the read-only candidate preview (record
164) and the reviewed-memory loader (record 136).

## 2. Design

### Why a new gate
`curator.review_memory_candidate` already performs the promotion on `decision='accepted'` (creates the
`MemoryItem` with `review_status='accepted'` + quality signals, persists via the store when
`emit=True`, sets candidate status) but enforces **no acceptance blocking** — it promotes whatever
decision is passed. So `memory/acceptance.py` adds a strict, fail-closed **acceptance gate**
(`evaluate_candidate_acceptance`) that must pass before the curator is invoked.

### The gate (collects all blocks; `acceptable = no blocks`)
`NO_SOURCE_REF`, `NO_STATEMENT`, `NO_MEMORY_TYPE`, `NO_CONFIDENCE_CLASS` (empty or `"unknown"`),
`INVALID_REVIEW_TIER`, `RAW_CONTENT_FINDING` (statement or any source-ref value trips `_is_raw_shaped`),
`UNRESOLVED_HIGH_IMPACT` (`review_tier >= 3` — tier-3 sensitive/unsupported/model-only/conflict/
low-confidence is never acceptable here; tier-1/2 are, the operator's `--confirm` resolving the review),
`FINAL_DETERMINATION` (`_implies_determination` over the shared seed `determination_terms`).

### Explicit confirmation
`accept_memory_candidate(candidate_id, *, db_path, confirm=False)`: reads the candidate (raise
`MemoryAcceptanceError` if absent = fail-closed), reconstructs `MemoryCandidate` (mirrors the existing
`memory review` CLI), runs the gate. `confirm=False` → dry-run (`accepted=False, would_accept=…`,
persists nothing). `confirm=True` + acceptable → `review_memory_candidate(decision='accepted',
emit=True)` (local SQLite only; guard columns default 0). `confirm=True` + not acceptable → refuse,
persist nothing. Returns a metadata-only envelope (no statement text).

### Reject / defer / supersede
`decide_memory_candidate(candidate_id, *, decision in {rejected,deferred,superseded}, reason, confirm)`
records the review decision via the curator and **never creates a `MemoryItem`**. These statuses never
load into retrieval/vector index — the reviewed-memory loader gates strictly on `review_status=
'accepted'` (proven by loading the accepted node while excluding a seeded `superseded` row).

### Listing
`list_accepted_memory(status='accepted')` is a metadata-only by-status reader of
`long_term_memory_items` (none existed in `store.py`): fixed SELECT of `memory_id, memory_type,
confidence_class, review_status, project_key, created_utc` + a source-ref count — **no statement text**.

## 3. Contract

`phase_09_memory_acceptance_contract.json` (registered as `memory_acceptance_contract`):
`acceptance_rules`, `block_codes`, `accepted_item_required_fields`, `decisions`, `non_loading_statuses`,
`requires_explicit_confirmation=true`, `no_auto_acceptance=true`, `schema_sufficient=true`,
`migration_required=false`, `guard_columns_must_be_false`, global requirements. Determination terms are
reused from the Prompt-01 candidate-preview seed (single source of truth).

## 4. CLI

Four commands directly under the existing `memory` group (siblings of `candidate`/`review`):
`memory accept --candidate-id --confirm/--no-confirm`, `memory reject --candidate-id --reason
[--decision rejected|deferred|superseded] --confirm`, `memory list [--status]`, `memory proof
[--evidence]`. Unique `_MEMORY_ACCEPTANCE_GUARDRAILS`; `_emit_08c` envelopes; exit 0 on a clean
evaluation, 3 fail-closed. `--confirm` defaults False (dry-run otherwise).

## 5. Validation

`ruff`/`mypy` clean on the new module + CLI; `tests/test_phase_09_memory_acceptance.py` (16 tests) green
plus the memory regression suite. The proof seeds a clean tier-1 candidate + raw/unsourced/sensitive/
determination candidates + a `superseded` item, then asserts: dry-run persists nothing; explicit confirm
promotes the clean candidate to `review_status='accepted'`; each unsafe candidate is refused with the
expected block code and nothing persists; reject creates no `MemoryItem`; the accepted node loads while
the superseded item is excluded; all guard columns 0; no external writeback. Pre-existing, unrelated
phase-08b/c/d lifecycle/gate failures remain out of scope.

## 6. Deferred

Accepting directly from an ephemeral Prompt-01 preview candidate (today acceptance operates on the
persisted `memory_update_candidates` store; previewed items are persisted via `memory candidate --emit`
first); `supersedes_memory_id` chaining on supersede decisions; bulk accept/reject.
