# 134 — Phase 09 Prompt 15: Approved Index Source Manifests

**Status:** Implementation — approved source manifest builder + approval/no-raw guardrail + proof (no retrieval runtime built).
**Schema:** V38 (unchanged). **Version:** 1.3.0. **HEAD (audited):** `23e6d87` (worked at `3c1004e`, Prompt 14 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/15-approved-index-source-manifests.md` (+ `.json`, `approved-source-manifest-proof.{json,md}`, `validation-outputs-prompt-15/`).
**Builds on:** records 131 (V38 substrate) + 132 (LlamaIndex config) + 133 (embedding policy); reuses the shared `_FORBIDDEN`/`_assert_no_raw`/`FORBIDDEN_REFERENCE_FIELDS`/`EXCLUDED_FAMILIES` primitives and the latest-apply-Obsidian-manifest selection idiom.

---

## 1. Purpose

The semantic-retrieval plane may index only approved, redacted, source-linked records. An **approved
source manifest** enumerates which records from three categories — generated outputs, approved Obsidian
outputs, reviewed memory — are eligible, and is the gate the vector-index build (Prompts 18–19) reads.
Prompt 15 delivers the manifest contract + seed, a read-only fail-closed builder + approval/no-raw
guardrail, a dry-run-default CLI build + proof. No embeddings computed, no index built.

## 2. Design

### Manifest = metadata-only summary
The V38 `second_brain_retrieval_approved_source_manifests` table is a single **summary row** (counts +
hash + tier summary + status); there is no per-entry table by design. The builder enumerates candidate
refs, hashes each (`source_ref_hash`, `content_hash`), and persists only aggregate counts and a
deterministic `manifest_hash` over the sorted approved-entry hashes — so the manifest is reproducible
without ever storing a raw ref or content.

### Three categories, reusing existing readers/idioms
- **generated outputs** = `second_brain_research_packets` (`review_status='accepted'`).
- **approved Obsidian outputs** = entries of the **latest `mode='apply'`** `obsidian_index_manifests`
  (apply = approved; dry-run excluded — the "unapproved notes" stop condition cannot be hit), reusing
  the latest-apply selection idiom from `corpus_balance_mart`/`obsidian_linkage_proof`.
- **reviewed memory** = `long_term_memory_items` (`review_status='accepted'`).

### Approval/no-raw guardrail as a single primitive
`validate_manifest_entry` composes the shared safety primitives (`_FORBIDDEN`,
`FORBIDDEN_REFERENCE_FIELDS`, `EXCLUDED_FAMILIES`) with the manifest's review-gating rules: exclude raw
families, excluded/unapproved review statuses, **unresolved high-impact** (tier > max-auto-approval or
`review_required` with status ≠ accepted — the stop condition cannot be hit), missing required
metadata, forbidden fields, and raw/secret/URL shapes. It reuses the no-raw primitives directly rather
than Prompt 14's family-bound `validate_embedding_candidate`, because the manifest's eligible families
(e.g. research packets) differ from the broker embeddable set; the build (18–19) later intersects
manifest ∩ embedding policy.

### Read-only by default; persistence opt-in
The builder opens the DB `mode=ro` and never writes; `persist_approved_source_manifest` (opt-in via
`--apply`) writes a single guard-clean summary row. The operator DB is left pristine (no `--apply`);
persistence is proven in a proof-DB test. The proof is in-memory and writes only its evidence companion.

## 3. Verification

Live: `approved-sources build` against the operator DB → status `empty` (sources empty → honest
source-coverage warnings); `proof` → `proof_passed`, 10 cases (3 safe approved, 7 planted excluded).
Proof-DB test: one accepted memory → `approved_ref_count=1`, guard-clean persisted row. Full matrix:
compileall/ruff clean, mypy 284 files, pytest **3101 passed** (3091 + 10 new), `construction-agent
validate` 4/4 V38, table-inventory 190 / 0 unmapped, 08A/08B/MCP gates + no-raw/no-writeback proofs
pass. Operator DB pristine (schema 38; manifest table 0 rows). `phase-08c-gates` skipped (mutating
ledger).

## 4. Guardrails & stop conditions

Metadata-only; read-only by default; persistence opt-in (single guard-clean summary row, not run on the
operator DB); unresolved high-impact / non-accepted / non-apply-Obsidian / raw-content entries
excluded; no embeddings / index built; no external writeback; review tier / confidence / source refs /
freshness preserved. No stop condition triggered.
