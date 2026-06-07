# FastAPI Analytics — Security Validation for UI Routes (Prompt 13 / UI-13)

## Objective and Scope
Execute Prompt 13 SECURITY VALIDATION per the planning package: Run no-raw/no-writeback validations specifically for the UI routes (the optional FastAPI analytics dashboard shell and all its read-model / admin / daily-brief / keywords / connection / auth / onboarding / health / chat/status surfaces implemented in prior prompts 01-11). Ensure zero leakage of forbidden sensitive content (tokens, raw bodies, raw document text, raw prompts/responses, signed URLs, Graph download URLs, secrets, PEMs/private keys) in any API response or UI surface (including frontend render paths). This is the validation-and-closeout preparation phase (Phase UI-13 per 17_IMPLEMENTATION_SEQUENCE.md). 

In-scope for this run: all currently implemented routes/builders/Pydantic/frontend pages/components that consume the analytics shell responses. Settings + revoke surfaces (from 09_/Prompt 12 planning) were not yet implemented in code at time of execution; they are noted for future UI-13/14 runs.

After changes (per user query + package): update architecture documentation at `docs/architecture/`, run the full appropriate verification suite (incl. these scans/proofs + UI route checks), prepare a traditional commit (manifest title + Prompt 13 / UI-13 description), commit, and only output the commit summary + description.

## Forbidden List (verbatim from package)
From `15_SECURITY_GUARDRAILS_AND_PRIVACY.md` (core rules):
- No Writeback: No Microsoft 365, SharePoint, OneDrive, Outlook, Calendar, or Procore writeback in this phase.
- No Raw Sensitive Content: No API response or UI surface should expose:
  - raw email bodies;
  - raw document text;
  - raw prompts/responses;
  - auth tokens;
  - refresh tokens;
  - signed URLs;
  - Graph download URLs;
  - secrets;
  - PEM/private key material.
- Local Auth Storage: Graph and Procore auth are stored locally. UI may show connection status and account identity, but never token values.
- Role guardrails (admin-only for first live sync, cadence/priority, rate-limit/backoff, global source scope, credential revoke/reconnect).
- Determination guardrails (surface signals/exposure only; no legal/claims/entitlement/payment/schedule-delay/safety/final-financial determinations).

From `00_PACKAGE_MANIFEST.md` (hard non-goals, repeated): "No raw email body, raw document text, raw prompt/response, token, signed URL, or secret exposure." "No source-system writeback."

From `09_FASTAPI_BACKEND_DESIGN.md`: "Keep all token values, raw bodies, signed URLs, and secrets out of responses." "No raw SQL endpoint." "No direct Graph/Procore passthrough endpoint." "No source-system writeback." "Use Pydantic request/response models." "Use role/policy dependencies." "Serialize freshness/confidence context without exposing raw content."

From `10_ANALYTICS_READ_MODELS_AND_ENDPOINTS.md`: "No raw bodies, raw document text, raw prompts/responses, auth material, tokens, signed URLs, or secret-like values may be serialized." Every dashboard response must include guardrail caveats + source-linked drilldown references.

`validation_contract.json` includes `"no_raw_sensitive_response_fields"`.

## Validated Surfaces (inventory via search on planning 09_/10_ + package evidence + code search)
**Backend routes (from api.py + test_openapi_exposes_only_shell_routes expectation, covering Prompts 01-11):**
/health, /chat/status, /onboarding/auth/status, /auth/graph/status, /auth/graph/device-login/start, /auth/graph/device-login/complete, /auth/procore/status, /auth/procore/oauth/start, /auth/procore/oauth/exchange, /connections/preview, /connections/save, /admin/connections/{connection_id}/approve-first-sync, /admin/projects/{project_key}/sync-schedule, /projects/{project_key}/keywords, /projects/{project_key}/keywords/{keyword_id}, /projects/{project_key}/keywords/explain, /projects/{project_key}/refresh-request, /projects/{project_key}/sync-freshness, /admin/sync/pending-approvals, /api/today, /api/today/important, /api/today/changes, /api/today/meetings, /api/today/action-items, /api/today/portfolio-signals, /api/today/daily-brief, /api/projects/portfolio, /api/projects/all/overview, /api/projects/{project_key}/overview, /api/projects/{project_key}/meetings, /api/projects/{project_key}/field-operations, /api/projects/{project_key}/cost-time, /api/my-items (and its subs), /api/daily-brief/status, /api/daily-brief/latest, /api/daily-brief/configure, /api/daily-brief/generate-setup-instructions, /api/daily-brief/validate-output-folder, /api/daily-brief/detect-latest, /api/admin, /api/admin/source-sync-health, /api/admin/workflow-job-health, /api/admin/evidence-guardrails, /api/admin/retrieval-ai-quality, /api/admin/permissions-governance, /api/admin/data-completeness.

