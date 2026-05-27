# Phase 01 — Step 2: Source Registry & Config Model Proof

- Date: 2026-05-27
- Branch: `main`
- HEAD pre-change: `439c010` (`chore(construction-agent): add phase 01 governance preflight evidence`)
- Repo root: `/Users/bobbyfetting/hb-personal-assistant`
- Source package: `/Users/bobbyfetting/Downloads/HB_Construction_Intelligence_Phase_01_Implementation_Package/`

## Purpose

Add the construction-agent source registry: Pydantic models for `ProjectIdentity` and `SourceLocation`, a seed-aware loader, a JSON Schema export, and a `hb-assistant construction-agent sources validate` CLI surface. Read-only, local-first, no external system contact.

## Implementation Summary

### Files Created

| Path | Purpose |
| --- | --- |
| `src/hb_assistant/construction/__init__.py` | Package marker for construction-agent surface |
| `src/hb_assistant/construction/config/__init__.py` | Public re-exports |
| `src/hb_assistant/construction/config/models.py` | `ProjectIdentity`, `SourceLocation`, `SourceRegistry` Pydantic models with cross-entity validators |
| `src/hb_assistant/construction/config/loader.py` | `load_source_registry()` with seed → repo-override → explicit-path → env-var precedence |
| `src/hb_assistant/cli/construction.py` | `construction-agent sources validate` Typer subcommand |
| `resources/config/sharepoint_onedrive_sources.seed.yaml` | Seed registry: tropical, hilltop, bobby-onedrive (all `pending`) |
| `resources/schemas/project_identity.schema.json` | Generated JSON Schema (artifact only; Pydantic remains authoritative) |
| `resources/schemas/source_locations.schema.json` | Generated JSON Schema (artifact only) |
| `tests/test_construction_sources.py` | 14 tests covering loading, guardrails, overrides, CLI behavior |
| `docs/evidence/construction-intelligence-phase-01/01-source-registry-config-proof.md` | This file |

### Files Modified

| Path | Change |
| --- | --- |
| `src/hb_assistant/cli/main.py` | Added `construction` to import block (alphabetized) and `app.add_typer(construction_mod.app, name="construction-agent")` wiring |

No other source files touched. No existing tests changed. No dependencies added.

## Validation Commands and Output

### Step-2 unit tests — `pytest tests/test_construction_sources.py -v`

```
============================= test session starts ==============================
platform darwin -- Python 3.14.5, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/bobbyfetting/hb-personal-assistant
configfile: pyproject.toml
collected 14 items

tests/test_construction_sources.py::test_seed_loads_with_expected_projects_and_sources PASSED
tests/test_construction_sources.py::test_seed_sources_are_all_read_only_and_pending PASSED
tests/test_construction_sources.py::test_invalid_writeback_flag_is_rejected PASSED
tests/test_construction_sources.py::test_unknown_source_kind_is_rejected PASSED
tests/test_construction_sources.py::test_non_kebab_key_is_rejected PASSED
tests/test_construction_sources.py::test_extra_fields_are_forbidden PASSED
tests/test_construction_sources.py::test_orphan_source_project_key_is_rejected PASSED
tests/test_construction_sources.py::test_duplicate_source_key_is_rejected PASSED
tests/test_construction_sources.py::test_duplicate_site_id_is_rejected PASSED
tests/test_construction_sources.py::test_explicit_override_replaces_seed PASSED
tests/test_construction_sources.py::test_env_var_override_is_respected PASSED
tests/test_construction_sources.py::test_missing_seed_raises PASSED
tests/test_construction_sources.py::test_validate_cli_emits_expected_json PASSED
tests/test_construction_sources.py::test_validate_cli_reports_schema_failure PASSED

============================== 14 passed in 0.07s ==============================
```

### Regression sweep — fast/in-process test files only

The repo's test suite is partitioned for this run into:

