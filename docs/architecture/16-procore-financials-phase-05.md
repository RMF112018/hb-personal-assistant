# 16 — Procore Contracts & Financials (Phase 05)

Status: **in progress** · Phase 05 Prompt 01 · Migration **V7** (V8 financial schema is Prompt 02) · registry 27 → 59 endpoints

Phase 05 extends the Procore subsystem into the contract / financial-control
surface (owner contracts, commitments, purchase orders, invoices, RFQs / change
events, budget). Prompt 00 produced the read-only endpoint inventory; **Prompt 01
adds the registry + live-gate shell** — making all 32 financial endpoints *known*
to the system while keeping every one fail-closed until per-endpoint smoke
evidence promotes it.

## Endpoint registry shells

`procore/endpoints.py` now carries 32 Phase 05 financial `EndpointAdapter` rows
appended after the 27 Phase 04A/04B operational rows (total 59). Every financial
row is:

- `live_verified=False` with `verification_reason="phase05_shell_pending_live_smoke"`
  (or, for `budget-details`, a fail-closed unresolved-path reason).
- `sensitivity="high"` and `review_required_default=True` (high-sensitivity
  business data posture).
- `sqlite_target="procore_live_records"` as a **placeholder** — the V8 financial
  projection target lands in Prompt 02; nothing is written while unverified.
- No normalizer registered — `live_sync.resolve_normalizer()` returns `None`, so
  even a hypothetical promotion fails closed (`normalizer_missing`). The real
  per-family normalizers are Prompts 03–09.

Parent/child linkage uses the existing `parent_path_template` /
`parent_record_id_field` fields (12 parents, 20 children). The `EndpointAdapter`
dataclass gains one **additive** trailing field, `response_envelope`
(`"array"` | `"object"` | `"object.data[]"`, default `"array"`), recording the
top-level wrapper shape from the endpoint matrix; the 27 pre-05 rows keep the
default and are otherwise unchanged.

## Fail-closed posture (no transport)

Unverified endpoints are command-visible (`procore live endpoints list` shows all
59 with their flags) but fail closed in `live_sync.py` **before** any transport:
the unverified branch returns `state="not_live_verified"`,
`no_live_call_performed=True`, `request_count=0`, reason
`endpoint_unverified_for_live`. This is locked in by
`tests/test_procore_endpoint_registry.py` (count/resolution/fail-closed/parent-child
consistency) and `tests/test_procore_live_gate.py`
(`test_live_sync_phase05_financial_endpoint_fails_closed_without_transport`, which
drives a real `prime-contracts` shell with a transport that raises if hit).

## Notable items

- **`budget-details`** has no resolved path in the source reference (Prompt 00
  §3.2). It is registered with a clearly non-routable sentinel
  (`path_template="unresolved:budget-details"`) so the id stays catalog-visible yet
  can never transport. The path is **not guessed**; it must be resolved (likely
  merged into `budget-detail-rows`) before promotion.
- **Commitments (v2) vs purchase orders (v1)** carry a double-counting risk
  (Prompt 00 §3.1); the v1 PO rows are registered as compatibility/backfill
  candidates pending live verification.
- Envelope / pagination / `sqlite_target` on unverified rows are **provisional**
  metadata, re-confirmed at live promotion.

Evidence: `docs/evidence/construction-intelligence-phase-05-financials/`
(`00-…source-inventory.md`, `phase05-financial-endpoint-inventory.json`,
`01-endpoint-registry-and-live-gate-shell.md`).
