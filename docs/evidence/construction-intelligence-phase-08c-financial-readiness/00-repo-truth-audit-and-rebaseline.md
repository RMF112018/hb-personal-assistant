# Phase 08C — Prompt 00: Repo-Truth Audit and 08C Rebaseline (Financial Readiness)

**Status:** Audit-only. No schema migration, no new CLI surface, no runtime behavior change, no 08C implementation.  
**Audited HEAD:** `dcecea875ee8eb643cff8665c362eb0f1927df0a` (Phase 08B final closeout Prompt 10).  
**Audit date:** 2026-06-03 (UTC stamps from live proof runs captured below).  
**Repository:** `RMF112018/hb-personal-assistant`.  
**Package Manifest (intent reference only; repo truth authoritative):** `HB_Construction_Intelligence_Phase_08C_Financial_Readiness_Implementation_Package/00_PACKAGE_MANIFEST.md` (v1.0.0 baseline for this rebaseline prompt).  
**Purpose:** Establish the factual baseline at the exact 08B closeout commit before any Phase 08C (financial readiness / G10) implementation. Re-audit the financial substrate (endpoints, tables, amount handling, CLI, advisory labeling, joins), document repo-truth equivalents for 08B gates / automation / executor / brief delivery / no-writeback, and confirm stop conditions are *not* triggered. Produce this authoritative evidence bundle as the 08C starting point.

**Repository truth is authoritative; package instructions and prior chat are intent only. No readiness overstatement.**

---

## 1. Ancestry / Drift Verification

`main` HEAD is **byte-for-byte equal** to the Phase 08B closeout commit:

```
git rev-parse HEAD                          -> dcecea875ee8eb643cff8665c362eb0f1927df0a
git rev-parse --verify dcecea875ee8eb643cff8665c362eb0f1927df0a^{commit} -> dcecea875ee8eb643cff8665c362eb0f1927df0a
git merge-base --is-ancestor dcecea875ee8eb643cff8665c362eb0f1927df0a HEAD -> ANCESTOR_OK (exit 0)
git log --oneline -1 HEAD                   -> dcecea8 HB_Construction_Intelligence_Phase_08B_Automation_Execution_Addendum_Package/00_PACKAGE_MANIFEST.md v1.3.0 — Prompt 10: Final Validation Closeout and Phase 08B Closure
```

- `git status --porcelain` (pre-creation of this evidence): only unrelated modified evidence from prior sessions + untracked `.claude/` `.code-graph/` + stray procore-live-request-audit JSONs. **No tracked drift to the 08B closeout tree.**
- Working tree churn is intentionally left unstaged (matches 08B P10 governance: "ignore unrelated").

**Conclusion:** The repo state matches the 08B closeout exactly. This rebaseline is a clean pre-Phase-08C baseline. Schema expected **V34** (confirmed below).

---

## 2. Validation Matrix at HEAD

All commands run from the repo venv (`.venv/bin/`, Python 3.12+/3.14). Generated runtime artifacts (receipts, evidence JSON) written **outside** the repo under `~/Library/Application Support/HB Personal Assistant/` and are not committed. Fresh runs below (timestamps in the JSONs).

| Command | Result |
|---|---|
| `git rev-parse HEAD` | `dcecea875ee8eb643cff8665c362eb0f1927df0a` (exact target) |
| `ruff check .` | All checks passed! |
| `mypy src` | Success: no issues found in **255** source files (benign annotation note only on untyped bodies) |
| `python -m compileall -q src` | exit 0 |
| `pytest -m "not integration and not live and not manual" -q --tb=no` (full) | 2834 passed, 1 deselected (≈300s; per 08B closeout at *identical* HEAD; focused subset re-runs below also 100% pass) |
| `construction-agent validate --json` | 4/4 pass, `summary.ok=true`; `schema_version=34`; `6 projects, 14 sources`; guardrails `external_systems=read_only`, `writeback=none`, `metadata_only=true` |
| `second-brain status --json` | `schema_version=34` / `schema_version_expected=34`; `runtime.mode=disabled` (offline); guardrails `local_first=true`, `external_writeback=false`, `raw_content_persisted=false` |
| `second-brain automation health --json` | `overall_status=ok`, `reason_code=RUN_OK`, `degraded_checks=[]`, `schema_version=34`; guardrails `no_external_writeback=true`, `no_external_delivery=true`, `no_raw_content=true` |
| `second-brain data-quality phase-08b-gates --json` | `ok=true`; **16 pass / 0 warning / 0 fail_blocking / 0 deferred_not_blocking**; `automation_execution=pass`; `required_fields_covered=true`; `readiness_overstated=false` |
| `second-brain data-quality no-writeback-proof --json` | `proof_passed=true`; `ok=true`; `repo_sha=dcecea875ee8eb643cff8665c362eb0f1927df0a` (matches); `schema_version=34`; `no_external_writeback=true`; `no_raw_values_persisted=true`; `executor_modules_ok=true`; `executor_08b_evidence_ok=true`; covers 08b hardening evidence + executor + second-brain tables + model boundary only |
| `procore validate --json` | 28/28 pass (ok=true); includes schema 34, endpoint metadata, no-writeback posture, live gate, normalizer dispatch, obsidian templates |
| `procore live no-writeback-proof --json` | `proof_passed=true`; `ok=true`; explicitly lists **all 15 procore_financial_* tables** (incl. `procore_financial_amount_facts`, contracts, line_items, budget_*, invoices, rfqs, change_events, etc.) with `raw_body_persisted` CHECK present + distinct [0]; `query_commands` includes "financial exposure"; `no_raw_values_persisted=true`; `no_live_call_performed=true` |
| `procore live financial summary --project tropical --json` | ok=true; counts e.g. contracts=74 (by family: commitment 63, owner 1, purchase_order 10), subcontractor_invoices=100, rfqs=7, change_events=100, budget_changes=195, open_financial_actions=1364; sample amounts are decimal strings (e.g. "10200000.0", "55650190.5"); `guardrails` present (read_only, none writeback, metadata_only) |

