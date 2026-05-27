# Phase 14 Prompt 08 — Deterministic Evidence Harness and CI (Evidence Summary)

**Prompt**: 08 — Deterministic Evidence Harness and CI  
**Objective**: Add local fixtures, evidence templates, and safe CI validation so the full validation suite runs reproducibly without Graph consent or real vault.

**Baseline (from handoff / P07 completion)**: HEAD baac7b5cf61d461d3b544262d02ad4c051aa9fa1 (post Prompt 07 orchestration upgrade with 05 stage model + Graph blocker classification).

**Git State at Start of Prompt 08 (mandatory 5 commands, captured before any edits in this execution phase)**:
- Remote: origin https://github.com/RMF112018/hb-personal-assistant.git (fetch/push)
- Branch: main
- HEAD: baac7b5cf61d461d3b544262d02ad4c051aa9fa1
- Log (top 5):
  baac7b5 feat(run): orchestrate full local morning workflow
  ed21a36 feat(actions): derive work items from bounded source signals
  78bae9a feat(store): add idempotent action persistence
  6776b2d feat(actions): add source-linked action extraction
  9a08fa4 docs(evidence): correct delegated proof blocker taxonomy
- Status (short): M in prior phase-14 evidence summaries/outputs (P01–P04/P07 refreshes) + ?? docs/architecture/remediation-obsidian-provenance-source-map.md + ?? docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-06/ + ?? docs/architecture/remediation-morning-run-orchestration-upgrade.md + ?? CLAUDE.md (untracked, pre-existing) + untracked phase-14-repo-truth-audit dir from prior subagent. Clean base for P08.

**Files Touched (anticipated / actual — surgical only, per approved plan)**:
- .github/workflows/local-validation.yml (new; exact skeleton from 16_CI_And_Quality_Gates.md)
- tests/fixtures/ (new dir + deterministic redacted seed data per Local_Fixture_Seed_Plan.json + pytest fixtures reusing conftest patterns)
- scripts/validate_local.py (if useful; optional safe wrapper)
- docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-08/ (this package)
- docs/architecture/ (new remediation note + 00-README index entry)
- Light touches to tests/conftest.py or pyproject.toml only if needed for fixture exposure (prefer minimal)

**Key Decisions (from approved plan + this session's terminal/grep exploration)**:
- Reuse existing conftest.py tmp_app_support / tmp_repo / isolated_hb_pa_config (autouse) + P03/P07 seeding style (CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE) for deterministic fixtures.
- Fixtures follow Local_Fixture_Seed_Plan.json exactly: redacted synthetic data only for source_records + emails, calendar_events, files, parser_outputs, source_links, action_items; no real Microsoft identifiers or content.
- .github/workflows/local-validation.yml follows the exact recommended skeleton in 16_CI_And_Quality_Gates.md (Python 3.12, -e '.[dev]', full baseline commands including hb run morning --dry-run --json and scan-sensitive; no auth login, no real vault/Graph).
- Evidence package follows Evidence_Register_Template.md + Validation_Result_Register.md (summary with git + SHA, commands, validation-outputs/, etc.).
- Optional validation script (if added) is thin and uses the new fixtures.
- No real Graph creds or real Obsidian vault required anywhere in the new artifacts or workflow.
- Architecture note will document the harness + CI addition under Phase 14.

**Sub-Agent Usage (per approved plan)**:
- Strict terminal/grep/list-only explore subagent launched during planning (active or completed; produced findings on 16_CI skeleton, templates, conftest patterns, no .github yet, etc.).
- 1x feature-dev:code-architect implementer subagent launched in isolated worktree (detailed prompt with approved plan, full P08 user_query, 16_CI skeleton, Evidence_Register_Template, Local_Fixture_Seed_Plan.json, conftest findings, strict surgical + Global Rules + Claude.md instructions).
- 1x reviewer/check subagent planned post-impl (workflow validity + no-creds, fixture redaction/determinism, script if added, evidence completeness, no scope creep).
- Loop until 0 high-severity issues.
- Main agent: coordinates, reviews worktree output via terminal, replicates surgically if needed, builds full evidence, updates architecture, runs final verification, exact commit, appends SHA, outputs **only** the traditional summary at the very end.

**Validation Commands (exact per P08 prompt + approved plan + baselines)**:
- CI workflow syntax review (yamllint or act if available).
- Local full validation:
  - `.venv/bin/python -m pytest`
  - `.venv/bin/ruff check .`
  - `mypy src`
  - `.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json` (clean)
  - `.venv/bin/hb-assistant run morning --dry-run --json`
- (Focused) pytest on new fixture tests if added.

**Evidence Artifacts in This Package**:
- summary.md (this file)
- commands.md (exact command outputs + exit codes)
- validation-outputs/ (pytest.txt, ruff.txt, mypy.txt, hb-run-morning-dry.json, hb-scan-sensitive.json, git-state.txt, workflow-syntax.txt if applicable, etc.)
- known-issues.md (if any non-blocking)

**Final Commit**: Expected exact message `ci: add local assistant validation workflow` (SHA to be appended after commit).

**Status**: Implementation subagent running in isolated worktree (as of this summary creation; early turn, ingesting long prompt). Main agent monitoring + preparing skeleton. Full population of validation outputs, architecture updates, commit, and "ONLY the traditional summary" output will occur after subagent + reviewer complete and changes are reviewed/replicated/verified in main.

**References**:
- Approved plan.md (current P08 version in session)
- User query: full P08 text + Phase README + Global Operating Rules + 16_CI skeleton path
- docs/plans/ph-14-workstream-Intelligence/16_CI_And_Quality_Gates.md (exact recommended workflow)
- docs/plans/ph-14-workstream-Intelligence/12_Testing_Validation_And_Evidence_Plan.md + resources/ (Evidence_Register_Template.md, Validation_Result_Register.md, Local_Fixture_Seed_Plan.json, etc.)
- Prior prompts 01–07 evidence (P07 baseline with 05 orchestration; P03/P07 test seeding patterns; P06 provenance; P05 delegated proof patterns)
- P07 remediation note + evidence (orchestration ready for CI exercising)

(Initial skeleton created while subagent processes; will be appended with actual results post-impl.)