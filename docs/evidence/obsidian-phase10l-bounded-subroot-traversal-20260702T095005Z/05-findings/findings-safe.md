# Bounded Subroot Traversal — Findings (count-only)

## Corrected conclusion (supersedes the earlier "availability blocker" framing)
- The project **root** fails root-level enumeration (`source_root_listable: false`, scandir EINTR).
- That does **not** prove all descendants are unavailable. Path-targeted `lstat` (no hydration) confirms
  a **named construction descendant exists** under the root (`existing_but_dormant_eintr: 1`), even though
  the root won't enumerate.
- Therefore the indexer needed a **bounded subroot / explicit-path traversal fallback** — now added.

## What was delivered (code changed = yes)
- New `src/hb_assistant/obsidian_mcp/source_subroot.py`: lexical `validate_subroot` (reject absolute /
  `..` / source-root escape), `is_contained`, `scandir_listable`, and a symlink-safe, EINTR-resilient,
  containment-checked `walk_files`.
- `--include-subroot` (repeatable) added to `obsidian_source_index_project_corpus.py`,
  `obsidian_source_index_eml_archive.py`, and `obsidian_source_root_availability_probe.py`. When
  supplied, traversal starts **at** each bounded subroot (bypassing the failing root scandir); project
  identity still resolves from `--source-root`.
- Symlink dirs are never followed; a symlink subroot is reported unusable; every emitted candidate is
  re-checked for lexical containment (`containment_rejected`).
- Tests prove: root EINTR while a supplied subroot is still traversed; absolute/`..` subroots refused;
  subroot selection for corpus and `.eml`; identity stays bound to source-root; symlink dirs not
  recursed; dry-run writes nothing.

## Live bounded dry-run status (this machine, headless)
- Subroot discovery (count-only): candidate_subroots_probed 7 → existing_but_dormant_eintr 1,
  missing 6, listable 0.
- Probe with `--include-subroot <cited construction subroot>`: source_root_listable false;
  include_subroots_requested 1, include_subroots_listable 0, include_subroots_failed 1;
  files_seen_under_include_subroots 0.
- Project-corpus dry-run: mode dry-run; include_subroots_failed 1; files_selected 0; cards_generated 0;
  queue_delta 0; ollama_calls 0.
- Email-archive dry-run: mode dry-run; include_subroots_failed 1; eml_selected 0; archive_notes_created 0.
- Interpretation: the cited construction subroot **exists** but is still **dormant for headless
  `scandir`** (Finder browsing triggers on-demand hydration that a headless process does not). So the
  bounded dry-run currently selects 0 — the feature ran correctly and reported the subroot as
  not-listable rather than silently returning empty.

## Whether zero candidates is explained
Yes — the specific subroot is currently not headless-listable (dormant). This is **not** a traversal
defect: the same bounded walk selects files in tests once a subroot is listable.

## Recommended next operator step (bounded, explicit)
In SynologyDrive, right-click the specific descendant folder (e.g. the permits/fire-phasing-approval
subtree) → **Make Available Offline** so its listing materializes for headless access. Then re-run — no
code change:
1. `obsidian_source_root_availability_probe.py --source-root <SRC> --include-subroot <that relative
   path>` → expect `include_subroots_listable: 1` and nonzero
   `candidate_doc_ext_count_under_include_subroots`.
2. Project-corpus / email-archive dry-runs with the same `--include-subroot` → nonzero candidates before
   any authorized apply.
