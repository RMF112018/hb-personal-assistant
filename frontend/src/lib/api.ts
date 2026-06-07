/* eslint-disable @typescript-eslint/no-explicit-any */
/* Thin, typed API client for the HB Analytics FastAPI shell (Prompt 07/08/09/10/11/14/16/20 + D + E).
 *
 * - Uses relative /api paths (Vite dev proxy in vite.config.ts forwards to backend, e.g. http://127.0.0.1:8000).
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
 * - Keep this surface thin: presentation only. Business logic lives in AnalyticsService + read models.
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

/* Settings / Connection surfaces (Prompt 14B). */
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

/* Project keywords (Prompt 20 / FPR-017): management UI over existing safe backend routes. */
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
};

export default api;