# Phase 06B — Prompt 01: Endpoint Ledger & Stale-Doc Reconciliation

**Status:** COMPLETE.
**Run date:** 2026-05-30
**Parent HEAD at start:** `1891815` (`phase-06b prompt-00: current-head procore rebaseline`)
**Objective:** Make Procore endpoint promotion status machine-readable, and reconcile
genuinely stale current-state docs against repo truth — without rewriting historical
narrative, mutating the registry, or making any live Procore call.

---

## 1. What was built — machine-readable promotion ledger

A new deterministic derivation layer projects the canonical registry into a promotion
ledger. The registry (`src/hb_assistant/procore/endpoints.py`, the `EndpointAdapter` rows)
is repo truth and is **unchanged** — the ledger is a read-only one-to-one projection.

- **`src/hb_assistant/procore/endpoint_ledger.py`** — `build_promotion_ledger()`; pure, no
  clock (dates are parsed only from `verification_reason`), no I/O, no live call.
- **`src/hb_assistant/cli/procore.py`** — new `procore live endpoints ledger --json` command
  (mirrors `live endpoints list`; reuses `_emit` + `_GUARDRAILS`).
- **`tests/test_procore_endpoint_ledger.py`** — 6 tests (count equality, partition, held
  fail-closed, required-fields, promoted-date, CLI parity).

### Ledger row schema (8 required fields) and derivation rules

| field | source / derivation |
| --- | --- |
| `endpoint_id` | `adapter.endpoint_id` (passthrough) |
| `family` | `adapter.family` (passthrough) |
| `live_verified` | `adapter.live_verified` — live verification status (repo truth) |
| `promotion_status` | `"promoted"` if `live_verified` else `"held"` |
| `verification_reason` | `adapter.verification_reason` (passthrough) |
| `evidence_path` | reason starts `phase05` → `…/construction-intelligence-phase-05-financials/`; else `…/construction-intelligence-phase-04a/` (both bundles exist in-repo) |
| `last_verified_date` | first `\d{4}-\d{2}-\d{2}` in `verification_reason`, else `null` |
| `next_step` | promoted → `none — live-verified; monitor for drift`; held + `unresolved_path` → resolve path + permission (fail-closed); held (shell) → operator bounded live smoke (fail-closed) |

Status is mirrored from `live_verified` only — **no live probe was performed**, so any
non-verified endpoint is reported `held` (fail-closed), per the prompt's stop condition.

---

## 2. Count-equality proof

`ledger_row_count` is `len(endpoints.list_all())` by construction (one-to-one projection),
asserted by `test_ledger_row_count_equals_registry_count`.

From `procore live endpoints ledger --json` (exit 0):

```
registry_endpoint_count = 59
ledger_row_count        = 59
promoted_count          = 56
held_count              = 3
```

Evidence path distribution: 27 → phase-04a bundle, 32 → phase-05-financials bundle (= 59,
matching doc 16's "27 Phase 04A/04B operational + 32 Phase 05 financial rows").

Full artifact: [`endpoint-promotion-ledger.json`](./endpoint-promotion-ledger.json).

---

## 3. Held-endpoint fail-closed proof

The 3 held endpoints retain explicit fail-closed status (asserted by
`test_held_endpoints_retain_fail_closed_status`): each has `promotion_status="held"`,
`live_verified=false`, `last_verified_date=null`, and a `next_step` that names fail-closed.

| endpoint_id | verification_reason | next_step |
| --- | --- | --- |
| `purchase-order-detail-line-items` | `phase05_shell_pending_live_smoke` | operator-run bounded live smoke …; remains fail-closed until verified |
| `budget-change-line-items` | `phase05_shell_pending_live_smoke` | operator-run bounded live smoke …; remains fail-closed until verified |
| `budget-details` | `phase05_unresolved_path_fail_closed_prompt00-3.2` | resolve API path and obtain permission grant …; remains fail-closed until verified |

---

## 4. Stale-doc reconciliation — decisions (edited vs preserved)

Per "Update docs only where repo truth is clear" and "Preserve historical evidence; do not
rewrite history," each candidate was reconciled against repo truth:

| Target | Finding | Action |
| --- | --- | --- |
| `docs/architecture/16-procore-financials-phase-05.md` top banner (L3–12) | Already current-accurate (56/59, 29 financial promoted 2026-05-29, the 3 named held endpoints) | **No correction needed.** Added one block-quote pointing to the machine-readable ledger and clarifying that the per-prompt narrative below records each Prompt's *landing* state. |
| doc 16 per-prompt passages ("stay `live_verified=False`", Prompts 04–09) | **Historical narrative of a CLOSED phase** — accurate description of each Prompt's landing state before later live-smoke promotion | **Preserved as-is** (editing would rewrite implementation history). |
| `CLAUDE.md` `store/` note | Said "versioned schema **V1…V7**" — stale; actual max is **V19** (confirmed Prompt 00) | **Fixed** → "V1…V19 … Procore-specific migrations span V6–V9". One-line factual correction. |
| `README.md` Phase 05 line | Already accurate ("56 / 59 endpoints live-verified, 3 fail-closed") | No change. |
| `docs/operations/procore-operator-runbook.md` | No Phase 05 financial status claims | No change. |
| `src/hb_assistant/procore/endpoints.py` (registry) | Accurate (it *is* repo truth) | No change. |
| `docs/evidence/construction-intelligence-phase-05-financials/**` | Historical evidence; per-Prompt "pending/shell/fail-closed" language is the intended narrative arc | **Preserved** (do not edit). |

**Net stale-doc surface:** the explorer's initial "6 stale doc-16 passages" finding was
narrowed by repo-truth reconciliation to (a) one new ledger pointer in doc 16 and (b) one
factual schema-version fix in CLAUDE.md. The per-prompt narrative is historical, not stale.

---

## 5. Validation (no live calls; `HB_PROCORE_LIVE` unset)

| Command | Exit | Result |
| --- | --- | --- |
| `pytest -q tests/test_procore_endpoint_ledger.py` | 0 | 6 passed |
| `ruff check src/hb_assistant/procore/endpoint_ledger.py src/hb_assistant/cli/procore.py` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues in 143 source files |
| `hb-assistant procore live endpoints ledger --json` | 0 | 59 rows, 56 promoted, 3 held |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |
| `pytest -m "not live" tests/test_procore*.py` | 0 | 715 passed, 1 skipped, 1 deselected (no regression; +6 new) |

---

## 6. Guardrail attestations

- **No Procore/M365 writeback**; the ledger command is read-only with no write path.
- **No live Procore call** (`HB_PROCORE_LIVE` unset); endpoint status mirrors the registry,
  no probes — non-verified endpoints reported `held` (fail-closed), per the stop condition.
- **No raw response bodies, tokens, signed URLs, or PEMs** in `endpoint-promotion-ledger.json`
  (secret-scanned: no matches). The ledger carries only registry metadata + derived fields.
- **No legal/claims/financial/safety/entitlement/schedule-impact determination** — the
  ledger is an intelligence/review aid (promotion status + next step only).
- **No registry promotion/demotion** and **no rewrite of historical narrative or evidence.**
