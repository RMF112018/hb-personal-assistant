# FastAPI Connection Setup Functional Hardening (Prompt 14A)

## Objective and Scope
Focused corrective hardening for the optional FastAPI analytics connection setup surface before deeper dashboard work.

The implementation already delivered preview → local save → admin first-sync approval separation, role guards, no live external calls in preview, and the no-raw/no-writeback contract. This prompt corrects two practical gaps reported by the user and adds the functional test coverage that proves the low-friction CM-first experience:

- Procore project homepage URLs of the form `https://app.procore.com/<id>/project/home` must be recognized and the numeric ID extracted as the `procore_project_id`.
- SharePoint folder/share-link URLs (including the encoded `/:f:/s/...` form) must classify as folder/share-link scope with appropriate user-facing description and pending admin approval.

Additional explicit requirements addressed:
- Outlook and Calendar "project matching only" remains optional and **false by default** in the preview response (classification / project-matching occurs after safe ingestion of the selected scope).
- OneDrive "all folders" requires explicit `scope_mode="all_folders_explicit"` and emits a user-facing warning that the scope may be large and that first sync requires admin approval.
- Preview never persists config and never calls external services.
- Save persists only local operator selections and never starts first sync (`first_sync_triggered` remains false).
- Admin approval (admin role only) marks the connection approved for a later first sync but does not start a live sync.
- Construction Management User / operator roles can preview and save where intended; they cannot approve first sync.
- Viewer cannot save or approve.
- Chat remains fully disabled and inaccessible.
- No source-system writeback or live external calls are introduced by this change.

This prompt does not implement missing Settings routes (Prompt 12), active chat, or any new dashboard read models. It is strictly connection-setup correctness + validation.

## Changes Made

### Procore URL Parser (connection_setup.py)
- Extended `_preview_procore` (the only Procore classification path used by the FastAPI analytics shell) to also accept the homepage form where the first path segment after the host is the numeric Procore project ID (e.g. segments `["2982068", "project", "home"]`).
- The existing `_PROJECT_ID_RE` (matching `/projects/<id>`) and query-parameter fallbacks (`project_id`, `project`) are preserved.
- On any URL that yields no valid numeric ID, the preview returns the pre-existing safe `unavailable` / `procore_project_id_not_found` response. No persistence and no external calls occur.
- Supported forms after this change (in addition to prior):
  - `https://app.procore.com/2982068/project/home`
  - `https://app.procore.com/2525840/project/home`
  - `https://app.procore.com/2091445/project/home`
- Legacy forms continue to work (`/projects/<id>`, `/projects/<id>/...`, `?project_id=...`, `?project=...`).

### SharePoint Folder / Share-Link Classification
- Updated `_preview_sharepoint` to detect the encoded share-link path prefix forms (`/:f:/s/...`, `/:u:/`, segments starting with `:`) used for direct folder or shared-folder links.
- Such links are classified as folder/share-link scope (`sharepoint_project_drive_folder` / folder-like), `folder_web_url` is populated with the cleaned URL, and `first_sync_status` is `pending_admin_approval`.
- The site example containing `/SitePages/...` continues to be recognized via the existing `is_page` logic (or as site).
- All classification remains purely local string/URL parsing. No Graph calls, no persistence on preview.

### Outlook / Calendar "project matching only" Default
- In `_preview_microsoft_options`, the `outlook` and `calendar` sub-dicts now explicitly include `"project_matching_only": false`.
- The options continue to advertise read-only / metadata-only posture (`mailbox_mutation_allowed`, `full_body_persisted`, `persist_event_body`, `persist_join_url` all false).
- The governing contract ("Index selected mailbox/calendar scope safely, then classify/project-match relevant items after ingestion") is the implied default behavior of the connection setup surface.

### OneDrive All-Folders Warning (confirmation + test coverage)
- `scope_mode` must be one of `selected_folders`, `all_folders_explicit`, or `excluded`. Implicit root-wide access is rejected.
- When `all_folders_explicit` is used, the preview response includes the warning `["onedrive_all_folders_requires_admin_approval"]` and `first_sync_status` indicates admin approval is required.

### Boundary, Role, and Guardrail Enforcement (no behavior change, stronger tests)
- `POST /connections/preview` — available to viewer+ (classification only).
- `POST /connections/save` — requires operator or admin; only local config is written; `first_sync_triggered` is false in the response and persisted state.
- `POST /admin/connections/{id}/approve-first-sync` — requires admin; sets `approved_first_sync_not_started`; `first_sync_triggered` remains false. Operator and viewer receive 403.
- Every response envelope carries the connection guardrails (`local_setup_only`, `no_live_endpoint_calls`, `no_external_writeback`, `first_sync_triggered: false`, etc.).
- Active chat remains disabled (`/chat/status` reports `chat_enabled=false` / `status=disabled`; direct `/chat*` routes return 404/405). No chat activation or model routing was added.

