# 128 — Phase 09 Prompt 09: Approved Obsidian Linkage Preflight (gap G-07)

**Status:** Preflight remediation (Prompt 09 — canonical source refs + broken-link check; read-only linkage proof).
**Schema:** V37 (unchanged). **Version:** 1.3.0. **HEAD (audited):** `23e6d87` (worked at `f617b86`, Prompt 08 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/09-obsidian-linkage-preflight.md` (+ `.json`).
**Builds on:** records 120–127 (Prompts 00–08); the Phase 08A approved Obsidian indexer (`construction/second_brain/obsidian_index/`).

---

## 1. Purpose

Resolve gap G-07 — the approved Obsidian index (V26 `obsidian_index_*` tables) is structurally present but
**0 rows** in the operator DB ("sqlite-linked-by-frontmatter 0"), and the existing indexer **counted** `[[`
wikilinks (`source_ref_count`) without ever **validating** them. Build approved Obsidian output linkage with
**canonical source refs** and a **broken-link check** so that, before any Phase 09 semantic-retrieval build,
note-to-note linkage is provably resolvable, approved-only, and guard-clean. Preflight boundary unchanged:
no LlamaIndex / embeddings / vector / semantic-retrieval code; metadata-only; no schema migration (V38 stays
reserved for the real build).

## 2. Canonical link metadata (additive, no migration)

The indexer's `source_refs_json` (a `TEXT` column — additive JSON, backward-compatible) now also carries two
**redacted, metadata-only** keys, computed by a shared normalizer (`_normalize_link_target` drops `|alias` and
`#anchor`, lowercases, collapses whitespace) hashed with the existing 16-char `_sha`:

- `note_name_hash` — hash of the entry's own note name (filename stem); the canonical identity a wikilink
  resolves against.
- `link_target_hashes` — distinct hashes of each `[[target]]` wikilink's normalized stem.

No raw note names or paths are persisted — only digests — so target identity is checkable without raw content.

## 3. Read-only linkage proof + controlled population

`construction/second_brain/obsidian_linkage_proof.py` · `build_obsidian_linkage_proof(db_path)` — read-only
(`mode=ro`, path-agnostic). For the latest index manifest it verifies: every `obsidian_index_manifests` guard
`CHECK(=0)` column sums to 0 (no raw body / prompt / URL / writeback); every entry preserves its canonical refs
(`content_hash`, `section_marker`, `confidence_class`, `review_status` + `review_tier`/`approved_root_label` in
the blob); every `approved_root_label` is inside the loaded policy's approved roots (an out-of-policy /
unapproved note in the index is a **hard failure**); and each wikilink (by target hash) is classified
**resolved** (target name indexed in the same manifest) / **broken** / **stale_unknown**. Broken / stale links
are surfaced as **advisory source-coverage warnings** — never a final determination — so they do not by
themselves fail the proof. A forbidden-raw scan (PEM / Bearer / JWT / signed-URL shapes) over the redacted
columns reports only `table.column`, never the value.

A companion `write_linkage_fixture_vault(tmp)` writes a throwaway fixture vault (two approved notes that
wikilink each other by filename → resolved, plus a dangling `[[Missing Note]]` → broken, plus one unmanaged
note → excluded) into a caller temp dir, so tests and the evidence driver populate a proof DB via the existing
`build_index` without ever touching the operator DB or the real vault. Against the controlled proof DB:
2 entries, guard sum 0, 3 links → **2 resolved / 1 broken**, raw-clean, `proof_passed=true`. Against the
operator DB: `populated=false`, `entry_count=0` (pristine G-07 posture).

## 4. CLI surface

`hb-assistant second-brain index linkage-proof --json [--db-path PATH]` (on `index_app`). Default targets the
operator DB (honest 0-row posture); `--db-path` lets the evidence driver point at a populated proof DB.

## 5. Guardrails & stop conditions

Read-only verifier; metadata-only (hashes + counts); no Graph/Procore/email/calendar/Slack/Teams/SMS/push/
external writeback; no raw content/prompts/responses/tokens/URLs/PEMs/arbitrary SQL; no raw vector search; no
final financial/legal/contractual/safety determinations. Fail-closed on missing policy and stale schema.
Hard-fails on unapproved notes entering the index. No stop condition triggered.
