# FastAPI Analytics — Daily Brief External Agent Workflow (Prompt 10 / UI-10)

## Objective and Scope

Implement the external-agent Markdown Daily Brief surfaces per the implementation package:

- External platform setup wizard (enable/disable, platform selector, output folder, file pattern, stale threshold, show/hide on Today).
- Platform-specific MCP/setup instructions and copy-ready scheduled prompt generation (with placeholders, MCP guidance where supported, advisory-only/no-raw/insufficient-context rules, platform variants for Claude/ChatGPT/Perplexity/Other).
- Markdown file detector (local FS only) that computes one of the 7 contracted states, performs light heading/section parse when practical, and exposes last-file metadata (mtime, size, warnings).
- Polished executive brief renderer inside Today (and reusable in Settings preview) that presents sections, generated time, path, parse warnings, "open original" affordance (copy path + instructions), and strong presenter-only advisory.
- Backend config + detection endpoints; Today read-model integration for the Daily Brief section.
- All per the "present/polish only" contract: generation owner is the external desktop AI platform; the app role is detect/parse/polish/present. The app never generates, authors, or materially rewrites the brief.

In-scope: Settings wizard UI, backend daily-brief service (config persistence under app support, detector, prompt/instructions helpers, status/latest), FastAPI routes + Pydantic request models, enrichment of Today Daily Brief section and DailyBriefRenderer, typed API client helpers, architecture doc, verification.

Out-of-scope (per package boundaries): in-app chat authoring of the brief, writeback, raw sensitive exposure, new top-level nav, activation of Chat, changes to the old second-brain daily brief generator/delivery (separate from this analytics UI presenter surface), non-additive schema changes.

Cross-refs: Prompt_10_DAILY_BRIEF.md, 08_DAILY_BRIEF_EXTERNAL_AGENT_WORKFLOW.md, 13_SETTINGS_AND_CONFIGURATION.md, 11_FRONTEND_UI_STRUCTURE.md, 10_ANALYTICS_READ_MODELS_AND_ENDPOINTS.md, 09_FASTAPI_BACKEND_DESIGN.md, 17_IMPLEMENTATION_SEQUENCE.md (UI-10), 16_TESTING_VALIDATION_ACCEPTANCE.md, 01_OBJECTIVE_AND_BOUNDARIES.md (Daily Brief Boundary), 12_UI_KIT_THEME_AND_COMPONENTS.md, Prompt_09_TODAY_VIEW.md, 00_PACKAGE_MANIFEST.md, resources/json/daily_brief_workflow_contract.json, resources/json/settings_registry.json (daily_brief_display, daily_brief_output_folder), resources/json/navigation_model.json (Today purpose includes Daily Brief; Settings purpose includes Daily Brief setup), 176 (UI kit/nav), 177 (Today/Projects/My Items screens).

## Contract and States (authoritative)

From daily_brief_workflow_contract.json and 08_:

```json
{
  "generation_owner": "external_desktop_ai_platform",
  "input_interface": "MCP where supported, manual prompt otherwise",
  "output_format": "markdown_file",
  "app_role": "detect_parse_polish_present",
  "ui_states": [
    "not_configured",
    "external_ai_setup_required",
    "configured_waiting",
    "brief_available",
    "brief_stale",
    "brief_generation_failed",
    "markdown_parse_warning"
  ],
  "chat_in_app_active": false
}
```

App responsibilities (verbatim from 08_):
- detect latest Markdown file
- verify current/stale status
- parse headings/sections when practical
- display polished executive brief cards
- preserve original Markdown as source artifact
- show generated time, file path, and parse warnings
- open original Markdown file on request
- not rewrite or alter substance without explicit transformation notice

" The app presents externally generated Markdown. It does not generate the Daily Brief through in-app chat." (repeated across 01_, 09_, 13_, Prompt_09, contract).

Recommended sections (when present in the external MD):
1. Executive Summary
2. Today's Meetings
3. Projects Needing Attention
4. Cost / Change Exposure Signals
5. Aging RFIs / Submittals / Decisions
6. Correspondence Worth Reviewing
7. Documents Changed or Requiring Review
8. Vendor / Subcontractor Attention Items
9. Billing / Cash / Retention Attention Items
10. Data Confidence Notes

Scheduled prompt rules: copy-ready text with placeholders for output folder/file naming; must instruct the external AI to use MCP/tools where connected, produce Markdown, save the file, preserve advisory-only language, avoid raw sensitive content, report insufficient context clearly. Platform-specific variants + fallback manual.

## Backend Surfaces

Module: `src/hb_assistant/construction/analytics/daily_brief.py` (DailyBriefService, framework-free).

