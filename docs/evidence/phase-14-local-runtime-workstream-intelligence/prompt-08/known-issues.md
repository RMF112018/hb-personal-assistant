# Phase 14 Prompt 08 — Known Issues / Non-Blocking Notes

**As of skeleton creation (P08 implementer subagent still processing initial prompt):**

- None blocking.
- P08 implementer (feature-dev:code-architect in isolated worktree) is ingesting the detailed prompt + plan + verbatim excerpts + rules (long context; early turn, 0 tool calls after ~10s — normal for careful first-turn reasoning on a complex, rule-bound CI/fixtures task with large template + skeleton sections).
- Main agent has prepared evidence skeleton (summary.md, commands.md, dir structure) and will draft the architecture remediation note based on the approved plan and prior P07 style.
- All P01–P07 context files were inspected only via terminal/grep/list_dir during planning and early execution (no read_file violations).
- Git state captured (5 commands) before any potential mutation in this execution phase.
- The background explore subagent from planning (strict terminal/grep/list only) produced findings on 16_CI skeleton, templates, conftest patterns, no .github yet, etc. (incorporated into plan and evidence).
- When implementer + reviewer complete and produce handoff (workflow + fixtures/ + optional script + evidence skeleton in worktree + test/verification results + decisions), main will:
  - Review via terminal inspection of worktree diffs.
  - Replicate any final surgical changes to main via terminal anchors + search_replace (if needed).
  - Run full verification suite (the baseline commands from the P08 prompt + CI syntax review).
  - Populate validation-outputs/ with live command results.
  - Commit with exact message `ci: add local assistant validation workflow`.
  - Append SHA to evidence summary.md.
  - Output *only* the traditional commit summary + description.

**Post-impl updates will be appended here if any non-blocking issues arise during reviewer loop or final verification.**

No other open items at skeleton time. All per approved plan and Global Operating Rules.