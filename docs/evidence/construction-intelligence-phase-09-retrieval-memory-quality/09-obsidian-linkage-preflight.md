# Phase 09 — Prompt 09: Approved Obsidian Linkage Preflight

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/09-obsidian-linkage-preflight.md`
**Machine-readable companion:** `09-obsidian-linkage-preflight.json` (+ `obsidian-linkage-proof.json`, `broken-link-classification.json`)
**Captured outputs:** `validation-outputs-prompt-09/`
**Gap:** G-07 (approved Obsidian linkage — `obsidian_index_entries` 0 rows; wikilinks counted but never validated)
**Audit date:** 2026-06-04 · **HEAD (audited):** `23e6d87` (worked at `f617b86`) · **Schema:** V37 · **Version:** 1.3.0
**Posture:** Additive **canonical link metadata** on the existing approved indexer + a **read-only linkage proof** with a **broken-link check** (resolved / broken / stale-unknown). Metadata-only (redacted hashes + counts); **no schema migration**; reads the operator DB read-only (verified unmutated). **No LlamaIndex/embeddings/vector/semantic-retrieval code.**

---

## 1. Scope & guardrail posture

G-07 remediation, "approved Obsidian output linkage with canonical source refs and broken-link checks, before
semantic retrieval." The operator substrate is empty (`obsidian_index_entries` = **0 rows**; one pre-existing
dry-run manifest), and the Phase 08A indexer **counted** `[[` wikilinks (`source_ref_count`) without ever
**validating** them. This prompt (a) extends the indexer to capture **canonical, redacted** link identity in
the already-`TEXT` `source_refs_json` (no migration), and (b) adds a read-only proof that classifies each link
and re-attests the no-raw / no-writeback / approved-only posture. Broken / stale links are **advisory
source-coverage warnings** — never a final determination — so they do not by themselves fail the proof; the
hard failures are guard violations, raw-content, writeback, stale schema, missing policy, or an **unapproved
note entering the index**.

---

## 2. Canonical link metadata (additive, no schema change)

`source_refs_json` (already a `TEXT` column) now also carries two **redacted, metadata-only** keys, computed by
a shared normalizer (`_normalize_link_target`: drop `|alias` + `#anchor`, lowercase, collapse whitespace) and
the existing 16-char `_sha`:

| Key | Meaning | Raw content? |
|---|---|---|
| `note_name_hash` | hash of the entry's own note name (filename stem) — the identity a wikilink resolves against | No — digest only |
| `link_target_hashes` | distinct hashes of each `[[target]]` wikilink's normalized stem | No — digests only |

No raw note names or paths are persisted. Existing entries without the keys default to empty (backward
compatible); the model gains two optional fields and existing `meta["…"]` consumers are unaffected.

---

## 3. Linkage proof — operator DB (pristine) + controlled proof DB

`build_obsidian_linkage_proof(db_path)` — read-only (`mode=ro`, path-agnostic). For the latest index manifest
it sums the `obsidian_index_manifests` guard `CHECK(=0)` columns, checks canonical-ref preservation
(`content_hash`/`section_marker`/`confidence_class`/`review_status` + `review_tier`/`approved_root_label`),
enforces **approved-only** (`approved_root_label ∈ policy.approved_roots`), classifies each wikilink against
the manifest's resolvable note-name set, and scans the redacted columns for forbidden raw shapes (reporting
only `table.column`).

| Target | Result |
|---|---|
| **Operator DB** (read-only) | `obsidian_index_manifests` = 1, **`obsidian_index_entries` = 0** → `populated=false`, `guard_sum=0`; **unchanged before == after** (read-only `mode=ro`) |
| **Controlled proof DB** (throwaway fixture vault → existing `build_index`, apply) | 2 entries, 1 excluded; `guard_sum=0`; canonical refs preserved; **approved_only=true**; links **total 3 → 2 resolved / 1 broken / 0 stale**; `raw_content_findings=[]`; **`proof_passed=true`** |

The fixture (`write_linkage_fixture_vault`) writes two approved notes that wikilink each other by filename
(**resolved**) plus a dangling `[[Missing Note]]` (**broken**) and one unmanaged note (**excluded**), entirely
inside a temp dir — the operator DB and the real vault are never touched.

---

## 4. Reusable helper + CLI + tests (committed code)

`src/hb_assistant/construction/second_brain/obsidian_linkage_proof.py` — `build_obsidian_linkage_proof`
(read-only `mode=ro`; hashes + counts only) and `write_linkage_fixture_vault` (temp-dir-only fixture). Fully
typed; `ruff` + `mypy src` clean (**278** files).

`src/hb_assistant/construction/second_brain/obsidian_index/{indexer,models}.py` — additive `note_name_hash` +
`link_target_hashes` capture (no migration).

`src/hb_assistant/cli/second_brain.py` — new read-only command
`hb-assistant second-brain index linkage-proof --json [--db-path PATH]` (operator DB by default → 0-row
posture; `--db-path` for a proof DB).

`tests/test_phase_09_obsidian_linkage_proof.py` (7 tests): normal resolved+broken population; empty operator
substrate; **missing-policy fail-closed**; **stale-schema** graceful; **unapproved-note hard failure**;
**no-raw injection** fail-closed (value never echoed; DB row count unchanged → no-writeback); **broken-link
advisory** (does not fail the proof).

---

## 5. Validation commands & results (`.venv/bin/python3.12`)

Captured under `validation-outputs-prompt-09/`.

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | ok |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | no issues / **278** files |
| `pytest -m "not live and not integration and not manual"` | 0 | green (prior 3039 + 7 new = **3046 passed**) |
| `construction-agent validate --json` | 0 | `ok=true` (4/4); `schema_version=37` |
| `construction-agent data-quality table-inventory --json` | 0 | schema 37; **0 unmapped live tables** |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true` |
| `second-brain data-quality phase-08a / phase-08b / phase-08d-gates --json` † | 0 | `ok=true` (08d `proof_passed=true`) |
| `second-brain mcp no-raw-access / no-writeback --json` † | 0 | `proof_passed=true` |
| **`second-brain index linkage-proof --json`** (new) | 0 | operator DB `populated=false`, `entry_count=0`, `proof_passed=true` |

† Same CLI-spelling resolutions as Prompts 00–06/08. Evidence re-stamps from the proof builders were reverted
to keep the commit surgical. **`phase-08c-gates` was deliberately skipped:** per the Prompt-02/05 disclosure it
appends ~1,299 rows to the append-only financial review ledger per call (a write to the operator DB), which
would violate this prompt's pristine-operator-DB posture; it is unrelated to the Obsidian-linkage surface and
was green at Prompt 06.

---

## 6. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Raw-content persistence | No — only redacted hashes + counts stored; forbidden-shape scan clean; no raw names/paths |
| Writeback | No — read-only `mode=ro`; operator DB `obsidian_index_*` counts unchanged (before == after) |
| Missing no-raw / no-writeback proof | No — linkage proof guardrails + MCP no-raw/no-writeback proofs pass |
| Unresolved high-impact review items entering an approved source manifest | N/A — no review items routed; indexer indexes approved generated notes only |
| **Unapproved Obsidian notes being indexed** | **No — `approved_only=true`; an out-of-policy `approved_root_label` is a hard failure (covered by a dedicated test)** |
| Semantic retrieval bypassing Research Packet / Evaluation | N/A — no retrieval/embeddings/vector code added (preflight) |

No stop condition triggered.

---

## 7. Verdict

G-07 **remediated (preflight)**: approved Obsidian linkage now carries **canonical, redacted source refs**
(`note_name_hash` + `link_target_hashes`, no migration) and a **read-only broken-link check** that classifies
each wikilink as resolved / broken / stale-unknown and re-attests guard-clean / no-raw / no-writeback /
approved-only. Demonstrated on a controlled proof DB (2 resolved / 1 broken, `proof_passed=true`) with the
operator DB and real vault left **pristine** (`obsidian_index_entries` 0 before == after). A reusable read-only
helper, the additive indexer capture, a read-only CLI command, and 7 tests are committed (suite green). No stop
condition triggered. **Proceed to the remaining Phase 09 preflight prompts** (G-05 memory, G-08 relationship
quality, G-10 corpus balance).
