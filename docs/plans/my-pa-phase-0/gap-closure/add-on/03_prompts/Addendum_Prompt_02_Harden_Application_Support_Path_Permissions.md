# Addendum Prompt 02: Harden Application Support Path Permissions

## Objective

Fix the Application Support permission blocker by making path initialization safer and adding diagnostics/repair guidance.

## Starting Checks

Run and capture:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -5
source .venv/bin/activate
python --version
hb-assistant --version
```

## Operating Rules

- Do not re-run broad feature work from the prior remediation package.
- Keep the patch scoped to this addendum prompt.
- Do not enable Microsoft 365 writeback.
- Do not persist full email bodies.
- Do not commit tokens, PEM contents, SQLite DB files, token caches, or private `.env` files.
- Evidence must be truthful. If a command fails, record it as failed.
- Do not claim final acceptance until Addendum Prompt 06 is green.

## Problem Context

Current auth/Graph/proof commands fail because `TokenCacheManager` calls `PathPolicy.ensure_dirs(create_sensitive=True)`, which attempts to `chmod 700` the Application Support root and raises `Operation not permitted`.

## Tasks

### 1. Refactor PathPolicy directory creation

Update `PathPolicy.ensure_dirs()` to support a richer policy:

- parent/root Application Support creation;
- auth directory creation;
- DB/cache/log/evidence creation;
- strict mode only for truly sensitive auth directory;
- best-effort chmod for non-auth directories;
- structured warnings available to diagnostics.

Recommended signature:

```python
def ensure_dirs(
    self,
    *,
    create_sensitive: bool = True,
    strict_sensitive: bool = False,
    return_report: bool = False,
) -> None | dict:
```

Behavior:

- `auth` directory should be `0700` where possible.
- token cache files should remain `0600`.
- Application Support root chmod failure should not crash status commands.
- If `strict_sensitive=True`, auth dir permission failure may raise.

### 2. Harden TokenCacheManager

- Do not crash `auth status` on root chmod failure.
- Return structured cache status with `path_error` when needed.
- Only fail hard when login/save requires a writable secure cache and cannot proceed.

### 3. Add diagnostics path command

Add command:

```bash
hb-assistant diagnostics paths --json
```

Recommended optional flags:

```bash
hb-assistant diagnostics paths --repair-dry-run --json
hb-assistant diagnostics paths --repair --json
```

Minimum output:

- app support path;
- auth path;
- db directory;
- logs directories;
- owner if available;
- mode if available;
- exists;
- writable;
- chmod attempted;
- repair recommendation.

### 4. Local repair guidance

Do not run `sudo` automatically. Output recommended commands only.

## Required Validation

```bash
hb-assistant diagnostics paths --json
hb-assistant auth status --json
hb-assistant diagnostics graph --safe --json
python -m pytest tests/test_auth.py tests/test_config.py tests/test_cli_canonical.py
```

## Expected Result

- Commands return valid JSON.
- They may report “no delegated token,” but must not fail due `Operation not permitted`.
- No traceback.

## Evidence Required

Create/update:

```text
docs/evidence/remediation-addendum/prompt-02/
```

Include:

- `commands.md`
- command output files
- `summary.md`
- `known-issues.md`

## Required Commit

```text
fix(paths): harden application support permission handling
```
