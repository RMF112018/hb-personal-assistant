/* eslint-disable @typescript-eslint/no-explicit-any */
/* Thin, typed API client for the HB Analytics local shell (historical notes 07/08/09/10/11/14/16/20 + D + E; see package docs).
 *
 * - Uses relative /api paths (dev server proxy in vite.config.ts forwards to backend, e.g. http://127.0.0.1:8000).
 * - Falls back to VITE_API_BASE when provided (e.g. for standalone backend).
 * - Injects X-HB-UI-Role header on every request from localStorage 'hb-ui-role' (viewer|operator|admin).
 *   Default: 'operator'. The value is local-dev simulation only; real backend role guards (require_admin_role etc.)
 *   remain fail-closed and are authoritative.
 * - All responses are advisory / metadata-only. No secrets, tokens, raw bodies, PEMs, or writeback paths exist here.
 * - Contract notes (Prompt 16):
 *   - /api/today and its /changes|/meetings|/action-items|/portfolio-signals return envelopes with optional .items for
 *     today-compat sections (see build_today_section).
 *   - Project tab responses (/api/projects/{key}/overview, /meetings, /field-operations, /cost-time) and
 *     /api/my-items + /api/admin* return OBJECT envelopes: { metric_cards: [...], attention_items: [...], sections: [...],
 *     freshness, confidence_summary, project_key?, surface, guardrails, ... }. They are NOT bare arrays and do not have
 *     a top-level 'items' for the primary tab content.
 *   - My Items page must consume the single aggregate /api/my-items only (no /api/my-items/{action-items|meetings|...}
 *     subroutes are implemented; calling them produces 404s). Sections are derived from the aggregate shape.
 * - Prompt D (Get Started / Account Connections): adds readiness + normalized auth flow helpers under /api/settings/connections/*.
 *   Responses are safe (no tokens, secrets, codes beyond one-time device user_code, cache paths, or raw payloads).
 * - Prompt E (Project Connections): adds preview/save/list for project sources (Procore, SharePoint, OneDrive, Outlook/Calendar)
 *   under the normalized /api/settings/connections/projects/* family. Preview and save are read-only metadata only and
 *   explicitly never start sync; first sync requires separate admin approval. Auth-aware surfaces are handled in UI by
 *   checking account status before enabling source types.
 * - Keep this surface thin: presentation only. Business logic lives in AnalyticsService + read projections (internal).
 * - any-tolerant per existing page style in this repo (see Project*Page.tsx etc.); eslint-disable at top to match.
 */

const API_BASE = ((import.meta as any)?.env?.VITE_API_BASE as string | undefined) || '';

export type LocalUiRole = 'viewer' | 'operator' | 'admin';

const ROLE_KEY = 'hb-ui-role';

export function getLocalUiRole(): LocalUiRole {
  if (typeof window === 'undefined') return 'operator';
  const v = window.localStorage.getItem(ROLE_KEY) as LocalUiRole | null;
  return v === 'viewer' || v === 'operator' || v === 'admin' ? v : 'operator';
}

export function setLocalUiRole(role: LocalUiRole): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(ROLE_KEY, role);
  }
}

/* Prompt D — minimal safe response shapes (matching backend contract; keep loose for page parity with any-tolerant style). */
export type AuthStatus =
  | 'never_connected'
  | 'connected_valid'
  | 'connected_refreshing'
  | 'connected_stale_refreshable'
  | 'connected_stale_reauth_required'
  | 'connected_error'
  | 'disconnected_by_user';

export interface OnboardingReadinessResponse {
  onboarding_state: 'first_time' | 'ready' | 'degraded' | 'reauth_required' | 'blocked';
  main_app_allowed: boolean;
  graph?: any;
  procore?: any;
  reauth_required?: string[];
  required_actions?: any[];
  has_prior_setup?: boolean;
  guardrails?: any;
}

export interface ConnectionsAccountsResponse {
  graph?: any;
  procore?: any;
  guardrails?: any;
}

export interface GraphAuthStartResult {
  flow_id: string;
  user_code: string;
  verification_uri: string;
  verification_uri_complete?: string;
  expires_at?: string;
  message?: string;
  guardrails?: any;
}

export interface ProcoreAuthStartResult {
  flow_id: string;
  authorization_url: string;
  expires_at?: string;
  callback_mode?: 'localhost' | 'oob';
  manual_code_fallback_available?: boolean;
  message?: string;
  guardrails?: any;
}

export interface AuthFlowStatus {
  flow_id: string;
  status: 'pending' | 'complete' | 'expired' | 'failed';
  message?: string;
  guardrails?: any;
}

export class ScheduleApiError extends Error {
  code: string;
  status: number;
  payload: Record<string, unknown>;

  constructor(code: string, payload: Record<string, unknown>, status: number, message?: string) {
    super(message || code);
    this.code = code;
    this.status = status;
    this.payload = payload;
  }
}

export class ScheduleNetworkError extends Error {
  cause?: unknown;

  constructor(message = 'schedule_upload_network_error', cause?: unknown) {
    super(message);
    this.name = 'ScheduleNetworkError';
    this.cause = cause;
  }
}

function parseScheduleApiError(status: number, body: unknown): ScheduleApiError | null {
  if (!body || typeof body !== 'object') return null;
  const detail = (body as { detail?: unknown }).detail;
  if (detail && typeof detail === 'object' && detail !== null && 'code' in detail) {
    const rec = detail as Record<string, unknown>;
    const code = String(rec.code ?? 'schedule_import_invalid');
    return new ScheduleApiError(code, rec, status, code);
  }
  if (typeof detail === 'string' && detail.startsWith('schedule_')) {
    return new ScheduleApiError(detail, { code: detail }, status, detail);
  }
  return null;
}

