# Phase 05 — Live Promotion of Parentless Financial Endpoints (2026-05-29)

> **Scope:** promote the parentless financial endpoints to `live_verified=True` — but
> only after a real bounded smoke whose live payload cleanly matched the normalizer +
> projection. Probe-first, fail-closed-on-divergence. Real Procore traffic (read-only
> GET; no writeback) against the `tropical` pilot project.

## Method (probe-first, no premature promotion)

For each candidate endpoint: temporarily promote the adapter **in memory only**
(`ep._BY_ID[id] = replace(adapter, live_verified=True)`; the on-disk registry is
untouched), run the full `run_live_sync` chain into a **throwaway temp DB**
(`apply=True`, bounded `--max-pages 1 --max-items 5`), then inspect the receipt +
target-table row count. The raw payload is never persisted (the chain's
`raw_body_persisted=0` guarantee holds). "Match" = `state=success`,
`normalized_count == retrieved_count`, `projection_error_count == 0`, and rows landed
in the target financial table. Only matching endpoints were then promoted in committed
code.

## Probe matrix (9 candidates)

| Endpoint | state | retrieved | normalized | proj_err | projected rows | Decision |
|---|---|--:|--:|--:|--:|---|
| prime-contracts | success | 1 | 1 | 0 | 1 | ✅ promote |
| commitment-contracts | success | 5 | 5 | 0 | 5 | ✅ promote |
| billing-periods | success | 5 | 5 | 0 | 5 | ✅ promote |
| subcontractor-invoices | success | 5 | 5 | 0 | 5 | ✅ promote |
| rfqs | success | 5 | 5 | 0 | 5 | ✅ promote |
| budget-views | success | 5 | 5 | 0 | 5 | ✅ promote |
| budget-modifications | success | 5 | 5 | 0 | 5 | ✅ promote |
| **change-events** | partial_success | 5 | 5 | **5** | **0** | 🔒 **HELD** — financial projection raised on every record (`rfq_projection_error`) |
| **budget-change-history** | partial_success | 5 | 5 | n/a | **0** | 🔒 **HELD** — normalizer rejected every live record (`normalize_error`) |

**Held endpoints (do not guess):** the live contract for `change-events` and
`budget-change-history` diverges from the package sample — the projection / normalizer
raised on the real payloads. They remain `live_verified=False` (fail-closed) pending a
normalizer/projection reconciliation against the observed live shape (separate
remediation). No flag was flipped for them.

## Promotion (committed)

`procore/endpoints.py`: 7 rows flipped `live_verified=False → True`,
`verification_reason="phase05_shell_pending_live_smoke" → "phase05_live_smoke_verified_2026-05-29"`.
Registry posture: **34 live-verified / 25 unverified / 59 total** (was 27/32/59).

## Full live cadence on the 7 promoted (post-promotion, real local DB)

`smoke` → `sync --apply` (`--max-pages 3 --max-items 100`) → idempotency re-run:

| Endpoint | smoke | retrieved/upserted/proj_err | total (run1==run2) | idempotent |
|---|---|---|---|---|
| prime-contracts | success | 1/1/0 | 1==1 | ✅ |
| commitment-contracts | success | 63/63/0 | 63==63 | ✅ |
| billing-periods | success | 21/21/0 | 21==21 | ✅ |
| subcontractor-invoices | success | 100/100/0 | 100==100 | ✅ |
| rfqs | success | 7/7/0 | 7==7 | ✅ |
| budget-views | success | 6/6/0 | 6==6 | ✅ |
| budget-modifications | success | 100/100/0 | 100==100 | ✅ |

## No-raw/no-secret probe over the real persisted financial data

After the cadence, **1,028** real financial rows are persisted (contracts 64, amount
facts 730, subcontractor invoices 100, budget changes 100, billing periods 21, rfqs 7,
budget views 6). A scan of every `procore_financial_*` row for Bearer / PEM / `sig=` /
`token=` / `access_token` / raw URLs / emails → **zero findings**; every row has
`raw_body_persisted=0` and (where present) `redaction_applied=1`.

## Test updates

- `tests/test_procore_endpoint_registry.py`: added `_PHASE05_PROMOTED` (the 7);
  `test_phase05_financial_endpoints_fail_closed_unless_promoted` (promoted → True, else
  False); `..._excluded_from_verified_except_promoted` (verified ∩ financial ==
  promoted); `test_verified_endpoints_match_phase04a_matrix` → `_CANONICAL_IDS | _PHASE05_PROMOTED`.
- `tests/test_procore_live_gate.py`: endpoints-list counts 27/32 → **34/25**; the
  fail-closed-without-transport test switched from `prime-contracts` (now promoted) to
  `prime-contract-line-items` (a child, still fail-closed).

## Out of scope / still fail-closed

- **Child financial endpoints** (line-items, responses/quotes, comments, budget-detail-*,
  compliance) — need the deferred N+1 parent→child fetch orchestration before promotion.
- **change-events**, **budget-change-history** — held (live contract diverged).
- **budget-details** — permanent non-routable sentinel.

## Verification

- `pytest -m "not integration and not live and not manual"` → **1239 passed, 1 skipped,
  1 deselected** (posture tests updated, counts unchanged).
- Live cadence above run with `HB_PROCORE_LIVE=1` via the credential loader
  (`default_procore_token_provider`); read-only GET, SQLite-only, no writeback.
