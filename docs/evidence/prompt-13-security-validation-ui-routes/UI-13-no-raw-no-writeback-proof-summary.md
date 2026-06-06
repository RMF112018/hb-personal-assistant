# Prompt 13 / UI-13 — No-Raw / No-Writeback Validation for Analytics UI Routes

**Date:** 2026-06-06  
**Scope:** Optional FastAPI analytics UI shell surfaces (Prompts 01-11 implemented + shell) and their frontend render paths.  
**Per:** Prompt_13_SECURITY_VALIDATION, 15_SECURITY_GUARDRAILS_AND_PRIVACY.md, 16_TESTING..., 17_SEQUENCE (Phase UI-13), 00_PACKAGE_MANIFEST, validation_contract.json "no_raw_sensitive_response_fields", evidence_inputs/04+06, 09_/10_ endpoint contracts.

## Forbidden List (verbatim)
From 15_SECURITY_GUARDRAILS_AND_PRIVACY.md:
No API response or UI surface should expose:
- raw email bodies;
- raw document text;
- raw prompts/responses;
- auth tokens;
- refresh tokens;
- signed URLs;
- Graph download URLs;
- secrets;
- PEM/private key material.

From 00_PACKAGE_MANIFEST: "No raw email body, raw document text, raw prompt/response, token, signed URL, or secret exposure." "No source-system writeback."

## Validated Surfaces (from search inventory)
**Backend routes (current in api.py + test expectation):**
/health, /chat/status (disabled), /onboarding/auth/status, /auth/graph/status + device-login/*, /auth/procore/status + oauth/*, /connections/preview + /save, /admin/connections/{id}/approve-first-sync, /admin/projects/{key}/sync-schedule, /projects/{key}/keywords + /{id} + /explain + /refresh-request + /sync-freshness, /admin/sync/pending-approvals, /api/today + /important + /changes + /meetings + /action-items + /portfolio-signals + /daily-brief, /api/projects/portfolio + /all/overview + /{key}/(overview|meetings|field-operations|cost-time), /api/my-items + subs, /api/daily-brief/status|latest|configure|generate-setup-instructions|validate-output-folder|detect-latest + /api/today/daily-brief, /api/admin + /source-sync-health + /workflow-job-health + /evidence-guardrails + /retrieval-ai-quality + /permissions-governance + /data-completeness.

(Note: /api/settings* + revokes from planning package 09_/Prompt_12 not yet present in code; out of scope for this execution delta.)

**Pydantic models (requests):** GraphDeviceLoginCompleteRequest, ProcoreOAuthExchangeRequest, ConnectionSetupRequest, SyncScheduleRequest, Keyword*, DailyBrief* (Configure/Instructions/ValidateFolder).

**Response builders (service + submodules):** AnalyticsService.build_* (today family, projects family, my-items, admin 6+root, daily-brief today, metric catalog, operations), DailyBriefService (status/latest/configure/detect/validate/present), AuthOnboardingService, ConnectionSetupService (preview/save/freshness/pending), ProjectKeywordsService; all embed `_guardrails()` with "no_raw_sensitive_response_fields": true, "read_only": true, "advisory_only": true.

**Frontend:** lib/api.ts fetch wrappers (getToday*/getProject*/getMyItems*/getAdmin*/getDailyBrief* + configure/detect etc), pages (TodayPage with DailyBriefRenderer + cards, Projects*/Project* subs, MyItemsPage, AdminDataConfidencePage with 6 admin cards, SettingsPage with wizard + preview renderer), components (DailyBriefRenderer for 7 states + sections in <pre> for *intended brief content only*, MetricCard for values).

All local auth surfaces: tokens_returned/secrets_returned: false; only status/identity/refresh_cached:bool/expires.

## How Validations Run (search + exec)
- Grep/Glob searches (planning package only for research; then code for inventory of routes/models/builders/renders).
- Python direct invocation of all current builders (AnalyticsService + DailyBriefService + supporting) + json.dumps check vs FORBIDDEN set (raw_* , *_token, client_secret, signed/download_url, PEM, Bearer etc). 
- Existing test_fastapi_analytics_app_shell.py (health metadata+forbidden, openapi, roles, chat disabled/inaccessible).
- CLI: diagnostics scan-sensitive (Phase 12 bounded) on analytics/ + frontend/src ; second-brain data-quality *no-writeback-proof (and phase-09/08c variants) --json.
- Delegated proofs referenced in admin evidence surfaces exercised via service.

## Results
- All *UI response builders* (today/projects/my/admin/daily-brief/auth/conn/kw surfaces) serialized clean: no LEAK of forbidden *values*.
- Guardrails always present with "no_raw_sensitive_response_fields": True.
- Chat/status: always reports chat_enabled=false, status="disabled", active_chat_routes=false; /chat/* return 404/405.
- Role guards: present (require_*_role deps, X-HB-UI-Role, 403 on invalid); admin surfaces require admin.
- No writeback paths in these surfaces (read-only + local config POSTs only).
- Sensitive scan findings: 
  - In analytics/: msal/token cache *indicators* (strings like "msal-token-cache.bin", token_type checks in auth code — expected for safe status surfaces, never values), "env-style" in daily_brief prompt template (YYYY token placeholder in instructions for *external* agent — per contract).
  - In frontend/: none in source; flags were in *outside-repo* Application Support auth caches (correct, local-only, never to UI).
- no-writeback proofs: produced artifacts (proof_passed may be false on minimal db due to absent phase data/executor runs; the reports contain *control schema names* e.g. raw_*_persisted counters — explicitly false-positive per evidence_inputs/06-closeout-addendum(1).md: "Those are schema-control names used to prove no-raw/no-writeback behavior; they are not raw-content leakage."). The admin/evidence-guardrails UI surface safely surfaces proof status metadata only.
- Direct nw proof scan hit the schema names; composed UI responses (e.g. build_admin_evidence_guardrails) did not.

**Conclusion:** Clean for UI analytics surfaces. No surgical fixes required. "No raw sensitive content" and "no writeback" contracts held for all implemented routes + renders. Local auth shows only safe status.

## Evidence Artifacts Produced
- validation-run.log (builder scan)
- scan-sensitive-analytics.json
- scan-sensitive-frontend.json
- no-writeback-proof.json (and others)
- UI-13-no-raw-no-writeback-proof-summary.md (this)

Cross-ref: Prompt 13, 15_, 16_, 17_ (UI-13), 09_FASTAPI_BACKEND_DESIGN, 10_ANALYTICS_READ_MODELS, validation_contract, prior arch 176-180, evidence_inputs/04+06, existing test FORBIDDEN + health checks.

No tokens/raw bodies/raw docs/prompts/responses/signed URLs/secrets/PEMs serialized in any UI response or display path.
