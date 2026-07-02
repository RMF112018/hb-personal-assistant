# Phase 10L — Regeneration Dry-Run Evidence

**Read-only regeneration dry-run against the cleaned live DB/vault. No vault write, no DB apply, no
archive migration, no README apply, no source-corpus/queue/runtime mutation.** All numbers are
count-only; row-level detail (and raw `--help`/stderr) is git-ignored under `local-sensitive/`.

## Posture verification
Every regeneration script ran in dry-run and returned `mode = dry-run` with all emitted write/queue/model
counters at 0 (`cards_generated`/`archive_notes_created`/`source_cards_generated`/`queue_delta`/
`ollama_calls` = 0). Where a counter is not emitted by a script, read-only posture is instead evidenced
by `mode = dry-run` plus **reconcile-before == reconcile-after** (no state drift caused by the dry-run).

## Reconcile before / after (identical → read-only confirmed)
- missing_generated_note_rows: 0 → 0
- orphan_vault_cards: 0 → 0
- queue_queued / queue_processing: 0 / 0 → 0 / 0
- runtime_state_unchanged: true (both)
- source_row_count: 9128 (both)

## Project-corpus regeneration dry-run (`23-435-01` / `tropical`)
- mode: dry-run; identity resolved to project 23-435-01 / tropical.
- files_readable_seen: 0; cloud_evicted: 0; files_selected (regeneration candidates): 0.
- cards_generated / queue_delta / ollama_calls: 0.
- **Reason for 0 candidates:** the Tropical source root is **cloud-dormant** (SynologyDrive on-demand;
  the folder is present but not hydrated locally, so the walk sees no readable files). This is corpus
  state, not a defect — the script resolved identity and ran read-only to completion.

## Email-archive regeneration dry-run
- mode: dry-run; eml_found: 0; eml_selected: 0; archive_notes_created/updated: 0; ollama_calls: 0.
- Same cloud-dormant source-root cause. Corrected archive routing
  (`Email Archive/{Work,Home,Shared}/`, never `Work/Work`) remains proven deterministically by
  `tests/test_obsidian_archive_path_routing.py`.

## README singleton dry-run
- mode: dry_run; 6 singleton targets; action_counts = {create: 3, protected_manual: 3};
  duplicate README variants: 0. No `README__<sha>.md` produced; 3 existing hand-authored READMEs were
  correctly protected (no generated marker → not overwritten); no vault write.

## Redaction
`obsidian_evidence_redaction_check.py` PASS over this folder (local-sensitive/ excluded).

## Next recommended operator step
Hydrate the Tropical source root (SynologyDrive → "Make available offline"), then re-run the
project-corpus and email-archive dry-runs to obtain nonzero candidate counts before any authorized
apply. No apply should be run until a hydrated dry-run confirms expected candidates.
