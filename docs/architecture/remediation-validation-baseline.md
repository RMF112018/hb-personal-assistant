# Remediation Validation Baseline (Prompt 04)

**Status**: COMPLETE (2026-05-25)

## Summary

Prompt 04 establishes a green, reproducible validation baseline by fixing the active failing config test, modernizing Ruff config to `[tool.ruff.lint]`, and introducing explicit scoped standards for Ruff and mypy.

## Key Outcomes

- `pytest` baseline green (`75 passed, 1 skipped`).
- `ruff check .` green under explicit Prompt 04 scope boundaries.
- `mypy src` green under explicit Prompt 04 scoped contract:
  - baseline ignore for legacy modules,
  - strict check enabled for remediation-critical modules (`launchd_manager`, `path_policy`, `cli.automation`).
- CLI runtime checks remain safe and deterministic:
  - version/env/automation diagnostics pass,
  - auth status remains safe JSON with expected non-zero in offline/no-token context.

## Validation Evidence

See:

- `docs/evidence/remediation/prompt-04-validation-baseline/`
- especially `validation-summary.md` for command matrix, exit codes, scope rationale, and isolation notes.
