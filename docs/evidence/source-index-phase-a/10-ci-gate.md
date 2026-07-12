# 10 — Source-index CI gate

**New workflow:** `.github/workflows/source-index-gate.yml` → runs `scripts/ci_source_index_gate.sh`.
**Recommended required-check name:** `Source Index Gate / source-index-gate` (job `source-index-gate` in
workflow `Source Index Gate`). **Branch protection was NOT modified** — this is a recommendation only.

## Why a dedicated gate

`origin/main` has `claude.yml`, `claude-code-review.yml`, and `forecasting-semantic-gates.yml` — none run the
source-index correctness/trust suites. A change to the migrator, a manifest, the config model, or a
source-index module could regress deletion safety, root trust, or the quarantine invariants with no failing
required check. This gate closes that hole, modeled exactly on the existing `forecasting-semantic-gates.yml`
(workflow → `scripts/ci_*.sh` → `pytest … && ruff check …`).

## Triggers (intentionally broad path filters)

Runs on `pull_request` and on `push` to `main`. The `paths` filter is deliberately wide so a shared change
cannot bypass the gate:

- `src/hb_assistant/obsidian_mcp/source_*.py`, `tool_*.py`, `client_tool_manifest.py`, `canonical_tool_specs.py`
- `src/hb_assistant/nas_mcp/**`
- `src/hb_assistant/store/source_index_*.py` **and `store/migrator.py`** (a schema change can break source
  indexing even with no `source_*` file touched)
- `src/hb_assistant/config/**` (a config-model change alters trust/policy inputs)
- `src/hb_assistant/cli/source_*.py`
- the corresponding `tests/test_source_*`, `tests/test_obsidian_source_*`, connector/manifest/parity tests
- the gate script and workflow file themselves

Including `store/migrator.py` and `config/**` is the specific guard against a shared DB/config/manifest change
slipping through a narrow `source_*`-only filter.

## What the gate runs

`scripts/ci_source_index_gate.sh` (CI-safe: scratch SQLite + temp roots + mocked FS failures only; no live
NAS / prod DB / network / real watcher activation):

**pytest targets** — A1 deletion-safety (`test_source_index_vault_deletion_safety`), A3 mapping
(`test_source_root_mapping`), A2 root-trust (`test_source_root_trust`), A4 quarantine
(`test_source_index_quarantine`, `test_source_index_quarantine_lifecycle`), generation hardening
(`test_source_index_generation_hardening`), migrations (`test_source_index_metadata_first_bootstrap`,
`test_source_index_metadata_generation`, `test_migrator_v117_source_index_bootstrap`,
`test_migrator_v123_relpath_index`), watcher lifecycle (`test_obsidian_source_watch`,
`…_lifecycle`, `…_ownership`, `…_reliability`, `test_source_index_watcher_automated_refresh`), connector
serving (`test_source_connector_service`, `test_nas_mcp_source_connector`, `test_source_connector_eval`),
source health (`test_source_index_health_readonly_conn`), and manifest freshness + direct/gateway parity
(`test_tool_manifest_freshness_guard`, `test_n8c23_client_tool_manifest`, `test_manifest_schema_parity`).

**ruff** — `ruff check` (lint only, **not** `ruff format --check`) over the source-index implementation
modules + the four new/updated test files. Format-check is deliberately excluded because several source-index
modules pre-date the repo's formatter adoption and must not be reformatted by the gate.

## Validity + runtime

- Workflow YAML parses (`yaml.safe_load` OK); script passes `bash -n`.
- Locally, the gate's full pytest target set is green (see `15-final-cumulative-validation.md`,
  run `source-index-broad-regression`). The three former `== 123` schema assertions were corrected to
  `== LATEST_SCHEMA_VERSION` (see `08`) so the gate is green without excluding any required suite.
- Runtime: the suite is dominated by the real-time watcher tests (polling/observer deadlines); expect a few
  minutes on a GitHub `ubuntu-latest` runner. `cache: pip` is enabled on `setup-python` to speed installs.
- **Local-runner note:** on a machine whose `pytest` console-script shebang points at a Python that is absent
  (this dev venv is 3.14 while the shebang names 3.12), invoke via `python -m pytest`. On CI (`setup-python`
  3.12 + `pip install -e ".[dev]"`) the bare `pytest`/`ruff` on PATH resolve correctly, matching the
  forecasting gate's convention.

## Branch-protection recommendation (not applied)

Add `Source Index Gate / source-index-gate` to the set of required status checks for `main`. This must be done
by a repository admin via branch-protection settings; this checkpoint does not (and is not authorized to)
change protection settings.
