# 10 — Tests

Invocation: `PYTHONPATH=src:subrepos/construction-financial-review/src .venv/bin/python -m pytest …`

## New N8C-2 suite — `tests/test_obsidian_source_card_identity.py` (20 tests)
compute_card_id determinism + distinct-from-source; source→card lookup; card→source reverse lookup
(unique / none / **ambiguous-never-arbitrary**); duplicate detection (one-source-many-paths,
cross-source, clean); stale-by-digest-drift; missing-card; **source-deleted classification-only**
(card + source untouched); source_id mismatch; card_version obsolete (constant, not legacy);
current-not-stale; **legacy card distinct-not-corruption**; AI-Outputs / Email-Archive / user-authored
NOT classified as source card; **card rendering byte-unchanged + neutral**; domain preserved.

## Combined run — **124 passed**
`test_obsidian_source_card_identity.py` (20) + N8C-1 regressions (`test_nas_mcp_ai_outputs.py`,
`test_nas_mcp_remote_profile.py`, `test_obsidian_source_card_local_summary_marker.py`) + identity
regressions (`test_source_index_repository.py`, `test_source_identity_v99_migration.py`,
`test_obsidian_generated_note_retirement.py`, `test_obsidian_generated_artifact_db_reset.py`,
`test_obsidian_source_maintenance.py`, `test_obsidian_source_self_index_guard.py`,
`test_obsidian_source_index_eml_archive.py`) → **92 passed**; card-rendering/quality spot-check
(`test_obsidian_source_card_quality_regression.py`, `test_obsidian_source_cards_pm_grade.py`,
`test_obsidian_source_auto_generate.py`) → **32 passed**. Total 124.

## Lint — `ruff check` clean
`source_card_identity.py`, `source_index_repository.py`, `test_obsidian_source_card_identity.py` →
**All checks passed!**

## Byte-unchanged proof
`test_source_card_rendering_is_byte_unchanged_and_neutral` asserts the generated card carries the
existing neutral identity fields and that N8C-2 added **no** `card_id`/`managed_by`/`card_status` and
**no** `hb`-branded metadata. The `git diff` touches only `source_index_repository.py` (+37, two
read-only methods) — card rendering (`source_notes.py`) is untouched.

## Bundles
These source-intelligence tests are **not** in `scripts/test-forecasting.sh` / `scripts/test-schedule.sh`
(no migrator change), so no bundle file needs updating; N8C-2 tests run as direct pytest targets.