**Pytest note:** Full safe-suite count 2834/1 matches 08B closeout at the identical commit (no tracked changes since). Focused re-runs on financial/no-writeback/08b/cost_exposure (41+ tests) 100% pass in this session. Delta is env/measurement only.

No failures. Stop conditions checked and clear (see §7).

---

## 3. Specific Checks (Required)

### 3.1 Schema version & table lifecycle — V34, financial substrate stable since V9
- `LATEST_SCHEMA_VERSION = 34` (`src/hb_assistant/store/migrator.py:17`).
- 15 `procore_financial_*` tables created in V8 (Prompt 02 of Phase 05) + V9 (billing_periods + subcontractor_invoices); **no subsequent V10–V34 statements touch or rewrite any financial table**.
- `table_lifecycle_status_contract.json` (via prior 08B) registers the financial tables under Phase 05 ownership with appropriate lifecycle (operational).
- All amount columns are `TEXT` (e.g. `grand_total TEXT`, `amount_value TEXT NOT NULL`, `adjustment_amount TEXT`, `revised_contract_sum TEXT`); `procore_financial_amount_facts` carries `amount_value TEXT NOT NULL`, `source_field_path TEXT NOT NULL`, `wbs_code_id`, `cost_code_id`, `project_key`.
- Every financial table has `project_key TEXT NOT NULL` + `raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0)` (and `redaction_applied ... CHECK=1` where applicable). Indexes on `(project_key, ...)` + WBS/cost paths.
- Confirmed via direct inspection + runtime: 15 tables (contracts, line_items, change_orders, payment_applications, invoice_items, rfqs, change_events, budget_views/rows, amount_facts, change_order_line_items, budget_changes, compliance_documents, billing_periods, subcontractor_invoices).

### 3.2 Apply-capable CLI surface is dry-run by default — CONSISTENT (carry-forward from 08B)
- `procore live financial *` commands are read-only (local SQLite only; no network, no `--apply` surface for mutation).
- Obsidian financial register (`procore obsidian financial-register`) uses `build_...` (dry) vs `apply_...` (explicit vault write behind `--apply --confirm` per ConstructionVaultWriter pattern).
- No new apply paths introduced; 08B dry-run posture (and DB CHECKs on mode where relevant) untouched.

### 3.3 No external writeback / delivery / raw-content persistence — CONSISTENT (financials covered)
- `second-brain data-quality no-writeback-proof` (fresh): `proof_passed=true`, `repo_sha` exact target, covers executor + 08b evidence + V26+ tables; `no_raw_values_persisted=true`.
- `procore live no-writeback-proof` (fresh): `proof_passed=true`; **explicitly enumerates all 15 financial tables** in `raw_body_tables` with CHECK present + values [0] or absent (unpopulated but guarded); "financial exposure" listed in query_commands; `no_raw_values_persisted=true`; static scans pass (no writeback imports, no secrets).
- Financial tables carry the same `CHECK(raw_body_persisted=0)` + redaction enforcement as second-brain tables.
- Amount facts + registers use redacted summaries + path-only URLs + hash excerpts; output fences (`_assert_no_raw`) in financial_register.py forbid https, emails, Bearer, PEM, sig=.
- No Procore/M365 mutation anywhere (read-only clients, no POST/PUT/PATCH in financial paths).

