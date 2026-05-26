# 16 — CI and Quality Gates

## Objective

Add safe local-only CI for the public repository without requiring Microsoft delegated credentials.

## Recommended GitHub Actions Workflow

Path:

```text
.github/workflows/local-validation.yml
```

Minimum jobs:

1. Checkout repository.
2. Set up Python 3.12.
3. Install package with dev extras.
4. Run tests.
5. Run Ruff.
6. Run mypy.
7. Run CLI smoke commands that do not require Graph consent.
8. Run sensitive scan.

## Example Workflow Skeleton

```yaml
name: Local Validation

on:
  pull_request:
  push:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python -m pip install --upgrade pip
      - run: python -m pip install -e '.[dev]'
      - run: python -m pytest
      - run: ruff check .
      - run: mypy src
      - run: hb-assistant --version
      - run: hb-assistant diagnostics env --json
      - run: hb-assistant diagnostics scan-sensitive --repo . --json
```

## CI Constraints

- Do not run `auth login` in CI.
- Do not require Microsoft credentials in CI.
- Do not use real Obsidian vault path in CI.
- Use temporary app-support config if needed.
- Keep fixture data synthetic/redacted.

## Quality Gate Maturity Plan

### Immediate

- Preserve current green baseline.
- Add Phase 14 tests.
- Avoid expanding Ruff/mypy exclusions.

### Near-Term

- Reduce Ruff exclusions by package.
- Reduce mypy `ignore_errors` scopes by package.
- Add schema/CLI JSON contract tests.

### Later

- Add coverage reporting.
- Add dependency audit.
- Add packaged release validation.