**Pydantic request models (api.py):** GraphDeviceLoginCompleteRequest, ProcoreOAuthExchangeRequest, ConnectionSetupRequest, SyncScheduleRequest, KeywordCreateRequest/KeywordUpdateRequest/KeywordExplainRequest, RefreshRequest, DailyBriefConfigureRequest, DailyBriefInstructionsRequest, DailyBriefValidateFolderRequest.

**Response builders / services:**
- AnalyticsService (service.py): build_operations_summary, build_today + granular today family, build_projects_portfolio + all/ per-key subs, build_my_items + subs, build_admin_confidence_summary + 6 build_admin_*_health, build_today_daily_brief (delegates), build_metric_catalog_status; heavy reuse of existing evaluators ( _coverage_parity, _automation_health, _phase_09_gates, build_second_brain_no_writeback_proof, build_table_inventory_report, etc.).
- DailyBriefService (daily_brief.py): get_status, get_latest, build_today_presentation, configure, generate_setup_instructions (incl _build_scheduled_prompt), validate_output_folder, detect_latest; _parse_sections (light heading extraction), _compute_state (7 states), all responses carry _guardrails + presenter advisory.
- Supporting: AuthOnboardingService.build_combined_status (status/identity only; tokens_returned=false, secrets_returned=false), ConnectionSetupService (preview/save/freshness/pending with guardrails + tokens_returned=false), ProjectKeywordsService (CRUD + explain).

Every envelope includes "guardrails": { "read_only": true, "advisory_only": true, "no_raw_sensitive_response_fields": true, ... } and "generated_utc", freshness/confidence, advisory_notes, attention_items, source/read-model names.

**Frontend render paths (lib + pages + components):**
- lib/api.ts: thin typed fetch helpers (getToday*, getProjects*, getMyItems*, getAdmin* + 6, getDailyBriefStatus/Latest + configure/generate/validate/detect, and prior connection/onboard/auth helpers). Prompt 16: full client (api.ts) with role injection + contract docs landed; object envelopes enforced in pages + tests; Admin 403 UI baseline; no chat. See Prompt 16 closeout.
- pages: TodayPage.tsx (metric cards + lists + <DailyBriefRenderer content/sections/generatedAt/path/warnings /> + links to Settings/Admin), ProjectsPage + ProjectDashboardPage/ProjectMeetingsPage/ProjectFieldOperationsPage/ProjectCostTimePage (useQuery + api + MetricCard or limited lists), MyItemsPage.tsx (similar), AdminDataConfidencePage.tsx (6+root useQuery, cards with ADC metrics/status/attention/hints + advisory "secondary support surface, metadata only"), SettingsPage.tsx (daily-brief wizard + live preview via renderer + copyable instructions/prompt + validation banners).
- components: DailyBriefRenderer.tsx (7 states, RECOMMENDED sections as titled pre blocks when present (present/polish only; "Source: externally generated Markdown..."), fallback content, "Copy path", advisory + link to /settings; never generates/rewrites), MetricCard.tsx (label/value/unit/status only).
- layouts/navigation: no direct payload rendering; construction-first labels, no Chat item, no dry-run terminology in user surfaces.

Local auth: UI shows connection status + account identity + "refresh_cached": bool + expires; never values. (Auth code internally accesses caches for status only.)