async function fetchJson<T = any>(path: string, init?: RequestInit): Promise<T> {
  const role = getLocalUiRole();
  const headers = new Headers(init?.headers || {});
  headers.set('X-HB-UI-Role', role);
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  if (!res.ok) {
    let detail = '';
    try {
      const j = await res.json();
      detail = (j && (j.detail || j.message)) ? String(j.detail || j.message) : '';
    } catch {
      // non-json error body; keep status only
    }
    const err = new Error(`${res.status} ${res.statusText}${detail ? ': ' + detail : ''}`);
    (err as any).status = res.status;
    throw err;
  }
  return res.json() as Promise<T>;
}

/* Today family (Prompt 07 / UI-09). */
export function getToday() {
  return fetchJson('/api/today');
}
export function getTodayChanges() {
  return fetchJson('/api/today/changes');
}
export function getTodayMeetings() {
  return fetchJson('/api/today/meetings');
}
export function getTodayActionItems() {
  return fetchJson('/api/today/action-items');
}
export function getTodayPortfolioSignals() {
  return fetchJson('/api/today/portfolio-signals');
}
export function getTodayDailyBrief() {
  return fetchJson('/api/today/daily-brief');
}

/* Projects (Prompt 07/18). Portfolio + per-project (incl. all) envelopes. */
export function getProjectsPortfolio() {
  return fetchJson('/api/projects/portfolio');
}
export function getProjectOverview(projectKey: string) {
  const key = projectKey || 'all';
  return fetchJson(`/api/projects/${encodeURIComponent(key)}/overview`);
}
export function getProjectMeetings(projectKey: string) {
  const key = projectKey || 'all';
  return fetchJson(`/api/projects/${encodeURIComponent(key)}/meetings`);
}
export function getProjectFieldOperations(projectKey: string) {
  const key = projectKey || 'all';
  return fetchJson(`/api/projects/${encodeURIComponent(key)}/field-operations`);
}
export function getProjectCostTime(projectKey: string) {
  const key = projectKey || 'all';
  return fetchJson(`/api/projects/${encodeURIComponent(key)}/cost-time`);
}

/* My Items (Prompt 09 / UI-09). Aggregate only — no subroutes. */
export function getMyItems() {
  return fetchJson('/api/my-items');
}

/* Admin / Data Confidence (Prompt 11). Admin role required by backend guards (fail-closed). */
export function getAdmin() {
  return fetchJson('/api/admin');
}
export function getAdminSourceSyncHealth() {
  return fetchJson('/api/admin/source-sync-health');
}
export function getAdminWorkflowJobHealth() {
  return fetchJson('/api/admin/workflow-job-health');
}
export function getAdminEvidenceGuardrails() {
  return fetchJson('/api/admin/evidence-guardrails');
}
export function getAdminRetrievalAiQuality() {
  return fetchJson('/api/admin/retrieval-ai-quality');
}
export function getAdminPermissionsGovernance() {
  return fetchJson('/api/admin/permissions-governance');
}
export function getAdminDataCompleteness() {
  return fetchJson('/api/admin/data-completeness');
}

/* Daily Brief external (Prompt 10). Viewer read; operator+ for configure/actions. */
export function getDailyBriefStatus() {
  return fetchJson('/api/daily-brief/status');
}
export function getDailyBriefLatest() {
  return fetchJson('/api/daily-brief/latest');
}
export function configureDailyBrief(patch: any) {
  return fetchJson('/api/daily-brief/configure', { method: 'POST', body: JSON.stringify(patch) });
}
export function generateDailyBriefSetupInstructions(body?: any) {
  return fetchJson('/api/daily-brief/generate-setup-instructions', { method: 'POST', body: JSON.stringify(body || {}) });
}
export function validateDailyBriefOutputFolder(body: { folder?: string }) {
  return fetchJson('/api/daily-brief/validate-output-folder', { method: 'POST', body: JSON.stringify(body || {}) });
}
export function detectDailyBriefLatest() {
  return fetchJson('/api/daily-brief/detect-latest', { method: 'POST' });
}

/* Settings / Connection surfaces (historical note 14B — see planning package for remediation context). */
export function getSettings() {
  return fetchJson('/api/settings');
}
export function getSettingsAccounts() {
  return fetchJson('/api/settings/accounts');
}
export function getSettingsProjects() {
  return fetchJson('/api/settings/projects');
}
export function getSettingsSources() {
  return fetchJson('/api/settings/sources');
}
export function getSettingsKeywords() {
  return fetchJson('/api/settings/keywords');
}

/* Project keywords (historical note 20 / FPR-017): management UI over existing safe backend routes. */
export function getProjectKeywords(projectKey: string) {
  const key = projectKey || 'all';
  return fetchJson(`/projects/${encodeURIComponent(key)}/keywords`);
}
export function addProjectKeyword(projectKey: string, term: string, strength: number = 1) {
  const key = projectKey || 'all';
  return fetchJson(`/projects/${encodeURIComponent(key)}/keywords`, { method: 'POST', body: JSON.stringify({ term, strength }) });
}
export function patchProjectKeyword(projectKey: string, keywordId: string | number, patch: any) {
  const key = projectKey || 'all';
  return fetchJson(`/projects/${encodeURIComponent(key)}/keywords/${encodeURIComponent(String(keywordId))}`, { method: 'PATCH', body: JSON.stringify(patch) });
}
export function deleteProjectKeyword(projectKey: string, keywordId: string | number) {
  const key = projectKey || 'all';
  return fetchJson(`/projects/${encodeURIComponent(key)}/keywords/${encodeURIComponent(String(keywordId))}`, { method: 'DELETE' });
}
export function explainProjectKeywordMatch(projectKey: string, text: string) {
  const key = projectKey || 'all';
  return fetchJson(`/projects/${encodeURIComponent(key)}/keywords/explain`, { method: 'POST', body: JSON.stringify({ text }) });
}
export function getSettingsDailyBrief() {
  return fetchJson('/api/settings/daily-brief');
}
export function getSettingsPreferences() {
  return fetchJson('/api/settings/preferences');
}
export function getSettingsAdminSync() {
  return fetchJson('/api/settings/admin-sync');
}
export function patchSettingsPreferences(patch: any) {
  return fetchJson('/api/settings/preferences', { method: 'PATCH', body: JSON.stringify(patch) });
}
export function patchSettingsAdmin(patch: any) {
  return fetchJson('/api/settings/admin', { method: 'PATCH', body: JSON.stringify(patch) });
}