- Config: small JSON under `PathPolicy().get_app_support() / "analytics" / "daily_brief_ui_config.json"` (enabled, platform, output_folder, file_pattern, stale_threshold_minutes, show_on_today). Defaults + best-effort load/save; never throws to UI.
- Detector (`detect_latest`): resolves folder, globs for pattern (fallback *.md), stats latest by mtime, bounded read + light re-based heading parse to map to recommended sections, computes state, returns metadata (last_file.path, mtime_utc, size_bytes), is_stale, parse_warnings, sections (canonical where matched), content (bounded), plus embedded advisory + guardrails.
- State machine (see 7 codes above + labels): not_configured (disabled or no folder), external_ai_setup_required (alias path), configured_waiting (enabled+folder but no file), brief_stale (file older than threshold), brief_generation_failed (read/stat error), markdown_parse_warning (file present + recent but warnings), brief_available (good recent file).
- Presentation builders: `get_status` (config + compact detect, no heavy content), `get_latest` (full for renderer), `build_today_presentation` (shape for Today section + /api/today/daily-brief).
- Wizard helpers: `validate_output_folder` (exists/is_dir/writable + message), `generate_setup_instructions` (returns mcp_setup_note, platform_specific, output_instructions, scheduled_prompt (the copy-ready text with rules + placeholders filled), test_steps), `configure` (save + return status).
- Guardrails object on every response (read_only, local_first, presenter_only, daily_brief_generation_owner, app_role, no_raw_..., advisory_only, ...). `_presenter_advisory()` string repeated in UI surfaces.

AnalyticsService integration (service.py): `build_today_daily_brief()` delegates to DailyBriefService for the Today read-model family.

FastAPI (api.py):
- Request models: DailyBriefConfigureRequest, DailyBriefInstructionsRequest, DailyBriefValidateFolderRequest.
- Routes (all under role_dep; viewer for reads, require_operator_role for configure/validate/instructions):
  - GET /api/daily-brief/status
  - GET /api/daily-brief/latest
  - POST /api/daily-brief/configure
  - POST /api/daily-brief/generate-setup-instructions
  - POST /api/daily-brief/validate-output-folder
  - POST /api/daily-brief/detect-latest
  - GET /api/today/daily-brief (Today family presentation; also callable via AnalyticsService.build_today_daily_brief)
- Lazy imports inside handlers (FastAPI remains optional). Guardrails + advisory included in bodies. App description/version updated for Prompt 10.
- No raw sensitive fields; paths are user-controlled local FS paths only.

Persistence: JSON under app support (no new SQLite table for this prompt; additive only if a later settings migration consolidates).

## Frontend

Client: `frontend/src/lib/api.ts` — added typed (any-tolerant) helpers: getDailyBriefStatus, getDailyBriefLatest, configureDailyBrief, generateDailyBriefSetupInstructions, validateDailyBriefOutputFolder, detectDailyBriefLatest. getTodayDailyBrief already pointed at /api/today/daily-brief (now live).

Settings wizard (SettingsPage.tsx): full UI for the selections + buttons per 13_ and Prompt 10. Local form state seeded from /status; on-change and explicit buttons call configure/validate/detect/instructions. Results surfaces: instructions + scheduled_prompt in copyable textareas, validate status banner, live detection preview via DailyBriefRenderer. "Test detection" forces fresh scan and updates preview + status. Strong business language and repeated presenter-only advisory. Link to Today.

Today integration (TodayPage.tsx): Daily Brief is section 2 (after Important Today). Uses useQuery on getTodayDailyBrief; passes richer payload (content/markdown, status, generated_at, path, warnings, sections) to renderer; renders advisory + states list + "Configure in Settings" link. No generation paths, no chat, no dry-run labels.

Renderer (DailyBriefRenderer.tsx): handles all 7 states (STATE_LABELS), empty/not-configured state with advisory + link to Settings, renders generatedAt/path with "Copy path" action (user opens locally in editor/Finder), parse warnings, and when `sections` present renders titled blocks for the 10 recommended (fallback to raw content pre for fidelity). Repeated strong "externally generated... presents/polishes only" advisory. "Open original on request" via copy-path + instructions (no raw serve over API).

UX/guardrails: compact badges, construction language, hide raw details, link diagnostics to Admin where appropriate, link config to /settings, no dry-run terminology, Chat remains disabled, no new top-level nav.

## Data Flows (external gen + app present)

