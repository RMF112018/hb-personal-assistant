# Phase 5 Summary (sanitized — counts only)

## Domain-routed Source Notes
- New generated cards route to `Source Notes/{Work,Home,Shared}/<sanitized-basename>__<source_id12>.md`.
- Domain via the single-source-of-truth `_domain_for` (extended: procore/sharepoint -> work).
- Filename: source basename only (no directory replication, no full path); 12-char source_id suffix
  for deterministic collision-safety; preserves UNIQUE(source_id, note_rel_path); overwrite=False never
  clobbers user files. Self-index guard already prefix-covers the routed subfolders.
- Sanitizer proven: no separators, no `..`, no leading-dot, no absolute fragments, no control chars,
  bounded length, deterministic `source` fallback, suffix preserved.

## First-indexing dry-run tool (read-only)
- `scripts/obsidian_source_first_indexing_dryrun.py`: single explicit --root-key required (no
  auto-fallback); refuses disabled/missing/unmounted root, active-vault root, quarantine root; symlinks
  recorded never followed; --max-files/--max-seconds caps; NO DB writes / enqueue / drain / generation
  / summaries / backend start.

## Production dry-run (syn-work, read-only)
- root_key=syn-work, max_files=500, max_seconds=120, cap_reached=true, elapsed ~0.1s, files_examined=500.
- counts_by_disposition: auto_card_high=98, auto_card_normal=323, metadata_only=77, unsupported=2.
- counts_by_domain: work=500.
- document types observed include: pay_application, purchase_order, submittal, schedule, specification,
  safety, manpower_log, drawing, closeout, cost_document, spreadsheet, general_pdf/general_document.
- skipped/deferred by reason: metadata_only_no_auto_card=77, unsupported_file_type=2. symlinks=0.

## Runtime status (read-only, pre-existing operator backend)
- A pre-existing operator backend (NOT started by this phase, main checkout) was on 8000; per rules,
  did not start a second and did not kill it. Read-only GET confirmed: clean vault recognized, queue
  0/0/0, generated/stale 0, watcher running in watchdog mode. Single-owner lease covered by tests.

## Tests / lint
- 200 targeted tests pass (incl. 11 domain-routing + 11 dry-run new). ruff clean. py_compile clean.

## Confirmations
- No production enqueue / queue drain / card generation / summaries / broad rescan.
- No phase-started backend left running; quarantine not deleted; external roots untouched.
- Sensitive evidence (dry-run detail, db baseline) kept local/untracked; only count-only summary committed.