/* Onboarding readiness (Prompt D) — drives first-time routing and returning-user reauth state.
 * Uses only normalized /api paths. Never triggers sync.
 */
export function getOnboardingReadiness() {
  return fetchJson<OnboardingReadinessResponse>('/api/onboarding/readiness');
}

/* Microsoft Graph device-code auth flows (Prompt B + D, normalized contract).
 * start returns safe {flow_id, user_code, verification_uri, ...}
 * status polls with flow_id (no secrets returned)
 * disconnect clears local cache only.
 */
export function startGraphDeviceAuth() {
  return fetchJson<GraphAuthStartResult>('/api/settings/connections/graph/auth/start', { method: 'POST' });
}
export function getGraphAuthStatus(flowId: string) {
  const qs = encodeURIComponent(flowId);
  return fetchJson<AuthFlowStatus>(`/api/settings/connections/graph/auth/status?flow_id=${qs}`);
}
export function disconnectGraphLocal() {
  return fetchJson('/api/settings/connections/graph/disconnect-local', { method: 'POST' });
}

/* Procore local OAuth flows (Prompt C + D, normalized contract).
 * start returns safe {flow_id, authorization_url, callback_mode, manual_code_fallback_available, ...}
 * status for polling after browser callback or manual.
 * exchange-code is the manual/OOB fallback under the normalized path (no cache_path in response).
 * disconnect clears local only.
 */
export function startProcoreAuth() {
  return fetchJson<ProcoreAuthStartResult>('/api/settings/connections/procore/auth/start', { method: 'POST' });
}
export function getProcoreAuthStatus(flowId: string) {
  const qs = encodeURIComponent(flowId);
  return fetchJson<AuthFlowStatus>(`/api/settings/connections/procore/auth/status?flow_id=${qs}`);
}
export function exchangeProcoreCode(body: { code: string }) {
  return fetchJson('/api/settings/connections/procore/auth/exchange-code', { method: 'POST', body: JSON.stringify(body) });
}
export function disconnectProcoreLocal() {
  return fetchJson('/api/settings/connections/procore/disconnect-local', { method: 'POST' });
}

/* Project Connections auth-aware setup (Prompt E).
 * Uses the normalized contract family added in Prompt A:
 *   POST /api/settings/connections/projects/preview
 *   POST /api/settings/connections/projects/save   (operator)
 *   GET  /api/settings/connections/projects
 * Request shape mirrors backend ConnectionSetupRequest (url + optional connection_type/scope/project_key/include_* etc.).
 * Responses are safe metadata only. Preview/save never start sync; first_sync_status is pending_admin_approval.
 * Auth gating (Procore vs Graph required) is enforced in the UI layer using account status.
 */
export interface ProjectConnectionPreviewRequest {
  url?: string;
  connection_type?: string;
  project_key?: string;
  source_name?: string;
  scope_mode?: string;
  selected_folder_item_ids?: string[];
  include_outlook?: boolean;
  include_calendar?: boolean;
  connection_id?: string;
}

export interface ProjectConnectionPreviewResponse {
  status: 'ready_to_save' | 'unavailable' | string;
  connection_id?: string;
  detected_source_type?: string;
  proposed_source?: any;
  warnings?: string[];
  admin_approval_required?: boolean;
  first_sync_status?: string;
  guardrails?: any;
  options?: any;
  reason_code?: string;
  message?: string;
}

export interface ProjectConnectionSaveResponse {
  ok: boolean;
  kind?: string;
  connection_id?: string;
  detected_source_type?: string;
  first_sync_status?: string;
  admin_approval_required?: boolean;
  guardrails?: any;
  preview?: any;
  reason_code?: string;
}

export function previewProjectConnection(body: ProjectConnectionPreviewRequest | any) {
  return fetchJson<ProjectConnectionPreviewResponse>('/api/settings/connections/projects/preview', {
    method: 'POST',
    body: JSON.stringify(body || {}),
  });
}

export function saveProjectConnection(body: ProjectConnectionPreviewRequest | any) {
  return fetchJson<ProjectConnectionSaveResponse>('/api/settings/connections/projects/save', {
    method: 'POST',
    body: JSON.stringify(body || {}),
  });
}

export function getProjectConnections() {
  return fetchJson('/api/settings/connections/projects');
}

/* Prompt F — Admin first-sync approval (normalized under /api/settings/connections/admin/*).
 * Only admin role can approve or reject. Responses are safe (no tokens, no raw source data).
 * first_sync_triggered is always false on these responses.
 */
export interface AdminApprovalResponse {
  ok?: boolean;
  kind?: string;
  connection_id?: string;
  source_type?: string;
  first_sync_status?: string;
  first_sync_triggered?: boolean;
  guardrails?: any;
  message?: string;
  reason_code?: string; // safe error detail for not-ok cases (e.g. connection_not_found)
}

export function getAdminPendingApprovals() {
  // Admin only (backend enforces); re-uses the existing settings admin-sync surface which returns pending list
  return fetchJson('/api/settings/admin-sync');
}

export function approveFirstSyncAdmin(connectionId: string) {
  const id = encodeURIComponent(connectionId);
  return fetchJson<AdminApprovalResponse>(`/api/settings/connections/admin/${id}/approve-first-sync`, { method: 'POST' });
}

export function rejectFirstSyncAdmin(connectionId: string) {
  const id = encodeURIComponent(connectionId);
  return fetchJson<AdminApprovalResponse>(`/api/settings/connections/admin/${id}/reject-first-sync`, { method: 'POST' });
}

/* Prompt G — Data Quality readiness/freshness surfaces (normalized /api/settings/data-quality/*).
 * Summary is safe for all roles (sidebar indicator + embedded in readiness).
 * Detail is admin-only (source-by-source approval/freshness/attention, advisory notes).
 * Responses are safe: no tokens, secrets, cache paths, raw payloads, signed URLs, or raw content.
 * Statuses: good | degraded | poor | unknown (conservative; degrade when freshness cannot be proven).
 */