```mermaid
flowchart LR
  subgraph External
    A[Desktop AI: Claude/ChatGPT/Perplexity/Other]
  end
  subgraph App
    B[Settings wizard: enable + platform + folder + pattern + stale + show_on_today]
    C[Wizard actions: Generate instructions (MCP + scheduled prompt) / Validate folder / Test detection]
    D[Backend: DailyBriefService (config json + FS detector + state machine + prompt helper) + /api/daily-brief/* + /api/today/daily-brief]
    E[Today: Daily Brief section (6th surface in Today family) + 7-state renderer]
    F[AnalyticsService.build_today_daily_brief (read-model family)]
  end
  A --"writes Markdown (per scheduled prompt + MCP/tools where connected)"--> G[(Local FS: user output_folder + pattern)]
  G --"detect latest + stat + light parse headings/sections + freshness"--> D
  D --"status / latest / today presentation (sections, metadata, advisory, guardrails)"--> E
  D --"status / latest / presentation"--> F
  B --"configure / generate-instr / validate / detect"--> D
  E --"open original (copy path) / link to Settings"--> B
  C --"POSTs"--> D
  style A fill:#f9f,stroke:#333
  style G fill:#ff9,stroke:#333
```

Today read model family and separate /daily-brief/* family both surface the same detector for consistency.

## Guardrails and Contracts (enforced)

- No generation, no rewrite, no in-app chat for the brief.
- External FS only (user-specified folder); no tokens, no Graph/Procore write, no raw source bodies in the brief payload (external agent is instructed to avoid them).
- All responses carry guardrails + presenter advisory.
- Role: viewer read (status/latest/today); operator/admin for configure/validate/instructions/detect.
- "Open original" never serves raw over HTTP; returns/ surfaces the local path for user to open.
- Freshness/staleness computed locally from file mtime vs threshold; parse warnings surfaced but never hide the brief.
- UI labels are business-oriented (no dry-run/apply/execute).

## Verification (per 16_ + 17_ UI-13 + package)

- Backend: analytics imports cleanly; targeted `test_fastapi_analytics_*` (including app_shell for new OpenAPI paths); safe `pytest -m "not integration and not live and not manual"` (tolerate only pre-existing unrelated Phase 09 failures); ruff + mypy on `src/hb_assistant/construction/analytics`.
- Frontend: clean install; lint; tsc --build; vite build. Manual smoke: all 7 states via Settings wizard (configure, instructions copy, validate, test detect) → Today renderer shows correct state + polished sections + path + advisory + copy action; links between Today/Settings work; no raw exposure; Chat disabled; no new top nav.
- Acceptance (16_): "Daily Brief file detector handles missing/current/stale/parse-warning states." "Today renders Daily Brief states." "Daily Brief Markdown renders as polished executive brief."
- Guardrail proofs (no-raw, no-writeback, presenter-only) exercised via existing second-brain + new surfaces; no unrelated Python outside daily-brief surfaces modified.
- Post-change: architecture 178 created; traditional commit with manifest title + Prompt 10 / UI-10 description; only intended delta staged (frontend daily-brief additions + backend daily_brief.py + api/service/__init__ updates + 178 md).

## Cross-References

- Planning package: Prompt_10_DAILY_BRIEF.md, 08_DAILY_BRIEF_EXTERNAL_AGENT_WORKFLOW.md, 13_SETTINGS_AND_CONFIGURATION.md, 11_FRONTEND_UI_STRUCTURE.md, 10_ANALYTICS_READ_MODELS_AND_ENDPOINTS.md, 09_FASTAPI_BACKEND_DESIGN.md, 17_IMPLEMENTATION_SEQUENCE.md, 16_TESTING_VALIDATION_ACCEPTANCE.md, 01_OBJECTIVE_AND_BOUNDARIES.md, 12_UI_KIT_THEME_AND_COMPONENTS.md, Prompt_09_TODAY_VIEW.md, 00_PACKAGE_MANIFEST.md, 02_PRODUCT_PRINCIPLES..., 03_USER_ROLES..., resources/json/{daily_brief_workflow_contract.json, settings_registry.json, navigation_model.json, validation_contract.json}.
- Prior architecture: 176 (UI kit + nav), 177 (Today/Projects/My Items screens), 175 (read models), 174 (sync governance), 173 (project keywords).
- Code: src/hb_assistant/construction/analytics/{daily_brief.py, api.py, service.py, __init__.py}, frontend/src/{lib/api.ts, pages/{TodayPage.tsx,SettingsPage.tsx}, components/daily-brief/DailyBriefRenderer.tsx}.
- Evidence/ops: metrics "Daily Brief Run Health", table inventory (legacy daily_brief_* tables are second-brain, not this UI presenter), validation_contract "daily_brief_markdown_presenter_only".

This doc records the Prompt 10 / UI-10 implementation. Later phases (UI-11 Admin, UI-12 full Settings, UI-13 closeout) may consolidate config or add receipts; changes will be additive and will reference this baseline.
See Prompt 25 runbook and INDEX for the packaged local smoke (FPR-018 final) and final evidence summary. Cite prompt-25-documentation-runbook-packaging-closeout.md.
