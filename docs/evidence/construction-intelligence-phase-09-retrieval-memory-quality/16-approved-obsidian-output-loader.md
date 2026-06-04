# Phase 09 Prompt 16 — Approved Obsidian Output Loader

**Evidence artifact:** `phase_09_approved_obsidian_output_loader` · **Companion JSON:** `16-approved-obsidian-output-loader.json`
**Proof companions:** `approved-obsidian-loader-proof.json` (+ `.md`).
**Classification:** Phase 09 implementation — first per-category node-preparation loader (Obsidian), reusing the Prompt 14 embedding guardrail.
**Schema:** V38 (unchanged). **Version:** 1.3.0.
**Posture:** metadata-only, local-only, read-only, fail-closed, apply-manifests-only. **No embeddings computed and no index built.**
**Builds on:** records 131–134 (V38 schema, LlamaIndex config, embedding policy, approved-source manifest); reuses `validate_embedding_candidate` + `_FORBIDDEN`/`_assert_no_raw` + the apply-manifest read idiom + `write_linkage_fixture_vault`/`build_index`.

---

## 1. Purpose

Phase 09's node-preparation layer (architecture doc 05 layer 2) converts approved outputs into safe
nodes for embedding. This prompt delivers the **Obsidian** loader: it loads **only approved,
source-linked generated Obsidian notes** — the entries of the latest **`mode='apply'`** index manifest
— and validates each as an embedding candidate. Dry-run/unapproved manifests are never loaded (the
"unapproved Obsidian notes indexed" stop condition cannot be hit). No embeddings computed, no index
built; node persistence is deferred to Prompts 18–19.

## 2. What changed

### Loader (`retrieval/obsidian_loader.py`)
- `load_approved_obsidian_nodes(db_path, *, project_key)` — read-only (`mode=ro`): fail-closed schema
  check (≥38); strict **`WHERE mode='apply'`** latest-manifest read (not the `list_approved_*` helper,
  which falls back to dry_run); builds metadata-only candidate nodes (`node_id`, `source_family`,
  `source_ref`, `content_hash`, `confidence_class`, `review_tier`, `review_status`, `review_required`,
  `freshness_label`, `source_ref_count`, `text_redacted` = the bounded redacted heading/section);
  validates each via Prompt 14's `validate_embedding_candidate` (embeddable family + required metadata +
  no forbidden fields + raw-shape scan + tier-3/unresolved exclusion). Returns the approved node list.
- `build_obsidian_loader_report(...)` — metadata-only summary (counts + per-node hashes; **no text**);
  status `loaded`/`empty` + `no_approved_obsidian_notes` warning.
- `build_obsidian_loader_proof(...)` — fail-closed proof combining an apply-mode fixture DB (loads ≥1),
  a dry-run-only fixture DB (loads 0), and candidate guardrail cases; writes a guard-clean JSON+MD
  companion (`_assert_no_raw` before write; synthetic raw shapes assembled at runtime). No operator-DB writes.

### CLI
- New nested `second-brain retrieval obsidian-loader status|proof` group (read-only).

## 3. Key results (live)

- `obsidian-loader status` (operator DB): **status `empty`**, `loaded_count=0` — the operator has 0
  apply-mode obsidian manifests (1 dry-run manifest, 0 apply entries), so the loader honestly loads
  nothing (dry-run/unapproved never loaded). Exit 0; warning `no_approved_obsidian_notes`.
- `obsidian-loader proof`: **`proof_passed=true`** — an apply-mode fixture index loads **2** guard-clean
  nodes; a dry-run-only fixture index loads **0** (unapproved excluded); the embedding guardrail rejects
  the planted tier-3 `review_required`, non-embeddable-family, missing-metadata, and raw-shape
  candidates. Guard-clean JSON+MD written.
- Operator DB: schema **38**; obsidian manifests/entries unchanged (loader read-only).

## 4. Validation

`compileall` exit 0 · `ruff check .` clean · `mypy src` clean (**285** source files) ·
`pytest -m "not live and not integration and not manual"` → **3110 passed / 0 failed / 1 deselected**
(prior 3101 + 9 new) · `construction-agent validate` 4/4 schema **V38** · `table-inventory` 190 / 0
unmapped · `no-writeback-proof` `proof_passed=true` · `phase-08a-gates`/`phase-08b-gates` ok ·
`mcp no-raw-access`/`mcp no-writeback` `proof_passed=true` · `retrieval obsidian-loader status`/`proof`
exit 0. `phase-08c-gates` deliberately skipped (mutating append-only ledger — disclosed Prompts 02/05).
Captures under `validation-outputs-prompt-16/`.

The 9 new tests cover: normal apply load + metadata-only report; missing-policy fail-closed;
stale-schema fail-closed; dry-run-only loads 0; guardrail excludes tier-3/non-embeddable/raw candidates;
proof passes + is clean; proof writes guard-clean artifacts; loader does not mutate the DB; CLI exit codes.

## 5. Guardrails & stop conditions

Read-only (`mode=ro`), persists nothing; **apply-manifests-only** (unapproved/dry-run notes never
loaded); metadata-only report/evidence (the redacted heading rides only on in-memory nodes, never
echoed); each node passes the embedding guardrail (no raw / no forbidden fields / embeddable family /
no unresolved high-impact); review tier / confidence / source refs / freshness preserved. No embeddings
or index built; no external writeback. No stop condition triggered.

## 6. Deferred / owning prompts

Reviewed-memory loader — Prompt 17. Embedding + vector index build — Prompts 18–19 (will consume the
loader's nodes, intersected with the approved manifest + embedding policy). Node text enrichment beyond
the indexed redacted heading is a build-phase concern.
