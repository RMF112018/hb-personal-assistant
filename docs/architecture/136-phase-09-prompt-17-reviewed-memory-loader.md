# 136 — Phase 09 Prompt 17: Reviewed Memory Loader

**Status:** Implementation — second per-category node-preparation loader (reviewed memory); read-only, no retrieval runtime built. Completes the loader pair.
**Schema:** V38 (unchanged). **Version:** 1.3.0. **HEAD (audited):** `23e6d87` (worked at `9115c9a`, Prompt 16 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/17-reviewed-memory-loader.md` (+ `.json`, `reviewed-memory-loader-proof.{json,md}`, `validation-outputs-prompt-17/`).
**Builds on:** records 131–135; reuses `validate_embedding_candidate` (Prompt 14), `_FORBIDDEN`/`_assert_no_raw`, `write_memory_item`/`MemoryItem`, and the read-only loader shape of `obsidian_loader.py` (Prompt 16).

---

## 1. Purpose

Phase 09's node-preparation layer converts approved outputs into safe nodes for embedding. This prompt
delivers the reviewed-memory loader, sibling to the Obsidian loader: load **only reviewed (accepted)
long-term memory** and validate each as an embedding candidate, with no embeddings computed and no index
built. Together with Prompt 16 it completes the two per-category loaders the build (Prompts 18–19) will
consume.

## 2. Design

### Reviewed = accepted only
The loader uses a strict `WHERE review_status='accepted'` read; `pending_review`/`rejected`/`superseded`
memory is never loaded, so the "unreviewed memory entering a manifest" stop condition is unreachable by
construction. Memory has no `review_tier` column — accepted is treated as resolved (`review_tier=1`,
`review_required=False`).

### Reuse the embedding guardrail
`accepted_long_term_memory` is in the Prompt 14 embeddable allowlist, so each candidate node is validated
directly by `validate_embedding_candidate` — embeddable family, required source-linked metadata, no
forbidden raw fields, and a raw-shape scan over every value (including the redacted statement). No new
guard logic is forked; this mirrors the Obsidian loader exactly, swapping the source and gate.

### Metadata-only surface; text stays in-memory
The redacted statement (`statement_redacted`) is carried as `text_redacted` only on the in-memory node
objects (for the future embedder); the report, CLI, and evidence are metadata-only (counts + per-node
hashes), never echoing the statement. The loader opens the DB `mode=ro` and persists nothing — node
persistence is Prompts 18–19. Source-linkage is reported (`source_ref_count`) with an advisory
`unsourced_memory` warning, not an exclusion.

### Self-contained proof
`build_reviewed_memory_loader_proof` seeds an accepted-memory and a pending-only fixture DB
(`write_memory_item`) and asserts accepted loads ≥1 while pending loads 0, plus candidate-level guardrail
cases — covering the reviewed-only gate and the no-raw exclusions in one artifact.

## 3. Verification

Live: operator `memory-loader status` → `empty` (0 accepted memory); `proof` → `proof_passed`
(accepted=1, pending=0, all candidate cases pass). Full matrix: compileall/ruff clean, mypy 286 files,
pytest **3119 passed** (3110 + 9 new), `construction-agent validate` 4/4 V38, table-inventory 190 / 0
unmapped, 08A/08B/MCP gates + no-raw/no-writeback proofs pass. Operator DB pristine (schema 38; memory
tables unchanged). `phase-08c-gates` skipped (mutating ledger).

## 4. Guardrails & stop conditions

Read-only; reviewed-only (accepted) gate; metadata-only report/evidence; each node passes the embedding
guardrail (no raw / embeddable family); no embeddings or index built; no external writeback; review
tier / confidence / source refs / freshness preserved. No stop condition triggered.
