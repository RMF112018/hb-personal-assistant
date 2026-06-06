# 173 — FastAPI Project Keywords Training (Prompt 05)

**Objective:** add project keyword training (registry + CRUD + folder exclusion + explain) to the optional analytics FastAPI shell. This fulfills Phase UI-05 and the explicit contract in Prompt 05 + `06_PROJECT_MATCHING_KEYWORDS.md` (no standard/template folder names as keywords; user can add/edit/disable/delete/exclude; UI explains why an item matched a project).

## Route Inventory

- `GET /projects/{project_key}/keywords` — list enabled (and optionally disabled/excluded) keywords for a project. Viewer+.
- `POST /projects/{project_key}/keywords` — add a term with strength. Operator+ (maps to `can_edit_keywords`).
- `PATCH /projects/{project_key}/keywords/{keyword_id}` — update strength or registry_status (enabled/disabled/excluded). Operator+.
- `DELETE /projects/{project_key}/keywords/{keyword_id}` — hard delete (prefer status for audit). Operator+.
- `POST /projects/{project_key}/keywords/explain` — redacted-only preview: which enabled keywords would fire for a candidate (text or small dict of redacted fields) and why (strength + location). Viewer+ (read-only diagnostic, analogous to `/connections/preview`).

All paths use the existing shell convention (no `/api` prefix in the mounted app). The `project_key` in the URL provides UX scoping; the stored rows carry the authoritative `project_key`.

## Validation and Exclusion Rules

Per `06_PROJECT_MATCHING_KEYWORDS.md` and the package `validation_contract.json` assertion `"no_folder_names_as_keywords"`:

- A hard-coded set of standard/template folder names (Drawings, Specifications, Submittals, RFIs, Photos, Contracts, Correspondence, Change Orders / ChangeOrders, Financials, Meeting Minutes / MeetingMinutes, Closeout, and common variants) is rejected at the service layer on add.
- Normalization (lower, collapse separators, strip trailing 's' for plurals) is applied before the check and before storage.
- Rejected adds return `kind: "keyword_rejected"`, `reason_code: "standard_folder_name_excluded"`.
- Deep-nested or ambiguous names may surface only as weak `suggest` candidates (service method; not auto-added).
- Allowed signals for training/keywords (outside this prompt's scope for ingestion): project name/number/ID from identity, safe SharePoint/OneDrive source names, confirmed matches, user aliases. The registry itself is the operator-controlled side of that.

The service never accepts or stores raw email subjects, file paths with tokens, bodies, or full evidence — only normalized terms + hash + strength/status/provenance.

## Local Persistence (V40)

Prompt 05 introduces an additive migration only:

- `src/hb_assistant/store/migrator.py`: `V40_STATEMENTS` (CREATE TABLE `construction_project_keyword_registry` + two indexes) and the apply block + migration row after V39. `LATEST_SCHEMA_VERSION` bumped to 40.
- Table shape (construction-family, 8 guard CHECK columns = 0):
  - `keyword_id` (PK, hash-derived stable id)
  - `project_key` (FK ref to `construction_project_identity`)
  - `keyword_hash` + `UNIQUE(project_key, keyword_hash)`
  - `keyword_normalized` (bounded 1–128, CHECK)
  - `keyword_class` (phrase / project_number / ... / exclusion_pattern)
  - `strength` (strong/normal/weak)
  - `registry_status` (enabled/disabled/excluded)
  - `provenance` (user_manual / seed_registry / confirmed_match / import_* / system_suggested)
  - `provenance_ref_hash`, `notes_redacted` (redacted only)
  - timestamps + `last_applied_utc`
  - 8 guard columns (`raw_*_persisted = 0`, `signed_url_persisted = 0`, `download_url_persisted = 0`, `external_writeback_performed = 0`)
- `ConstructionStore` (in `repositories.py` after the project source matches methods) adds:
  - `upsert_project_keyword_registry_entry`
  - `get_project_keyword_registry_entry`
  - `list_project_keyword_registry` (with status/strength/include_excluded filters; primary matcher path uses `registry_status="enabled"`)
  - `set_project_keyword_registry_status`
  - `delete_project_keyword_registry_entry`
- `table_lifecycle_status_contract.json` records the new table (family `construction_canonical_v5`, `operational_empty_expected`, `v: "V40"`, phase `UI-05`).

No changes to deterministic match outcome tables (`email_project_matches`, `calendar_project_match_candidates`, `construction_document_project_match_candidates`, drive-item match columns, etc.). The registry is training/config only; matchers will load enabled entries in a later integration step.

## Guardrails

Responses follow the established analytics surface contract:
- `"guardrails"` dict always present (local_first, no_cli_shellout, no_live_endpoint_calls, no_external_writeback, no_folder_names_as_keywords, raw_content_never_stored).
- `"surface"` (reads) or `"kind"` (mutations).
- Never serialize tokens, raw bodies, signed URLs, download URLs, or secret-like values.
- Folder rejection and explain both operate on redacted/normalized input only.
- Role enforcement via the existing `role_dependency()` + `require_operator_role` (viewer may list and explain; only operator/admin may mutate the registry). This aligns with `roles_permissions.json` (`can_edit_keywords` true for both CM user and admin).

Active chat remains disabled; no writeback; no source-system calls.

## Validation

- New dedicated test: `tests/test_fastapi_analytics_project_keywords.py` (FastAPI-optional, mirrors connection-setup style: `_client` returning (TestClient, db path), `FORBIDDEN` + `_assert_safe`, viewer list/explain, operator CRUD roundtrips with post-action `ConstructionStore` inspection, 403 on viewer mutate, direct service + HTTP rejection of standard folder names ("Drawings", "RFIs", "Submittals", ...), explain returns reasons without raw markers).
- `tests/test_fastapi_analytics_app_shell.py` updated: exact OpenAPI path set now includes the five new routes.
- Existing analytics service-boundary and store tests continue to pass (additive schema + no behavior change to prior surfaces).
- After changes: targeted pytest runs, safe subset (`-m "not integration and not live and not manual"`), ruff, mypy on analytics + touched store, followed by the traditional commit.

## Cross-References

- Prompt: `docs/planning/fastapi-analytics-dashboard-implementation-package/prompts/Prompt_05_PROJECT_KEYWORDS.md`
- Spec: `.../06_PROJECT_MATCHING_KEYWORDS.md`
- Implementation sequence: `.../17_IMPLEMENTATION_SEQUENCE.md` (Phase UI-05)
- Backend design: `.../09_FASTAPI_BACKEND_DESIGN.md` (keywords routes)
- Validation contract: `.../resources/json/validation_contract.json` (no_folder_names_as_keywords)
- Roles: `.../resources/json/roles_permissions.json`
- Predecessor arch notes: 169 (service boundary), 170 (app shell), 171 (auth onboarding), 172 (connection setup)

This change is additive, local-first, metadata-only, and fully contained within the existing optional `analytics-ui` surface and construction store/migration discipline. No frontend, no live data paths, and no impact on the core CLI or second-brain phases.