export interface DataQualitySummary {
  status?: string; // good | degraded | poor | unknown
  label?: string; // "Data Quality"
  last_updated_at?: string | null;
  message?: string | null;
  admin_detail_available?: boolean;
}

export interface DataQualityDetail {
  surface?: string;
  generated_utc?: string | null;
  summary?: any;
  sources?: any[];
  attention_items?: any[];
  advisory_notes?: string[];
  guardrails?: any;
}

export function getDataQualitySummary() {
  return fetchJson<DataQualitySummary>('/api/settings/data-quality/summary');
}

export function getDataQualityDetail() {
  return fetchJson<DataQualityDetail>('/api/settings/data-quality/detail');
}

/* P05 — Graph/Procore Dev UI: environment + aggregate source status, per-source Graph/Procore status +
 * safe auth bridges, source-refresh actions, and scheduler status. Typed, normalized state models.
 * Responses are safe metadata only (no tokens, secrets, cache paths, or raw payloads). Errors thrown by
 * fetchJson are normalized for the UI via getErrorCopy()/safeDisplayText() in lib/errorCopy.ts. */

export interface EnvironmentStatus {
  surface?: string;
  status?: string;
  environment?: 'dev' | 'production' | string;
  source_refresh_mode?: string;
  frontend_url?: string;
  frontend_port?: number;
  backend_port?: number;
  app_support_root?: string; // home-redacted (~)
  live_reads?: any;
  live_refresh?: { available?: boolean; enabled?: boolean; reason?: string };
  guardrails?: any;
}

export interface GraphSourceStatus {
  surface?: string;
  system?: string; // microsoft_365_graph
  state?: string; // connected_valid | reauth_required | cache_present_unverified | not_connected
  token_type?: string | null;
  classification?: string | null;
  account?: string | null;
  tenant?: string | null;
  scopes?: string[];
  expires_in_seconds_if_known?: number | null;
  scope_presence?: { expected?: string[]; missing?: string[]; all_present?: boolean };
  next_step?: string | null;
  message?: string | null;
  guardrails?: any;
}

export interface ProcoreSourceStatus {
  surface?: string;
  system?: string; // procore
  state?: string; // not_configured | configured_not_connected | connected
  auth_status?: string | null;
  ready_for_live_calls?: boolean;
  token_cache_present?: boolean;
  keychain_secret_present?: boolean;
  env_keys_present?: string[];
  env_keys_missing?: string[];
  expires_in_seconds_if_known?: number | null;
  missing_config?: boolean;
  missing_mapping?: boolean;
  mapping?: any;
  live_reads_enabled?: boolean;
  hint?: string | null;
  guardrails?: any;
}

export interface SourcesStatus {
  surface?: string;
  status?: string;
  environment?: string;
  source_refresh_mode?: string;
  live_reads?: any;
  live_refresh?: any;
  graph?: any;
  procore?: any;
  scheduler?: any;
  guardrails?: any;
}

export interface SchedulerStatus {
  surface?: string;
  status?: string;
  job_id?: string;
  environment?: string;
  enabled?: boolean;
  schedule_time_local?: string;
  timezone?: string;
  catch_up_on_wake?: boolean;
  current_local_date?: string;
  next_expected_run?: string;
  next_expected_run_from_state?: string | null;
  last_status?: string | null;
  last_successful_schedule_date?: string | null;
  last_attempted_schedule_date?: string | null;
  consecutive_failures?: number;
  live_reads_enabled?: boolean;
  state_health?: string;
  guardrails?: any;
}

export interface RefreshReceipt {
  surface?: string;
  status?: string; // ok | degraded | blocked | failed
  dry_run?: boolean;
  apply?: boolean;
  mock_data?: boolean;
  live_reads_enabled?: boolean;
  live_mode?: string; // local_only | live_source
  live_read_performed?: boolean; // present on the live (blocked) receipt
  reason?: string; // present when blocked
  sqlite_upsert_summary?: any;
  guardrails?: any;
  warnings?: string[];
  failures?: string[];
  next_operator_action?: string;
}

export type RefreshMode = 'dry_run' | 'local' | 'live';

/* Environment + aggregate source status (P01/P02). */
export function getEnvironment() {
  return fetchJson<EnvironmentStatus>('/api/environment');
}

export function getSourcesStatus() {
  return fetchJson<SourcesStatus>('/api/sources/status');
}

/* Microsoft Graph source status + safe auth bridge (P02). */
export function getGraphSourceStatus() {
  return fetchJson<GraphSourceStatus>('/api/sources/graph/status');
}

export function startGraphSourceAuth() {
  return fetchJson<GraphAuthStartResult>('/api/sources/graph/auth/start', { method: 'POST' });
}

export function getGraphSourceAuthStatus(flowId: string) {
  const qs = encodeURIComponent(flowId);
  return fetchJson<AuthFlowStatus>(`/api/sources/graph/auth/status?flow_id=${qs}`);
}

export function refreshGraphSourceAuth() {
  return fetchJson('/api/sources/graph/auth/refresh', { method: 'POST' });
}

/* Procore source status + safe OAuth bridge (P03). */
export function getProcoreSourceStatus() {
  return fetchJson<ProcoreSourceStatus>('/api/sources/procore/status');
}

export function startProcoreSourceAuth() {
  return fetchJson<ProcoreAuthStartResult>('/api/sources/procore/auth/start', { method: 'POST' });
}

export function getProcoreSourceAuthStatus(flowId: string) {
  const qs = encodeURIComponent(flowId);
  return fetchJson<AuthFlowStatus>(`/api/sources/procore/auth/status?flow_id=${qs}`);
}

export function refreshProcoreSourceAuth() {
  return fetchJson('/api/sources/procore/auth/refresh', { method: 'POST' });
}

/* Source-refresh actions (P04). Dry-run never writes the DB; local never calls live clients; live fails
 * closed unless backend env/config + explicit confirmation permit it. */
