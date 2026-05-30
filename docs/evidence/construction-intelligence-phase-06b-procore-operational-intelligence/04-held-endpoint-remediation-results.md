# Phase 06B — Prompt 04: Held Endpoint Remediation & Disposition

**Status:** COMPLETE — all three held endpoints explicitly preserved fail-closed.
**Run date:** 2026-05-30
**Parent HEAD at start:** `9a638e6` (`phase-06b prompt-03: n+1 rate-limit & cadence hardening`)
**Objective:** Resolve or explicitly preserve fail-closed status for the three held endpoints,
with a machine-readable disposition and the human action each requires. No live Procore call
(`HB_PROCORE_LIVE` unset); no writeback; no permission change; no path guessing; no promotion.

---

## 1. Per-endpoint inspection & determination

Blockers are cited from the **historical** Phase 05 closeout evidence
(`docs/evidence/construction-intelligence-phase-05-financials/12-final-validation-coverage-evidence-and-closeout.md`,
not edited). Registry state from `src/hb_assistant/procore/endpoints.py`.

### `purchase-order-detail-line-items` → `fail_closed_pending_live_smoke`
- **Registry:** `live_verified=False`, `verification_reason="phase05_shell_pending_live_smoke"`,
  path `/rest/v1.0/purchase_order_contracts/{purchase_order_contract_id}/line_item_contract_details`.
  In `_N1_CHILD_ENDPOINTS`; normalizer **registered** (offline machinery ready).
- **Blocker:** per-PO **404 data condition** — the detail path 404s for the *sampled* POs whose
  `/line_items` sibling succeeds, i.e. those POs simply have no detail items. The path is correct;
  this is a data condition, not a path bug.
- **Determination:** cannot promote here — promotion requires a live bounded smoke (no live env).
  **Operator action:** run a bounded live smoke against a PO known to have contract-detail items
  (or an operator-supplied real payload), then re-probe and promote on a clean projection.

### `budget-change-line-items` → `fail_closed_permission_blocked`
- **Registry:** `live_verified=False`, `verification_reason="phase05_shell_pending_live_smoke"`,
  path `/rest/v2.0/companies/{company_id}/projects/{project_id}/budget_changes/adjustment_line_items`,
  `parent_record_id_field=None` (a top-level project-scoped list, correctly **not** in
  `_N1_CHILD_ENDPOINTS`); normalizer **registered**.
- **Blocker:** live **403 FORBIDDEN** — the Procore token/role lacks budget-changes
  adjustment-line-items access.
- **Determination:** cannot promote — bypassing the permission blocker is a stop condition, and
  this tool does not change Procore permissions. **Operator action:** a Procore administrator must
  grant the integration user's role access to budget changes (adjustment line items) for the
  company/project, then re-probe.

### `budget-details` → `fail_closed_unresolved_path`
- **Registry:** `live_verified=False`, `verification_reason="phase05_unresolved_path_fail_closed_prompt00-3.2"`,
  `path_template="unresolved:budget-details"` (non-routable sentinel); normalizer **intentionally
  not registered**.
- **Blocker:** no resolved REST path in the source reference (Prompt 00 §3.2).
- **Determination:** cannot promote — guessing the path is a stop condition; the sentinel guarantees
  the id can never transport while staying catalog-visible (Phase 05 chose preservation over
  retirement). **Operator action:** obtain the authoritative path from Procore (likely a merge into
  `budget-detail-rows`) with an operator-supplied real path — the path will not be guessed.

---

## 2. Stop-condition mapping (why no promotion)

| Endpoint | Remaining blocker | Stop condition that forbids the workaround |
| --- | --- | --- |
| purchase-order-detail-line-items | needs live smoke (no live env) | promotion needs live bounded smoke evidence — unavailable here |
| budget-change-line-items | 403 permission | "bypassing a permission blocker" |
| budget-details | unresolved path | "promotion requires guessing a path" |

No endpoint was promoted, retired, or merged; no `live_verified` flag flipped. The
"if any endpoint is promoted → live smoke + sync + idempotent re-run evidence" clause is moot.

---

## 3. Ledger updated with disposition

`endpoint_ledger.py` now adds, per row, a `disposition` (`"promoted"` for live-verified, else the
held endpoint's explicit disposition) and a `held_detail` (`{blocker, operator_action, evidence}`
for held rows, else `None`). A small `_HELD_DISPOSITION` map carries the three dispositions above.
The authoritative ledger artifact (`endpoint-promotion-ledger.json`) was regenerated to carry these
fields, and the held subset is captured in
[`held-endpoint-disposition.json`](./held-endpoint-disposition.json)
(`held_count: 3`, `promoted_this_prompt: 0`, `all_fail_closed: true`, `live_call_performed: false`).

A **drift guard** test asserts `_HELD_DISPOSITION` keys equal the registry's held set, so any future
held endpoint must receive an explicit disposition.

---

## 4. Fail-closed proof

`tests/test_procore_live_sync_unverified_fail_closed.py` now parametrizes
`_UNVERIFIED_IDS = (purchase-order-detail-line-items, budget-change-line-items, budget-details)`:
each runs `run_live_sync` with the live gate satisfied (`HB_PROCORE_LIVE`, token, `--confirm-live-get`)
and a transport that raises if hit, and asserts `state="not_live_verified"`,
`no_live_call_performed=True`, `request_count=0`, `endpoint_unverified_for_live` in `reason_codes`,
and that the transport was **never** invoked. This proves the held endpoints fail closed without any
live call when not promoted.

---

## 5. Validation (no live calls)

| Command | Exit | Result |
| --- | --- | --- |
| `pytest tests/test_procore_endpoint_ledger.py tests/test_procore_live_sync_unverified_fail_closed.py` | 0 | 15 passed (disposition + drift guard + 3 fail-closed) |
| `pytest -m "not live" tests/test_procore*.py` | 0 | 736 passed, 1 deselected (no regression; +6) |
| `ruff check src/hb_assistant/procore/endpoint_ledger.py` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues in 143 source files |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |
| `hb-assistant procore live endpoints ledger --json` | 0 | held rows carry `disposition` + `held_detail` |

---

## 6. Guardrail attestations

- **No Procore/M365 writeback**; **no live Procore call** (`HB_PROCORE_LIVE` unset); held endpoints
  and the `unresolved:budget-details` sentinel untouched; no `live_verified` flip.
- **No Procore permission change** — the 403 disposition documents the required **admin** action.
- **No path guessing** — `budget-details` stays a non-routable sentinel.
- **No raw response bodies, tokens, signed URLs, or PEMs** in either artifact (secret-scanned, 0
  findings); dispositions are metadata/operator-guidance only.
- **No legal/claims/financial/safety/entitlement/schedule-impact determination** — dispositions are
  intelligence/review aids.
- **Historical Phase 05 evidence preserved** (cited, not edited).
