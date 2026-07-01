# Phase 10D — Tropical bounded corpus entity enrichment + graph-signal proof (safe summary)

Count-only summary. No source paths, card filenames, or note bodies. Runtime detail, the DB backup,
and the rollback card manifest are kept under `local-sensitive/` (untracked, never committed).

## Base
- Base commit: `c2b4f702` (`origin/main`; Phase 10C merged at `617bc4a8`).
- Branch: `feat/obsidian-phase10d-tropical-entity-enrichment` worktree.

## Runtime preconditions (read-only)
- Backend on :8000 clear; runtime frozen flags all `false`
  (`external_source_watch_enabled`, `source_card_auto_generate_enabled`,
  `source_summary_auto_generate_enabled`, `source_note_auto_refresh_enabled`).
- Write capability `true` (`source_card_generation_enabled`, `writes_enabled`,
  `vault_markdown_write_enabled`); vault_root and `syn-work` root matched config.
- Queue 0/0; generated notes before run: generated 25 / not_generated 67.

## Source-root confirmation (sanitized)
- `--source-root` == `--confirm-source-root` == the allowlisted `23-435-01 - Tropical` project folder,
  resolved **under** the configured `syn-work` external-source root. All reads bounded to that folder.

## Folder identity parse → procore resolution (read-only)
- Folder parse: `project_number=23-435-01`, `short_name=Tropical`, `year=2023`.
- Resolved against `procore_ep_projects` (reused read model; DB project rows never mutated):
  - `project_key=tropical`, `procore_project_id=2525840`,
    canonical name `Tropical World Nursery Senior Living Facility`.
  - External alias/acronym `TWN` attached from the project alias **seed** only — not asserted as a DB value.
  - `project_match_basis = [folder_project_number, procore_project_number, procore_project_key]`
    (folder-derived number and canonical Procore identity reported separately, per amendment #1/#2).
- Derived number asserted equal to `--confirm-project-number 23-435-01` / key `tropical`.

## Bounded selection (dry-run; stat-only readability, no forced download)
- files_readable_seen: 935 · cloud_evicted: 1231 · skipped_temp/hidden: 168 · skipped_nondoc: 8000
- files_selected: 100 (capped at `--max-files 100`)
- by_extension: pdf 15, xlsx 15, csv 15, eml 15, md 14, xls 10, xer 8, docx 5, ods 1, rtf 1, xlsm 1
- by_folder_bucket: 00_Project_Admin 40, 30_Financials 36, 20_Construction 20, 50_3rd_Party 4

## Bounded apply (production; rollback bundle taken first)
- Rollback bundle written under `local-sensitive/` before any write: DB backup + `rollback-manifest.json`
  + pre-run copy of existing cards (amendment #5). No bundle ⇒ no apply.
- files_indexed_new: 100 · already_indexed: 0 · skipped_unavailable: 0
- project_number_derived (auto from rel-path `23-435-01` code): 100 / 100
- cards_generated: 100 · cards_skipped_existing: 0 · cards_enriched_existing: 100 · metadata_only: 31
- ollama_calls: 0 (deterministic indexing — no cloud/local model during index or enrichment)
- queue_delta: 0 (no watcher start, no queue drain, no broad scan)
- generated notes: before 25 → after 125 (expected +100 delta; authorized bounded growth)

## Graph-signal proof (Phase 10C tool, `--dry-run` only — NO link/tag apply)
- candidate_pairs: 100 (capped at `--max-relationships 100`)
- candidate_basis_counts:
  - same_project_number: 100
  - same_project_key: 100
  - same_procore_id: 100
  - same_document_type: 100
  - same_document_number: 1
  - shared_title_phrase (weak): 29
- Candidates are driven by the deterministic project-identity signals (strong bases at 100 each), not by
  weak path/title matching (`shared_title_phrase` is a weak signal and never forms a candidate alone).
  Phase 10C showed 0 candidates on the metadata-poor cards; enrichment closes that gap.

## Amendment compliance
1. Path-derived `project_number` retained on the DB source row **and** canonical Procore identity added
   (23-435-01 / tropical / 2525840 / canonical name); `TWN` alias-seed-only, never falsely a DB value.
2. Graph proof distinguishes identity bases separately (project number vs canonical key vs procore id vs
   document type/number); candidates proven from enriched metadata, not weak signals.
3. Canonical identity is **graph-readable**: enrichment writes a managed `hb-project-identity` block whose
   start marker carries `project_number`/`project_key`/`procore_project_id`; the facts layer parses it —
   no DB schema change, not human-visible-text-only.
4. Same-project-only pairs are treated as **proof candidates**, not auto-apply. Link/tag apply is deferred
   to Phase 10E (needs local vetting + human-review report); recorded here as evidence only.
5. Rollback bundle taken before apply (DB backup + card manifest, local-sensitive). Enforced gate.
6. Committed: code + tests + this count-only safe summary only. Card bodies, source paths, filenames,
   backups, and runtime JSON stay under `local-sensitive/` (untracked).
7. Apply is idempotent: already-indexed/carded files are skipped unless `--update`; a unit test proves the
   second run reports `already_indexed` and `cards_generated == 0`.

## Validation
- `py_compile` clean on the new module + script.
- `ruff check` clean on all changed files.
- Tests green: `test_obsidian_source_project_identity.py`, `test_obsidian_source_project_corpus.py`,
  `test_obsidian_source_entity_enrichment.py`, plus unchanged regression
  (`test_obsidian_source_note_graph.py`, `test_obsidian_source_card_local_summary_appender.py`,
  `test_obsidian_source_taxonomy_phase10a.py`, `test_obsidian_source_notes.py`,
  `test_obsidian_source_note_domain_routing.py`) and the slow suites (watch-ownership, mcp-backend).
  No Phase 10A/10B/10C test weakened.

## Not done (by design)
No graph link/tag apply, no note delete/rename/move, no DB project-row mutation, no cloud model,
no full-vault/all-projects/broad-Synology scan, no runtime-config mutation, no push, no PR.
