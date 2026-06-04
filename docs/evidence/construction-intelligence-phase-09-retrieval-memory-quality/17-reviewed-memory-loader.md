# Phase 09 Prompt 17 — Reviewed Memory Loader

**Evidence artifact:** `phase_09_reviewed_memory_loader` · **Companion JSON:** `17-reviewed-memory-loader.json`
**Proof companions:** `reviewed-memory-loader-proof.json` (+ `.md`).
**Classification:** Phase 09 implementation — second per-category node-preparation loader (reviewed memory); completes the loader pair (Obsidian + memory).
**Schema:** V38 (unchanged). **Version:** 1.3.0.
**Posture:** metadata-only, local-only, read-only, fail-closed, reviewed-only (accepted). **No embeddings computed and no index built.**
**Builds on:** records 131–135 (V38 schema, LlamaIndex config, embedding policy, approved-source manifest, Obsidian loader); reuses `validate_embedding_candidate` + `_FORBIDDEN`/`_assert_no_raw` + `write_memory_item`/`MemoryItem`.

---

## 1. Purpose

The node-preparation layer (architecture doc 05 layer 2) converts approved outputs into safe nodes for
embedding. This prompt delivers the **reviewed memory** loader (sibling of Prompt 16's Obsidian loader):
it loads **only reviewed (accepted) long-term memory** — `long_term_memory_items` with
`review_status='accepted'` — and validates each as an embedding candidate. `pending_review`, `rejected`,
and `superseded` memory are never loaded (the "unreviewed memory entering a manifest" stop condition
cannot be hit). No embeddings computed, no index built; node persistence is deferred to Prompts 18–19.

## 2. What changed

### Loader (`retrieval/memory_loader.py`)
- `load_reviewed_memory_nodes(db_path, *, project_key)` — read-only (`mode=ro`): fail-closed schema
  check (≥38 + `long_term_memory_items` present); strict **`WHERE review_status='accepted'`** bounded
  read (with a `source_ref_count` from `long_term_memory_source_refs`); builds metadata-only candidate
  nodes (`node_id`, `source_family='accepted_long_term_memory'`, `source_ref`=memory_id,
  `content_hash`, `confidence_class`, `review_tier=1`, `review_status='accepted'`, `review_required=False`,
  `freshness_label`, `memory_type`, `source_ref_count`, `text_redacted`=bounded statement); validates
  each via Prompt 14's `validate_embedding_candidate` (embeddable family + required metadata + no
  forbidden fields + raw-shape scan). Returns approved nodes.
- `build_reviewed_memory_loader_report(...)` — metadata-only summary (counts + per-node hashes; **no
  statement text**); status `loaded`/`empty`; warnings `no_reviewed_memory` + advisory `unsourced_memory`.
- `build_reviewed_memory_loader_proof(...)` — fail-closed proof: accepted-memory fixture loads ≥1; a
  pending-only fixture loads 0; candidate guardrail cases; writes a guard-clean JSON+MD companion
  (`_assert_no_raw` before write; synthetic raw shapes assembled at runtime). No operator-DB writes.

### CLI
- New nested `second-brain retrieval memory-loader status|proof` group (read-only).

## 3. Key results (live)

- `memory-loader status` (operator DB): **status `empty`**, `loaded_count=0` — the operator has 0
  accepted long-term memory items, so the loader honestly loads nothing (pending/rejected/superseded
  never loaded). Exit 0; warning `no_reviewed_memory`.
- `memory-loader proof`: **`proof_passed=true`** — an accepted-memory fixture loads **1** guard-clean
  node; a pending-only fixture loads **0** (unreviewed excluded); the embedding guardrail rejects the
  planted non-embeddable-family, missing-metadata, raw-shape-statement, and unresolved-review
  candidates. Guard-clean JSON+MD written.
- Operator DB: schema **38**; `long_term_memory_items` unchanged (loader read-only).

## 4. Validation

`compileall` exit 0 · `ruff check .` clean · `mypy src` clean (**286** source files) ·
`pytest -m "not live and not integration and not manual"` → **3119 passed / 0 failed / 1 deselected**
(prior 3110 + 9 new) · `construction-agent validate` 4/4 schema **V38** · `table-inventory` 190 / 0
unmapped · `no-writeback-proof` `proof_passed=true` · `phase-08a-gates`/`phase-08b-gates` ok ·
`mcp no-raw-access`/`mcp no-writeback` `proof_passed=true` · `retrieval memory-loader status`/`proof`
exit 0. `phase-08c-gates` deliberately skipped (mutating append-only ledger — disclosed Prompts 02/05).
Captures under `validation-outputs-prompt-17/`.

The 9 new tests cover: normal accepted load + metadata-only report; missing-policy fail-closed;
stale-schema fail-closed; pending-only loads 0; guardrail excludes non-embeddable/raw/missing/unresolved
candidates; proof passes + is clean; proof writes guard-clean artifacts; loader does not mutate the DB;
CLI exit codes.

## 5. Guardrails & stop conditions

Read-only (`mode=ro`), persists nothing; **reviewed-only (accepted)** gate so pending/rejected/superseded
memory is never loaded; metadata-only report/evidence (the redacted statement rides only on in-memory
nodes, never echoed); each node passes the embedding guardrail (no raw / embeddable family); source
references reported (`source_ref_count`) with an advisory `unsourced_memory` warning; review tier /
confidence / freshness preserved. No embeddings or index built; no external writeback. No stop condition
triggered.

## 6. Deferred / owning prompts

Embedding + vector index build — Prompts 18–19 (consume the Obsidian + reviewed-memory loader nodes,
intersected with the approved manifest + embedding policy). This prompt completes the per-category
node-preparation loaders (Obsidian + reviewed memory).