const REFRESH_ENDPOINTS: Record<RefreshMode, string> = {
  dry_run: '/api/sources/refresh/dry-run',
  local: '/api/sources/refresh/local',
  live: '/api/sources/refresh/live',
};

export function refreshSourcesDryRun() {
  return fetchJson<RefreshReceipt>(REFRESH_ENDPOINTS.dry_run, { method: 'POST' });
}

export function refreshSourcesLocal() {
  return fetchJson<RefreshReceipt>(REFRESH_ENDPOINTS.local, { method: 'POST' });
}

export function refreshSourcesLive(confirm: boolean) {
  return fetchJson<RefreshReceipt>(REFRESH_ENDPOINTS.live, {
    method: 'POST',
    body: JSON.stringify({ confirm: Boolean(confirm) }),
  });
}

/* Action URL selection — choose the refresh endpoint by mode; only `live` carries a confirmation. */
export function refreshSources(mode: RefreshMode, opts?: { confirm?: boolean }) {
  const path = REFRESH_ENDPOINTS[mode];
  if (!path) {
    throw new Error(`unknown refresh mode: ${mode}`);
  }
  const init: RequestInit = { method: 'POST' };
  if (mode === 'live') {
    init.body = JSON.stringify({ confirm: Boolean(opts?.confirm) });
  }
  return fetchJson<RefreshReceipt>(path, init);
}

/* Scheduler status for the daily source-refresh job (P04). */
export function getSchedulerStatus() {
  return fetchJson<SchedulerStatus>('/api/scheduler/daily-source-refresh/status');
}

/* Forecasting — read-only package browser (Implementation Phase 1).
 * Pure reads over deterministic forecast packages the backend has already produced.
 * Responses are advisory metadata only: the service exposes friendly labels + an opaque
 * package id, and never returns filesystem paths, run stamps, directory names, or internals.
 */
export interface ForecastProject {
  project_key: string;
  project_name?: string | null;
  job_reference?: string | null;
}

export interface ForecastPeriod {
  period: string;
  package_count?: number;
}

export interface ForecastPackage {
  package_id: string;
  package_type: string;
  display_label: string;
  status: string; // validated | attention | invalid | unsupported | unknown
  project_key?: string | null;
  period?: string | null;
  job_reference?: string | null;
  generated_display?: string | null;
  validation_total?: number;
  validation_passed?: number;
  validation_failed?: number;
  output_file_count?: number;
}

export function getForecastProjects() {
  return fetchJson('/api/forecast/projects');
}
export function getForecastPeriods(projectKey: string) {
  return fetchJson(`/api/forecast/projects/${encodeURIComponent(projectKey)}/periods`);
}
export function getForecastPackages(projectKey: string, period: string) {
  return fetchJson(
    `/api/forecast/projects/${encodeURIComponent(projectKey)}/periods/${encodeURIComponent(period)}/packages`,
  );
}
export function getForecastPackageSummary(packageId: string) {
  return fetchJson(`/api/forecast/packages/${encodeURIComponent(packageId)}/summary`);
}
export function getForecastPackageValidation(packageId: string) {
  return fetchJson(`/api/forecast/packages/${encodeURIComponent(packageId)}/validation`);
}
export function getForecastPackageManifest(packageId: string) {
  return fetchJson(`/api/forecast/packages/${encodeURIComponent(packageId)}/manifest`);
}
export function getForecastPackageReviewItems(packageId: string) {
  return fetchJson(`/api/forecast/packages/${encodeURIComponent(packageId)}/review-items`);
}
export function getForecastPackageRows(packageId: string) {
  return fetchJson(`/api/forecast/packages/${encodeURIComponent(packageId)}/forecast-rows`);
}

/* Forecast Review surfaces — read-only model forecast detail (Implementation Phase 5).
 * Monthly trend, probability/confidence bands, risk register, and top overrun risks per package. */
export function getForecastPackageMonthly(packageId: string) {
  return fetchJson(`/api/forecast/packages/${encodeURIComponent(packageId)}/monthly`);
}
export function getForecastPackageProbability(packageId: string) {
  return fetchJson(`/api/forecast/packages/${encodeURIComponent(packageId)}/probability`);
}
export function getForecastPackageRiskRegister(packageId: string) {
  return fetchJson(`/api/forecast/packages/${encodeURIComponent(packageId)}/risk-register`);
}
export function getForecastPackageTopRisks(packageId: string) {
  return fetchJson(`/api/forecast/packages/${encodeURIComponent(packageId)}/top-risks`);
}

/* Forecast configuration — read-only viewer over the v60 config snapshot (Implementation Phase 2).
 * Read-only metadata: business config settings only (no paths, run stamps, endpoints, or internals). */
export function getForecastConfigSnapshots() {
  return fetchJson('/api/forecast/config/snapshots');
}
export function getForecastConfigSnapshot(snapshotId: string) {
  return fetchJson(`/api/forecast/config/snapshots/${encodeURIComponent(snapshotId)}`);
}
export function getForecastConfigDomain(snapshotId: string, domain: string) {
  return fetchJson(
    `/api/forecast/config/snapshots/${encodeURIComponent(snapshotId)}/domains/${encodeURIComponent(domain)}`,
  );
}
export function getForecastConfigItem(snapshotId: string, itemId: string) {
  return fetchJson(
    `/api/forecast/config/snapshots/${encodeURIComponent(snapshotId)}/items/${encodeURIComponent(itemId)}`,
  );
}

/* Forecast config editing — isolated proposals (Implementation Phase E). An operator proposes edits
 * to a chosen snapshot; the backend seeds from the live snapshot (read-only), applies edits in an
 * isolated config-edit root, runs the CFR import→snapshot→materialize→parity pipeline, and returns a
 * redacted report (parity pass/fail + changed summary). No live-DB writes. POST=operator, GET=viewer. */