## Guardrails and Contracts
- Preview paths are strictly offline and side-effect free (string/URL parsing + local registry lookup for friendly project name only).
- No tokens, raw bodies, raw document text, signed URLs, Graph download URLs, PEMs, prompts, or responses are ever returned or stored by these routes.
- First live sync is never started by preview, save, or admin approval in this surface. Approval only mutates local scheduling/approval state.
- Role matrix is enforced at the route layer (`require_operator_role`, `require_admin_role`) and re-asserted in tests.

## Tests Added / Updated (test_fastapi_analytics_connection_setup.py)
New or extended tests covering (at minimum) the 13 cases required by the spec:
- Procore homepage URL extraction for the three explicit user examples.
- Procore legacy `/projects/{id}` and query forms continue to work.
- Invalid Procore URL → safe `unavailable` / `procore_project_id_not_found`, no persistence, no external call.
- SharePoint site example (SitePages) and the exact folder/share-link `/:f:/s/...` form both produce pending admin approval and appropriate folder/site classification.
- OneDrive all-folders explicit case emits the admin-approval warning.
- Outlook and Calendar previews return `project_matching_only: false` (and the prior read-only flags).
- Save persists only local config/selection and never sets `first_sync_triggered`.
- Admin approval (admin only) leaves `first_sync_triggered=false`; operator/viewer are denied.
- Viewer cannot save; operator can preview+save where intended.
- Local re-assertion that `/chat/status` remains disabled and `/chat*` routes are inaccessible (the full matrix lives in `app_shell.py` and is executed in the validation suite).

All new tests follow the existing pattern (`_client`, `_assert_safe` for the FORBIDDEN markers, role headers via `X-HB-UI-Role`).

## Validation Performed
Targeted (as specified):
- `python -m pytest tests/test_fastapi_analytics_connection_setup.py`
- `python -m pytest tests/test_fastapi_analytics_app_shell.py`
- `python -m pytest tests/test_fastapi_analytics_service_boundary.py`

Scoped:
- `python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_connection_setup.py`
- `python -m mypy src/hb_assistant/construction/analytics`

Broader safe analytics/security subset (per phase convention) may be run; only pre-existing unrelated Phase 09 noise is tolerated. No live external calls are executed.

## Documentation / Evidence
- This file (`182-fastapi-connection-setup-functional-hardening.md`) records the Prompt 14A changes (additive companion to `172-fastapi-connection-setup-surfaces.md`).
- An additive evidence artifact is created under `docs/evidence/prompt-14a-connection-setup-hardening/` containing a summary note and captured command outputs for the validation commands.

## Cross-References
- Prompt 14A objective and governing product intent (low-friction CM-first, paste-URL → plain preview → local save → admin approve, no heavy sync surprises).
- `docs/architecture/172-fastapi-connection-setup-surfaces.md` (base contract for the surfaces).
- Prior Prompts 04 (connection), 06 (sync governance admin-only), 09/10/11 (CM-first surfaces, admin secondary, advisory), 13 (no-raw, role guards, chat disabled, FORBIDDEN contract).
- `src/hb_assistant/construction/analytics/connection_setup.py` (parser, preview/save/approve logic) and `api.py` (routes + `require_*_role`).
- `tests/test_fastapi_analytics_connection_setup.py` + `app_shell.py`.
- Validation contract, roles/permissions, guardrails from 15_SECURITY, 16_TESTING, 09/10 design, and `evidence_inputs`.
- No schema migration was required.

## Post-Execution Summary (per query)
- Architecture documentation updated at `docs/architecture/` (this file + reference in 172).
- Appropriate verification suite executed (targeted pytest files first, ruff + mypy on delta scope, broader safe subset).
- Traditional commit prepared with manifest title "HB FastAPI Analytics Dashboard — CM-First Implementation Package" + Prompt 14A description.
- Only the commit summary and description are output as final result.

This completes the Prompt 14A functional hardening for connection setup. The Procore homepage URLs now parse as required, SharePoint share links are recognized, defaults and warnings match the spec, the preview/save/approve boundary and role matrix are proven by tests, chat remains disabled, and no live calls or source writeback were introduced.