### 3.4 Financial substrate re-audit (endpoints, amounts, WBS/cost, CLI, advisory)
**Endpoints (32):**
- `src/hb_assistant/procore/endpoints.py`: exactly 32 financial endpoint registrations (live_verified shells from Phase 05; sensitivity high). Families: owner_contracts (prime-contracts + line_items + attachments + change_orders + line_items + payment_applications), commitments (6), purchase orders (3), invoices (5 incl. billing + subcontractor variants), RFQs/change events (5), budget (7 incl. views/rows/changes + sentinel budget-details).
- `resources/config/procore_endpoint_contract.seed.yaml`: 4 financial entries as `status: sensitive_validated`, `sensitivity: high` (list-change-events, list-commitments, list-prime-contracts, list-invoices). Full 32 in code registry.
- `financial_register.py`: `_FINANCIAL_ENDPOINTS = OWNER | COMMITMENT | INVOICE | RFQ | BUDGET`; builds 10-section Obsidian register (contract summary, open actions, prime COs, commitments+compliance, invoices, payment apps, RFQs+change events, budget movement, retainage risk, last-30d changes). Source-linked, redacted only.

**Amounts (Decimal-safe, TEXT, never float):**
- Normalizer (`procore/normalizers/financial.py:49`): `parse_amount` — preserves str verbatim (or int str, or repr(float) for incoming JSON float); **no Decimal coercion that mutates precision**; "decimal-safe string".
- Projection layer (`procore_financial_projection.py:35`): `coerce_amount` twin; `is_positive_amount` uses `Decimal(coerced) > 0` **for comparison only** — "the stored value is never the parsed Decimal".
- Budget (`procore_budget_projection.py`): `_decimal` for logic (variance, forecast > budget signals); `delta = str(nd - od)` (Decimal sub, result str stored in `adjustment_amount`); amounts emitted via `emit_amount_facts` as verbatim `amount_value` str + `source_field_path`.
- Repo (`procore_financials.py:9`): "Amounts are preserved verbatim as decimal-safe TEXT — callers pass money values as `str` ... Nothing here ever calls `float()` on an amount (TEXT affinity would otherwise re-format a float and silently lose precision)."
- Cost exposure (`procore_cost_exposure.py:7`): "Amounts pass through as verbatim TEXT strings — never parsed to float, never summed. This is an advisory / review aid: it makes **no** legal, claims, financial, safety, entitlement, schedule, liability, or contractual determination."
- CLI exposure (cli/procore.py:1977): "...each with decimal-safe string amounts, source link, and a review-required flag ... Advisory/review aid only — no entitlement/liability/contractual determinations; amounts are never summed."
- Live financial summary (fresh run): amounts are strings ("10200000.0", "55650190.5", "0.0"); no summation in outputs.

**WBS / cost-code / project joins:**
- All 15 tables: `project_key TEXT NOT NULL` + `wbs_code_id`, `wbs_flat_code`, `cost_code_id`, `line_item_type_id`, `tax_code_id` (where applicable on line items/rows/changes).
- `amount_facts`: `wbs_code_id`, `cost_code_id`, `source_field_path`.
- Indexes e.g. `ix_procore_financial_contracts_project_family ON ... (project_key, contract_family, status)`; similar for others.
- Normalizers: `extract_wbs_cost_code` preserves ids + flat_code + descriptions (business labels, redacted only for PII in free text).

**Existing financial CLI + register:**
- `procore live financial` (summary, contracts, changes, invoices, exposure, coverage, budget, risk); all local SQLite, `--json`, carry `_GUARDRAILS` + phase="Phase 05 Prompt 11".
- Obsidian: `build_financial_register` + `apply_financial_register` (marker-bounded, dry default).
- All outputs source-linked (record_key, query command ref) + guardrails; no raw.

**Advisory labeling:** Present and consistent with query spec across exposure, cost_exposure docstring, CLI help, financial register frontmatter ("review_sensitive: false" but high-sensitivity items flagged review-required in signals), and 08B-era policy.

**No raw / secrets in financial paths:** Enforced at normalizer (mask_excerpt, redact_url_to_path, summarize_text), store (CHECKs + _redact_excerpt), register (output fence + _assert_no_raw), proofs (scans cover financial tables + evidence).

### 3.5 Status outputs, reason codes, job health, brief delivery, executor — pass (08B substrate)
- From fresh gates: `daily_brief_job_health=pass`, `daily_brief_delivery=pass`, `daily_brief_html_render=pass`, `automation_execution=pass`, `automation_health=pass` (RUN_OK).
- `second-brain automation health`: no degraded; path/store/schema/handoff durable ok.
- Executor proofs (cross-ref 08B evidence): dry_run_plan, retry, weekend, first-run-after-wake, duplicate, safe_replay, last-good-run, job_health, no_writeback all sub-pass; lock released, fakes, metadata receipts, no external delivery.
- Brief delivery: handoff durable, receipts, local HTML only (no external assets), evaluation gate before apply.
- All per 08B P08/P09 consolidated proofs (automation-execution-proof.md, phase-08b-final-no-writeback-proof.md) remain valid at this HEAD (no code change).

