# Phase 09 — Prompt 03: Generated Output & Research Packet Preflight

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/03-generated-output-and-research-packet-preflight.md`
**Machine-readable companions:** `03-generated-output-and-research-packet-preflight.json`, `source-linked-retrieval-proof.json`
**Captured outputs:** `validation-outputs-prompt-03/`
**Gap:** G-01 (generated-output tables structurally present but 0 rows)
**Audit date:** 2026-06-04 · **HEAD:** `23e6d87` · **Schema:** V37 · **Version:** 1.3.0
**Posture:** Controlled, **offline (mock) / dry-run / no-vault** population into a **labeled proof-DB copy** of the operator DB (outside the repo). The **operator DB and the real Obsidian vault stay pristine**; only metadata-only evidence is committed. New reusable guard-clean **proof helper + tests** added; **no CLI command, no schema migration, no LlamaIndex/embeddings/vector/semantic-retrieval code.**

---

## 1. Scope & guardrail posture

G-01 resolution: demonstrate that the Phase 08A generation pipeline produces **controlled, safe,
source-linked, confidence-labeled, guard-clean** generated outputs **before any indexing**, without
polluting the operator's real second-brain or vault. Per the approved approach, the population is written
to a **throwaway proof-DB copy** of the operator DB (a separate file outside the repo); the builders run
fully offline with the **mock** Claude adapter, **dry-run** mode, and **no vault write**. All writes are
metadata-only and protected by the per-table guard `CHECK(… = 0)` columns.

`parser_outputs` is a Phase 06A **file-extraction** artifact, not a second-brain generation surface; it is
**out of scope** here and classified as a deferred carry-forward (not populated).

---

## 2. Controlled population (proof-DB copy, offline mock, no vault)

Recipe (Python builder API, all against the proof-DB copy; mock adapter; `emit_receipt=True`; no vault):

- `run_daily_brief(brief_date="2026-06-04", project_key="tropical", mode="dry_run", adapter=MockClaudeAdapter(), emit_receipt=True)`
  → research packet (daily_brief) + `daily_brief_runs` + `daily_brief_source_refs` + `daily_brief_handoff_lines` + `second_brain_evaluation_runs`.
- `RetrievalOrchestrator.orchestrate(packet_type="interactive_query", project_key="tropical", emit_receipt=True)`
  → a second, distinct research packet (+ retrieval receipt/context refs).

Two distinct `packet_type`s avoid the deterministic-`packet_id` `UNIQUE` collision (the research-packet
write is a plain INSERT — re-emitting the same `(packet_type, project_key, families)` packet collides;
disclosed as a minor idempotency note).

### Populated counts (proof DB)

| Table | Rows | Guard `CHECK(=0)` cols | Guard sum |
|---|---|---|---|
| `second_brain_research_packets` | 2 | 10 | **0** |
| `daily_brief_runs` | 1 | 9 | **0** |
| `daily_brief_source_refs` | 408 | 0 (metadata refs) | n/a |
| `daily_brief_handoff_lines` | 408 | 9 | **0** |
| `second_brain_evaluation_runs` | 1 | 4 | **0** |
| **total** | **820** | — | **0** |

`build_generated_output_population_proof(proof_db)` → **`proof_passed=true`**, `populated=true`,
`guard_violation=false`, `source_linked=true`, `confidence_present=true`, `raw_content_findings=[]`,
`schema_version=37`.

### Source-linkage + confidence (samples, redacted)

- Research packets: `project_key=tropical`, `source_ref_count=408`, `confidence_class=medium`,
  `review_tier=1`, `context_quality_class=partial`, `retrieval_receipt_id` populated (→ source-linked).
- `daily_brief_source_refs`: `source_family=cross_source_relationships`, `source_ref=<hash>` (redacted).
- `second_brain_evaluation_runs`: `mode=dry_run`, `passed=1`, `score=1.0`, `confidence_class=medium`,
  `review_tier=1`, `research_packet_id` linked.

Full samples: `source-linked-retrieval-proof.json`.

### Operator DB stays pristine

Operator generated-output tables **before == after == 0 rows** (unchanged); the proof DB was a separate
copy outside the repo and was **deleted** after measurement. The real vault `12_Daily_Brief/` was never
written (dry-run / no apply).

---

## 3. Reusable proof helper + tests (the only committed code)

`src/hb_assistant/construction/second_brain/generated_output_proof.py` —
`build_generated_output_population_proof(db_path)` is **read-only** (opens `mode=ro`): per-table counts,
guard-column sums (discovered via `PRAGMA table_info`, every `*_persisted` / `*_performed` / `*_allowed`
column summed → must be 0), source-linkage, confidence-label presence, and a forbidden-pattern scan
(PEM / bearer / JWT / tokenized-URL) over the safe text columns (a match reports only `table.column`,
never the value). Fully typed; `ruff` + `mypy src` clean (273 files).

`tests/test_phase_09_generated_output_proof.py` (4 tests, all pass):
normal (seeded + populated → `proof_passed=true`, guards 0), empty (`populated=false`, no crash),
**no-raw fail-closed** (inject a tokenized URL → proof fails, value never echoed), stale-schema (below-V37
→ handled gracefully, tables reported missing).

---

## 4. Validation commands & results (HEAD `23e6d87`, `.venv/bin/python3.12`)

Captured under `validation-outputs-prompt-03/`.

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | ok |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | no issues / **273** files (new helper in scope) |
| `pytest -m "not live and not integration and not manual"` | 0 | green (prior 3016 + 4 new = **3020 passed**) |
| `construction-agent validate --json` | 0 | `ok=true`; `schema_version=37` |
| `construction-agent data-quality table-inventory --json` | 0 | schema 37; **0 unmapped** |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true` |
| `second-brain data-quality phase-08a/08b/08c-gates --json` † | 0 | `ok=true` (08c `proof_passed=true`) |
| `second-brain data-quality phase-08d-gates --json` † | 0 | `ok=true`; `ready_to_serve=true` |
| `second-brain mcp no-raw-access / no-writeback --json` † | 0 | `proof_passed=true` |

† Same CLI-spelling resolutions as Prompts 00–02. Evidence re-stamps from the proof builders were reverted
to keep the commit surgical (the `phase-08c-gates` append-only-ledger side effect from Prompt 02 still
applies; run once for the required matrix). The operator DB was opened read-only for verification.

---

## 5. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Raw-content persistence | No — every guard sum 0; forbidden-pattern scan clean on all 820 rows |
| External writeback | No — offline mock, dry-run, no vault, proof-DB copy only |
| Missing no-raw / no-writeback proof | No — `build_generated_output_population_proof` passes; MCP proofs pass |
| Unresolved high-impact review items entering an approved source manifest | N/A — no approved manifest exists yet |
| Unapproved Obsidian notes indexed | N/A — no vault write, no indexing |
| Semantic retrieval bypassing Research Packet / Evaluation | N/A — outputs flow research packet → evaluation; no semantic retrieval exists |

No stop condition triggered.

---

## 6. Verdict

G-01 **resolved (pipeline-proven)**: the Phase 08A generation pipeline produces controlled, source-linked,
confidence-labeled, **guard-clean** generated outputs offline (820 rows across research packets / daily-brief
runs / source refs / handoff lines / evaluation runs; all guard sums 0), demonstrated in a labeled proof-DB
copy with the **operator DB and real vault left pristine**. A reusable read-only proof helper + 4 tests are
committed (suite green). `parser_outputs` carried forward as out-of-scope (Phase 06A file-extraction). No
stop condition triggered. **Proceed to Phase 09 Prompt 04** (MCP runtime receipt & denial smoke).