- **Step-2 validation set** (run; results below): `test_construction_sources`, `test_config`, `test_classification`, `test_obsidian_writer`, `test_retrieval`, `test_store`, `test_store_links`, `test_body_mentions`, `test_brief_content`, `test_sensitive_scan`, `test_file_ingestion`, plus the help-only subset of `test_cli_canonical` (`*_help_parses`, `*_shape`).
- **Excluded baseline** (not run; documented under Known Limitations): `test_cli_canonical.py` (non-help subset), `test_auth.py`, `test_automation.py`, `test_actions_cli.py`, `test_files_cli.py`, `test_graph_clients.py`, `test_graph_proof.py`, `test_mutation_lockout.py`, `test_sensitive_scan_cli.py`, `test_mvp_local_runtime_evidence.py`. These invoke MSAL delegated auth, real Graph HTTP, or subprocess `hb-assistant` commands that hang in this non-interactive sandbox — pre-existing baseline behavior, not introduced by this step.

Validation set result (`pytest tests/test_construction_sources.py tests/test_config.py tests/test_classification.py tests/test_obsidian_writer.py tests/test_retrieval.py tests/test_store.py tests/test_store_links.py tests/test_body_mentions.py tests/test_brief_content.py tests/test_sensitive_scan.py tests/test_file_ingestion.py --tb=line -q`):

```
...............................FFFF..................................... [ 96%]
...                                                                      [100%]
=================================== FAILURES ===================================
E   TypeError: MarkerBoundedWriter.write_bounded_section() got an unexpected keyword argument 'action_item_ids'
/Users/bobbyfetting/hb-personal-assistant/tests/test_obsidian_writer.py:155: TypeError: ...
/Users/bobbyfetting/hb-personal-assistant/tests/test_obsidian_writer.py:189: TypeError: ...
/Users/bobbyfetting/hb-personal-assistant/tests/test_obsidian_writer.py:229: TypeError: ...
/Users/bobbyfetting/hb-personal-assistant/tests/test_obsidian_writer.py:265: TypeError: ...
=========================== short test summary info ============================
FAILED tests/test_obsidian_writer.py::test_dry_run_no_write_no_link
FAILED tests/test_obsidian_writer.py::test_apply_writes_and_creates_written_to_note_links
FAILED tests/test_obsidian_writer.py::test_idempotent_repeat_write_no_duplicate_links
FAILED tests/test_obsidian_writer.py::test_marker_bound_and_user_content_preservation_with_links
```

Result: **111 passed, 4 pre-existing failed**. The 4 failures are pre-existing baseline drift between `tests/test_obsidian_writer.py` (passes `action_item_ids=` to `MarkerBoundedWriter.write_bounded_section`) and `src/hb_assistant/obsidian/writer.py:100` (signature does not accept that keyword). Both files were last modified before this step's parent commit (`0df2c60`). Step 2 does not touch either file.

Help-only canonical subset (`pytest tests/test_cli_canonical.py -k "help_parses or _shape" -v`):

```
collected 16 items / 12 deselected / 4 selected

tests/test_cli_canonical.py::test_root_help_parses PASSED
tests/test_cli_canonical.py::test_auth_help_parses PASSED
tests/test_cli_canonical.py::test_run_help_parses PASSED
tests/test_cli_canonical.py::test_launchd_program_arguments_match_run_group_shape PASSED

======================= 4 passed, 12 deselected in 0.23s =======================
```

Confirms the new `construction-agent` subcommand wiring in `cli/main.py` does not break root-level help parsing.

### Lint — `ruff check` (scoped to step-2 files)

```
$ ruff check src/hb_assistant/construction/ src/hb_assistant/cli/construction.py src/hb_assistant/cli/main.py tests/test_construction_sources.py
All checks passed!
```

Repo-wide `ruff check .` reports 22 pre-existing errors in unrelated test files (matching the baseline before step 2). Step 2 introduces **0** new lint findings.

