# Phase 06B — Prompt 00: Current-HEAD Procore Rebaseline

**Status:** COMPLETE — baseline captured, no objective-changing contradiction found.
**Run date:** 2026-05-30
**Purpose:** Establish current repo truth for the Procore subsystem at the actual HEAD
*before* any Phase 06B implementation begins. This is a no-op/check step that gates the
remaining Phase 06B prompts (01–16). It produces evidence only — no code changes, no
features, no schema migrations, no live Procore calls.

---

## 1. Repository state

| Field | Value |
| --- | --- |
| Branch | `main` |
| HEAD SHA | `f3cc0e189870fec4c452362cebaa69c2bc37c3a4` |
| HEAD subject | `phase-06a prompt-17: final validation closeout (CLOSED · schema V19)` |
| Tree clean? | **No** — pre-existing unrelated modifications (see below) |
| `HB_PROCORE_LIVE` | **unset** throughout this run |
| Live Procore call performed? | **No** |

### Recent commits (last 10)

```
f3cc0e1 phase-06a prompt-17: final validation closeout (CLOSED · schema V19)
c40f53b phase-06a prompt-16: end-to-end pilot & no-writeback/no-secret proof
f29db81 phase-06a prompt-15: operational cli & runbooks
a89ccd1 phase-06a prompt-14: source-linked retrieval proof
f80b34f phase-06a prompt-13: obsidian source manifests & project file registers
634af7f phase-06a prompt-12: sensitive file review routing
378e153 phase-06a controlled download + bounded extraction (schema V19)
a7df1e4 phase-06a ingestion eligibility policy: pre-download/extraction gate (schema V18)
a4167e6 phase-06a project-aware file matching: deterministic + heuristic matcher (schema V17)
35e4271 phase-06a delta sync hardening: incremental V5 sync + stale-token recovery + raw-link redaction
```

### Pre-existing working-tree changes (NOT produced by this prompt)

```
 M docs/evidence/construction-intelligence-phase-06-email/13-operational-obsidian-preview.md
 M docs/evidence/construction-intelligence-phase-06-email/13-operational-review-queue-proof.md
 M docs/evidence/construction-intelligence-phase-06-email/13-operational-workflow-pilot-dry-run.json
 M docs/evidence/construction-intelligence-phase-06-email/13-operational-workflow-pilot-index-proof.md
 M docs/evidence/mvp-local-runtime/outputs/06-harness-success.marker
 M docs/evidence/mvp-local-runtime/outputs/scan-sensitive.json
 M docs/evidence/remediation/prompt-05-delegated-graph-proof/summary.json
?? .code-graph/
```

These belong to Phase 06 (email), the MVP local-runtime bundle, and a remediation bundle,
plus the untracked `.code-graph/` index directory. They are **outside Procore scope** and
are excluded from this prompt's commit.

**Finding:** The Phase 06/06A (email/Graph/file) commits that landed after Phase 05's
closeout did **not** alter Procore state — all Procore validation below is green and the
held-endpoint disposition is unchanged from Phase 05.

---

## 2. Components inspected

| Area | Path | Note |
| --- | --- | --- |
| README phase ledger | `README.md` | Procore phases 04A/04B/05 recorded as the prior baseline |
| Architecture — live sync | `docs/architecture/14-procore-live-sync-phase-04a.md` | Phase 04A GET-only sync |
| Architecture — second brain | `docs/architecture/15-procore-second-brain-phase-04b.md` | V7 history/enrichment |
| Architecture — financials | `docs/architecture/16-procore-financials-phase-05.md` | V8/V9 contracts & billing |
| Operator runbook | `docs/operations/procore-operator-runbook.md` | live-gate + dry-run posture |
| Endpoint registry | `src/hb_assistant/procore/endpoints.py` | canonical endpoint list |
| Live sync | `src/hb_assistant/procore/sync.py` | dry-run default; `--apply` requires `HB_PROCORE_LIVE=1` |
| Live gate | `src/hb_assistant/procore/live_gate.py` | exact `HB_PROCORE_LIVE=1` opt-in |
| CLI surface | `src/hb_assistant/cli/procore.py` | `validate`, `live endpoints list`, sync/auth/tools groups |
| Migrator | `src/hb_assistant/store/migrator.py` | additive V1…V19; Procore = V6–V9 |
| Obsidian outputs | `src/hb_assistant/procore/obsidian.py`, `obsidian_register.py` | deterministic, marker-bounded, redacted |
| Financial query/projection | `src/hb_assistant/store/procore_financial_projection.py`, `procore_financials.py` | read models |

---

## 3. Validation results (no live calls)

All commands run via `.venv/bin/` with `HB_PROCORE_LIVE` unset.

| # | Command | Exit | Result |
| --- | --- | --- | --- |
| 1 | `hb-assistant procore validate --json` | `0` | `ok=true`, **28/28 checks passed**, strict=false |
| 2 | `hb-assistant procore live endpoints list --json` | `0` | `ok=true`, **59 endpoints** (56 live-eligible, 3 held) |
| 3 | `python -m pytest -m "not live" tests/test_procore*.py` | `0` | **709 passed, 1 skipped, 1 deselected** |
| 4 | `ruff check src/hb_assistant/procore src/hb_assistant/cli/procore.py` | `0` | All checks passed |
| 5 | `mypy src` | `0` | Success: no issues in 142 source files |

