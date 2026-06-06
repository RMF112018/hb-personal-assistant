# 167 — Phase 09 Addendum Prompt 04: Memory Quality & Supersession Controls

**Status:** Implementation — minimum-viable quality controls so accepted memory does not become stale, duplicative, or unsafe: deterministic duplicate detection (suppressed at acceptance), metadata-only supersession, freshness labeling, source retention, and review-status transition validation.
**Schema:** unchanged (V39; no migration — uses `supersedes_memory_id`, `review_status` CHECK incl. `superseded`, and `quality_signals.freshness_class`). **Version:** 1.8.0-phase-09-addendum.
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/accepted-memory-quality-controls-proof.{json,md}`.
**Builds on:** records 66, 136, 164–166. Reuses `memory.store` (new `set_memory_item_status`), `memory.curator`, `memory.acceptance`, `retrieval.memory_loader`, and `memory.quality_signals`.

---

## 1. Purpose

Add the controls that keep the accepted-memory corpus healthy. The schema already supported all five
controls; **no item-level status/supersedes setter, normalization/fingerprint, supersession mutation,
or transition validator existed** — this prompt adds them. No migration; time-based expiration is a
documented future enhancement.

## 2. The five controls (`memory/quality_controls.py`)

- **Duplicate detection** — `normalize_statement` (whitespace-collapse + casefold) +
  `statement_fingerprint` (SHA256 over `project_key | memory_type | source_family | normalized
  statement`). `detect_duplicate_accepted` (read-only) compares an incoming item's fingerprint against
  existing accepted items. **Suppressed at acceptance**: `accept_memory_candidate` runs the duplicate
  check after the pure gate and refuses with block `DUPLICATE_ACCEPTED` (added to the acceptance
  contract's `block_codes`).
- **Supersession** — `supersede_accepted_memory` (metadata-only, explicit `--confirm`): requires both
  items accepted, validates `accepted→superseded`, sets the old item `review_status='superseded'` and
  the new item `supersedes_memory_id=old` via the new `store.set_memory_item_status`. The superseded
  item is then excluded from retrieval (the reviewed-memory loader gates on `accepted`).
- **Freshness** — the loader's `freshness_label` (`current`/`unknown` from `created_utc`) plus
  `mark_memory_freshness` writing a `signal_type='freshness'` quality signal (schema-supported
  stale/fresh flag). Time-based auto-expiration (a `valid_until` column) is reported as a **future
  enhancement** — no schema added.
- **Source retention** — `write_memory_item` already cascades `source_family` / `source_ref` /
  `evidence_trail_id` into `long_term_memory_source_refs`; the proof attests preservation (+ source_ref
  hash) with no raw content.
- **Review-status transitions** — `ALLOWED_STATUS_TRANSITIONS` + `validate_status_transition`:
  `pending_review→{accepted,rejected}`, `accepted→{superseded}`, terminal `rejected`/`superseded`.
  **Repo policy: `accepted→rejected` is disallowed — accepted memory is removed by supersession**
  (revocation == supersede; no `revoked` status is added). `set_memory_item_status` is the low-level
  metadata-only setter (the CHECK enforces the enum); the transition policy is enforced by the control.

## 3. CLI

Two commands under the existing `memory` group: `memory supersede --old-id --new-id --confirm` (dry-run
without confirm) and `memory quality-controls-proof`. Duplicate suppression needs no command — it is
folded into `memory accept`.

## 4. Contract

`phase_09_memory_quality_controls_contract.json` (registered): `duplicate_detection`,
`supersession`, `freshness` (with `future_enhancement`), `source_retention_fields`,
`allowed_status_transitions`, `transition_policy_note`, global requirements. The acceptance contract
gains the `DUPLICATE_ACCEPTED` block code (additive).

## 5. Validation

`ruff`/`mypy` clean on the new/changed modules + CLI; `tests/test_phase_09_memory_quality_controls.py`
(13 tests) green plus the memory + acceptance + inclusion regression (the `DUPLICATE_ACCEPTED` block
does not regress Prompt-02's acceptance suite — its clean candidate has no pre-existing accepted
duplicate). The proof seeds an accepted item + an equivalent candidate (blocked duplicate) + a newer
accepted item (supersedes the original), then asserts duplicate detection + suppression, supersession
retrieval-exclusion + link, freshness label + freshness signal, source-ref preservation, the full
transition matrix, guard columns 0, and no external writeback. Pre-existing, unrelated phase-08b/c/d
failures remain out of scope.

## 6. Deferred / future enhancement

Time-based memory expiration (`valid_until` column + a sweep that auto-marks stale) — explicitly not
added (no unnecessary schema); supersession chains across more than two items; surfacing the freshness
signal in the daily brief.
