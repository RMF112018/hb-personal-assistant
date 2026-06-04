# Phase 09 — Prompt 02: Attached Audit Package Gap Preflight Remediation

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/02-agent-data-quality-gap-preflight-remediation.md`
**Machine-readable companions:** `02-agent-data-quality-gap-preflight-remediation.json`, `02-live-gap-measurement.json`
**G-11 companions:** `attached-audit-summary-companions/` · **Captured outputs:** `validation-outputs-prompt-02/`
**Attached audit packet:** `docs/evidence/construction-intelligence-phase-08d-agent-data-quality-evaluation/`
**Audit date:** 2026-06-04 · **HEAD:** `23e6d87` · **Schema:** V37 · **Version:** 1.3.0
**Posture:** Verify every attached-audit gap against current DB/vault/repo truth (read-only) and **resolve G-11**. **No runtime, schema, `pyproject`, or test change; no LlamaIndex/embeddings/vector/semantic-retrieval code.** The historical 08D packet is not modified.

---

## 1. Scope & guardrail posture

This prompt re-measures every attached-audit gap (G-01…G-11) against the **live operator DB** and vault,
and resolves the one gap it owns — **G-11** (compact summary companions for oversized field-profile /
completeness evidence). Gaps G-01…G-10 are owned by later prompts → verified and **carried forward**.
All DB access is read-only (`file:…?mode=ro`); only counts / null-rates / enum distributions / hashes are
recorded — **no raw content**. Local-first, read-only, advisory-only posture preserved.

---

## 2. Attached-audit → live verification matrix (read-only, HEAD `23e6d87`)

| Gap | Attached-audit claim | Live now | Verdict | Owner | Blocks 09? |
|---|---|---|---|---|---|
| G-01 generated output | 0 rows | daily_brief/research/parser/eval = **0/0/0/0** | confirmed empty | Prompt 03 | Yes |
| G-02 MCP runtime | 0 receipts | tool-call **0** / denial **0** | confirmed empty | Prompt 04 | Yes |
| **G-03 review queue** | ~66,466 review items | **101,490 ledger rows across 112 runs → ~801 DISTINCT items** | **reframed (see §3)** | Prompt 05 | Yes |
| G-04 financial completeness | currency 100% null; period ~98.7% null; wbs sparse | currency `1.0000`, period_start `0.9871`, wbs/cost `0.0338` (of 85,521 facts) | confirmed | Prompt 06 | Yes |
| G-05 memory | 0 | long_term_memory_items / candidates / preference_profiles = **0** | confirmed empty | Prompt 07 | Yes |
| G-06 automation/delivery | 0 | run-registry + delivery/notification/open receipts = **0** | confirmed empty | Prompt 08 | Yes |
| G-07 Obsidian linkage | sqlite-linked-by-frontmatter 0 | `obsidian_index_entries` = **0** | confirmed empty | Prompt 09 | Yes |
| G-08 relationship quality | population exists; quality marts absent | candidates **1880** (det 1671 / strong 51 / weak 158); relationships **1671**; no quality mart | confirmed | Prompt 10 | Yes |
| G-09 repo baseline literals | hashes not literals | safe literals emitted (Prompt 00) | **resolved (Prompt 00)** | Prompt 00 | No |
| G-10 corpus balance | procore/financial heavy; others empty | procore_live_records 30,035 / amount_facts 85,521 / record_edges 30,822 vs brief/research/mcp/memory/automation **0** | confirmed imbalance | Prompt 11 | Yes |
| **G-11 oversized evidence** | summarized companions needed | 5 compact companions created (§4) | **RESOLVED (this prompt)** | Prompt 02 | No |

The live measurement is in `02-live-gap-measurement.json`.

---

## 3. Key finding — G-03 is an append-only ledger (review burden ≈ 801, not 66k)

`second_brain_financial_review_required_items` carries a **`run_id`** column. Each financial-review
routing run logs a fresh batch (≈1,299 rows) tagged with a new `run_id` (`08c-comp-…`):

- **101,490 total rows** across **112 distinct routing runs**.
- Collapsing by natural key (`project_key, trigger_category, source_ref, amount_ref`) →
  **801 DISTINCT review items**. The latest single routing run emitted 1,299 rows.
- **All guard columns sum to 0** (`external_writeback_performed`, `raw_financial_source_payload_persisted`,
  `raw_prompt_persisted`, `financial_determination_performed`, `payment_decision_performed`).

So the attached-audit headline of **"66,466 review items"** (and the live 101,490) is substantially a
**row-count artifact of an append-only per-run ledger**, not a distinct review backlog. The true distinct
financial-review burden is **≈801 items** (plus small construction 26 / email 22 / document 1 review
counts).

**Side effect (disclosed):** `second-brain data-quality phase-08c-gates` — described as a read-only
advisory surface — **appends a fresh non-pruned routing run (~1,299 rows) per invocation**. This
verification's runs and prior preflight Prompts 00/01/02 each ran that command and grew the table. It is
a **local append-only ledger** (guard columns all 0; no external writeback, no raw persistence, no
determination) — **not a stop condition** — but it means the gate is not strictly read-only and the
ledger grows unboundedly.

**Recommendation (carried to Prompt 05 / an 08C hygiene follow-up):** count review burden by **DISTINCT**
review items (latest `run_id` or natural key), not raw ledger rows; make `phase-08c-gates` evaluation
read-only or prune prior routing runs. Subsequent preflight prompts should avoid unnecessary
`phase-08c-gates` re-runs.

---

## 4. G-11 resolution — compact summary companions

Five oversized field-profile / completeness files in the attached packet now have compact, inspectable
companions under `attached-audit-summary-companions/` (originals unchanged; each companion carries the
original's bytes / lines / **SHA-256**; counts + structure only, no per-field dumps):

| Original | Original size | Companion size |
|---|---|---|
| `02-sqlite-field-profile.json` | 4,528,050 B / 118,213 lines | 979 B |
| `06-data-completeness-freshness-shape.json` | 1,738,702 B / 49,947 lines | 1,051 B |
| `12-data-dictionary-and-evaluator-index.json` | 476,683 B / 18,327 lines | 1,300 B |
| `08-financial-data-structure-quality-evidence.json` | 337,687 B / 9,669 lines | 1,061 B |
| `01-sqlite-structure-inventory.json` | 149,258 B / 4,971 lines | 6,594 B |

Index + per-file SHA-256: `attached-audit-summary-companions/README.md`.

---

## 5. Validation commands & results (HEAD `23e6d87`, `.venv/bin/python3.12`)

Captured under `validation-outputs-prompt-02/`. **No code change**, so the suite is fully green.

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | ok |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | no issues / 272 files |
| `pytest -m "not live and not integration and not manual"` | 0 | **3016 passed / 0 failed / 0 skipped** |
| `construction-agent validate --json` | 0 | `ok=true`; `schema_version=37` |
| `construction-agent data-quality table-inventory --json` | 0 | schema 37; **0 unmapped live tables** |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true` |
| `second-brain data-quality phase-08a/08b/08c-gates --json` † | 0 | `ok=true` (08c `proof_passed=true`) |
| `second-brain data-quality phase-08d-gates --json` † | 0 | `ok=true`; 14 pass; `ready_to_serve=true` |
| `second-brain mcp no-raw-access / no-writeback --json` † | 0 | `proof_passed=true` |