### 3.1 `procore validate` — 28/28 checks passed

Notable check details:
- `sqlite_schema_at_expected_version` → `{"current_version": 19, "expected_minimum": 5}`
- `procore_tables_present` → tables created on demand by the sync coordinator; absence on a
  fresh checkout is expected (`all_present=false` is normal, no DB has been written).
- `endpoint_verification_metadata_complete` → 13 Phase-01-included endpoints, `incomplete: []`.
- `live_eligibility_blocks_ineligible` → no ineligible endpoints leaked.
- Redaction, Obsidian templates (10 artifact types), live-env-gate, and
  `live_commands_require_env_var` all PASS.

Full output: [`procore-validate-current-head.json`](./procore-validate-current-head.json).

### 3.2 `procore live endpoints list` — 59 endpoints, 3 held

Guardrails block reported by the command:
`external_systems=read_only, writeback=none, metadata_only=true, live_calls_disabled=true,
correspondence_excluded=true, schedule_tasks_deferred=true`.

| Disposition | Count |
| --- | --- |
| `live_eligible` / `live_verified=true` | 56 |
| `not_live_verified` (held) | 3 |
| **Total** | **59** |

**The 3 held endpoints** (Phase 05 fail-closed shells; carried forward unchanged):

| endpoint_id | state | verification_reason |
| --- | --- | --- |
| `purchase-order-detail-line-items` | `not_live_verified` | `phase05_shell_pending_live_smoke` |
| `budget-change-line-items` | `not_live_verified` | `phase05_shell_pending_live_smoke` |
| `budget-details` | `not_live_verified` | `phase05_unresolved_path_fail_closed_prompt00-3.2` |

Full output: [`procore-live-endpoints-current-head.json`](./procore-live-endpoints-current-head.json).

---

## 4. Schema & migration status

- **Current SQLite schema version: V19** (confirmed by `validate`'s
  `sqlite_schema_at_expected_version` check: `current_version=19`).
- **Procore-specific migrations** (additive, in `src/hb_assistant/store/migrator.py`):
  - **V6** — `procore_live_sync`: live-sync baseline (`procore_live_sync_runs`,
    `procore_live_records`, `procore_live_sync_watermarks`) with redaction/no-raw-body CHECKs.
  - **V7** — `procore_history_and_enrichment`: snapshots, change events, timelines, entity
    enrichment, and inspection projection tables.
  - **V8** — `procore_financials`: contracts/line-items/change-orders/payment-apps/budget
    views (money stored as TEXT for decimal precision; CHECK-constrained).
  - **V9** — `procore_billing_and_subcontractor_invoices`: billing periods + subcontractor
    invoices.
- V10–V19 are non-Procore (Graph/email/file phases). **No Procore migration is added by this
  prompt.** The next additive Procore migration, if needed by a later 06B prompt, will be
  **V20** (V19 is already taken).

---

## 5. Repo-vs-package reconciliation (recorded, not fixed)

Per the prompt header ("Repo truth wins over package instructions"), the following deltas
between the Phase 06B package narrative and repo truth are **recorded here only**. None
changes the phase objective; no stop condition is triggered.

| # | Package narrative | Repo truth | Disposition |
| --- | --- | --- | --- |
| 1 | "migrator at V18+, next migration V19" | Schema is already at **V19** | Record only. Next Procore migration = V20. |
| 2 | CLAUDE.md describes schema "V1…V7" | Actual max is **V19** | Stale doc. Fixing is **Prompt 01** ("stale comment/doc reconciliation") scope, not this prompt. |
| 3 | "59 endpoints / 56 verified / 3 fail-closed" | `live endpoints list` surfaces **exactly 59 / 56 / 3** | **Matches.** (The raw adapter table in `endpoints.py` has more rows; the canonical command output of 59 is authoritative.) |
| 4 | "held endpoints" terminology | Repo state value is `not_live_verified` (no `held` status enum) | Terminology mapping only: package "held" == repo `not_live_verified`. |

**Conclusion:** Current repo truth is consistent with the Phase 06B objective. The Procore
subsystem is green, the held-endpoint disposition is exactly as the package expects, and the
only drift (CLAUDE.md schema version text, item 2) is explicitly deferred to Prompt 01.
**Proceed to Prompt 01.**

---

## 6. Guardrail attestations for this run

- **No Procore writeback** and **no Microsoft 365 writeback** introduced (read-only commands only).
- **No live Procore call** performed; `HB_PROCORE_LIVE` unset the entire run.
- **No raw Procore response body** persisted (the two JSON artifacts are command outputs:
  validation results and the static endpoint registry — neither contains response payloads).
- **No secrets emitted:** both JSON artifacts were scanned for `authorization|bearer|
  refresh_token|client_secret|access_token|signed|PEM` value patterns — only check *names*
  and boolean capability flags matched; no token, header, or secret value is present.
- **No legal/claims/financial/safety/entitlement/schedule-impact determination** made.
- **No code, schema, or Procore-permission change** made by this prompt.
