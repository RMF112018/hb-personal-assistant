# 135 — Phase 09 Prompt 16: Approved Obsidian Output Loader

**Status:** Implementation — first per-category node-preparation loader (Obsidian); read-only, no retrieval runtime built.
**Schema:** V38 (unchanged). **Version:** 1.3.0. **HEAD (audited):** `23e6d87` (worked at `d2e5e33`, Prompt 15 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/16-approved-obsidian-output-loader.md` (+ `.json`, `approved-obsidian-loader-proof.{json,md}`, `validation-outputs-prompt-16/`).
**Builds on:** records 131–134; reuses `validate_embedding_candidate` (Prompt 14), `_FORBIDDEN`/`_assert_no_raw`, the strict apply-manifest read idiom, and `write_linkage_fixture_vault`/`build_index` for proof/tests.

---

## 1. Purpose

Phase 09's node-preparation layer converts approved outputs into safe nodes for embedding. This prompt
delivers the Obsidian loader: load **only approved, source-linked generated Obsidian notes** (the latest
`mode='apply'` index manifest) and validate each as an embedding candidate, with no embeddings computed
and no index built. It is the first of the per-category loaders (Prompt 17 adds reviewed memory).

## 2. Design

### Approved = strict apply-mode only
The existing `list_approved_obsidian_index_entries` helper falls back to the latest **dry_run** manifest
when no apply manifest exists — unsafe for an "approved-only" loader. The loader therefore uses a strict
`WHERE mode='apply'` latest-manifest read; a dry-run-only or empty store yields **zero** nodes. This
makes the "unapproved Obsidian notes indexed" stop condition unreachable by construction.

### Reuse the embedding guardrail
`approved_obsidian_generated_outputs` is in the Prompt 14 embeddable allowlist, so each candidate node
is validated directly by `validate_embedding_candidate` — embeddable family, required source-linked
metadata, no forbidden raw fields, raw-shape scan over every value (including the redacted heading), and
tier-3/`review_required` exclusion (an unresolved high-impact note is dropped with no extra code). No new
guard logic is forked.

### Metadata-only surface; text stays in-memory
The index holds only redacted, bounded text (`heading_redacted`/`section_marker`) — never raw note
bodies. The loader carries that as `text_redacted` on the in-memory node objects (for the future
embedder), but the report, CLI, and evidence are **metadata-only** (counts + per-node hashes); the text
is never echoed. The loader opens the DB `mode=ro` and persists nothing — node persistence is Prompts
18–19.

### Self-contained proof
`build_obsidian_loader_proof` builds an apply-mode and a dry-run-only fixture index in temp DBs
(`write_linkage_fixture_vault` + `build_index`) and asserts apply loads ≥1 while dry-run loads 0, plus
candidate-level guardrail cases — covering the apply-only gate and the no-raw/no-unresolved exclusions in
one artifact.

## 3. Verification

Live: operator `obsidian-loader status` → `empty` (0 apply manifests); `proof` → `proof_passed`
(apply=2, dry_run=0, all candidate cases pass). Full matrix: compileall/ruff clean, mypy 285 files,
pytest **3110 passed** (3101 + 9 new), `construction-agent validate` 4/4 V38, table-inventory 190 / 0
unmapped, 08A/08B/MCP gates + no-raw/no-writeback proofs pass. Operator DB pristine (schema 38; obsidian
tables unchanged). `phase-08c-gates` skipped (mutating ledger).

## 4. Guardrails & stop conditions

Read-only; apply-manifests-only; metadata-only report/evidence; each node passes the embedding guardrail
(no raw / embeddable family / no unresolved high-impact); no embeddings or index built; no external
writeback; review tier / confidence / source refs / freshness preserved. No stop condition triggered.