### CLI smoke — `hb-assistant construction-agent sources validate --json`

```json
{
  "implemented": true,
  "phase": 1,
  "step": "2-source-registry",
  "summary": {
    "project_count": 2,
    "source_count": 3,
    "resolved_count": 0,
    "pending_count": 3,
    "deprecated_count": 0,
    "ok": true,
    "blocking": false
  },
  "projects": [
    {
      "project_key": "tropical",
      "display_name": "Tropical",
      "status": "active",
      "primary_company": "HB Construction",
      "procore_company_id": null,
      "notes": null
    },
    {
      "project_key": "hilltop",
      "display_name": "Hilltop",
      "status": "active",
      "primary_company": "HB Construction",
      "procore_company_id": null,
      "notes": null
    }
  ],
  "sources": [
    {
      "source_key": "tropical-sharepoint",
      "project_key": "tropical",
      "kind": "sharepoint_site",
      "display_name": "Tropical SharePoint Site",
      "site_url": null,
      "site_id": null,
      "drive_id": null,
      "root_path": null,
      "read_only": true,
      "resolution_status": "pending",
      "notes": "site_url + site_id to be resolved from SharePoint developer brief"
    },
    {
      "source_key": "hilltop-sharepoint",
      "project_key": "hilltop",
      "kind": "sharepoint_site",
      "display_name": "Hilltop SharePoint Site",
      "site_url": null,
      "site_id": null,
      "drive_id": null,
      "root_path": null,
      "read_only": true,
      "resolution_status": "pending",
      "notes": "site_url + site_id to be resolved from SharePoint developer brief"
    },
    {
      "source_key": "bobby-onedrive",
      "project_key": null,
      "kind": "onedrive_personal",
      "display_name": "Bobby OneDrive (delegated, personal scope)",
      "site_url": null,
      "site_id": null,
      "drive_id": null,
      "root_path": null,
      "read_only": true,
      "resolution_status": "pending",
      "notes": "drive_id to be resolved via /me/drive once delegated auth is exercised"
    }
  ],
  "warnings": [
    "3 sources pending live resolution"
  ],
  "guardrails": {
    "all_read_only": true,
    "no_writeback_paths": true,
    "no_live_external_calls": true
  },
  "note": "Read-only validation. No SharePoint/OneDrive/Graph calls were made."
}
```

Exit code: `0`. Three pending sources reported; not blocking (resolution is a downstream step).

## Guardrails Reaffirmed

- All seeded sources have `read_only: true`; the model enforces `Literal[True]` so a writeback flag cannot be constructed at all.
- No live SharePoint/OneDrive/Graph/Procore calls during loading or validation (confirmed by code path — loader only reads local YAML).
- No source documents copied into Obsidian.
- No payload added under `docs/plans/**` (governance rule).
- Procore fields (`procore_company_id`) left nullable, deferred to step 10.
- `jsonschema` runtime dependency NOT added; the two JSON Schema artifacts under `resources/schemas/` are generated documentation only — Pydantic remains authoritative.

## Known Limitations

- All 3 seeded sources ship with `resolution_status: pending`. The supporting reference files (`sharepoint_onedrive_configuration_developer_brief(1).md`, `HB SharePoint Creator(8).json`) were not attached to this session; real `site_url`, `site_id`, and `drive_id` values land via a subsequent prompt or repo override at `config/construction_sources.yml`.
- Pre-existing baseline: 4 failures in `tests/test_obsidian_writer.py` due to `action_item_ids` keyword drift; 22 pre-existing ruff findings in unrelated files; 9 test files that hit MSAL/Graph/subprocess hang in this non-interactive sandbox. None of these are introduced by step 2.

## Next Prompt

Per the Phase 01 build sequence: **Step 3 — SQLite schema and migrations** — to be implemented atop `src/hb_assistant/store/{connection,migrator,repositories}.py`, adding tables for the source registry projects/sources, delta tokens, source manifests, and sync receipts.
