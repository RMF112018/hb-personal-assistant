# Remediation: Obsidian Provenance and Source Map (Phase 14 Prompt 06)

## Summary
Phase 14 Prompt 06 closes the output loop for the work-product intelligence system by adding structured source traceability to generated Daily Brief content in the user's Obsidian vault.

- Action identity comments (stable_key + id) are now embedded in generated task lines for robust preservation across regenerations and human traceability.
- Brief generation surfaces richer provenance (building on its existing internal source_map + "## Sources" section).
- The writer now actually records `written_to_note` provenance on apply via the Registry (using the existing `link_action` helper with action_item_id).
- Dry-run paths (especially `hb-assistant diagnostics brief --dry-run --json`) report would-write + would-link behavior with zero mutation.
- Tests prove marker safety, frontmatter merge, user text outside markers, stable_key-driven task state preservation, dry-run safety, and apply-mode link creation.

Daily notes / AI Outputs companions are external vault artifacts (via PathPolicy) and are **not modeled as source_records** in the local store (source_records are for M365 graph objects and ingested files). Per the explicit allowance in the P06 spec and Source_Link_Contract, we use the repo-truth-compatible alternative: action-centric `written_to_note` links (via `link_action` on the contributing actions) + the visible marker-bounded markdown file itself. The action's prior source_links (P03) provide the full provenance chain back to original M365/local records. Clear documentation added in code, evidence, and this note.

All changes surgical, redacted, dry-run-first, following P02–P04 patterns exactly.

## Files Updated
- `src/hb_assistant/obsidian/brief.py` — stable_key identity comments added to task lines generated from `get_recent_action_items` (which already return stable_key/id post P02–P04); provenance threading extended to support writer.
- `src/hb_assistant/obsidian/writer.py` — `_preserve_task_state` upgraded to match on the new `<!-- hb-action stable_key=... -->` comments (beyond title heuristic); `record_link` block implemented with `registry.link_action(..., link_type="written_to_note")`; dry_run path surfaces would_links.
- `tests/test_obsidian_writer.py` — new/extended tests for identity comments, stable_key preservation, dry_run would-link reporting + no mutation (before/after counts), apply-mode `written_to_note` row creation (P03 temp-DB + temp_vault patterns).
- `src/hb_assistant/cli/diagnostics.py` — minimal update to the `brief` sample command payload to include would-link information in the `--dry-run --json` output (the primary validation "brief dry-run command").
- (None or at most 1-line wrapper) `src/hb_assistant/links/registry.py` — reused existing `link_action` + `ALLOWED_LINK_TYPES` (already includes "written_to_note").
- New: `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-06/` (full evidence package).
- New: `docs/architecture/remediation-obsidian-provenance-source-map.md` (this note).
- Updated: `docs/architecture/00-README.md` (P06 index entry under Phase 14 workstream intelligence, matching P01/P03/P04 style).

## Key Changes
- Generated notes are now source-traceable: every task line carries the originating action's stable_key (and id), enabling perfect task-state preservation and grep/Obsidian queries.
- `written_to_note` is no longer a stub: apply mode records the relationship for contributing actions; dry-run reports the would-link intent.
- The modeling decision (notes ≠ source_records) is explicitly documented and implemented via the action-centric alternative allowed by the spec — no schema or contract invention.
- All prior Phase 8 guarantees (marker-bounded replacement only, 100% user text outside markers preserved, frontmatter merge, redaction, Dataview-friendly output) remain untouched.
- Tests and the `diagnostics brief` CLI provide repeatable proof of the new behaviors.

## Validation Performed
- New obsidian provenance + preservation tests: green (including stable_key comment cases and apply-mode link counts).
- `hb-assistant diagnostics brief --dry-run --json`: emits would-write + would-link payload; zero FS or DB mutation.
- Full verification suite: pytest (obsidian + brief content), ruff, mypy (touched files), `diagnostics scan-sensitive --json` (clean, exit 0), `run morning --dry-run --json`.
- Sensitive scan clean (only expected indicators in tests/evidence).
- Commit: `feat(obsidian): record source links for generated notes`

## References
- `docs/plans/ph-14-workstream-Intelligence/08_Obsidian_Output_And_Provenance_Specification.md` and `Prompt_06_Obsidian_Provenance_And_Source_Map.md`
- `docs/plans/ph-14-workstream-Intelligence/resources/Source_Link_Contract.json` (allowedLinkTypes includes "written_to_note"; dry-run would-link rule)
- `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-06/summary.md` (complete package + final SHA)
- `docs/architecture/08-obsidian-writer-and-daily-brief-module.md` (Phase 8 baseline; explicitly anticipated stable_key strengthening and "written_to_note links via Reg")
- `docs/architecture/00-README.md` (Phase 14 workstream intelligence index + P06 entry)
- P02–P04 evidence (actions with stable_keys, idempotent persistence, signal integration, link_action helper)

**Status**: Obsidian generated notes are now source-traceable and provenance-safe. Generated content is user-preserved and dry-run auditable. Ready for Prompt 07+ (morning orchestration upgrades that will exercise the full apply path).