export interface ForecastConfigEdit {
  domain: string;
  op?: 'modify' | 'add';
  item_key: string;
  fields: Record<string, unknown>;
}
export function proposeForecastConfigEdit(payload: {
  base_snapshot_id: string;
  edits: ForecastConfigEdit[];
  project_key?: string;
}) {
  return fetchJson('/api/forecast/config/edits', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
export function getForecastConfigEdits() {
  return fetchJson('/api/forecast/config/edits');
}
export function getForecastConfigEdit(editId: string) {
  return fetchJson(`/api/forecast/config/edits/${encodeURIComponent(editId)}`);
}

/* Forecast config promotion — certified live write (Implementation Phase E2). Promotes an approved
 * (parity-passed) proposal into the live config DB as a new snapshot. Gated by a default-OFF opt-in
 * + an explicit confirm; backed up; operator/admin. Updates the recorded current config, not generation. */
export function promoteForecastConfigEdit(editId: string, confirm: boolean) {
  return fetchJson(`/api/forecast/config/edits/${encodeURIComponent(editId)}/promote`, {
    method: 'POST',
    body: JSON.stringify({ confirm }),
  });
}

/* Forecast Run Center — isolated context→analysis generation (Implementation Phase 3).
 * POST triggers a deterministic generation into an isolated work-root (operator); GET reads runs.
 * Responses are advisory metadata only (no paths, run stamps, or internals). */
export function startForecastRun() {
  return fetchJson('/api/forecast/runs', { method: 'POST' });
}
export function getForecastRuns() {
  return fetchJson('/api/forecast/runs');
}
export function getForecastRun(runId: string) {
  return fetchJson(`/api/forecast/runs/${encodeURIComponent(runId)}`);
}
/* DB-config-backed generation: a forecast package consuming the live config snapshot (operator).
 * generatorKind selects which generator (comprehensive [default] / model_controls / monthly /
 * probability); the default keeps existing callers backward-compatible. */
export type ForecastGeneratorKind = 'comprehensive' | 'model_controls' | 'monthly' | 'probability';
export function startForecastDbConfigRun(generatorKind: ForecastGeneratorKind = 'comprehensive') {
  return fetchJson('/api/forecast/runs/db-config', {
    method: 'POST',
    body: JSON.stringify({ generator_kind: generatorKind }),
  });
}
export function getForecastDbConfigRuns() {
  return fetchJson('/api/forecast/runs/db-config');
}
export function getForecastDbConfigRun(runId: string) {
  return fetchJson(`/api/forecast/runs/db-config/${encodeURIComponent(runId)}`);
}

/* External-Forecast Evaluation — upload an operator forecast, map it, and compare it against
 * actuals / budget / ERP-JTD / backend-model / prior baselines (Implementation Phase 4).
 * Upload is base64-in-JSON (no multipart). POST routes are operator-gated; results are viewer
 * reads. Responses are redacted business metadata only — no paths, run stamps, or internals. */
export function previewExternalForecast(
  filename: string,
  contentB64: string,
  sourceSystem = 'excel',
  period?: string | null,
) {
  return fetchJson('/api/forecast/external/preview', {
    method: 'POST',
    body: JSON.stringify({
      filename,
      content_b64: contentB64,
      source_system: sourceSystem,
      period: period ?? null,
    }),
  });
}
export function proposeExternalMapping(importId: string, projectKey = 'tropical') {
  return fetchJson('/api/forecast/external/mapping', {
    method: 'POST',
    body: JSON.stringify({ import_id: importId, project_key: projectKey }),
  });
}
export function evaluateExternalForecast(
  importId: string,
  columnRoles: Record<string, string>,
  projectKey = 'tropical',
) {
  return fetchJson('/api/forecast/external/evaluate', {
    method: 'POST',
    body: JSON.stringify({ import_id: importId, column_roles: columnRoles, project_key: projectKey }),
  });
}
export function getExternalEvaluations() {
  return fetchJson('/api/forecast/external/evaluations');
}
export function getExternalEvaluation(evalId: string) {
  return fetchJson(`/api/forecast/external/evaluations/${encodeURIComponent(evalId)}`);
}

/* Schedule Intelligence (V62) — import, versions, activities, cost mapping. */
export function getScheduleProjects() {
  return fetchJson('/api/schedules/projects');
}
export function listScheduleVersions(opts?: {
  projectKey?: string;
  sort?: string;
  order?: 'asc' | 'desc';
}) {
  const params = new URLSearchParams();
  if (opts?.projectKey) params.set('project_key', opts.projectKey);
  if (opts?.sort) params.set('sort', opts.sort);
  if (opts?.order) params.set('order', opts.order);
  const qs = params.toString();
  return fetchJson(`/api/schedules/versions${qs ? `?${qs}` : ''}`);
}
export function getScheduleVersions(
  projectKey: string,
  opts?: { sort?: string; order?: 'asc' | 'desc' },
) {
  const params = new URLSearchParams();
  if (opts?.sort) params.set('sort', opts.sort);
  if (opts?.order) params.set('order', opts.order);
  const qs = params.toString();
  const suffix = qs ? `?${qs}` : '';
  return fetchJson(
    `/api/schedules/projects/${encodeURIComponent(projectKey)}/versions${suffix}`,
  );
}
export function listScheduleQualityEvaluations(opts?: {
  projectKey?: string;
  sort?: string;
  order?: 'asc' | 'desc';
  includeHistory?: boolean;
}) {
  const params = new URLSearchParams();
  if (opts?.projectKey) params.set('project_key', opts.projectKey);
  if (opts?.sort) params.set('sort', opts.sort);
  if (opts?.order) params.set('order', opts.order);
  if (opts?.includeHistory) params.set('include_history', 'true');
  const qs = params.toString();
  return fetchJson(`/api/schedules/quality${qs ? `?${qs}` : ''}`);
}
export function getScheduleVersionSummary(scheduleVersionKey: string) {
  return fetchJson(`/api/schedules/versions/${encodeURIComponent(scheduleVersionKey)}/summary`);
}
export function getScheduleActivities(
  scheduleVersionKey: string,
  opts?: { limit?: number; offset?: number },
) {
  const params = new URLSearchParams();
  if (opts?.limit != null) params.set('limit', String(opts.limit));
  if (opts?.offset != null) params.set('offset', String(opts.offset));
  const qs = params.toString();
  const suffix = qs ? `?${qs}` : '';
  return fetchJson(
    `/api/schedules/versions/${encodeURIComponent(scheduleVersionKey)}/activities${suffix}`,
  );
}
export function getScheduleQuality(scheduleVersionKey: string) {
  return fetchJson(`/api/schedules/versions/${encodeURIComponent(scheduleVersionKey)}/quality`);
}
export function getScheduleQualityFindings(
  scheduleVersionKey: string,
  opts?: { evaluationRunId?: string; limit?: number; offset?: number },
) {
  const params = new URLSearchParams();
  if (opts?.evaluationRunId) params.set('evaluation_run_id', opts.evaluationRunId);
  if (opts?.limit != null) params.set('limit', String(opts.limit));
  if (opts?.offset != null) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return fetchJson(
    `/api/schedules/versions/${encodeURIComponent(scheduleVersionKey)}/quality/findings${qs ? `?${qs}` : ''}`,
  );
}
export function getScheduleQualityMetrics(scheduleVersionKey: string) {
  return fetchJson(
    `/api/schedules/versions/${encodeURIComponent(scheduleVersionKey)}/quality/metrics`,
  );
}
export function rerunScheduleQuality(scheduleVersionKey: string, profile?: string) {
  const qs = profile ? `?profile=${encodeURIComponent(profile)}` : '';
  return fetchJson(
    `/api/schedules/versions/${encodeURIComponent(scheduleVersionKey)}/quality/rerun${qs}`,
    { method: 'POST' },
  );
}
export function getScheduleQualityRun(evaluationRunId: string) {
  return fetchJson(`/api/schedules/quality/runs/${encodeURIComponent(evaluationRunId)}`);
}
export function getScheduleProjectQualitySummary(projectKey: string) {
  return fetchJson(`/api/schedules/projects/${encodeURIComponent(projectKey)}/quality/summary`);
}
export function getScheduleVersionDiff(projectKey: string, fromVersion: string, toVersion: string) {
  const params = new URLSearchParams({ from: fromVersion, to: toVersion });
  return fetchJson(
    `/api/schedules/projects/${encodeURIComponent(projectKey)}/diff?${params.toString()}`,
  );
}
export async function uploadScheduleImportPreview(
  file: File,
  projectKey: string,
  columnRoles?: Record<string, string> | null,
  confirmSupersede = false,
) {
  const form = new FormData();
  form.append('file', file);
  form.append('project_key', projectKey);
  if (columnRoles) {
    form.append('column_roles', JSON.stringify(columnRoles));
  }
  if (confirmSupersede) {
    form.append('confirm_supersede', 'true');
  }
  const role = getLocalUiRole();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/schedules/import-preview`, {
      method: 'POST',
      headers: { 'X-HB-UI-Role': role },
      body: form,
    });
  } catch (err) {
    throw new ScheduleNetworkError('schedule_upload_network_error', err);
  }
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    const schedErr = parseScheduleApiError(res.status, body);
    if (schedErr) throw schedErr;
    const detail =
      body && typeof body === 'object' && 'detail' in body
        ? String((body as { detail?: unknown }).detail ?? '')
        : '';
    const err = new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ''}`);
    (err as { status?: number }).status = res.status;
    throw err;
  }
  return res.json();
}
export function commitScheduleImport(
  importId: string,
  projectKey: string,
  columnRoles?: Record<string, string> | null,
  confirmSupersede = false,
) {
  return fetchJson('/api/schedules/import-commit', {
    method: 'POST',
    body: JSON.stringify({
      import_id: importId,
      project_key: projectKey,
      confirm: true,
      confirm_supersede: confirmSupersede,
      column_roles: columnRoles ?? null,
    }),
  });
}
export function createScheduleCostMappingRun(
  projectKey: string,
  scheduleVersionKey: string,
  operatorObjective = 'association_only',
) {
  return fetchJson('/api/schedules/cost-mapping/runs', {
    method: 'POST',
    body: JSON.stringify({
      project_key: projectKey,
      schedule_version_key: scheduleVersionKey,
      operator_objective: operatorObjective,
    }),
  });
}
export function getScheduleCostMappingRun(mappingRunId: string) {
  return fetchJson(`/api/schedules/cost-mapping/runs/${encodeURIComponent(mappingRunId)}`);
}
export function getScheduleCostWeighting(projectKey: string) {
  return fetchJson(`/api/schedules/cost-weighting/${encodeURIComponent(projectKey)}`);
}
export function getScheduleCostMappingCandidates(mappingRunId: string) {
  return fetchJson(`/api/schedules/cost-mapping/runs/${encodeURIComponent(mappingRunId)}/candidates`);
}
export function reviewScheduleCostMappingCandidate(
  candidateId: number,
  body: { operator_status: string; operator_notes?: string; candidate_cost_code?: string },
) {
  return fetchJson(`/api/schedules/cost-mapping/candidates/${candidateId}/review`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
export function approveScheduleCostMappingRun(mappingRunId: string) {
  return fetchJson(`/api/schedules/cost-mapping/runs/${encodeURIComponent(mappingRunId)}/approve`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}
export function getScheduleCostMappingDistributions(mappingRunId: string) {
  return fetchJson(
    `/api/schedules/cost-mapping/runs/${encodeURIComponent(mappingRunId)}/distribution`,
  );
}

/* Forecast runtime configuration — wires the data roots into the live app (Implementation Phase 6).
 * Status is viewer-readable and redaction-safe (booleans + coded blockers, never paths). The raw
 * configured paths are admin-only (getForecastRuntimeConfig). Saving validates + persists. */
export interface ForecastRuntimeConfigInput {
  package_roots?: string[] | null;
  data_root?: string | null;
  runs_root?: string | null;
  eval_root?: string | null;
  db_path?: string | null;
  cfr_src?: string | null;
  config_edit_root?: string | null;
}
export function getForecastRuntimeStatus() {
  return fetchJson('/api/forecast/runtime/status');
}
export function getForecastRuntimeConfig() {
  return fetchJson('/api/forecast/runtime/config');
}
export function saveForecastRuntimeConfig(payload: ForecastRuntimeConfigInput) {
  return fetchJson('/api/forecast/runtime/config', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
export function repairForecastRuntimeStorage() {
  return fetchJson('/api/forecast/runtime/repair', { method: 'POST' });
}
export function resetForecastRuntimeDefaults() {
  return fetchJson('/api/forecast/runtime/reset', {
    method: 'POST',
    body: JSON.stringify({ confirm: true }),
  });
}

/* Convenience aggregate for pages that prefer a single object. */
export const api = {
  getToday,
  getTodayChanges,
  getTodayMeetings,
  getTodayActionItems,
  getTodayPortfolioSignals,
  getTodayDailyBrief,
  getProjectsPortfolio,
  getProjectOverview,
  getProjectMeetings,
  getProjectFieldOperations,
  getProjectCostTime,
  getMyItems,
  getAdmin,
  getAdminSourceSyncHealth,
  getAdminWorkflowJobHealth,
  getAdminEvidenceGuardrails,
  getAdminRetrievalAiQuality,
  getAdminPermissionsGovernance,
  getAdminDataCompleteness,
  // Daily Brief + Settings named fns are also re-exported as methods for any legacy object-style calls.
  getDailyBriefStatus,
  configureDailyBrief,
  generateDailyBriefSetupInstructions,
  validateDailyBriefOutputFolder,
  detectDailyBriefLatest,
  getSettings,
  getSettingsAccounts,
  getSettingsProjects,
  getSettingsSources,
  getSettingsKeywords,
  getProjectKeywords,
  addProjectKeyword,
  patchProjectKeyword,
  deleteProjectKeyword,
  explainProjectKeywordMatch,
  getSettingsDailyBrief,
  getSettingsPreferences,
  getSettingsAdminSync,
  patchSettingsPreferences,
  patchSettingsAdmin,
  // Prompt D — onboarding + normalized auth flows (safe surfaces only)
  getOnboardingReadiness,
  startGraphDeviceAuth,
  getGraphAuthStatus,
  disconnectGraphLocal,
  startProcoreAuth,
  getProcoreAuthStatus,
  exchangeProcoreCode,
  disconnectProcoreLocal,
  // Prompt E — project connection preview/save/list (normalized, no-sync, admin approval explicit)
  previewProjectConnection,
  saveProjectConnection,
  getProjectConnections,
  // Prompt F — admin first-sync approve/reject (admin role only; safe responses; eligibility enforced server-side)
  getAdminPendingApprovals,
  approveFirstSyncAdmin,
  rejectFirstSyncAdmin,
  // Prompt G — data quality summary (all roles) + admin detail (safe, approval/freshness per source)
  getDataQualitySummary,
  getDataQualityDetail,
  // P05 — Graph/Procore Dev UI source status + refresh client surfaces (safe metadata only)
  getEnvironment,
  getSourcesStatus,
  getGraphSourceStatus,
  startGraphSourceAuth,
  getGraphSourceAuthStatus,
  refreshGraphSourceAuth,
  getProcoreSourceStatus,
  startProcoreSourceAuth,
  getProcoreSourceAuthStatus,
  refreshProcoreSourceAuth,
  refreshSourcesDryRun,
  refreshSourcesLocal,
  refreshSourcesLive,
  refreshSources,
  getSchedulerStatus,
  // Forecasting — read-only package browser (Implementation Phase 1). Pure metadata reads.
  getForecastProjects,
  getForecastPeriods,
  getForecastPackages,
  getForecastPackageSummary,
  getForecastPackageValidation,
  getForecastPackageManifest,
  getForecastPackageReviewItems,
  getForecastPackageRows,
  // Forecast Review surfaces (Implementation Phase 5). Read-only model forecast detail.
  getForecastPackageMonthly,
  getForecastPackageProbability,
  getForecastPackageRiskRegister,
  getForecastPackageTopRisks,
  // Forecast configuration viewer (Implementation Phase 2). Read-only metadata.
  getForecastConfigSnapshots,
  getForecastConfigSnapshot,
  getForecastConfigDomain,
  getForecastConfigItem,
  // Forecast config editing — isolated proposals (Implementation Phase E).
  proposeForecastConfigEdit,
  getForecastConfigEdits,
  getForecastConfigEdit,
  // Forecast config promotion — certified live write (Implementation Phase E2).
  promoteForecastConfigEdit,
  // Forecast Run Center (Implementation Phase 3).
  startForecastRun,
  getForecastRuns,
  getForecastRun,
  // DB-config-backed comprehensive generation (consumes the live config snapshot).
  startForecastDbConfigRun,
  getForecastDbConfigRuns,
  getForecastDbConfigRun,
  // External-Forecast Evaluation (Implementation Phase 4).
  previewExternalForecast,
  proposeExternalMapping,
  evaluateExternalForecast,
  getExternalEvaluations,
  getExternalEvaluation,
  // Schedule Intelligence (V62).
  getScheduleProjects,
  listScheduleVersions,
  listScheduleQualityEvaluations,
  getScheduleVersions,
  getScheduleVersionSummary,
  getScheduleActivities,
  getScheduleQuality,
  getScheduleQualityFindings,
  getScheduleQualityMetrics,
  rerunScheduleQuality,
  getScheduleQualityRun,
  getScheduleProjectQualitySummary,
  getScheduleVersionDiff,
  uploadScheduleImportPreview,
  commitScheduleImport,
  createScheduleCostMappingRun,
  getScheduleCostMappingRun,
  getScheduleCostMappingCandidates,
  reviewScheduleCostMappingCandidate,
  approveScheduleCostMappingRun,
  getScheduleCostMappingDistributions,
  getScheduleCostWeighting,
  // Forecast runtime configuration (Implementation Phase 6).
  getForecastRuntimeStatus,
  getForecastRuntimeConfig,
  saveForecastRuntimeConfig,
  repairForecastRuntimeStorage,
  resetForecastRuntimeDefaults,
};

export default api;