# 123 — Phase 09 Prompt 03: Generated-Output Population Proof (gap G-01)

**Status:** Preflight remediation (Prompt 03 — populate controlled outputs; prove guard-clean).
**Schema:** V37 (unchanged). **Version:** 1.3.0 (unchanged). **HEAD:** `23e6d87`.
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/03-generated-output-and-research-packet-preflight.md` (+ `.json`, `source-linked-retrieval-proof.json`).
**Builds on:** records 120 (P00), 121 (P01), 122 (P02).

---

## 1. Purpose

Resolve gap G-01 — the second-brain generated-output tables (research packets, daily-brief runs + source
refs + handoff lines, evaluation runs) were structurally present but 0 rows. Demonstrate that the existing
Phase 08A generation pipeline produces **controlled, source-linked, confidence-labeled, guard-clean**
outputs **before any indexing**. Preflight boundary unchanged: no LlamaIndex / embeddings / vector /
semantic-retrieval code.

## 2. Controlled-population pattern (proof-DB copy)

To resolve G-01 without polluting the operator's real second-brain or vault, the population is written to
a **labeled proof-DB copy** of the operator DB (a separate file **outside the repo**). The Phase 08A
builders run **offline (mock Claude adapter) / dry-run / no-vault** against the copy:

- `run_daily_brief(...mode="dry_run", adapter=MockClaudeAdapter(), emit_receipt=True)` → research packet +
  `daily_brief_runs` + `daily_brief_source_refs` + `daily_brief_handoff_lines` + `second_brain_evaluation_runs`.
- `RetrievalOrchestrator.orchestrate(packet_type="interactive_query", emit_receipt=True)` → a second,
  distinct research packet.

Two distinct `packet_type`s avoid the deterministic-`packet_id` `UNIQUE` collision (the research-packet
write is a plain INSERT — re-emitting the same packet collides; minor idempotency note). Result: **820
rows** (research packets 2 / brief runs 1 / source refs 408 / handoff lines 408 / evaluation 1), **all
guard `CHECK(=0)` sums 0**, source-linked, confidence-labeled. The **operator DB stayed at 0 generated
rows (pristine)**; the proof DB was deleted after measurement; the real vault was never written.

## 3. Reusable proof helper (the only committed code)

`construction/second_brain/generated_output_proof.py` ·
`build_generated_output_population_proof(db_path)` — read-only (`mode=ro`): per-table counts, guard-column
sums (discovered via `PRAGMA table_info`), source-linkage, confidence presence, and a forbidden-pattern
scan (PEM / bearer / JWT / tokenized URL) over safe text columns (reports only `table.column`, never the
value). 4 tests (normal / empty / no-raw fail-closed / stale-schema). `parser_outputs` excluded as a Phase
06A file-extraction artifact.

## 4. Guardrails & stop conditions

Offline mock only (no Anthropic/Graph/Procore/external call or writeback); writes only to a throwaway
proof-DB copy; metadata-only rows with guard `CHECK(=0)` enforced; no raw content/prompts/responses/
tokens/URLs/PEMs; no raw vector search; advisory only; review tier / confidence / source refs preserved.
No stop condition triggered.
