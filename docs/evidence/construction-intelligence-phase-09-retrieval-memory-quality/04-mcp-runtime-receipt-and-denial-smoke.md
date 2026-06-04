# Phase 09 — Prompt 04: MCP Runtime Receipt & Denial Smoke Preflight

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/04-mcp-runtime-receipt-and-denial-smoke.md`
**Machine-readable companion:** `04-mcp-runtime-receipt-and-denial-smoke.json`
**Captured outputs:** `validation-outputs-prompt-04/`
**Gap:** G-02 (V37 MCP receipt tables present but operator DB has 0/0 receipts)
**Audit date:** 2026-06-04 · **HEAD:** `23e6d87` · **Schema:** V37 · **Version:** 1.3.0
**Posture:** In-process **real-broker** allowed/denied smoke (**no MCP SDK / no serve / no external call**) persisting **metadata-only** receipts to a **labeled proof DB outside the repo**. The **operator DB stays pristine** (0/0 receipts). New reusable guard-clean **proof helper + tests**; **no CLI command, no schema migration, no LlamaIndex/embeddings/vector/semantic-retrieval code.**

---

## 1. Scope & guardrail posture

G-02 resolution: run safe **allowed + denied** MCP tool dispatches that persist **metadata-only**
receipts and **prove no raw payloads**. The dispatch is driven in-process through the deny-first
`ToolBroker` wired with the nine real workflow wrappers (`build_default_broker`) — no MCP SDK and no
stdio serve are needed. Receipts are written only to a **fresh V37-migrated proof DB outside the repo**;
the operator DB is left untouched. Every receipt is hashes/counts/enums/reason-codes only, protected by
the 20 guard `CHECK(… = 0)` columns enforced at the DB layer.

---

## 2. Smoke run (in-process real broker → labeled proof DB)

Dispatched through `build_default_broker(db_path=proof, persist=True)`:

| Tool/action | Decision | Reason code | Receipt table |
|---|---|---|---|
| `hb_status` | allowed | — | `second_brain_mcp_tool_call_receipts` |
| `arbitrary_sql` | denied | `action_denied_by_policy` | `second_brain_mcp_denial_receipts` |
| `graph_api_call` | denied | `action_denied_by_policy` | denial |
| `email_send` | denied | `action_denied_by_policy` | denial |
| `source_system_writeback` | denied | `action_denied_by_policy` | denial |
| `hb_delete_everything` | denied | `tool_not_allowed` | denial |

### Persisted counts (proof DB)

| Table | Rows | Guard `CHECK(=0)` cols | Guard sum |
|---|---|---|---|
| `second_brain_mcp_tool_call_receipts` (allowed) | **1** | 20 | **0** |
| `second_brain_mcp_denial_receipts` (denied) | **5** | 20 | **0** |

`build_mcp_receipt_smoke_proof(proof_db)` → **`proof_passed=true`**, `populated=true`,
`tool_call_decisions_ok=true` (`{allowed}`), `denial_decisions_ok=true` (`{denied}`),
`allowed_tools_valid=true`, `denials_missing_reason=0`, `raw_content_findings=[]`,
`structural_no_raw.passed=true`, `structural_no_writeback.passed=true`, `schema_version=37`.

### Receipt samples (metadata-only, redacted)

- Allowed: `tool_name=hb_status`, `decision=allowed`, `workflow_wrapper=mcp_status_wrapper`,
  `output_classification=bounded_summary`, `source_count=3`, `result_count=1`, `args_hash`/`result_hash`
  = SHA-256 hex (no raw args/results).
- Denial: `requested_action=arbitrary_sql`, `decision=denied`, `denial_reason_code=action_denied_by_policy`,
  `request_hash` = SHA-256 hex.

Reason codes observed: `action_denied_by_policy`, `tool_not_allowed`. Full samples in the `.json`.

### Operator DB stays pristine

Operator MCP receipt tables **before == after == 0 / 0** (unchanged). The proof DB was a separate file
outside the repo and was **deleted** after measurement.

---

## 3. Reusable proof helper + tests (the only committed code)

`src/hb_assistant/construction/second_brain/mcp/receipt_smoke_proof.py` —
`build_mcp_receipt_smoke_proof(db_path)` is **read-only** (`mode=ro`): allowed/denial counts, guard-column
sums on both tables (reusing `_guards_all_zero` + `_GUARD_COLUMNS` from `mcp/proof.py`), decision
well-formedness, allowed-tool-registry validity, denial reason-code presence, a forbidden-pattern scan
over safe text columns (reports `table.column` only), and the reused structural `_receipts_no_raw` /
`_receipts_no_writeback` attestations. Fully typed; `ruff` + `mypy src` clean (274 files).

`tests/test_phase_09_mcp_receipt_smoke_proof.py` (5 tests, all pass): normal (real broker → `proof_passed`),
missing-wrapper fail-closed (`WRAPPER_UNAVAILABLE` denial), unsafe-output fail-closed (`UNSAFE_OUTPUT`
denial; URL never persisted), empty DB (`populated=false`), stale-schema (below-V37 → missing tables
reported, no crash).

---

## 4. Validation commands & results (HEAD `23e6d87`, `.venv/bin/python3.12`)

Captured under `validation-outputs-prompt-04/`.

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | ok |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | no issues / **274** files (new helper in scope) |
| `pytest -m "not live and not integration and not manual"` | 0 | green (prior 3020 + 5 new = **3025 passed**) |
| `construction-agent validate --json` | 0 | `ok=true`; `schema_version=37` |
| `construction-agent data-quality table-inventory --json` | 0 | schema 37; **0 unmapped** |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true` |
| `second-brain data-quality phase-08a/08b/08c-gates --json` † | 0 | `ok=true` (08c `proof_passed=true`) |
| `second-brain data-quality phase-08d-gates --json` † | 0 | `ok=true`; `ready_to_serve=true` |
| `second-brain mcp no-raw-access / no-writeback --json` † | 0 | `proof_passed=true` |

† Same CLI-spelling resolutions as Prompts 00–03. Evidence re-stamps from the proof builders were reverted
to keep the commit surgical; the `phase-08c-gates` append-only-ledger side effect (Prompt 02) still applies
(run once for the required matrix). The operator DB was opened read-only for verification.

---

## 5. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Raw-content persistence | No — both guard sums 0 (DB-enforced `CHECK`); forbidden-pattern scan clean; structural no-raw passes |
| External writeback | No — in-process broker, deny-first; denied actions never execute; proof-DB only |
| Missing no-raw / no-writeback proof | No — smoke proof + `mcp no-raw-access` / `mcp no-writeback` all pass |
| Unresolved high-impact review items entering an approved source manifest | N/A — no approved manifest exists yet |
| Unapproved Obsidian notes indexed | N/A — no vault write, no indexing |
| Semantic retrieval bypassing Research Packet / Evaluation | N/A — no semantic retrieval exists |

No stop condition triggered.

---

## 6. Verdict

G-02 **resolved (pipeline-proven)**: the deny-first MCP broker produces guard-clean, metadata-only
allowed/denied receipts (1 allowed + 5 denied; both guard sums 0; reason codes present; no raw payloads),
demonstrated in a labeled proof DB with the **operator DB left pristine (0/0)**. A reusable read-only
proof helper + 5 tests are committed (suite green). No stop condition triggered. **Proceed to Phase 09
Prompt 05** (review-load & human-in-loop preflight).
