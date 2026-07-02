# Tropical Source Availability — Findings (count-only)

## Result: **A. Source availability blocker** (not a traversal defect)

The Tropical SynologyDrive source root **exists** and **is a directory**, but is **not listable**: a
resilient `os.scandir` walk that **retries EINTR (3×)** still fails to enumerate the root
(`root_listable: false`, `interrupted_system_call_count: 1`). Because a strictly-more-resilient walk than
the selectors' `sorted(root.rglob("*"))` also returns zero, the zero-candidate outcome is caused by the
OS/SynologyDrive keeping the folder cloud-dormant (on-demand, not materialized locally) — **not** by a
traversal/detection bug in the project/eml selectors. No selector change is warranted.

## Evidence (stat-only; no byte reads; no hydration)
- Source root: exists=true, is_dir=true, **listable=false**.
- Files seen: 0; directories seen: 0; locally-readable supported files: 0; placeholders detected: 0
  (nothing could be enumerated to classify).
- Errors: interrupted_system_call_count=1 (persistent EINTR on the root scandir, retried 3×);
  permission_error_count=0; other_error_count=0.
- DB readiness (reconcile): missing_generated_note_rows=0, orphan_vault_cards=0, queue=0/0,
  runtime_state_unchanged=true, source_row_count=9128.
- Project-corpus dry-run: mode=dry-run, files_readable_seen=0, files_selected=0, cards_generated=0,
  queue_delta=0, ollama_calls=0.
- Email-archive dry-run: mode=dry-run, eml_found=0, eml_selected=0, archive_notes_created=0,
  queue_delta=0, ollama_calls=0.

## Whether zero candidates is explained
Yes — fully explained by source availability (root not enumerable). No selector defect was found, so
selector logic was **not** changed. The only code added is a reusable read-only diagnostic probe
(`scripts/obsidian_source_root_availability_probe.py`) + tests.

## Locally-available-files note
Because the root itself will not enumerate, any files that are individually hydrated in subfolders cannot
be discovered by directory traversal — the OS does not return the child entries. Detection of "some
locally available files" requires the containing directories to be listable first.

## Recommended next operator step (bounded, explicit)
In SynologyDrive, make the Tropical project folder (or a bounded subfolder) **available offline** so its
directory listing materializes locally, then re-run — with no code change — in this order:
1. `obsidian_source_root_availability_probe.py --source-root <SRC>` (stat-only) → expect
   `root_listable: true` and nonzero `candidate_doc_ext_count` / `candidate_eml_count`.
2. Optionally, to confirm true local availability without hydration risk:
   add `--read-probe-limit N --confirm-read-probe-local-files` (byte-reads only fully-local files;
   placeholders are never opened).
3. Re-run the project-corpus and email-archive dry-runs to obtain nonzero candidate counts **before** any
   authorized apply.

## CORRECTION (2026-07-02, superseded by the bounded-subroot pass)

The "availability blocker" conclusion above is **too strong** and is corrected here (original text
preserved above for the record). Root-level EINTR only means the **root** will not enumerate — it does
**not** prove every descendant is unavailable. Path-targeted `lstat` (no hydration) subsequently
confirmed that a **named construction descendant exists** under the dormant root, and Bobby's Finder
evidence shows locally-available descendant files. The correct remedy is **bounded subroot traversal**
(start the walk at an explicit, contained, symlink-safe descendant, bypassing the failing root scandir),
which has now been implemented (`--include-subroot` on the probe and both indexers, plus
`src/hb_assistant/obsidian_mcp/source_subroot.py`). See the superseding evidence bundle
`docs/evidence/obsidian-phase10l-bounded-subroot-traversal-*/` for the corrected finding and live
count-only results.