† Same CLI-spelling resolutions documented in Prompts 00/01. **Evidence re-stamps** produced by the
proof builders were reverted to keep the commit surgical (authoritative outputs under
`validation-outputs-prompt-02/`). Note the `phase-08c-gates` ledger side effect in §3.

---

## 6. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Raw-content persistence | No — G-03 ledger guard columns sum to 0; `no_raw` proofs pass |
| External writeback | No — `external_writeback_performed=0`; the `phase-08c-gates` ledger growth is local-only |
| Missing no-raw / no-writeback proof | No — all present and passing |
| Unresolved high-impact review items entering an approved source manifest | N/A — no approved manifest exists yet |
| Unapproved Obsidian notes indexed | N/A — `obsidian_index_entries=0` |
| Semantic retrieval bypassing Research Packet / Evaluation | N/A — no semantic retrieval exists |

No stop condition triggered.

---

## 7. Verdict

Every attached-audit gap is verified against live operator-DB truth. **Confirmed empty:** G-01, G-02,
G-05, G-06, G-07. **Confirmed:** G-04 (financial null profile), G-10 (corpus imbalance). **G-08:**
relationship population present (1880/1671) but no quality mart. **G-03 reframed:** the "66k review
items" headline is an append-only ledger artifact — the distinct financial-review burden is **≈801**.
**G-09** resolved in Prompt 00; **G-11 resolved here** (5 compact companions). G-01…G-08, G-10 carried to
owning Prompts 03–11. The `phase-08c-gates` non-pruning ledger side effect is disclosed and routed to
Prompt 05 / an 08C hygiene follow-up. No stop condition triggered. **Proceed to Phase 09 Prompt 03.**
