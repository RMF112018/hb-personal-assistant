# Phase 05 Evidence — Prompt 12: Final Validation, Coverage Evidence & Closeout

## Objective

Perform full repo-truth validation of the Procore contract / financial endpoint
implementation (schema, sync, enrichment, query, evidence, guardrails) and close
Phase 05. Disposition: **Phase 05 CLOSED** with a remediation list for the 3 held
(fail-closed) endpoints — none of Prompt 12's "Do Not Close If" blockers are tripped.

## Repo Truth

- Pre-closeout SHA: `6d77d35` (`fix(procore): flat payment-applications path + rfq-child contract_id param; promote 3 (56 verified)`)
- Ending SHA: *(this closeout commit — see git log after commit)*
- Branch: `main`
- Dirty tree before: clean except untracked `.code-graph/` (pre-built code-graph index; left untouched, not part of this phase)
- Dirty tree after: only this closeout doc + `docs/architecture/16-procore-financials-phase-05.md` + `README.md` (pytest-mutated evidence fixtures restored before staging); `.code-graph/` remains untracked.

## Files Changed

- `docs/evidence/construction-intelligence-phase-05-financials/12-final-validation-coverage-evidence-and-closeout.md` (new — this file)
- `docs/architecture/16-procore-financials-phase-05.md` (status → closed; closeout cross-ref)
- `README.md` (Phase 05 line added to Repository Status ledger)

No source / schema / test changes — this is a validation-and-evidence closeout. The
implementation landed in Prompts 01–11 + the live-promotion / N+1 passes (commits
`dbd003b`…`6d77d35`).

## Validation

All checks run inside `.venv`. `HB_PROCORE_LIVE` unset throughout — **no live Procore
HTTP performed** (Prompt 12 requires none).

```text
$ python -m pytest -q --no-header
  exit 0 · 1246 collected · 2 skipped · ~1244 passed
  (default-safe markers; live/integration/manual not selected; no Procore HTTP)

$ ruff check .
  All checks passed!

$ mypy src
  Success: no issues found in 115 source files
  # Note: package prompt lists `mypy .`; repo convention (CLAUDE.md, pyproject
  # [[tool.mypy.overrides]]) holds an intentionally partial module set to strict
  # mypy and runs `mypy src`. `mypy src` is the authoritative in-scope check.

$ python -m compileall -q src tests
  exit 0

$ hb-assistant procore validate --json
  ok=true · summary={total:28, passed:28, failed:0}
  (seed contract 16 endpoints / company 5280; 4 pilot project mappings)

$ hb-assistant procore mapping validate --json
  exit 0 · company 5280 (HB Construction) · total=4 · by_status={pilot:4}
  (tropical→2525840, pga-modern-garage→2091445, …; all mapped=true)

$ hb-assistant procore live endpoints list --json
  ok=true · total=59 · live_verified=56 · unverified=3
  guardrails: external_systems=read_only, writeback=none, metadata_only=true,
              live_calls_disabled=true
```

## V8 (+V9) Financial Table Inventory

15 `procore_financial_*` tables present (migration **V9**; V8 created 13, V9 added
`procore_financial_billing_periods` + `procore_financial_subcontractor_invoices`).
Live row counts from the local app-support SQLite (outside repo,
`~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`):

| Table | Rows | Introduced |
|---|---:|---|
| procore_financial_contracts | 74 | V8 |
| procore_financial_line_items | 101 | V8 |
| procore_financial_change_orders | 100 | V8 |
| procore_financial_change_order_line_items | 100 | V8 |
| procore_financial_payment_applications | 0 | V8 |
| procore_financial_invoice_items | 10 | V8 |
| procore_financial_rfqs | 7 | V8 |
| procore_financial_change_events | 100 | V8 |
| procore_financial_budget_views | 6 | V8 |
| procore_financial_budget_rows | 5 | V8 |
| procore_financial_amount_facts | 1317 | V8 |
| procore_financial_budget_changes | 195 | V8 |
| procore_financial_compliance_documents | 73 | V8 |
| procore_financial_billing_periods | 21 | **V9** |
| procore_financial_subcontractor_invoices | 100 | **V9** |
| **Total financial rows** | **2209** | |

`procore_attachment_refs`: 81 rows (path-only references; no signed-URL query strings).
`procore_financial_payment_applications` is empty on the pilot project (valid empty —
see Limitations).

## Endpoint Coverage Summary

- Registry total: **59** (27 Phase 04A/04B operational + 32 Phase 05 financial).
- `live_verified=True`: **56**.
- `live_verified=False` (fail-closed): **3**.
- Phase 05 financial endpoints promoted this phase (`_PHASE05_PROMOTED`): **29**, covering
  prime/commitment/PO contracts + line items + attachments, prime/commitment change
  orders + CO line items, billing periods, subcontractor invoices + child items, RFQs +
  responses/quotes, change events + comments, commitment compliance, budget
  views/rows/detail columns+rows/modifications/change-history, payment-applications.
- Parent→child linkage: N+1 children are fetched per-parent with parent-id tagging
  (`live_sync.py` `_N1_CHILD_ENDPOINTS` / `_resolve_child_path`), so child records are
  linked to their parents and not double-counted.

## Live Verification Summary

29 financial endpoints were promoted via the probe-first harness (in-memory promote →
real bounded `run_live_sync` into a throwaway DB → cadence: smoke → sync → idempotent
re-run) against the `tropical` pilot (procore_project_id 2525840, company 5280), GET-only.
Per-endpoint acceptance + cadence tables live in evidence:

