# P4 Evidence — Multi-project generalization (tractable slice)

Generated: P4-multi-project-20260623T101104Z  ·  Branch: feature/forecast-multi-project-eligibility-p4  ·  No live-DB mutation.

## What this proves
The 26 tropical-only CFR guards were replaced by a CFR-local, stdlib-only eligibility policy
(`common/project_eligibility.py`), and `package_resolution` derives package prefixes per project.

- `01-eligibility-resolution.json`: default allowlist = ['fixtureproj', 'tropical']; tropical &
  fixtureproj eligible, `other` rejected; the `forecast_projects` registry unions enabled projects;
  `source_package_name('tropical')` = `twn_cost_forecast_json_package`.
- `02-multiproject-chain-resolution.json`: an eligible **non-tropical** project (`fixtureproj`)
  resolves its context + analysis packages and builds a chain (prefix derived as
  `forecast_<kind>_package_fixtureproj_`).
- `03-ineligible-fail-closed.txt`: an ineligible project (`other`) is refused with
  `PackageResolutionError` — fail-closed preserved.

## Scope / deferral
Tractable slice: guards + source-package-name parameterization + synthetic second-project proof at
the guard/package-resolution layer. Deferred to **P4b**: detropicalizing the 2,000-line
`generate_forecast_context_package.py` and a live second-project context→analysis→projection run
(blocked on second-project source data + config).

## Validation
Full CFR suite: 649 passed (no regressions). New: `test_project_eligibility.py` (8),
`test_package_resolution_multiproject.py` (4). ruff + mypy clean. CFR imports no `hb_assistant`
(enforced by `test_model_engines_readiness.py`, still green).
