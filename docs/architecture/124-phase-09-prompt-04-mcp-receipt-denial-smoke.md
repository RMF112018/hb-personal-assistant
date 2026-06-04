# 124 — Phase 09 Prompt 04: MCP Receipt & Denial Smoke Proof (gap G-02)

**Status:** Preflight remediation (Prompt 04 — run allowed/denied smoke; prove guard-clean receipts).
**Schema:** V37 (unchanged). **Version:** 1.3.0 (unchanged). **HEAD:** `23e6d87`.
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/04-mcp-runtime-receipt-and-denial-smoke.md` (+ `.json`).
**Builds on:** records 120–123 (Prompts 00–03).

---

## 1. Purpose

Resolve gap G-02 — the V37 MCP receipt tables existed but the operator DB had 0 tool-call / 0 denial
receipts. Demonstrate that the deny-first MCP broker produces **controlled, metadata-only** allowed/denied
receipts with **no raw payloads**. Preflight boundary unchanged: no LlamaIndex / embeddings / vector /
semantic-retrieval code.

## 2. In-process smoke pattern (no SDK, proof-DB)

`build_default_broker(db_path=proof, persist=True)` (`mcp/__init__.py`) wires the nine real workflow
wrappers; `ToolBroker.dispatch(tool, args)` is the deny-first authority and persists receipts in-process —
**no MCP SDK / serve required**. Smoke (against a **fresh V37 proof DB outside the repo**): `hb_status`
(allowed) + `arbitrary_sql` / `graph_api_call` / `email_send` / `source_system_writeback` (denied by
policy) + `hb_delete_everything` (denied, not in registry) → **1 allowed + 5 denied** receipts, **both
guard `CHECK(=0)` sums 0**, reason codes present, receipts hashes/counts/enums only. The **operator DB
stayed 0/0 (pristine)**; the proof DB was deleted after measurement.

## 3. Reusable proof helper (the only committed code)

`construction/second_brain/mcp/receipt_smoke_proof.py` · `build_mcp_receipt_smoke_proof(db_path)` —
read-only (`mode=ro`): allowed/denial counts, guard-column sums (reuse `_guards_all_zero` +
`_GUARD_COLUMNS`), decision well-formedness, allowed-tool-registry validity, denial reason-code presence,
forbidden-pattern scan, and the reused structural `_receipts_no_raw` / `_receipts_no_writeback`
attestations. 5 tests (normal / missing-wrapper / unsafe-output / empty / stale-schema).

## 4. Guardrails & stop conditions

In-process only (no SDK, no Anthropic/Graph/Procore/email/calendar/external call or writeback); deny-first
authority (denied actions never execute); receipts written only to a throwaway proof DB; metadata-only
rows with 20 guard `CHECK(=0)` columns enforced at the DB layer; no raw args/results/prompts/responses/
tokens/URLs/PEMs/arbitrary SQL; advisory only. No stop condition triggered.
