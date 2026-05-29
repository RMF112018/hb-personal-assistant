# Phase 05 Prompt 10 — Live-Sync Dispatch Verification & Idempotency Sweep

> **Scope:** verify the Phase 05 dispatch chain end-to-end, harden the receipt to the
> Receipt Requirements, prove projection failures don't break latest-state sync, and run
> no-raw/no-secret probes over the V8/V9 financial tables. **No live GETs** — no endpoint
> is promoted; the live cadence is operator-gated (see §3). Final prompt of the package.

## 1. Dispatch chain (confirmed order)

All 5 families were wired in Prompts 04–09; `run_live_sync` processes each fetched
record in the required order — verified by reading the per-record loop and by the
synthetic end-to-end chain test:

| Step | Call | Guarded? |
|---|---|---|
| normalize | family normalizer (`_NORMALIZER_BY_ID`) | yes → `normalize_error` |
| latest-state upsert | `upsert_procore_live_record` | yes → `upsert_error` (skips record) |
| history recording | `record_procore_history_for_record` | yes → `history_error` |
| financial projection | `project_{owner,commitment,invoice,rfq_change_event,budget}_family` | yes → `<family>_projection_error` |
| child-extract | inline child normalize + upsert | yes → `child_*` |
| watermark / receipt | `update_watermark` + `_build_receipt` | — |

Each family projection block is `try/except` and appends a redacted
`{"<family>_projection_error": "projection_failed"}` to `redacted_errors`, so a
projection failure never rolls back the latest-state upsert + history.

## 2. Receipt requirements

`_build_receipt` now emits the full set:

| Requirement | Field(s) |
|---|---|
| parent counts | `parent_retrieved_count`, `parent_normalized_count`, `parent_upserted_count` |
| child counts | `child_retrieved_count`, `child_normalized_count`, `child_upserted_count`, `child_errors_count` |
| **projection error counts** | **`projection_error_count`** (NEW — count of `*_projection_error` entries) |
| redacted error details | `redacted_errors` (each entry names its family; no raw text) |

`projection_error_count` is computed in the success path from `redacted_errors`. The
fail-closed early returns keep it at `0`. CLI `procore live sync … --json` surfaces it
(verified: a gated/unverified financial sync returns `projection_error_count: 0`,
`no_live_call_performed: true`).

## 3. Live-promotion status — operator-gated (deferred with reason)

No financial endpoint is `live_verified=True` (all 32 remain fail-closed). Promotion
requires real Procore smoke evidence + operator action and is **out of scope** under the
standing no-live-traffic rule, so the required cadence runs against **zero** endpoints:

| Endpoint family | Endpoints | live_verified | Live cadence |
|---|---|---|---|
| owner / commitment / invoice / rfq-change-event / budget | 31 implemented | False | **deferred — operator-gated** |
| budget-details | 1 | False (non-routable sentinel) | n/a |

The `smoke → apply → apply(larger) → rerun(idempotency)` cadence is executed by an
operator once an endpoint is promoted with smoke evidence; the commands are recorded in
the prompt for that future run. The dispatch chain, idempotency, and projection-failure
isolation are proven here **without live traffic** via synthetic-transport tests (a
test-only in-memory adapter promotion — the on-disk registry is never mutated).

## 4. Synthetic chain / idempotency / isolation (tests/test_procore_live_sync_phase05_chain.py)

Drives `run_live_sync(endpoint="prime-contracts", apply=True, sqlite_only=True,
transport=_FakeTransport(payload))` with the adapter promoted in-memory:
- **Full chain** — asserts the latest-state row (`procore_live_records`), history
  (`procore_live_record_snapshots`), the financial projection
  (`procore_financial_contracts` row + amount facts `grand_total` /
  `original_contract_sum` / `retainage_percent`), and a `success` receipt with
  `parent_upserted_count == 1` and `projection_error_count == 0`.
- **Idempotency** — identical re-sync: contract rows stay at 1, live records at 1,
  amount-fact count stable (deterministic ids → upserts, no duplicates).
- **Projection-failure isolation** — monkeypatch `project_owner_contract_family` to
  raise; the latest-state row + history are still written, the run reports
  `partial_success` with `projection_error_count >= 1` and a redacted
  `owner_projection_error` detail, and `procore_financial_contracts` is empty.

## 5. No-raw/no-secret SQL probe (tests/test_procore_financial_tables_no_raw_secret.py)

Projects deliberately leaky synthetic payloads (email, `Bearer …`, a PEM line, a
signed-URL `…?sig=…&token=…`, raw URLs) through every family, then enumerates all
`procore_financial_*` tables (`sqlite_master LIKE`) and scans every string cell:
- **Forbidden patterns** (zero matches required): `sig=`, `token=…`, `Bearer …`,
  `-----BEGIN`, `access_token`/`refresh_token`/`client_secret`, `https?://`, bare email.
- **Structural guards:** every row has `raw_body_persisted == 0`, and (where present)
  `redaction_applied == 1`.

**Finding fixed during this sweep:** the probe revealed `_redact_excerpt` /
`mask_excerpt` masked emails/phones/URLs but **not** `Bearer` tokens or PEM blocks, so
adversarial text in a `title_redacted` / `description_summary_json` excerpt survived.
Both maskers now also mask `Bearer …` → `[token]` and `-----BEGIN…` → `[pem]`
(`procore/normalizers/financial.py`, `store/procore_financials.py`). Probe now passes
with 0 findings across all financial tables.

## 6. Verification run

- `ruff check .` clean; `ruff format` clean on edited source; `mypy src` → no issues in 114 source files.
- `pytest -m "not integration and not live and not manual"` → **1221 passed, 1 skipped, 1 deselected** (was 1217; +4 new tests). Repo-wide sensitive scan (`test_repo_sensitive_scan`) still passes (synthetic secrets are assembled at runtime, not committed as literals).
- Fail-closed unchanged: `procore live endpoints list --json` → 27 verified / 32 unverified / 59 total.

## 7. Acceptance criteria status

| Criterion | Status |
|---|---|
| Promoted endpoints have smoke/apply/idempotency evidence | ✅ 0 promoted → operator-gated (§3); chain/idempotency proven synthetically (§4) |
| Projection failures captured without breaking latest-state sync | ✅ guarded blocks + `projection_error_count`; isolation test (§4) |
| No raw bodies/secrets/signed URLs in persisted financial tables | ✅ SQL probe 0 findings + Bearer/PEM masking hardened (§5) + `raw_body_persisted=0` |
