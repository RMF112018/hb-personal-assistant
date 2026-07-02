# Operator decision log

- selected packages: TWNU07 → TWNU14 → TWNU16 → TWNU18 → TWNU19 (xer-examples zips)
- second schedule versions available: yes (5 versions imported)
- browser screenshots captured: no (API-primary validation)
- raw traces kept local-only: yes (`local-sensitive/evidence/...`)
- stages skipped: none
- live DB mutation: no
- live vault write: no
- production import: no
- copied DB mutation: yes, expected

## Baseline decision (recorded before mutation)

- baseline slot/name: current_contract_baseline
- selected baseline package: TWNU14
- selected baseline schedule_version_key: tropical|851|2025-11-28 08:00
- current package: TWNU19
- current schedule_version_key: tropical|1071|2026-06-23 08:00
- rationale: TWNU14 vs TWNU19 per operator plan; import evidence shows both succeeded with zero duplicate counts

## Obsidian scripts (repo-truth)

- scripts/obsidian_schedule_review_notes.py (confirmed)
- scripts/obsidian_schedule_note_graph.py (confirmed)