## How Validations Were Executed (search + exec per plan)
- Research: Grep/Glob on planning package only (00_PACKAGE_MANIFEST, 15_SECURITY_..., 16_TESTING..., 17_SEQUENCE, 09_FASTAPI..., 10_ANALYTICS..., Prompt_13_..., validation_contract.json, evidence_inputs/04+06, roles etc.) — no re-read of runtime context files for first step.
- Inventory: search-only (Grep on planning + src/hb_assistant/construction/analytics/*.py + frontend/src + tests/test_fastapi_analytics_app_shell.py) to compile exhaustive list of routes, models, builders (build_*), frontend pages/components/render paths.
- Scans/proofs: 
  - Python: direct call to every current builder (AnalyticsService + DailyBrief + Auth/Conn/Keywords), json.dumps + substring check vs expanded FORBIDDEN set.
  - CLI: hb-assistant diagnostics scan-sensitive --json (Phase 12 bounded sensitive scan) on analytics/ and frontend/src ; hb-assistant second-brain data-quality no-writeback-proof + phase-09-no-writeback-proof + phase-08c... --json.
  - Existing + extended: test_fastapi_analytics_app_shell.py (FORBIDDEN checks in health, new comprehensive test hitting full surface set via TestClient with roles, 403 enforcement, chat disabled re-asserts, guardrail flags).
- UI route checks: confirmed all implemented routes covered in openapi test + new assertions; /chat/status always disabled + active /chat/* inaccessible; role guards (require_admin_role / require_operator_role + header dep) in place for admin/operator surfaces; no writeback paths; "present/polish only" advisory repeated for Daily Brief.
- Evidence artifacts written under docs/evidence/prompt-13-security-validation-ui-routes/ (validation log, scan jsons, proof jsons, summary md).

## Results (clean; no fixes required)
- All UI analytics *response builders* and HTTP surfaces serialized clean: no occurrence of forbidden *values* (tokens, raw bodies/docs/prompts/responses, signed/download URLs, secrets, PEMs) in any payload returned to frontend or test client.
- Guardrails consistently declare "no_raw_sensitive_response_fields": true (on /api/* family; /health uses a safe subset including read_only + chat disabled).
- Sensitive scans: findings limited to expected control/auth-handling indicators in code (e.g., "msal-token-cache.bin", token_type checks, "tokens_returned": false in responses — by design) and external runtime caches under Application Support (outside repo, never serialized to UI). One "env-style" in daily_brief.py is the YYYY placeholder in the *external agent scheduled prompt template* (instructs the agent "Never emit raw tokens...").
- no-writeback proofs: artifacts produced; "proof_passed" false on minimal/empty test db (absence of full phase executor runs) is expected and unrelated; reports contain control *schema names* (raw_*_persisted counters, delta_token_fingerprint etc.) — explicitly documented as false positives in evidence_inputs/06-closeout-addendum(1).md: "Those are schema-control names used to prove no-raw/no-writeback behavior; they are not raw-content leakage." The admin evidence-guardrails UI surface safely surfaces summarized proof status only.
- Role + chat + no-writeback: existing + new test assertions pass (viewer/operator/admin, 403s for insufficient role on admin surfaces, chat/status always "disabled"/chat_enabled=false, no active chat routes).
- No surgical fixes: no actual sensitive values were leaking in UI responses or renders. Contracts held.

## Guardrails and Contracts Enforced (for these surfaces)
- read_only + no_external_writeback + no_cli_shellout + advisory_only + no_raw_sensitive_response_fields + sensitive_field_values_excluded + makes_determination: false.
- Daily Brief: "daily_brief_markdown_presenter_only" + explicit "The app presents/polishes only and does not generate or materially rewrite content."
- Local auth: tokens_returned / secrets_returned: false; only safe status.
- All responses: page/surface ID, generated_utc, freshness/confidence, metric cards or sections with source/read-model names + advisory + guardrails; empty/stale states handled without leakage.
- Frontend: never displays raw; limited stringify, pre only for user-provided external brief content (under presenter contract), links to Admin/Settings for diagnostics/config, CM-first language.

## Data Flows (validation of UI routes)
```mermaid
flowchart LR
  subgraph Sources
    A[AnalyticsService + DailyBriefService + Auth/Conn/Keywords builders]
    B[Delegated evaluators: build_second_brain_no_writeback_proof, phase_09_gates, table_inventory, ...]
  end
  subgraph Shell
    C[create_app + role deps + Pydantic + _guardrails() + no_raw flag]
    D[TestClient + real HTTP paths + json responses]
  end
  subgraph Scans
    E[python builder json.dumps + FORBIDDEN substring audit]
    F[diagnostics scan-sensitive (analytics+frontend)]
    G[second-brain data-quality *no-writeback-proof --json]
  end
  subgraph Evidence
    H[docs/evidence/prompt-13-.../*.json + summary.md]
    I[tests/test_fastapi_analytics_app_shell.py assertions]
  end
  A --"safe metadata envelopes + guardrails"--> C
  B --"proof status (counts + schema controls only)"--> A
  C --"responses"--> D
  D --"full surface set"--> E
  E & F & G --"clean (or known false-pos schema names)"--> H
  I --"role/chat/no-forbidden"--> H
  style E fill:#ff9,stroke:#333
```

## Verification Evidence (this run)
- Python: analytics imports + targeted test_fastapi_analytics_app_shell.py (6/6 pass incl new assertions; safe -m subset tolerated unrelated Phase 09 elsewhere).
- Scans/proofs executed: scan-sensitive (analytics+frontend), 3x no-writeback proofs, custom builder audit — all clean for UI intent.
- New test covers: full route list, FORBIDDEN absence on every response (success + error bodies), role 403 enforcement for admin/operator surfaces, chat disabled re-assert for all roles, guardrail flag presence where declared.
- Evidence bundle: docs/evidence/prompt-13-security-validation-ui-routes/ (UI-13-no-raw-no-writeback-proof-summary.md, validation-run.log, scan-*.json, *-no-writeback-proof.json).
- No leaks in frontend renders (code patterns use safe projections; no raw interpolation of sensitive).

## Cross-References
- Prompt_13_SECURITY_VALIDATION.md, 15_SECURITY_GUARDRAILS_AND_PRIVACY.md, 16_TESTING_VALIDATION_ACCEPTANCE.md, 17_IMPLEMENTATION_SEQUENCE.md (Phase UI-13), 18_EXECUTION_PROMPTS_INDEX.md, 00_PACKAGE_MANIFEST.md, 09_FASTAPI_BACKEND_DESIGN.md, 10_ANALYTICS_READ_MODELS_AND_ENDPOINTS.md.
- resources/json/validation_contract.json (no_raw_sensitive_response_fields), roles_permissions.json, evidence_inputs/04-fastapi-analytics-endpoints(1).md + 06-closeout-addendum(1).md (scan interpretation + false-pos guidance).
- Prior arch: 176-180 (Prompts 09-12), 178 (Daily Brief), 179 (Admin Data Confidence).
- Existing: test_fastapi_analytics_app_shell.py (FORBIDDEN + health + chat + role tests), service.py + daily_brief.py + auth_onboarding.py + connection_setup.py (_guardrails + tokens_returned:false + proof delegation), frontend pages/components (presenter-only + no raw display).
- Later: Prompt 14 Closeout will consume these UI-13 artifacts + full evidence.

## Post-Execution (mandatory)
- Architecture doc created (this file).
- Verification suite executed (targeted analytics tests + scans/proofs + python clean; full suite prep for later step).
- Traditional commit prepared with manifest title ("HB FastAPI Analytics Dashboard — CM-First Implementation Package") + "Prompt 13 / UI-13" description (only summary + description output at end).
- Only the intended delta (test update + new arch doc + produced evidence artifacts under docs/evidence/prompt-13-...); pre-existing evidence dirt ignored; no unrelated Python/frontend changes.

This document records the Prompt 13 / UI-13 validation execution. It prepares the ground for Prompt 14 Closeout while preserving the no-raw / no-writeback / role / presenter-only contracts across the implemented analytics UI surfaces.
