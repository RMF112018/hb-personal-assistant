# 62 — Phase 08A: Approved Obsidian Indexing (Synthesized Prompt 05)

Status: implemented (Phase 08A Synthesized Prompt 05). Builds on records 57–61.
Local-first, read-only over the vault, no new SQLite tables, no source-note mutation.

## Purpose

Index **only** system-generated/approved, marker-bounded Obsidian notes (registers,
data-quality notes, daily briefs) into the V26 `obsidian_index_manifests` +
`obsidian_index_entries` tables — hashes, bounded path/heading labels, section
markers, review/confidence enums, and counts only. No raw note content, no raw
vault browsing, no source-note mutation. The index is the read-model for the
retrieval broker's `approved_obsidian_generated_outputs` family (closing the
Prompt-04 coverage gap).

## Policy + contract

- `resources/json/obsidian_index_manifest_contract.json` (v2) — required logical
  fields; registered in `second_brain/contracts.py`.
- `resources/config/phase_08a_obsidian_index_policy.seed.yaml` — `approved_roots`
  (Construction Intelligence Phase 07A/07C/07D + 08A Daily Briefs), `exclude`
  (attachments, raw source documents, unmanaged private notes, copied email bodies),
  `marker_boundaries_required`, `review_tier_metadata_required`.

**Managed-note detection:** a note is indexed only if it contains an
`<!-- HB-...:START -->` marker (the system's generated-output boundary). One index
entry per marker section; everything else (no marker, or an excluded path) is
counted in `excluded_count` and never indexed.

## Code (`construction/second_brain/obsidian_index/`, strict-mypy)

- `models.py` — `ObsidianIndexEntry` / `ObsidianIndexManifest` (Pydantic; URL guard
  on labels; tier 1/2/3).
- `policy.py` — `load_obsidian_index_policy()`, `MANAGED_MARKER_RE`, `is_excluded`.
- `indexer.py` — `scan_approved_notes` (walk approved roots, sha256[:16] of the
  bounded section text — text never stored; path hash; bounded heading/path labels;
  wikilink count as `source_ref_count`; defaults tier 1 / auto_advisory / high for
  approved generated outputs); `build_index` (dry_run/apply); `write_index_manifest`
  (persist manifest + entries, guard cols 0); `list_approved_obsidian_index_entries`
  (latest apply-or-recent manifest, for the broker); `build_approved_obsidian_index_proof`.

**Repo-truth reconciliation:** the V26 `obsidian_index_entries` table has no
`review_tier` / `approved_root_label` / `source_ref_count` columns; these contract
fields are carried inside the entry's `source_refs_json` metadata blob (safe JSON:
counts/enums/labels only). No schema change; schema head stays V26 / lifecycle 141.

## CLI

`hb-assistant second-brain index obsidian --dry-run | --apply --json` (mutual
exclusion, default dry-run; both modes persist a manifest with the matching `mode`;
fail-safe to 0 entries if the vault/roots are absent). Reports manifest_id,
entry_count, excluded_count, approved_roots, and the planned entries (safe fields).

## Retrieval integration

`retrieval/readers.py::read_approved_obsidian` reads
`list_approved_obsidian_index_entries` and maps entries into `RetrievalItem`s
(family `approved_obsidian_generated_outputs`), registered in `READER_REGISTRY` —
the broker now retrieves approved Obsidian outputs (previously a coverage warning).

## Guardrails

- **Read-only over the vault** — the indexer never opens a source note for writing
  (proven: source bytes unchanged after index).
- **No raw content** — only the section *hash* is stored, never the text; labels are
  bounded and URL-guarded; all 10 `CHECK(col=0)` guard columns stay 0.
- **No raw vault browsing** — only approved roots scanned; only marker-bounded
  managed notes indexed; excludes enforced.

## Out of scope (later prompts)
- HTML/delivery rendering → Phase 08B (08B-compat metadata only).
- Memory-note indexing beyond approved reviewed notes → later.
- 08A no-writeback proof arm / V27 → owning prompts.
