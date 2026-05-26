# Prompt 03: Launchd Path And Command Rendering

## Objective

Correct launchd plist rendering so scheduled automation invokes the real CLI command from a valid executable path and working directory.

## Required Starting Checks

Run and capture:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -5
python --version
```

Do not proceed if the working tree contains unrelated uncommitted changes unless you first document them and isolate your patch.

## Agent Rules

- Do not trust prior closeout claims.
- Do not re-read files already in current context unless changed or required by failing tests.
- Do not enable Microsoft 365 writeback.
- Do not log or commit tokens, private keys, PEM bodies, full email bodies, or full file contents.
- Keep the patch tightly scoped to this prompt.
- Create evidence under `docs/evidence/remediation/prompt-03-*/`.

## Tasks

1. Add explicit config support for:
   - `automation.launchd.executable_path`
   - `automation.launchd.working_directory`
   - `automation.launchd.label`
   - optional `automation.launchd.python_path`
2. Resolve defaults safely:
   - Prefer current `sys.executable` / installed console script when available.
   - Use repo root from `PathPolicy.resolve_repo_root()` for working directory.
   - Do not derive executable or working directory from Application Support parent.
3. Render ProgramArguments as:

```text
[hb_assistant_executable, "run", "morning"]
```

4. Dry-run preview must include readiness:
   - executable exists;
   - working directory exists;
   - command grammar valid;
   - log directories writable;
   - plist path.
5. If executable cannot be verified, return a blocking diagnostic rather than rendering a misleading “ready” plist.
6. Add tests for rendered ProgramArguments, working directory, executable readiness, and dry-run behavior.

## Validation

```bash
hb-assistant automation install-launchd --dry-run --json
hb-assistant diagnostics automation --json
python -m pytest tests/test_automation.py
```

## Required Commit

```text
fix(automation): correct launchd executable and command rendering
```

The commit message body must summarize files changed, validation commands run, evidence path, and remaining issues if any.
