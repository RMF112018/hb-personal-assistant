# Phase 14 Prompt 07 — Morning Run Orchestration Upgrade (Evidence Summary)

**Prompt**: 07 — Morning Run Orchestration Upgrade  
**Objective**: Upgrade `run morning` to execute full local stages while classifying Graph consent blockers per the 05_Local_Runtime_Orchestration_Specification.md stage model.

**Baseline (from handoff / P06 completion)**: HEAD ed21a36d34026d9f22b0e0f84c80d3c9204b13a3 (P04 signal integration + P06 provenance foundation). P06 added stable_key comments, written_to_note recording, would-link dry-run reporting, and action-centric provenance alternative (notes are not source_records).

**Git State at Start of Prompt 07 (mandatory 5 commands, captured before any edits in this execution phase)**:
- Remote: origin https://github.com/RMF112018/hb-personal-assistant.git (fetch/push)
- Branch: main
- HEAD: ed21a36d34026d9f22b0e0f84c80d3c9204b13a3
- Log (top 5):
  ed21a36 feat(actions): derive work items from bounded source signals
  78bae9a feat(store): add idempotent action persistence
  6776b2d feat(actions): add source-linked action extraction
  9a08fa4 docs(evidence): correct delegated proof blocker taxonomy
  6f2a3dd docs(plans): add Phase 14 workstream intelligence package for hb-personal-assistant v1.3.0
- Status (short): M in prior phase-14 evidence summaries/outputs (P01–P04/P06 refreshes) + ?? docs/architecture/remediation-obsidian-provenance-source-map.md + ?? docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-06/ + ?? CLAUDE.md (untracked, pre-existing). Clean base for P07 changes.

**Files Touched (anticipated / actual — surgical only, per approved plan)**:
- src/hb_assistant/automation/orchestrator.py (primary: extend run() + per-stage logic to full 05 stage model with graph_auth_status classification, wire P02-P06 pieces, emit exact 05 JSON contract including blocker_classification + stages array).
- src/hb_assistant/cli/run.py (minimal: richer payload passthrough for new orchestrator result; preserve StoreReadinessError special case).
- tests/test_automation.py (and/or test_cli_canonical.py): new/extended tests for no-token/consent-blocked (Graph stages skipped, local succeed), DB blocked, dry-run vs apply, isolated failure, full 05 JSON match.
- docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-07/ (this package).
- docs/architecture/ (new remediation note + 00-README.md index entry under Phase 14 workstream intelligence).

**Key Decisions (from approved plan + this session's terminal/grep exploration)**:
- Reuse and extend the existing per-stage try/except + "skipped" + reason pattern (already present in orchestrator) to the full 05 model.
- graph_auth_status stage added early: probe delegated token/consent (reuse P05 patterns); subsequent Graph stages (graph_retrieval) get skipped_external_admin_consent / skipped_no_token while *all local stages continue* (action_extraction, brief_generation + obsidian_write with P06 provenance, etc.).
- Local stages succeed and report structured 05 statuses even when Graph is consent-blocked (core acceptance criterion).
- Obsidian write stage uses P06 generator + writer (dry_run flag + record_link/provenance already in place).
- Evidence/ledger patterns (sanitized JSON, registry record_run/finish_run) extended but not reinvented.
- cli/run.py remains thin wrapper; main richness comes from orchestrator.

**Sub-Agent Usage (per approved plan)**:
- Strict terminal/grep/list-only explore subagent launched during planning (active; using list_dir + grep on 05 spec, orchestrator, cli/run, tests — no read_file).
- 1x feature-dev:code-architect implementer subagent launched in isolated worktree (detailed prompt with approved plan, full P07 user_query, 05 spec excerpts, verbatim terminal anchors, P06 provenance pieces, strict surgical + Global Rules + Claude.md instructions).
- 1x reviewer/check subagent planned post-impl (05 JSON fidelity, blocker classification + local continuation, isolation, dry-run safety, tests).
- Loop until 0 high-severity issues.
- Main agent: coordinates, reviews worktree output via terminal, replicates surgically if needed, builds full evidence, updates architecture, runs final verification, exact commit, appends SHA, outputs **only** the traditional summary at the very end.

**Validation Commands (exact per P07 prompt + approved plan + baselines)**:
- `.venv/bin/python -m pytest -q --tb=line -k "automation or run or morning or orchestrator"`
- `.venv/bin/ruff check src/hb_assistant/automation src/hb_assistant/cli/run.py tests/test_automation.py`
- `mypy src/hb_assistant/automation src/hb_assistant/cli/run.py`
- `.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json` (clean, exit 0)
- `.venv/bin/hb-assistant run morning --dry-run --json` (must emit full 05 stages + blocker_classification; Graph stages skipped, local succeed)
- (Focused) pytest on automation/run tests + the above.

**Evidence Artifacts in This Package**:
- summary.md (this file)
- commands.md (exact command outputs + exit codes)
- validation-outputs/ (01-pytest-automation-run.txt, 02-ruff.txt, 03-mypy.txt, 04-hb-run-morning-dry.json showing stages+blocker, 05-hb-scan-sensitive.json, 06-git-state.txt, etc.)
- known-issues.md (if any non-blocking)

**Final Commit**: Expected exact message `feat(run): orchestrate full local morning workflow` (SHA to be appended after commit).

**Status**: Implementation subagent + explore subagent running in background (as of this summary creation). Main agent monitoring + preparing skeleton. Full population of validation outputs, architecture updates, commit, and "ONLY the traditional summary" output will occur after subagents complete and changes are reviewed/replicated/verified in main.

**References**:
- Approved plan.md (current P07 version in session)
- User query: full P07 text + Phase README + Global Operating Rules + 05 spec path
- docs/plans/ph-14-workstream-Intelligence/05_Local_Runtime_Orchestration_Specification.md (stage model, JSON contract, isolation rules)
- Prior prompts 01–06 evidence (P06 baseline with provenance; P04 signals/actions; P05 delegated proof patterns)
- P06 remediation note + evidence (obsidian_write stage ready)

(Initial skeleton created while subagents process; will be appended with actual results, SHAs, and verification outputs post-impl.)---EXPLORE SUBAGENT FINDINGS SUMMARY (incorporated for evidence)---
Strict terminal/grep/list-only explore completed successfully (202.5s, 24 tool calls). Key outputs: full 05 stage model table + JSON contract + failure isolation rules verbatim; current orchestrator.py signatures, stages_order=["context","brief_preview","files_discover"], per-stage try/except "skipped"+reason pattern, brief_preview + files_discover call sites, ledger/evidence logic; cli/run.py morning_cmd wrapper + StoreReadinessError special case; P05 classifier/proof patterns for graph_auth_status; test_automation.py usage patterns. All verbatim excerpts captured in subagent output and planning thinking trace. Used to inform approved plan and implementer prompt. No read_file on any context files.

## Final Commit & Verification Results
- Commit: baac7b5 feat(run): orchestrate full local morning workflow (exact message)
- Files: 13 (orchestrator + cli/run + tests + full prompt-07/ evidence + architecture remediation note + 00-README index)
- Verification: pytest (automation/run) green after minimal test assertion update for new 05 stages; ruff/mypy clean on touched files; hb run morning --dry-run --json shows full 13-stage 05 model + blocker_classification + local success + dry_run obsidian_write; scan-sensitive clean (exit 0).
- Sensitive scan: clean.
- All Global Operating Rules + approved plan followed. Evidence package complete with live 05 JSON output.

**Prompt 07 complete. Full local morning orchestration with truthful Graph consent blocker classification delivered.**