- `12-live-promotion-parentless-financial-endpoints.md`
- `13-reconcile-change-events-and-budget-change-history.md`
- `14-n1-child-orchestration-and-child-promotion.md`
- `15-n1-child-project-id-fix-and-subcontractor-invoice-children.md`
- `16-remaining-child-fixes-payment-applications-and-rfq-children.md`

## Command Proof (local-only — no Procore call)

All financial query / register commands are SQLite-only (read `procore_financials` /
`procore_enrichment`; never import `ProcoreHTTPClient`, never call `require_live_env()`).

```text
$ hb-assistant procore live financial summary  --help   → exit 0  ("…Local SQLite only.")
$ hb-assistant procore live financial contracts --help  → exit 0
$ hb-assistant procore live financial changes   --help  → exit 0
$ hb-assistant procore live financial invoices  --help  → exit 0
$ hb-assistant procore live financial budget    --help  → exit 0
$ hb-assistant procore live financial risk      --help  → exit 0
$ hb-assistant procore obsidian financial       --help  → exit 0

# Representative JSON run with HB_PROCORE_LIVE UNSET (proves no live dependency):
$ hb-assistant procore live financial summary --project tropical --json
  ok=true · counts={contracts:74, subcontractor_invoices:100, rfqs:7,
                    change_events:100, budget_changes:195, open_financial_actions:804}
```

## No-Secret / No-Raw-Body Proof

Read-only SQL probe over all 15 `procore_financial_*` tables (2209 rows scanned):

- Secret/URL pattern scan — `Bearer <token>`, `-----BEGIN` (PEM), `?sig=`,
  `X-Amz-*`, email, `https://…?query`: **0 findings** in every table.
- `raw_body_persisted` distinct values: **0** across all populated tables.
- `redaction_applied` distinct values: **1** across all populated tables.
- Attachment refs reduced to path-only (no signed-URL query strings).

No tokens, OAuth payloads, Authorization headers, signed URLs, raw response bodies,
free-text notes, addresses, phones, emails, or personal PII are persisted or emitted.
Financial amounts are preserved as structured business facts (per Phase 04B posture).

## Limitations / Deferrals — Remediation List (3 held endpoints)

All 3 are **fail-closed by design** (external/operator-gated), not validation failures.
They remain `live_verified=False`; live_sync fails closed before any transport.

1. **purchase-order-detail-line-items** — `verification_reason=phase05_shell_pending_live_smoke`.
   Path `/rest/v1.0/purchase_order_contracts/{id}/line_item_contract_details` 404s for the
   sampled POs (the `/line_items` sibling succeeds, so the sampled POs simply have no
   detail items — a per-PO data condition, not a path bug).
   *Remediation:* sample a PO that has contract-detail items (or operator-supplied real
   payload), re-probe, promote on a clean projection.
2. **budget-change-line-items** — `phase05_shell_pending_live_smoke`. Live **403 FORBIDDEN**;
   the Procore token/role lacks budget-changes adjustment-line-items access.
   *Remediation:* confirm/grant the Procore permission, then re-probe.
3. **budget-details** — `verification_reason=phase05_unresolved_path_fail_closed_prompt00-3.2`;
   `path_template=unresolved:budget-details` (permanent non-routable sentinel, no resolved
   REST path). *Remediation:* resolve the correct endpoint (likely merge into
   budget-detail-rows) only with an operator-supplied real path — do not guess.

Other watch items (not blockers):
- Empty-on-pilot promotions (`payment-applications` = 0 rows; `rfq-responses` / `rfq-quotes`
  empty on pilot): normalizers/projections are unit-tested but not yet exercised against
  real records. Backfill against a project/period that has them.
- N+1 fan-out is rate-sensitive at large `--max-items`; keep child syncs bounded.

## Recommended Phase 06 Scope

1. Resolve the 3 held endpoints (data sample / permission grant / operator path), re-probe
   with the established probe-first harness, promote only clean matches.
2. Real-record backfill validation for the empty-on-pilot endpoints.
3. Financial enrichment / second-brain projection into Obsidian (roll-ups, exposure/risk
   surfacing) building on the V8/V9 ledger + amount-facts.
4. N+1 cadence hardening: a separate, smaller parent-count cap for child syncs to avoid
   transient 429s.

## "Do Not Close If" Blocker Checklist

- [x] Any required validation fails — **not tripped**: pytest exit 0, ruff/mypy/compileall clean, all 3 JSON validators ok.
- [x] Financial records only as latest-state JSON with no projection/query layer — **not tripped**: 15 projection tables + 7 SQLite-only query commands + Obsidian register.
- [x] Promoted endpoints lack live verification evidence — **not tripped**: 29 promotions documented in evidence 12–16 with cadence tables.
- [x] Child endpoints not linked to parents — **not tripped**: N+1 parent-id tagging in `live_sync.py`.
- [x] Duplicate commitment/PO data double-counted — **not tripped**: idempotent upserts (Prompt 10 idempotency sweep; `record_key`-keyed).
- [x] Query commands call Procore — **not tripped**: all query commands SQLite-only; `summary --json` runs with `HB_PROCORE_LIVE` unset.
- [x] Raw payloads / signed URLs / tokens / raw free text / personal PII persisted or emitted — **not tripped**: no-secret probe = 0 findings; `raw_body_persisted=0`, `redaction_applied=1`.

## Acceptance

- [x] Full validation green.
- [x] Closeout evidence complete (all Prompt 12 sections present).
- [x] All acceptance blockers checked (none tripped).
- [x] No raw payload body persisted.
- [x] No Procore writeback (GET-only; no live calls in this prompt).
- [x] **Phase 05 CLOSED** with a remediation list for the 3 fail-closed endpoints.
