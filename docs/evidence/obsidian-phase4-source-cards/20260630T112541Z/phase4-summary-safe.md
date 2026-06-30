# Phase 4 Summary (sanitized — counts only)

## Generated-note retirement (status transition only)
- Transition: `generated`/`stale` -> `not_generated` (no migration, no row/file/source/event deletion).
- Dry-run candidate count: 67 (all under the Source Notes folder, all card files missing post-reset;
  0 invalid-path, 0 active-file-exists, 0 not-under-folder).
- Applied: retired 67. Before: {generated: 15, stale: 52}. After: {not_generated: 67}.
- No files deleted; quarantine untouched; external roots untouched.
- Post-apply live status: generated_card_count=0, stale_note_count=0, queue 0/0.

## Source-card taxonomy / analyzer upgrades
- Added document types: potential_change_order, subcontract, purchase_order, manpower_log,
  cost_report, warranty, operations_maintenance, safety, quality, inspection, drawing (generic).
- punchlist -> punch_list canonical; legacy `punchlist` still recognized (both in HIGH set).
- New deterministic fields (filename/excerpt only, never invented): document_number, title, vendor,
  amount (explicit $ only), date (ISO only), status (explicit keyword only).
- Card frontmatter additions: domain (from source_root_key), source_disposition, source_confidence
  (deterministic high/medium/low), review_status (needs_review for low/ambiguous), template_version,
  card_version, updated_at. New card body sections: Why This Matters, PM Review Cues, Source Basis,
  Follow-Up. Advisory summaries remain clearly labeled and never feed deterministic fields.
- Two-file rule honored (source_analyzers + source_value HIGH set).

## First-indexing readiness runbook
- Added docs/runbooks/obsidian-source-first-indexing-pass.md (NOT run this phase).

## Runtime check (watchdog mode)
- watcher.running=true, mode=watchdog, degraded=false, is_owner=true; queue 0/0/0; backend stopped.

## Tests
- 178 targeted tests pass (incl. 10 retirement + 9 taxonomy/extraction new). ruff clean. py_compile clean.

## Confirmations
- No broad rescan; no manual production queue drain; one backend only, stopped at closeout.
- Quarantine not deleted; external roots untouched; sensitive evidence kept local/untracked.