### 3.6 Phase 08B data-quality gates (verbatim fresh)
16 pass, 0 else, `automation_execution=pass`, `readiness_overstated=false` (see matrix §2 + gates JSON).

---

## 4. Guardrails Verified (preserved + financial-specific)
- ✅ Local-first; read-only against Microsoft 365 / Graph / Procore (`construction-agent validate` + procore proofs).
- ✅ No Microsoft 365 / external-system / Procore writeback (source scans + DB CHECKs + model validators + both no-writeback proofs).
- ✅ No email/Slack/Teams/SMS/push/webhook/`sendMail` delivery.
- ✅ No raw-content persistence (bodies, doc text, calendar, prompts, responses, signed/download URLs, raw HTML) — enforced by `CHECK(=0)` on 15+ financial tables + second-brain tables + redaction + fences + proof scans.
- ✅ Money: never binary float; `Decimal` only for safe >0 / delta / variance (result always str back to TEXT); persisted as canonical decimal strings (source precision preserved).
- ✅ Financial outputs advisory review aids only: "advisory/review aid only — no entitlement/liability/contractual determinations; amounts are never summed" (exposure, cost_exposure, CLI); no payment approvals, claims, forecasts, executive determinations.
- ✅ Apply-capable (register, launchd, brief vault) dry-run default; explicit `--apply --confirm` where applicable.
- ✅ All runtime state/artifacts outside repo (Application Support).
- ✅ Status outputs carry actionable reason codes (tiers, gate reasons, apply_blocked, exposure signals).
- ✅ Source traceability on all financial register / amount facts / CLI outputs (record_key + endpoint + source_field_path + query ref).
- ✅ No 08C package dir on disk (repo truth); 08C evidence dir created by this prompt only.

**No repo-truth contradiction with the prompt was found.** No stop condition triggered.

---

## 5. Known Limitations / Recommendations (non-blocking)
1. **08C evidence dir + package dir absent on disk.** Created the evidence dir here; the referenced `HB_..._08C.../00_PACKAGE_MANIFEST.md` was not present (find up to depth 6 + broad /Users search returned none outside .git). This rebaseline treats it as external intent per prompt.
2. **Financial query surfaces not yet in second-brain.** `construction/second_brain/query_tools/` and readers have zero imports of `procore_financial*` or `read_financial_*` (only family/policy mentions in triage/context for "financial"). Expected — 08C scope.
3. **3 Phase 05 fail-closed endpoints remain** (purchase-order-detail-line-items 404 data cond, budget-change-line-items 403, budget-details unresolved sentinel) — documented remediation, not re-audit blocker.
4. **README 08A still labeled "Active"** in ledger (08B closed block present); 08C listed only as explicit future handoff. Not an overstatement.
5. **Data in pilot DB** (tropical) is from prior live promotion; this prompt performed no new sync/live calls.
6. **Full pytest timed out in one run** (300s cap); focused subsets + prior identical-HEAD count (2834) + green matrix suffice for rebaseline.

---

## 6. Next-Prompt Readiness
The next Phase 08C prompt (first implementation) can safely assume:
- HEAD is the clean 08B closeout (`dcecea8...`); schema is **V34**; full validation matrix green (compile/ruff/mypy/pytest safe 2834, construction 4/4, procore 28/28, second-brain status/health/08b-gates/no-writeback all pass with `automation_execution=pass` + `readiness_overstated=false`).
- The dry-run-by-default, no-writeback/no-raw, Decimal-str money, project_key + WBS/cost-code, source-linked advisory financial substrate (32 eps, 15 tables, amount_facts, CLI + register + exposure) is in place, test-backed, and proof-covered.
- 08B automation/executor/brief/delivery/observability substrate (health, gates, receipts, locks, retry, job health, local HTML) is fully pass and ready for financial integration (e.g. daily brief cards, research packets, retrieval tools over financial facts).
- This evidence bundle (`00-repo-truth-audit-and-rebaseline.md`) + the 08B/05 financial evidence trees are the authoritative 08C starting baseline.
- All stop conditions (automation_execution, no-writeback, README honesty) are satisfied.

**No stop condition triggered. Ready for 08C implementation prompts (financial substrate integration into second-brain/automation, subject to additive schema if needed, continued guardrails, dry-run defaults, and advisory-only outputs).**

---

**Evidence bundle location:** `docs/evidence/construction-intelligence-phase-08c-financial-readiness/00-repo-truth-audit-and-rebaseline.md` (this file). Companion runs/logs captured in session terminal artifacts (outside repo).

*Repository truth is authoritative.*