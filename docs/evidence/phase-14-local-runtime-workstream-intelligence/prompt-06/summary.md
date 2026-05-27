# Phase 14 Prompt 06 — Obsidian Provenance and Source Map (Evidence Summary)

**Prompt**: 06 — Obsidian Provenance and Source Map  
**Objective**: Add source maps and `written_to_note` provenance for generated notes (action identity comments in task lines, source map output from brief, apply-mode link recording or repo-truth alternative, dry-run would-write/would-link reporting, tests for preservation + provenance).

**Baseline (from handoff / P04 completion)**: HEAD ed21a36d34026d9f22b0e0f84c80d3c9204b13a3  
**Worktree for implementation**: Isolated subagent worktree (feature-dev:code-architect) per approved plan.

**Git State at Start of Prompt 06 (mandatory 5 commands, captured before any edits)**:
- Remote: origin https://github.com/RMF112018/hb-personal-assistant.git (fetch/push)
- Branch: main
- HEAD: ed21a36d34026d9f22b0e0f84c80d3c9204b13a3
- Log (top 5): 
  ed21a36 feat(actions): derive work items from bounded source signals
  78bae9a feat(store): add idempotent action persistence
  6776b2d feat(actions): add source-linked action extraction
  9a08fa4 docs(evidence): correct delegated proof blocker taxonomy
  6f2a3dd docs(plans): add Phase 14 workstream intelligence package for hb-personal-assistant v1.3.0
- Status (short): only M in prior phase-14 evidence summaries/outputs (P01–P04 refreshes) + ?? CLAUDE.md (untracked, pre-existing). Clean base.

**Files Touched (anticipated / actual — surgical only)**:
- src/hb_assistant/obsidian/brief.py (stable_key identity comments in task lines; provenance threading)
- src/hb_assistant/obsidian/writer.py (_preserve_task_state upgrade for stable_key; record_link implementation for written_to_note; would-link in dry_run)
- tests/test_obsidian_writer.py (new/extended tests for comments, stable_key preservation, dry_run would-link, apply-mode provenance)
- src/hb_assistant/cli/diagnostics.py (minimal: surface would-link in `diagnostics brief --dry-run --json` payload)
- (optional/minimal) src/hb_assistant/links/registry.py (only if 1-line wrapper cleaner)
- docs/architecture/remediation-obsidian-provenance-source-map.md (new)
- docs/architecture/00-README.md (P06 index entry under Phase 14 workstream intelligence)
- docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-06/ (this package)

**Key Decisions (from plan + exploration)**:
- Daily notes / AI Outputs companions are *external vault artifacts* (PathPolicy), **not source_records** in the store (confirmed via terminal/grep on store schema and writer stub). Therefore: implement the explicit "repo-truth-compatible alternative" — action-centric `written_to_note` via existing `link_action(from_action_item_id=..., link_type="written_to_note")` (action's prior source_links provide the full chain); embed stable identities in the generated markdown for human + preservation use; document clearly in code + this evidence + architecture note. No schema changes.
- Action identity comments: `<!-- hb-action stable_key=... id=... -->` (or close variant) in generated task lines — enables robust `_preserve_task_state` and user traceability.
- Source map: Enhance brief's existing internal `source_map` + text "## Sources" section + thread structured provenance (actions list) to writer.
- Dry-run: `diagnostics brief --dry-run --json` becomes the validation path and must report would-write + would-link without mutation.
- Tests: Reuse P03/P04 temp-DB + `CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE` + temp_vault patterns for isolation and before/after counts on links.

**Sub-Agent Usage**:
- Strict terminal/grep/list-only exploration performed by main during planning (full cats of brief.py, writer.py, key registry/test/diagnostics/store slices, Prompt_06 spec, Source_Link_Contract.json, 08_Obsidian arch doc).
- 1x feature-dev:code-architect subagent launched in isolated worktree for implementation (detailed prompt with plan + excerpts + rules).
- 1x reviewer/check subagent planned after impl (marker safety, dry-run proof, apply provenance, stable_key preservation, redaction, tests).
- Loop until 0 high-severity issues.

**Validation Commands (per plan + P06 prompt)**:
- `.venv/bin/python -m pytest -q --tb=line tests/test_obsidian_writer.py tests/test_brief_content.py`
- `.venv/bin/ruff check src/hb_assistant/obsidian tests/test_obsidian_writer.py`
- `mypy src/hb_assistant/obsidian src/hb_assistant/links/registry.py`
- `.venv/bin/hb-assistant diagnostics brief --dry-run --json` (must show would-write + would-link)
- `.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json` (exit 0)
- `.venv/bin/hb-assistant run morning --dry-run --json`
- Full relevant pytest + sensitive scan clean.

**Evidence Artifacts in This Package**:
- summary.md (this file)
- commands.md (exact command outputs + exit codes)
- validation-outputs/ (01-pytest-obsidian.txt, 02-ruff.txt, 03-mypy.txt, 04-hb-diagnostics-brief-dry.json with would-link, 05-hb-scan-sensitive.json, 06-git-state.txt, 07-morning-dry.json, etc.)
- known-issues.md (if any non-blocking)

**Final Commit**: Expected exact message `feat(obsidian): record source links for generated notes` (SHA to be appended after commit).

**Status**: Implementation subagent running in isolated worktree (as of this summary creation). Main agent monitoring. Full population of validation outputs, architecture updates, commit, and "ONLY the traditional summary" output will occur after subagent + reviewer complete and changes are replicated/verified in main.

**References**:
- Approved plan.md (session)
- User query: full P06 text + Phase README + Global Operating Rules
- Prior prompts 01–04 evidence (P04 baseline ed21a36)
- Phase 14 plans: 08_Obsidian_Output_And_Provenance_Specification.md, Prompt_06_..., resources/Source_Link_Contract.json, 00_README.md
- Architecture: 08-obsidian-writer-and-daily-brief-module.md (baseline), 00-README.md (to be updated)

(Initial skeleton created while subagent processes; will be appended with actual results post-impl.)