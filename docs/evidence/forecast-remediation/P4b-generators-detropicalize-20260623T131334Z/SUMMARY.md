# P4b Evidence — Detropicalize the forecast generators (config-driven) + tropical byte-parity

Generated: P4b-generators-detropicalize-20260623T131334Z  ·  Branch: feature/forecast-generators-detropicalize-p4b  ·  No live-DB mutation.

## What this proves
The context/analysis/crosswalk-v2/mapping/comprehensive generators + the CLI now read every
project-specific value from `config/projects/<key>.json` (selected via `CFR_PROJECT_KEY`, default
`tropical`), via the new stdlib-only `common/project_config.py`.

- `01-tropical-config-equivalence.json`: the tropical config reproduces the EXACT former hardcoded
  literals (project name/display/job/period, `procore_export_folder`, cutoffs, the 8 row-count
  expectations, and the owner-SOV crosswalk stem == former `XW_AUTHORITATIVE_NAME`). Identical
  config => byte-identical tropical output.
- `02-generator-project-scoping.json`: with `CFR_PROJECT_KEY` unset the context generator resolves
  tropical names byte-identically; with `CFR_PROJECT_KEY=fixtureproj` the output folder + procore
  dir scope to `fixtureproj`.

## Byte-parity gate (the safety anchor)
- Config-equivalence unit tests (`tests/test_project_config_loader.py`, `tests/test_generators_project_scoping.py`).
- **Full CFR suite: 670 passed (0 failed)** — including the Phase 17–20 *_db_config_proof tests and the
  model-controls e2e, which RUN the real generators and compare output file-by-file. Their passing is
  direct proof that tropical generator output is unchanged.
- ruff/mypy clean on the new modules; the 18 ruff warnings in the legacy generator bodies pre-exist on
  `origin/main` (untouched). CFR imports no `hb_assistant` (loader is stdlib + CFR-internal only).

## Scope / deferral (P4c)
Config-driving + tropical parity only. Deferred to **P4c**: a complete synthetic `fixtureproj` data
root + a real second-project context→analysis→comprehensive run. The `fixtureproj.json`
`default_data_root` is a non-existent placeholder so an accidental run fails fast. A few embedded
tropical-domain literals are intentionally left for P4c (the `(127 keys)` schema text and the
`*_all_88_rows` JSON field-name counts); they are byte-identical for tropical.
