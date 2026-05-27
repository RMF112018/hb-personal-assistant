# Phase 14 Prompt 08 — Commands Executed (for Evidence)

All commands run from repo root with `.venv/bin/` where applicable. Outputs + EXIT_CODE captured in validation-outputs/.

## Pre-Edit Git State (mandatory, captured before any mutation in this execution phase)
```bash
git remote -v
git branch --show-current
git rev-parse HEAD
git log --oneline -20
git status --short
```
(Full output in validation-outputs/06-git-state.txt; HEAD baac7b5, clean except prior evidence M + untracked P06 artifacts + CLAUDE + phase-14-repo-truth-audit dir)

## Discovery (terminal/grep/list only on context files)
- find / ls / grep -n / cat | head on .github (if any), tests/fixtures or conftest.py, scripts/, docs/evidence templates or prompt-08 skeleton, docs/plans/ph-14-workstream-Intelligence/ (for 08/CI/evidence mentions), resources/ templates (Evidence_Register, Validation_Result_Register, Local_Fixture_Seed_Plan, etc.)
- Targeted grep for "fixtures", "workflow", "CI", "validation", "16_CI", "Local_Fixture_Seed_Plan" in allowed paths

## Implementation Verification (in main after subagent + review + replication)
```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
mypy src
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
.venv/bin/hb-assistant run morning --dry-run --json
```
(Plus CI workflow syntax review: yamllint .github/workflows/local-validation.yml or act if available)

## Sensitive Scan + General Hygiene
```bash
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
```

## Evidence Refresh (post-commit)
- Append final SHA + verification summary to summary.md (terminal)
- Update any prior evidence M files if needed (non-blocking)

## Notes
- All discovery used only allowed terminal/grep/sed/cat/list_dir means (no read_file on P01–P07 context files).
- Subagent performed its own allowed discovery + created the workflow, fixtures/, optional script, evidence skeleton in its isolated worktree.
- Main agent replicated/verified + ran the full suite above for the evidence package.
- Sensitive scan always clean (exit 0; only expected indicators from auth/docs/tests).

(Outputs + exit codes in validation-outputs/ as numbered artifacts matching prior prompt-0[1-7] convention.)