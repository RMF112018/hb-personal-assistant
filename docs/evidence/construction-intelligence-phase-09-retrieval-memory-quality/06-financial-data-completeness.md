# Phase 09 — Prompt 06: Financial Data Completeness Preflight

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/06-financial-data-completeness.md`
**Machine-readable companion:** `06-financial-data-completeness.json`
**Captured outputs:** `validation-outputs-prompt-06/` (incl. `sb-financial-completeness-advisory.txt`)
**Gap:** G-04 (currency fully null; period nearly null; WBS/cost-code orphan risk)
**Audit date:** 2026-06-04 · **HEAD:** `23e6d87` · **Schema:** V37 · **Version:** 1.3.0
**Posture:** Deterministic **read-only advisory** financial-completeness mart (**no new schema**) over the existing financial fact tables, plus a read-only CLI command. Emits **advisory recommendations + review labels only** — never assigns a currency, sets a period, makes a determination, writes to the facts, or routes into the review ledger. Reads the operator DB read-only (verified unmutated). **No LlamaIndex/embeddings/vector/semantic-retrieval code.**

---

## 1. Scope & guardrail posture

G-04 remediation, "advisory only, before semantic retrieval over financial outputs." The guardrails forbid
**final financial determinations**, so currency fallback / period enrichment / WBS-cost-code reconciliation
are delivered as **advisory recommendations + review labels** — never assignments. The mart is a derived
read model (no schema), computed read-only over the financial fact tables; money values are **never read or
echoed** (only counts, ISO-currency codes, and labels). Nothing is routed into
`second_brain_financial_review_required_items` (the append-only ledger flagged in Prompt 02).

---

## 2. Live completeness profile (read-only, operator DB)

| Gap | Live value | Advisory recommendation |
|---|---|---|
| **Currency** (`procore_financial_amount_facts`, 85,521 facts) | `currency_iso_code` null **100%** | per project → **`project_default_currency_required`** (3 projects) — *no source currency present anywhere; cannot derive a dominant currency; requires a policy/document default (never assigned)* |
| **Period** | `period_start`/`period_end` null **98.7%** | **`period_context_required`** — period is source-context dependent (invoice/contract/budget date); not derivable |
| **WBS / cost-code** | orphan/missing: **2,887 WBS** + **3,510 cost-code** (across amount-facts + line-item / budget-row / change-order tables) | **`wbs_cost_code_context_required`** — no WBS/cost-code parent tables exist (presence-only detection); reconcile from source |
| Normalized layer | `second_brain_financial_amount_facts_normalized` = **0 rows** | `normalized_layer_populated=false` — the 08C normalization has not been run on the operator DB |

**Key finding:** because **no non-null currency exists anywhere** in the raw facts, the "project-default
currency fallback" cannot be data-derived — it is correctly surfaced as an advisory
`project_default_currency_required` recommendation (eligibility for an evidence-backed default = **false**),
**not** a determination. (When a dominant source currency *is* present, the mart recommends
`advisory_use_dominant_source_currency` with the code — still advisory, never assigned; covered by tests.)

---

## 3. Advisory-only / no-determination attestation

`build_financial_completeness_advisory_proof` → `proof_passed=true`, `advisory_only=true`,
`no_determination_attested=true`, `raw_content_findings=[]`. The 08C financial **guard columns** on the
populated snapshot tables (`financial_determination_performed`, `payment_decision_performed`,
`claim_or_entitlement_decision_performed`, `external_writeback_performed`,
`raw_financial_source_payload_persisted`) re-attested clean (`violation=false`); `advisory_only=1`
throughout. The mart **writes nothing** — the operator DB financial facts / normalized / review ledger are
**unmutated** (before == after).

---

## 4. Reusable helper + CLI + tests (committed code)

`src/hb_assistant/construction/second_brain/financial_completeness_advisory.py` —
`build_financial_completeness_advisory` + `build_financial_completeness_advisory_proof` (read-only,
`mode=ro`; counts/enums/ISO-codes/labels only; money never echoed). Fully typed; `ruff` + `mypy src` clean
(276 files).

`src/hb_assistant/cli/second_brain.py` — a new read-only command
`hb-assistant second-brain financial completeness-advisory --json` (emits the advisory mart + proof; exit
0/3).

`tests/test_phase_09_financial_completeness_advisory.py` (5 tests): gap profiling without determination;
dominant-currency advisory when a source currency IS present (recommendation only); proof passes +
advisory-clean; empty DB; stale-schema graceful.

---

## 5. Validation commands & results (HEAD `23e6d87`, `.venv/bin/python3.12`)

Captured under `validation-outputs-prompt-06/`.

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | ok |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | no issues / **276** files |
| `pytest -m "not live and not integration and not manual"` | 0 | green (prior 3030 + 5 new = **3035 passed**) |
| `construction-agent validate --json` | 0 | `ok=true`; `schema_version=37` |
| `construction-agent data-quality table-inventory --json` | 0 | schema 37; **0 unmapped** |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true` |
| `second-brain data-quality phase-08a/08b/08c/08d-gates --json` † | 0 | `ok=true` (08c `proof_passed=true`) |
| `second-brain mcp no-raw-access / no-writeback --json` † | 0 | `proof_passed=true` |
| **`second-brain financial completeness-advisory --json`** (new) | 0 | `proof_passed=true`; `no_determination=true`; currency null 100% |

† Same CLI-spelling resolutions as Prompts 00–05. Evidence re-stamps from the proof builders were reverted
to keep the commit surgical. **Disclosed:** `phase-08c-gates` (the Prompt-02 append-only ledger) appends a
routing run per call — run once for the matrix; the advisory mart is read-only and does not touch the
ledger. The operator DB financial tables were **unmutated** by the mart (read-only `mode=ro`).

---

## 6. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Raw-content / raw-amount persistence | No — mart emits counts/enums/ISO-codes/labels only; money never echoed; no writes |
| External writeback | No — read-only `mode=ro`; operator DB unmutated |
| Missing no-raw / no-writeback proof | No — advisory proof + 08C/MCP proofs pass |
| **Final financial determination** | **No — currency/period/WBS outputs are advisory recommendations + review labels, never assignments; guard columns `financial_determination_performed`/`payment_decision_performed`/`claim_or_entitlement_decision_performed` = 0** |
| Unresolved high-impact review items entering an approved source manifest | N/A — no approved manifest; nothing routed |
| Unapproved Obsidian indexing / semantic retrieval bypass | N/A |

No stop condition triggered.

---

## 7. Verdict

G-04 **remediated (advisory)**: the live financial-completeness gaps are profiled (currency 100% null,
period 98.7% null, WBS/cost-code 2,887/3,510 orphan-or-missing, normalized layer empty) and surfaced as
**advisory recommendations + review labels** — `project_default_currency_required` (no derivable currency),
`period_context_required`, `wbs_cost_code_context_required` — with a verified **no-determination /
no-writeback / no-ledger-routing** posture, the operator DB left unmutated. A reusable read-only advisory
mart helper, a read-only CLI command, and 5 tests are committed (suite green). No stop condition triggered.
**Proceed to Phase 09 Prompt 07** (memory runtime & review preflight).
