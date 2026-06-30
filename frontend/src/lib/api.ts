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
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      // non-json error body; keep status only
    }
    const schedErr = parseScheduleApiError(res.status, body);
    if (schedErr) throw schedErr;
    if (body && typeof body === 'object') {
      const rec = body as { detail?: unknown; message?: unknown };
      detail = rec.detail || rec.message ? String(rec.detail || rec.message) : '';
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

/* Projects. Entry-page summaries + existing portfolio/per-project envelopes. */
export type ProjectSummary = {
  project_key: string
  procore_project_id?: string | null
  display_name?: string | null
  address?: string | null
  city?: string | null
  state_code?: string | null
  zip?: string | null
  project_number?: string | null
  status?: string | null
}

export type ProjectsListResponse = {
  surface: string
  projects: ProjectSummary[]
  guardrails?: Record<string, unknown>
}

export function getProjects(): Promise<ProjectsListResponse> {
  return fetchJson('/api/projects');
}
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
export interface ProjectScheduleSummaryResponse {
  surface?: string;
  project_key: string;
  project_display_name?: string;
  as_of_date?: string;
  status?: string;
  current_schedule?: Record<string, any>;
  previous_update?: Record<string, any>;
  readiness?: Record<string, any>;
  schedule_story?: Record<string, any>;
  command_summary?: Record<string, any>;
  recent_progress?: Record<string, any>;
  change_impact?: Record<string, any>;
  remaining_health?: Record<string, any>;
  critical_path?: Record<string, any>;
  milestones?: Record<string, any>;
  computed_cpm?: Record<string, any>;
  trend_summary?: Record<string, any>;
  actions?: { preview_limit?: number; preview?: any[]; all_items?: any[]; total_count?: number };
  technical_links?: Record<string, string>;
  technical_evidence?: Record<string, any>;
  [key: string]: any;
}
export function getProjectScheduleSummary(
  projectKey: string,
  opts?: { asOf?: string | null },
) {
  const params = new URLSearchParams();
  if (opts?.asOf) params.set('as_of', opts.asOf);
  const qs = params.toString();
  return fetchJson<ProjectScheduleSummaryResponse>(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule${qs ? `?${qs}` : ''}`,
  );
}
export type ScheduleControlsComparisonBasis =
  | 'prior_update'
  | 'current_contract_baseline'
  | 'previous_progress_update_baseline'
  | 'secondary_progress_update_baseline';
export type ReviewWorkbenchComparisonBasis = 'prior_update' | 'baseline';
export type ProjectScheduleControlsResponse = {
  available?: boolean;
  reason?: string | null;
  project_key?: string;
  schedule_version_key?: string | null;
  schedule_data_date?: string | null;
  as_of_date?: string | null;
  comparison_basis?: ScheduleControlsComparisonBasis | 'baseline';
  baseline_context?: Record<string, any>;
  advisory_posture?: string;
  summary?: Record<string, any>;
  sections?: Record<string, any>;
  top_controls?: any[];
  provenance?: Record<string, any>;
  links?: Record<string, string>;
  controls_language_qa?: Record<string, any>;
  [key: string]: any;
};
export function getProjectScheduleControls(
  projectKey: string,
  opts?: { asOf?: string | null; comparisonBasis?: ScheduleControlsComparisonBasis | 'baseline' },
) {
  const params = new URLSearchParams();
  if (opts?.asOf) params.set('as_of', opts.asOf);
  if (opts?.comparisonBasis) params.set('comparison_basis', opts.comparisonBasis);
  const qs = params.toString();
  return fetchJson<ProjectScheduleControlsResponse>(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/controls${qs ? `?${qs}` : ''}`,
  );
}
export type ProjectScheduleMetricTrendResponse = {
  available?: boolean;
  project_key?: string;
  metric_key?: string;
  display_name?: string;
  readiness_status?: string;
  as_of_date?: string;
  basis_labels?: string[];
  comparison_basis?: string[];
  weighting_basis?: string;
  caveats?: string[];
  formula_summary?: string;
  points?: any[];
  summary?: Record<string, any>;
  unavailable_variants?: any[];
  source_version_keys?: string[];
  data_quality_notes?: string[];
  reason?: string;
  [key: string]: any;
}
export type ProjectScheduleMetricTrendsResponse = {
  available?: boolean;
  project_key?: string;
  as_of_date?: string;
  metrics?: ProjectScheduleMetricTrendResponse[];
  errors?: { metric_key?: string; detail?: string }[];
  [key: string]: any;
}
export function getProjectScheduleMetricTrend(
  projectKey: string,
  metricKey: string,
  opts?: { asOf?: string; weightingBasis?: string },
) {
  const params = new URLSearchParams();
  if (opts?.asOf) params.set('as_of', opts.asOf);
  if (opts?.weightingBasis) params.set('weighting_basis', opts.weightingBasis);
  const qs = params.toString();
  return fetchJson<ProjectScheduleMetricTrendResponse>(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/metrics/${encodeURIComponent(metricKey)}/trend${qs ? `?${qs}` : ''}`,
  );
}
export function getProjectScheduleMetricTrends(
  projectKey: string,
  opts?: { asOf?: string; metrics?: string[] },
) {
  const params = new URLSearchParams();
  if (opts?.asOf) params.set('as_of', opts.asOf);
  if (opts?.metrics?.length) params.set('metrics', opts.metrics.join(','));
  const qs = params.toString();
  return fetchJson<ProjectScheduleMetricTrendsResponse>(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/metrics/trends${qs ? `?${qs}` : ''}`,
  );
}
export function getProjectScheduleDrivers(
  projectKey: string,
  drilldownType: string,
  opts?: { limit?: number; offset?: number; asOf?: string; driverActivityId?: string },
) {
  const params = new URLSearchParams({ type: drilldownType });
  if (opts?.limit != null) params.set('limit', String(opts.limit));
  if (opts?.offset != null) params.set('offset', String(opts.offset));
  if (opts?.asOf) params.set('as_of', opts.asOf);
  if (opts?.driverActivityId) params.set('driver_activity_id', opts.driverActivityId);
  return fetchJson(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/drivers?${params.toString()}`,
  );
}
export function getProjectScheduleDrilldown(
  projectKey: string,
  drilldownType: string,
  opts?: { limit?: number; offset?: number; asOf?: string },
) {
  const params = new URLSearchParams({ type: drilldownType });
  if (opts?.limit != null) params.set('limit', String(opts.limit));
  if (opts?.offset != null) params.set('offset', String(opts.offset));
  if (opts?.asOf) params.set('as_of', opts.asOf);
  return fetchJson(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/drilldowns?${params.toString()}`,
  );
}
export function getProjectScheduleBaseline(
  projectKey: string,
  opts?: { asOf?: string | null },
) {
  const params = new URLSearchParams();
  if (opts?.asOf) params.set('as_of', opts.asOf);
  const qs = params.toString();
  return fetchJson(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/baseline${qs ? `?${qs}` : ''}`,
  );
}
export function putProjectScheduleBaseline(
  projectKey: string,
  body: {
    current_schedule_version_key: string;
    selected_baseline_schedule_version_key: string;
    selection_note?: string | null;
  },
) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectKey)}/schedule/baseline`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}

export type ProjectScheduleBaselinesResponse = {
  available?: boolean;
  reason?: string;
  project_key?: string;
  as_of_date?: string | null;
  current_schedule_version_key?: string;
  current_schedule_data_date?: string | null;
  slots?: Array<Record<string, any>>;
  available_versions?: Array<Record<string, any>>;
  [key: string]: any;
};
export function getProjectScheduleBaselines(projectKey: string, opts?: { asOf?: string | null }) {
  const params = new URLSearchParams();
  if (opts?.asOf) params.set('as_of', opts.asOf);
  const qs = params.toString();
  return fetchJson<ProjectScheduleBaselinesResponse>(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/baselines${qs ? `?${qs}` : ''}`,
  );
}
export function updateProjectScheduleBaselines(
  projectKey: string,
  payload: { selections: Record<string, { schedule_version_key: string; display_name?: string; notes?: string } | null> },
  opts?: { asOf?: string | null },
) {
  const params = new URLSearchParams();
  if (opts?.asOf) params.set('as_of', opts.asOf);
  const qs = params.toString();
  return fetchJson<ProjectScheduleBaselinesResponse>(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/baselines${qs ? `?${qs}` : ''}`,
    { method: 'PUT', body: JSON.stringify(payload) },
  );
}
export function getProjectScheduleDriverDetail(
  projectKey: string,
  activityId: string,
  opts?: { comparisonBasis?: 'prior_update' | 'baseline'; asOf?: string },
) {
  const params = new URLSearchParams();
  if (opts?.comparisonBasis) params.set('comparison_basis', opts.comparisonBasis);
  if (opts?.asOf) params.set('as_of', opts.asOf);
  const qs = params.toString();
  return fetchJson(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/drivers/${encodeURIComponent(activityId)}/detail${qs ? `?${qs}` : ''}`,
  );
}
export function syncProjectScheduleReviewItems(
  projectKey: string,
  opts?: { asOf?: string; comparisonBasis?: 'prior_update' | 'baseline' },
) {
  const params = new URLSearchParams();
  if (opts?.asOf) params.set('as_of', opts.asOf);
  if (opts?.comparisonBasis) params.set('comparison_basis', opts.comparisonBasis);
  const qs = params.toString();
  return fetchJson(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/review-items${qs ? `?${qs}` : ''}`,
    {
      method: 'POST',
      body: JSON.stringify({}),
    },
  );
}
export function getProjectScheduleReviewItems(
  projectKey: string,
  opts?: {
    reviewStatus?: string;
    limit?: number;
    offset?: number;
    asOf?: string;
    comparisonBasis?: 'prior_update' | 'baseline';
    sourceMetric?: string;
    severity?: string;
    itemType?: string;
    confidence?: string;
    phase?: string;
    floor?: string;
    sectorArea?: string;
    subcontractor?: string;
    costCode?: string;
  },
) {
  const params = new URLSearchParams();
  if (opts?.reviewStatus) params.set('review_status', opts.reviewStatus);
  if (opts?.limit != null) params.set('limit', String(opts.limit));
  if (opts?.offset != null) params.set('offset', String(opts.offset));
  if (opts?.asOf) params.set('as_of', opts.asOf);
  if (opts?.comparisonBasis) params.set('comparison_basis', opts.comparisonBasis);
  if (opts?.sourceMetric) params.set('source_metric', opts.sourceMetric);
  if (opts?.severity) params.set('severity', opts.severity);
  if (opts?.itemType) params.set('item_type', opts.itemType);
  if (opts?.confidence) params.set('confidence', opts.confidence);
  if (opts?.phase) params.set('phase', opts.phase);
  if (opts?.floor) params.set('floor', opts.floor);
  if (opts?.sectorArea) params.set('sector_area', opts.sectorArea);
  if (opts?.subcontractor) params.set('subcontractor', opts.subcontractor);
  if (opts?.costCode) params.set('cost_code', opts.costCode);
  const qs = params.toString();
  return fetchJson(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/review-items${qs ? `?${qs}` : ''}`,
  );
}
export function getProjectScheduleReviewItemDetail(projectKey: string, reviewItemId: string) {
  return fetchJson(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/review-items/${encodeURIComponent(reviewItemId)}`,
  );
}
export function getProjectScheduleReviewItemEvents(
  projectKey: string,
  reviewItemId: string,
  opts?: { limit?: number; offset?: number },
) {
  const params = new URLSearchParams();
  if (opts?.limit != null) params.set('limit', String(opts.limit));
  if (opts?.offset != null) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return fetchJson(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/review-items/${encodeURIComponent(reviewItemId)}/events${qs ? `?${qs}` : ''}`,
  );
}
export function patchProjectScheduleReviewItem(
  projectKey: string,
  reviewItemId: string,
  body: { review_status?: string; pm_notes?: string | null },
) {
  return fetchJson(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/review-items/${encodeURIComponent(reviewItemId)}`,
    {
      method: 'PATCH',
      body: JSON.stringify(body),
    },
  );
}
export async function downloadProjectScheduleExport(
  projectKey: string,
  format: 'markdown' | 'html' = 'markdown',
  opts?: {
    asOf?: string;
    variant?: 'standard' | 'executive';
    scope?: 'full' | 'review_items';
    includePersistedReview?: boolean;
  },
) {
  const { downloadBlob } = await import('../components/forecast/forecastMonthlyExportWriters');
  const role = getLocalUiRole();
  const params = new URLSearchParams({ format });
  if (opts?.asOf) params.set('as_of', opts.asOf);
  if (opts?.variant) params.set('variant', opts.variant);
  if (opts?.scope) params.set('scope', opts.scope);
  if (opts?.includePersistedReview) params.set('include_persisted_review', 'true');
  const response = await fetch(
    `${API_BASE}/api/projects/${encodeURIComponent(projectKey)}/schedule/export?${params.toString()}`,
    { headers: { 'X-HB-UI-Role': role } },
  );
  if (!response.ok) {
    throw new Error(`export_failed_${response.status}`);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] || `schedule-memo-${projectKey}.${format === 'markdown' ? 'md' : 'html'}`;
  downloadBlob(blob, filename);
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

/**
 * Known Obsidian MCP config fields used by the settings UI. Index signature keeps it
 * compatible with the existing `saveConfig(patch: Record<string, unknown>)` callers while
 * documenting the typed source-intelligence generation controls.
 */
export interface ObsidianMcpConfigPatch {
  source_card_auto_generate_enabled?: boolean;
  source_summary_auto_generate_enabled?: boolean;
  source_note_auto_refresh_enabled?: boolean;
  source_summary_auto_max_per_drain?: number;
  source_card_auto_max_per_drain?: number;
  source_index_excluded_path_parts?: string[];
  source_index_deferred_path_parts?: string[];
  source_index_unsupported_file_types?: string[];
  source_index_metadata_only_file_types?: string[];
  source_value_high_priority_path_signals?: string[];
  source_value_normal_priority_path_signals?: string[];
  source_card_auto_metadata_only_enabled?: boolean;
  [key: string]: unknown;
}

export function getObsidianMcpConfig() {
  return fetchJson('/api/settings/obsidian-mcp/config');
}
export function patchObsidianMcpConfig(patch: ObsidianMcpConfigPatch) {
  return fetchJson('/api/settings/obsidian-mcp/config', { method: 'PATCH', body: JSON.stringify(patch) });
}
export function getObsidianMcpStatus() {
  return fetchJson('/api/settings/obsidian-mcp/status');
}
export function runObsidianMcpHealthCheck() {
  return fetchJson('/api/settings/obsidian-mcp/health-check', { method: 'POST' });
}
export function getObsidianMcpTools() {
  return fetchJson('/api/settings/obsidian-mcp/tools');
}
export function getObsidianMcpMutations(limit = 20) {
  return fetchJson(`/api/settings/obsidian-mcp/mutations?limit=${encodeURIComponent(String(limit))}`);
}
export function getObsidianMcpReadReceipts(limit = 20) {
  return fetchJson(`/api/settings/obsidian-mcp/read-receipts?limit=${encodeURIComponent(String(limit))}`);
}
export function runObsidianMcpWriteReadiness() {
  return fetchJson('/api/settings/obsidian-mcp/write-readiness', { method: 'POST' });
}
export function enableObsidianMcp() {
  return fetchJson('/api/settings/obsidian-mcp/enable', { method: 'POST' });
}
export function disableObsidianMcp() {
  return fetchJson('/api/settings/obsidian-mcp/disable', { method: 'POST' });
}
export function restartObsidianMcp() {
  return fetchJson('/api/settings/obsidian-mcp/restart', { method: 'POST' });
}
export function testObsidianMcpListDirectory(body: any) {
  return fetchJson('/api/settings/obsidian-mcp/test/list-directory', { method: 'POST', body: JSON.stringify(body || {}) });
}
export function testObsidianMcpSearch(body: any) {
  return fetchJson('/api/settings/obsidian-mcp/test/search', { method: 'POST', body: JSON.stringify(body || {}) });
}
export function testObsidianMcpReadFile(body: any) {
  return fetchJson('/api/settings/obsidian-mcp/test/read-file', { method: 'POST', body: JSON.stringify(body || {}) });
}
export function testObsidianMcpWriteSmoke() {
  return fetchJson('/api/settings/obsidian-mcp/test/write-smoke', { method: 'POST' });
}
export function getObsidianMcpGrokConfig() {
  return fetchJson('/api/settings/obsidian-mcp/grok-config');
}
export function getObsidianMcpOAuth() {
  return fetchJson('/api/settings/obsidian-mcp/oauth');
}
export function getObsidianMcpLlmChatStatus() {
  return fetchJson('/api/settings/obsidian-mcp/llm-chat/status');
}
export function getObsidianMcpChatGPT() {
  return fetchJson('/api/settings/obsidian-mcp/chatgpt');
}
export function runObsidianMcpChatGPTReadiness() {
  return fetchJson('/api/settings/obsidian-mcp/chatgpt/readiness-check', { method: 'POST' });
}

/* Source Intelligence (PR A1): external-source index, watcher lifecycle, and model panel. */
export function getObsidianMcpSourceIndexStatus() {
  return fetchJson('/api/settings/obsidian-mcp/source-index/status');
}
export function rebuildObsidianMcpSourceIndex() {
  return fetchJson('/api/settings/obsidian-mcp/source-index/rebuild', { method: 'POST' });
}
export function generateObsidianMcpSourceCard(body: any) {
  return fetchJson('/api/settings/obsidian-mcp/source-card/generate', { method: 'POST', body: JSON.stringify(body || {}) });
}
export function summarizeObsidianMcpSource(body: any) {
  return fetchJson('/api/settings/obsidian-mcp/source-card/summarize', { method: 'POST', body: JSON.stringify(body || {}) });
}
export function refreshObsidianMcpStaleSourceNotes(body: any) {
  return fetchJson('/api/settings/obsidian-mcp/source-notes/refresh-stale', { method: 'POST', body: JSON.stringify(body || {}) });
}
export function testObsidianMcpModel() {
  return fetchJson('/api/settings/obsidian-mcp/model/test', { method: 'POST' });
}
export function getObsidianMcpSourceWatchStatus() {
  return fetchJson('/api/settings/obsidian-mcp/source-watch/status');
}
export function startObsidianMcpSourceWatch() {
  return fetchJson('/api/settings/obsidian-mcp/source-watch/start', { method: 'POST' });
}
export function stopObsidianMcpSourceWatch() {
  return fetchJson('/api/settings/obsidian-mcp/source-watch/stop', { method: 'POST' });
}
export function restartObsidianMcpSourceWatch() {
  return fetchJson('/api/settings/obsidian-mcp/source-watch/restart', { method: 'POST' });
}
export function testObsidianMcpSourceWatchEvent() {
  return fetchJson('/api/settings/obsidian-mcp/source-watch/test-event', { method: 'POST' });
}
export function recoverObsidianMcpSourceWatchStuck() {
  return fetchJson('/api/settings/obsidian-mcp/source-watch/recover-stuck', { method: 'POST' });
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

/* Forecast DB read-model — persisted v63 run-output + v66 decision-support (Phase 4/5).
 * Read-only, redaction-safe (navigates by hash-based output_id; never the run_id/paths). Renders
 * gracefully empty until an operator runs the authorized live-write. */
export interface ForecastDbProject {
  project_key: string;
  output_count: number;
  latest_display: string | null;
}
export interface ForecastDbOutputSummary {
  output_id: string;
  project_key: string;
  estimated_final_cost: string | null;
  cost_to_complete: string | null;
  variance_to_budget: string | null;
  variance_to_prior_forecast: string | null;
  created_display: string | null;
}
export interface ForecastDbBudgetCode {
  budget_code_key: string | null;
  cost_code: string | null;
  category: string | null;
  forecast_action: string | null;
  recommended_projected_cost: string | null;
  recommended_cost_to_complete: string | null;
  confidence: string | null;
}
export interface ForecastDbCommitmentExposure {
  budget_code_key: string | null;
  committed_amount: string | null;
  exposure_amount: string | null;
}
export interface ForecastDbSchedulePhasing {
  budget_code_key: string | null;
  phase: string | null;
  start_month: string | null;
  end_month: string | null;
  amount: string | null;
}
/* Consolidated, typed Forecast Summary KPI object for the active output. Read-model-only bridge
 * (whitelist over the v63 header envelope; the envelope itself is never surfaced). Money fields are
 * canonical strings preserving missing(null)-vs-zero("0.00"); *_status fields carry explicit
 * provenance ("reconciled" / "reconciliation_mismatch" / "budget_unavailable" / "no_prior_forecast"
 * / "computed"). Confidence/maturity come from the HB readiness ladder, not the v66 scorecard. */
export interface ForecastDbForecastSummary {
  estimated_at_completion: string | null;
  total_cost_to_date: string | null;
  cost_to_complete: string | null;
  current_budget: string | null;
  budget_basis_label: string | null;
  budget_status: string | null;
  variance_to_budget: string | null;
  variance_to_budget_status: string | null;
  variance_to_prior_forecast: string | null;
  variance_to_prior_forecast_status: string | null;
  forecast_confidence_label: string | null;
  forecast_confidence_basis: string | null;
  forecast_maturity_label: string | null;
  forecast_maturity_basis: string | null;
  basis_limitations: string[];
}
export interface ForecastDbOutputDetail extends ForecastDbOutputSummary {
  forecast_at_completion: string | null;
  variance_to_prior_forecast: string | null;
  summary: ForecastDbForecastSummary | null;
  budget_codes: ForecastDbBudgetCode[];
  risks: Record<string, unknown>[];
  monthly: Record<string, unknown>[];
  probability: Record<string, unknown>[];
  changes: Record<string, unknown>[];
  staffing: Record<string, unknown>[];
  commitment_exposure: ForecastDbCommitmentExposure[];
  schedule_phasing: ForecastDbSchedulePhasing[];
}
export interface ForecastDbConfidenceFactor {
  factor_key: string;
  direction: string | null;
  magnitude: string | null;
  reason: string | null;
}
export interface ForecastDbScorecard {
  scope: string;
  scope_key: string | null;
  score: string | null;
  label: string | null;
  factors: ForecastDbConfidenceFactor[];
}
export interface ForecastDbAvailability {
  domain: string;
  availability: string | null;
  coverage: string | null;
  freshness: string | null;
  reason: string | null;
}
export interface ForecastDbMethodEligibility {
  method: string;
  status: string | null;
  weight: string | null;
  reason: string | null;
}
export interface ForecastDbMaturity {
  maturity_tier: string | null;
  completed_month_count: number | null;
  nonzero_month_count: number | null;
  lifecycle_signal: string | null;
  basis: string | null;
}
export interface ForecastDbDecisionSupport {
  output_id: string;
  maturity: ForecastDbMaturity | null;
  data_availability: ForecastDbAvailability[];
  confidence_scorecards: ForecastDbScorecard[];
  method_eligibility: ForecastDbMethodEligibility[];
  model_selection: Record<string, unknown>[];
}

// P9: per-scope explainability / audit narratives (curated, redaction-safe) for one output.
export interface ForecastNarrativeProject {
  narrative_key: string | null;
  estimated_final_cost: string | null;
  forecast_at_completion: string | null;
  cost_to_complete: string | null;
  variance_to_budget: string | null;
  budget_code_count: number | null;
  risk_count: number | null;
  override_count: number | null;
  warning_count: number | null;
  narrative: string | null;
}
export interface ForecastNarrativeBudgetCode {
  narrative_key: string | null;
  budget_code_key: string | null;
  recommended_projected_cost: string | null;
  recommended_cost_to_complete: string | null;
  forecast_action: string | null;
  confidence: string | null;
  risk_count: number | null;
  overridden: boolean | null;
  narrative: string | null;
}
export interface ForecastNarrativeOverride {
  narrative_key: string | null;
  budget_code_key: string | null;
  assumption_type: string | null;
  column: string | null;
  original: string | null;
  override: string | null;
  delta_amount: string | null;
  source: string | null;
  applied_display: string | null;
  narrative: string | null;
}
export interface ForecastNarrativeSourceQa {
  narrative_key: string | null;
  budget_code_count: number | null;
  null_projected_cost_count: number | null;
  zero_projected_cost_count: number | null;
  duplicate_budget_code_keys: string[] | null;
  narrative: string | null;
}
export interface ForecastNarrativeLineage {
  narrative_key: string | null;
  context_sha256: string | null;
  analysis_sha256: string | null;
  output_sha256: string | null;
  methodology_sha256: string | null;
  narrative: string | null;
}
export interface ForecastDbNarratives {
  output_id: string;
  narratives: {
    project?: ForecastNarrativeProject[];
    budget_code?: ForecastNarrativeBudgetCode[];
    human_override?: ForecastNarrativeOverride[];
    source_qa?: ForecastNarrativeSourceQa[];
    lineage?: ForecastNarrativeLineage[];
  };
}

export function getForecastDbProjects() {
  return fetchJson<{ projects: ForecastDbProject[] }>('/api/forecast/db/projects');
}

/* Generation-ready project projection (Phase P-B). Discovers projects from procore identity +
 * committed schedule imports + forecast outputs; exposes per-project availability + readiness
 * (ready/degraded/blocked, coded reasons). Read-only, redaction-safe (no paths/source payloads). */
export type ForecastProjectReadinessStatus = 'ready' | 'degraded' | 'blocked';
export type ForecastProjectMaturity =
  | 'no_financial_basis'
  | 'baseline_only'
  | 'cost_informed'
  | 'schedule_informed'
  | 'full_context';
export interface ForecastGenerationProject {
  project_key: string;
  display_name: string | null;
  project_number: string | null;
  procore_project_id: string | null;
  has_schedule_data: boolean;
  has_activity_data: boolean;
  latest_schedule_version_key: string | null;
  latest_schedule_date: string | null;
  has_prior_forecast_output: boolean;
  latest_forecast_status: string | null;
  latest_forecast_display: string | null;
  has_budget_cost_data: boolean;
  config_snapshot_available: boolean;
  readiness_status: ForecastProjectReadinessStatus;
  readiness_reasons: string[];
  // Phase P-2 best-effort maturity metadata (optional; emitted by the backend readiness API).
  forecast_maturity?: ForecastProjectMaturity;
  confidence_level?: 'none' | 'low' | 'medium' | 'high';
  forecast_basis?: string;
  basis_limitations?: string[];
  initial_forecast?: boolean;
  prior_forecast_available?: boolean;
  schedule_available?: boolean;
  actual_cost_available?: boolean;
  commitment_available?: boolean;
}
export interface ForecastGenerationProjectsResponse {
  surface: string;
  generation_enabled: boolean;
  projects: ForecastGenerationProject[];
  guardrails: Record<string, boolean | string>;
}
export function getForecastGenerationProjects() {
  return fetchJson<ForecastGenerationProjectsResponse>('/api/forecast/generation/projects');
}

/* Recent generation requests (Phase P-C). Read-only, redaction-safe coded fields only. */
export interface ForecastGenerationRequest {
  request_id: string;
  run_id: string | null;
  project_key: string;
  generation_mode: string;
  generator_kind: string | null;
  request_status: string;
  validation_status: string;
  forecast_start_date: string | null;
  forecast_cutoff_date: string | null;
  forecast_cutoff_date_basis: string | null;
  readiness_status_at_request: string | null;
  readiness_reasons: string[];
  failure_code: string | null;
  failure_message: string | null;
  created_utc: string | null;
  updated_utc: string | null;
}
export interface ForecastGenerationRequestsResponse {
  surface: string;
  requests: ForecastGenerationRequest[];
  guardrails: Record<string, boolean>;
}
export function getForecastGenerationRequests(projectKey?: string) {
  const qs = projectKey ? `?project_key=${encodeURIComponent(projectKey)}` : '';
  return fetchJson<ForecastGenerationRequestsResponse>(`/api/forecast/generation/requests${qs}`);
}

/* Schedule-derived forecast date defaults (Phase P-D). Read-only, redaction-safe, advisory. */
export interface ForecastGenerationDateDefaults {
  project_key: string;
  forecast_start_date: string | null;
  forecast_start_date_basis: string | null;
  forecast_cutoff_date: string | null;
  forecast_cutoff_date_basis: string | null;
  schedule_version_key: string | null;
  schedule_data_date: string | null;
  schedule_data_date_basis: string | null;
  schedule_source_status: 'available' | 'degraded' | 'missing';
  // Operator month-window defaults (YYYY-MM). forecast_end_month is null when no reliable schedule
  // finish is resolvable — the UI then requires operator confirmation (no arbitrary horizon).
  actuals_start_month: string | null;
  actuals_through_month: string | null;
  forecast_start_month: string | null;
  forecast_end_month: string | null;
  forecast_end_month_basis: string | null;
  warnings: string[];
}
export function getForecastGenerationDateDefaults(projectKey: string) {
  return fetchJson<ForecastGenerationDateDefaults>(
    `/api/forecast/generation/date-defaults?project_key=${encodeURIComponent(projectKey)}`,
  );
}
export function getForecastDbOutputs(projectKey = 'tropical') {
  return fetchJson<{ outputs: ForecastDbOutputSummary[] }>(
    `/api/forecast/db/projects/${encodeURIComponent(projectKey)}/outputs`,
  );
}
export function getForecastDbNarratives(outputId: string) {
  return fetchJson<ForecastDbNarratives>(
    `/api/forecast/db/outputs/${encodeURIComponent(outputId)}/narratives`,
  );
}
export function getForecastDbOutput(outputId: string) {
  return fetchJson<ForecastDbOutputDetail>(
    `/api/forecast/db/outputs/${encodeURIComponent(outputId)}`,
  );
}
export function getForecastDbDecisionSupport(outputId: string) {
  return fetchJson<ForecastDbDecisionSupport>(
    `/api/forecast/db/outputs/${encodeURIComponent(outputId)}/decision-support`,
  );
}

/* Operator assumptions capture (first interactive forecast write surface). Operator-entered
 * assumptions persist directly into the v66 managed-DB tables. GET=viewer, POST/PATCH=operator
 * (role header auto-injected by fetchJson). Read paths never surface raw_json/run_id. */
export interface ForecastOperatorAssumption {
  assumption_id: string;
  project_key: string;
  assumption_type: string;
  budget_code_key: string | null;
  value: string | null;
  unit: string | null;
  source: string | null;
  operator: string | null;
  confidence_impact: string | null;
  is_required: boolean;
  reused_from_prior: boolean;
  overridden: boolean;
  created_display: string | null;
  updated_display: string | null;
}
export interface ForecastRequiredAssumption {
  id: string;
  project_key: string;
  assumption_type: string;
  reason: string | null;
  satisfied: boolean;
  created_display: string | null;
  updated_display: string | null;
}
export function getForecastOperatorAssumptions(projectKey = 'tropical') {
  return fetchJson<{ assumptions: ForecastOperatorAssumption[] }>(
    `/api/forecast/db/projects/${encodeURIComponent(projectKey)}/operator-assumptions`,
  );
}
export function createForecastOperatorAssumption(
  projectKey: string,
  body: Record<string, unknown>,
) {
  return fetchJson(
    `/api/forecast/db/projects/${encodeURIComponent(projectKey)}/operator-assumptions`,
    { method: 'POST', body: JSON.stringify(body) },
  );
}
export function editForecastOperatorAssumption(
  assumptionId: string,
  patch: Record<string, unknown>,
) {
  return fetchJson(`/api/forecast/db/operator-assumptions/${encodeURIComponent(assumptionId)}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}
export function getForecastRequiredAssumptions(projectKey = 'tropical') {
  return fetchJson<{ required: ForecastRequiredAssumption[] }>(
    `/api/forecast/db/projects/${encodeURIComponent(projectKey)}/required-assumptions`,
  );
}
export function createForecastRequiredAssumption(
  projectKey: string,
  body: Record<string, unknown>,
) {
  return fetchJson(
    `/api/forecast/db/projects/${encodeURIComponent(projectKey)}/required-assumptions`,
    { method: 'POST', body: JSON.stringify(body) },
  );
}
export function setForecastRequiredAssumptionSatisfied(requiredId: string, satisfied: boolean) {
  return fetchJson(`/api/forecast/db/required-assumptions/${encodeURIComponent(requiredId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ satisfied }),
  });
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

/* Forecast config — global staffing templates (Phase 5). */
export function getForecastStaffingTemplates() {
  return fetchJson<{ templates: Record<string, unknown>[] }>(
    '/api/forecast/config/staffing-templates',
  );
}
export function createForecastStaffingTemplate(body: Record<string, unknown>) {
  return fetchJson('/api/forecast/config/staffing-templates', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
export function getForecastStaffingTemplate(templateId: string) {
  return fetchJson<{
    template?: Record<string, unknown>
    versions?: Record<string, unknown>[]
    current_version?: Record<string, unknown> | null
    ok?: boolean
  }>(`/api/forecast/config/staffing-templates/${encodeURIComponent(templateId)}`);
}
export function addForecastStaffingTemplateVersion(
  templateId: string,
  body: Record<string, unknown>,
) {
  return fetchJson(
    `/api/forecast/config/staffing-templates/${encodeURIComponent(templateId)}/versions`,
    { method: 'POST', body: JSON.stringify(body) },
  );
}
export function deleteForecastStaffingTemplate(templateId: string) {
  return fetchJson(`/api/forecast/config/staffing-templates/${encodeURIComponent(templateId)}`, {
    method: 'DELETE',
  });
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
/* Generation request contract (Phase P-C). Every Generate Forecast attempt carries the selected
 * project and optional operator-supplied forecast start / cut-off dates; the UI never sends an empty
 * body and never hardcodes a project. Dates are ISO YYYY-MM-DD; schedule-derived cut-off is P-D. */
export interface ForecastGenerationRequestInput {
  project_key: string;
  forecast_start_date?: string | null;
  forecast_cutoff_date?: string | null;
  // P-D: the cut-off basis (operator_supplied or a schedule-derived code); re-verified server-side.
  forecast_cutoff_date_basis?: string | null;
  // Operator month windows (YYYY-MM) — the source of truth for the monthly matrix.
  actuals_start_month?: string | null;
  actuals_through_month?: string | null;
  forecast_start_month?: string | null;
  forecast_end_month?: string | null;
}
export interface ForecastDbConfigGenerationRequestInput extends ForecastGenerationRequestInput {
  generator_kind: ForecastGeneratorKind;
}
function _generationBody(input: ForecastGenerationRequestInput): Record<string, string> {
  const body: Record<string, string> = { project_key: input.project_key };
  if (input.forecast_start_date) body.forecast_start_date = input.forecast_start_date;
  if (input.forecast_cutoff_date) body.forecast_cutoff_date = input.forecast_cutoff_date;
  if (input.forecast_cutoff_date_basis) body.forecast_cutoff_date_basis = input.forecast_cutoff_date_basis;
  if (input.actuals_start_month) body.actuals_start_month = input.actuals_start_month;
  if (input.actuals_through_month) body.actuals_through_month = input.actuals_through_month;
  if (input.forecast_start_month) body.forecast_start_month = input.forecast_start_month;
  if (input.forecast_end_month) body.forecast_end_month = input.forecast_end_month;
  return body;
}
export function startForecastRun(input: ForecastGenerationRequestInput) {
  return fetchJson('/api/forecast/runs', {
    method: 'POST',
    body: JSON.stringify(_generationBody(input)),
  });
}
export function getForecastRuns() {
  return fetchJson('/api/forecast/runs');
}
export function getForecastRun(runId: string) {
  return fetchJson(`/api/forecast/runs/${encodeURIComponent(runId)}`);
}
/* DB-config-backed generation: a forecast package consuming the live config snapshot (operator).
 * generator_kind selects which generator (comprehensive / model_controls / monthly / probability). */
export type ForecastGeneratorKind = 'comprehensive' | 'model_controls' | 'monthly' | 'probability';
export function startForecastDbConfigRun(input: ForecastDbConfigGenerationRequestInput) {
  return fetchJson('/api/forecast/runs/db-config', {
    method: 'POST',
    body: JSON.stringify({ ..._generationBody(input), generator_kind: input.generator_kind }),
  });
}
export function getForecastDbConfigRuns() {
  return fetchJson('/api/forecast/runs/db-config');
}
/* DB-config-backed generation readiness (viewer-readable, redaction-safe). Lets the UI disable the
 * Generate control BEFORE click and explain why, instead of surfacing a raw 503 after the POST.
 * Returns coded fields only — never a path. The frontend maps each action code to a UI route. */
export interface ReadinessAction {
  code: string;
  label: string;
}
export interface ForecastGenerationReadiness {
  generation_enabled: boolean;
  ready: boolean;
  disabled_reasons: string[];
  warnings: string[];
  actions: ReadinessAction[];
  guardrails: Record<string, boolean>;
}
export function getForecastGenerationReadiness() {
  return fetchJson<ForecastGenerationReadiness>('/api/forecast/generation/readiness');
}
export function getForecastDbConfigRun(runId: string) {
  return fetchJson(`/api/forecast/runs/db-config/${encodeURIComponent(runId)}`);
}

/* True DB-native generation (Phase F+): reads the app DB, computes in memory, and persists v63
 * forecast outputs when the run-output DB-write gate is enabled. No source/context/analysis package.
 * This is the primary operator Generate path; the legacy db-config/file-config routes are package-backed.
 * A request fails closed with HTTP 200 + request_status="failed"/"rejected" and a curated failure_code
 * (e.g. run_output_db_write_disabled, db_native_insufficient_basis). Success is request_status=
 * "completed" with db_persisted=true. The primary path is restricted to the comprehensive kind. */
export interface ForecastDbNativeGenerationResponse {
  request_id: string;
  project_key: string;
  generation_mode: string;
  generator_kind: string | null;
  request_status: string;
  validation_status: string;
  forecast_start_date: string | null;
  forecast_cutoff_date: string | null;
  forecast_cutoff_date_basis: string | null;
  source_snapshot_id: string | null;
  db_persisted: boolean;
  package_generated: boolean;
  persisted_output_ids: string[];
  failure_code: string | null;
  failure_message: string | null;
  readiness_status_at_request: string | null;
  readiness_reasons: string[];
}
export function startForecastDbNativeRun(input: ForecastGenerationRequestInput) {
  return fetchJson<ForecastDbNativeGenerationResponse>('/api/forecast/runs/db-native', {
    method: 'POST',
    body: JSON.stringify({ ..._generationBody(input), generator_kind: 'comprehensive' }),
  });
}

/* Table-ready operator month-window matrix for a persisted output. The backend returns the displayed
 * month columns (each tagged actual/forecast), one row per budget code with a DENSE month_values map
 * (missing cells are backend-certified "0.00" — the UI never infers zeros), and the persisted total
 * row. Outputs that predate operator month windows return status "legacy_output_no_operator_window".
 * All values are authoritative (backend-calculated); the UI only formats / sorts / filters / groups. */
export interface ForecastDbMonthlyTableMonth {
  month: string;
  label: string;
  value_type: 'actual' | 'forecast';
}
export interface ForecastDbMonthlyTableRow {
  budget_code_key: string;
  budget_code: string | null;
  cost_code: string | null;
  cost_type: string | null;
  // Cost Category derived (read-time) from the cost_code prefix; always present (else "Other").
  cost_category: string;
  projected_budget: string;
  projected_budget_source: string | null;
  projected_budget_source_warning: string | null;
  month_values: Record<string, string>;
  completed_to_date: string;
  forecast_to_complete: string;
  estimated_at_completion: string;
  variance_to_budget: string;
  confidence: string | null;
  method_code: string | null;
  reason_codes: string[];
}
export interface ForecastDbMonthlyTableTotalRow {
  projected_budget: string;
  month_values: Record<string, string>;
  completed_to_date: string;
  forecast_to_complete: string;
  estimated_at_completion: string;
  variance_to_budget: string;
}
export interface ForecastDbMonthlyTable {
  surface: string;
  output_id: string;
  project_key: string;
  status: 'ready' | 'legacy_output_no_operator_window';
  actuals_start_month?: string;
  actuals_through_month?: string;
  forecast_start_month?: string;
  forecast_end_month?: string;
  month_window_basis?: string | null;
  month_window_warnings?: string[];
  months?: ForecastDbMonthlyTableMonth[];
  rows?: ForecastDbMonthlyTableRow[];
  total_row?: ForecastDbMonthlyTableTotalRow | null;
  guardrails?: Record<string, boolean>;
}
export function getForecastDbMonthlyTable(outputId: string) {
  return fetchJson<ForecastDbMonthlyTable>(
    `/api/forecast/db/outputs/${encodeURIComponent(outputId)}/monthly-table`,
  );
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
export type ScheduleCapabilityStatus =
  | 'available'
  | 'partially_available'
  | 'unavailable'
  | 'not_applicable'
  | 'requires_companion_file'
  | 'requires_user_mapping'
  | 'conflict_detected'
  | 'deferred'
  | string;

export interface ScheduleSourceCapability {
  capability_id?: string;
  capability_key?: string;
  capability_status?: ScheduleCapabilityStatus;
  basis?: string | null;
  source_format?: string | null;
  unavailable_reason?: string | null;
  recommended_action?: string | null;
  evidence_json?: string | Record<string, unknown> | null;
  [key: string]: unknown;
}

// Phase 9A.1: additive, read-only Application-computed CPM evidence carried on /health-data.
// Every field is application_computed_cpm (never source-export). null = not computed / unavailable.
export interface ComputedCpmHealthRunStatus {
  available: boolean;
  status?: string | null;
  analysis_scope?: string | null;
}

export interface ComputedCpmHealthCounts {
  computed_activity_count?: number | null;
  computed_critical_activity_count?: number | null;
  computed_near_critical_activity_count?: number | null;
  computed_noncritical_activity_count?: number | null;
  longest_path_member_count?: number | null;
  critical_float_threshold_days?: number | null;
  near_critical_float_threshold_days?: number | null;
  negative_total_float_count?: number | null;
  zero_total_float_count?: number | null;
  high_total_float_count?: number | null;
  classified_total_float_count?: number | null;
  high_total_float_threshold_days?: number | null;
}

export interface ComputedCpmHealthLongestPath {
  available: boolean;
  reason?: string | null;
  path_id?: string | null;
  path_type?: string | null;
  activity_count?: number | null;
  relationship_count?: number | null;
  path_duration?: number | null;
  path_total_float?: number | null;
  start_activity_id?: string | null;
  end_activity_id?: string | null;
}

export interface ComputedCpmHealthDcmaMetric {
  available: boolean;
  measurable?: boolean;
  basis?: string | null;
  source_critical_flags_used?: boolean;
  reason_codes?: string[];
  caveats?: string[];
  path_id?: string | null;
  path_activity_count?: number | null;
  computed_critical_activity_count?: number | null;
  longest_path_critical_activity_count?: number | null;
  dependency_run_ids?: unknown;
}

export interface ComputedCpmHealthDiagnostics {
  available: boolean;
  total_count?: number | null;
  by_severity?: Record<string, number>;
  by_calculation_type?: Record<string, number>;
}

export interface ComputedCpmHealth {
  available: boolean;
  reason?: string | null;
  evidence_class: 'application_computed_cpm';
  source_export_evidence: 'separate';
  run_chain?: Record<string, ComputedCpmHealthRunStatus>;
  counts?: ComputedCpmHealthCounts;
  longest_path_summary?: ComputedCpmHealthLongestPath;
  dcma_critical_path_metric?: ComputedCpmHealthDcmaMetric;
  diagnostics_summary?: ComputedCpmHealthDiagnostics;
  missing_dependency_reasons?: string[];
  links?: { computed_cpm?: string };
}

export interface ScheduleHealthData {
  schedule_version_key?: string;
  project_key?: string | null;
  current_schedule?: Record<string, unknown> | null;
  import_package?: Record<string, unknown> | null;
  capabilities?: ScheduleSourceCapability[] | null;
  quality_summary?: Record<string, unknown> | null;
  default_prior_version?: Record<string, unknown> | null;
  default_version_diff?: Record<string, unknown>[] | null;
  available_version_diffs?: Record<string, unknown>[] | null;
  schedule_identity?: Record<string, unknown> | null;
  identity_match?: Record<string, unknown> | null;
  comparison_basis?: Record<string, unknown> | null;
  baseline_projects?: Record<string, unknown>[] | null;
  baseline_health_facts?: Record<string, unknown>[] | null;
  top_health_findings?: Record<string, unknown>[] | null;
  deferred_domains?: Record<string, unknown> | null;
  computed_cpm_health?: ComputedCpmHealth | null;
  [key: string]: unknown;
}

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
export function getScheduleHealthData(scheduleVersionKey: string, projectKey?: string) {
  const params = new URLSearchParams();
  if (projectKey) params.set('project_key', projectKey);
  const qs = params.toString();
  return fetchJson<ScheduleHealthData>(
    `/api/schedules/versions/${encodeURIComponent(scheduleVersionKey)}/health-data${qs ? `?${qs}` : ''}`,
  );
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

// --- Phase 8: read-only computed CPM surfacing ---------------------------------------
export interface ScheduleCpmRunEntry {
  available: boolean;
  cpm_run_id?: string;
  calculation_type?: string;
  cpm_recalculation_status?: string;
  analysis_scope?: string;
  source_run_id?: string | null;
  created_at?: string;
  diagnostic_count?: number;
  computed_activity_count?: number;
  [key: string]: unknown;
}
export interface ScheduleCpmDcmaEvidence {
  available: boolean;
  measurable?: boolean;
  basis?: string | null;
  dependency_run_ids?: Record<string, string | null>;
  path_id?: string | null;
  path_activity_count?: number;
  computed_critical_activity_count?: number;
  longest_path_critical_activity_count?: number;
  reason_codes?: string[];
  caveats?: string[];
  source_critical_flags_used?: boolean;
  [key: string]: unknown;
}
export interface ScheduleCpmSummary {
  schedule_version_key: string;
  available: boolean;
  runs: Record<string, ScheduleCpmRunEntry>;
  dcma_critical_path: ScheduleCpmDcmaEvidence;
  missing_dependency_reasons: string[];
  evidence_class?: string;
  source_export_evidence?: string;
  [key: string]: unknown;
}
export interface ScheduleCpmActivity {
  activity_id?: string;
  activity_name?: string | null;
  topological_index?: number | null;
  computed_early_start?: string | null;
  computed_early_finish?: string | null;
  computed_late_start?: string | null;
  computed_late_finish?: string | null;
  computed_total_float?: number | null;
  computed_free_float?: number | null;
  computed_criticality_class?: string | null;
  computed_critical_flag?: number | null;
  computed_near_critical_flag?: number | null;
  longest_path_member_flag?: number | null;
  longest_path_sequence?: number | null;
  [key: string]: unknown;
}
export interface ScheduleCpmActivitiesResponse {
  schedule_version_key: string;
  available: boolean;
  source_run?: { cpm_run_id?: string; calculation_type?: string } | null;
  activities: ScheduleCpmActivity[];
  total_count: number;
  limit: number;
  offset: number;
  truncated: boolean;
  reason?: string;
  [key: string]: unknown;
}
export interface ScheduleCpmLongestPath {
  schedule_version_key: string;
  available: boolean;
  reason?: string;
  path?: Record<string, unknown> | null;
  activities: ScheduleCpmActivity[];
  [key: string]: unknown;
}
export interface ScheduleCpmDiagnostics {
  schedule_version_key: string;
  available: boolean;
  diagnostics: Array<Record<string, unknown>>;
  total_count: number;
  [key: string]: unknown;
}
export function getScheduleCpmSummary(scheduleVersionKey: string) {
  return fetchJson<ScheduleCpmSummary>(
    `/api/schedules/versions/${encodeURIComponent(scheduleVersionKey)}/cpm/summary`,
  );
}
export function getScheduleCpmActivities(
  scheduleVersionKey: string,
  opts?: { limit?: number; offset?: number },
) {
  const params = new URLSearchParams();
  if (opts?.limit != null) params.set('limit', String(opts.limit));
  if (opts?.offset != null) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return fetchJson<ScheduleCpmActivitiesResponse>(
    `/api/schedules/versions/${encodeURIComponent(scheduleVersionKey)}/cpm/activities${qs ? `?${qs}` : ''}`,
  );
}
export function getScheduleCpmLongestPath(scheduleVersionKey: string) {
  return fetchJson<ScheduleCpmLongestPath>(
    `/api/schedules/versions/${encodeURIComponent(scheduleVersionKey)}/cpm/longest-path`,
  );
}
export function getScheduleCpmDiagnostics(scheduleVersionKey: string) {
  return fetchJson<ScheduleCpmDiagnostics>(
    `/api/schedules/versions/${encodeURIComponent(scheduleVersionKey)}/cpm/diagnostics`,
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
export function getScheduleDiffSummary(projectKey: string, diffId: string | number) {
  return fetchJson(
    `/api/schedules/projects/${encodeURIComponent(projectKey)}/diffs/${encodeURIComponent(String(diffId))}/summary`,
  );
}
export function getScheduleDiffDetails(
  projectKey: string,
  diffId: string | number,
  opts?: {
    changeDomain?: string;
    changeType?: string;
    severity?: string;
    requiresAttention?: boolean;
    wbsCode?: string;
    activityId?: string;
    limit?: number;
    offset?: number;
  },
) {
  const params = new URLSearchParams();
  if (opts?.changeDomain) params.set('change_domain', opts.changeDomain);
  if (opts?.changeType) params.set('change_type', opts.changeType);
  if (opts?.severity) params.set('severity', opts.severity);
  if (opts?.requiresAttention != null) params.set('requires_attention', String(opts.requiresAttention));
  if (opts?.wbsCode) params.set('wbs_code', opts.wbsCode);
  if (opts?.activityId) params.set('activity_id', opts.activityId);
  if (opts?.limit != null) params.set('limit', String(opts.limit));
  if (opts?.offset != null) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return fetchJson(
    `/api/schedules/projects/${encodeURIComponent(projectKey)}/diffs/${encodeURIComponent(String(diffId))}/details${qs ? `?${qs}` : ''}`,
  );
}
export function getScheduleDiffImpact(
  projectKey: string,
  diffId: string | number,
  opts?: {
    rollupType?: string;
    impactLevel?: string;
    requiresAttention?: boolean;
    wbsCode?: string;
    activityId?: string;
    limit?: number;
    offset?: number;
  },
) {
  const params = new URLSearchParams();
  if (opts?.rollupType) params.set('rollup_type', opts.rollupType);
  if (opts?.impactLevel) params.set('impact_level', opts.impactLevel);
  if (opts?.requiresAttention != null) params.set('requires_attention', String(opts.requiresAttention));
  if (opts?.wbsCode) params.set('wbs_code', opts.wbsCode);
  if (opts?.activityId) params.set('activity_id', opts.activityId);
  if (opts?.limit != null) params.set('limit', String(opts.limit));
  if (opts?.offset != null) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return fetchJson(
    `/api/schedules/projects/${encodeURIComponent(projectKey)}/diffs/${encodeURIComponent(String(diffId))}/impact${qs ? `?${qs}` : ''}`,
  );
}
export function getScheduleIdentities(projectKey: string, opts?: { showMerged?: boolean }) {
  const params = new URLSearchParams();
  if (opts?.showMerged) params.set('show_merged', 'true');
  const qs = params.toString();
  return fetchJson(
    `/api/schedules/projects/${encodeURIComponent(projectKey)}/identities${qs ? `?${qs}` : ''}`,
  );
}
export function getScheduleIdentity(projectKey: string, scheduleIdentityKey: string, opts?: { showMerged?: boolean }) {
  const params = new URLSearchParams();
  if (opts?.showMerged === false) params.set('show_merged', 'false');
  const qs = params.toString();
  return fetchJson(
    `/api/schedules/projects/${encodeURIComponent(projectKey)}/identities/${encodeURIComponent(scheduleIdentityKey)}${qs ? `?${qs}` : ''}`,
  );
}
export function getScheduleIdentityReview(projectKey: string) {
  return fetchJson(`/api/schedules/projects/${encodeURIComponent(projectKey)}/identity-review`);
}
export function setScheduleSeriesMembership(
  projectKey: string,
  scheduleVersionKey: string,
  membershipStatus: 'accepted' | 'excluded' | 'pending',
  reason?: string,
) {
  return fetchJson(
    `/api/schedules/projects/${encodeURIComponent(projectKey)}/versions/${encodeURIComponent(scheduleVersionKey)}/series-membership`,
    {
      method: 'POST',
      body: JSON.stringify({ membership_status: membershipStatus, reason: reason || null }),
    },
  );
}
export function reassignScheduleIdentity(
  projectKey: string,
  scheduleVersionKey: string,
  targetIdentityKey: string,
  reason?: string,
) {
  return fetchJson(
    `/api/schedules/projects/${encodeURIComponent(projectKey)}/versions/${encodeURIComponent(scheduleVersionKey)}/identity`,
    { method: 'POST', body: JSON.stringify({ target_identity_key: targetIdentityKey, reason: reason || null }) },
  );
}
export function splitScheduleIdentity(
  projectKey: string,
  scheduleVersionKey: string,
  canonicalScheduleName?: string,
  reason?: string,
) {
  return fetchJson(
    `/api/schedules/projects/${encodeURIComponent(projectKey)}/versions/${encodeURIComponent(scheduleVersionKey)}/identity/split`,
    {
      method: 'POST',
      body: JSON.stringify({
        canonical_schedule_name: canonicalScheduleName || null,
        reason: reason || null,
      }),
    },
  );
}
export function mergeScheduleIdentities(
  projectKey: string,
  sourceIdentityKey: string,
  targetIdentityKey: string,
  reason?: string,
) {
  return fetchJson(
    `/api/schedules/projects/${encodeURIComponent(projectKey)}/identities/${encodeURIComponent(sourceIdentityKey)}/merge`,
    { method: 'POST', body: JSON.stringify({ target_identity_key: targetIdentityKey, reason: reason || null }) },
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
    let body: unknown;
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

export async function uploadProjectScheduleImportPreview(
  projectKey: string,
  file: File,
  columnRoles?: Record<string, string> | null,
  confirmSupersede = false,
) {
  const form = new FormData();
  form.append('file', file);
  if (columnRoles) {
    form.append('column_roles', JSON.stringify(columnRoles));
  }
  if (confirmSupersede) {
    form.append('confirm_supersede', 'true');
  }
  const role = getLocalUiRole();
  let res: Response;
  try {
    res = await fetch(
      `${API_BASE}/api/projects/${encodeURIComponent(projectKey)}/schedule/import-preview`,
      {
        method: 'POST',
        headers: { 'X-HB-UI-Role': role },
        body: form,
      },
    );
  } catch (err) {
    throw new ScheduleNetworkError('schedule_upload_network_error', err);
  }
  if (!res.ok) {
    let body: unknown;
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

export function commitProjectScheduleImport(
  projectKey: string,
  importId: string,
  columnRoles?: Record<string, string> | null,
  confirmSupersede = false,
) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectKey)}/schedule/import-commit`, {
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

export function getProjectScheduleImportStatus(projectKey: string, importId: string) {
  return fetchJson(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/imports/${encodeURIComponent(importId)}/status`,
  );
}

export function retryProjectScheduleImportCpm(projectKey: string, importId: string) {
  return fetchJson(
    `/api/projects/${encodeURIComponent(projectKey)}/schedule/imports/${encodeURIComponent(importId)}/recompute-cpm`,
    { method: 'POST', body: JSON.stringify({}) },
  );
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

/* ---- Project Staffing (Phase 4) ------------------------------------------------ */

export interface StaffingConfigRow {
  staffing_config_id: string;
  project_key: string;
  template_id: string | null;
  role_title: string | null;
  person_name: string | null;
  employment_type: string | null;
  cost_code: string | null;
  cost_code_description: string | null;
  rate_unit: string | null;
  lab_rate: string | null;
  lbn_rate: string | null;
  mat_rate: string | null;
  start_date: string | null;
  finish_date: string | null;
  active_status: string;
  override_fields_json: string[];
  validation_status: string;
  validation_errors_json: { field: string; code: string; message: string }[];
  updated_utc: string | null;
}

function staffingPath(projectKey: string, suffix: string): string {
  return `/api/projects/${encodeURIComponent(projectKey)}/staffing/${suffix}`;
}

export function getProjectStaffingConfig(projectKey: string) {
  return fetchJson<{ rows: StaffingConfigRow[] }>(staffingPath(projectKey, 'config'));
}
export function createProjectStaffingConfig(projectKey: string, body: Record<string, unknown>) {
  return fetchJson(staffingPath(projectKey, 'config'), {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
export function updateProjectStaffingConfig(
  projectKey: string,
  configId: string,
  patch: Record<string, unknown>,
) {
  return fetchJson(staffingPath(projectKey, `config/${encodeURIComponent(configId)}`), {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}
export function deleteProjectStaffingConfig(projectKey: string, configId: string) {
  return fetchJson(staffingPath(projectKey, `config/${encodeURIComponent(configId)}`), {
    method: 'DELETE',
  });
}
export function getProjectStaffingAssumptions(projectKey: string) {
  return fetchJson<{ assumptions: Record<string, unknown> }>(
    staffingPath(projectKey, 'assumptions'),
  );
}
export function updateProjectStaffingAssumptions(projectKey: string, patch: Record<string, unknown>) {
  return fetchJson(staffingPath(projectKey, 'assumptions'), {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}
export function getProjectStaffingAbsences(projectKey: string) {
  return fetchJson<{ rows: Record<string, unknown>[] }>(
    staffingPath(projectKey, 'absence-overrides'),
  );
}
export function createProjectStaffingAbsence(projectKey: string, body: Record<string, unknown>) {
  return fetchJson(staffingPath(projectKey, 'absence-overrides'), {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
export function deleteProjectStaffingAbsence(projectKey: string, absenceId: string) {
  return fetchJson(staffingPath(projectKey, `absence-overrides/${encodeURIComponent(absenceId)}`), {
    method: 'DELETE',
  });
}
export function getProjectStaffingReadiness(projectKey: string) {
  return fetchJson<{
    readiness_status: string;
    readiness_reasons: string[];
    active_row_count: number;
    unmatched_review_count: number;
  }>(staffingPath(projectKey, 'readiness'));
}
export function getProjectStaffingUnmatched(projectKey: string) {
  return fetchJson<{ review_items: Record<string, unknown>[] }>(
    staffingPath(projectKey, 'unmatched-actuals'),
  );
}
export function resolveProjectStaffingReview(
  projectKey: string,
  reviewItemId: string,
  body: Record<string, unknown>,
) {
  return fetchJson(
    staffingPath(projectKey, `attribution-review/${encodeURIComponent(reviewItemId)}/resolve`),
    { method: 'POST', body: JSON.stringify(body) },
  );
}
export function getProjectStaffingMatSummary(projectKey: string) {
  return fetchJson<{ materials: Record<string, unknown>[] }>(
    staffingPath(projectKey, 'mat-summary'),
  );
}
export function rebuildProjectStaffingProjection(projectKey: string) {
  return fetchJson(staffingPath(projectKey, 'actuals/rebuild-projection'), {
    method: 'POST',
    body: JSON.stringify({}),
  });
}
export function getForecastHolidayCalendars() {
  return fetchJson<{ calendars: Record<string, unknown>[] }>(
    '/api/forecast/config/holiday-calendars',
  );
}

/* Convenience aggregate for pages that prefer a single object. */
export const api = {
  getProjectStaffingConfig,
  createProjectStaffingConfig,
  updateProjectStaffingConfig,
  deleteProjectStaffingConfig,
  getProjectStaffingAssumptions,
  updateProjectStaffingAssumptions,
  getProjectStaffingAbsences,
  createProjectStaffingAbsence,
  deleteProjectStaffingAbsence,
  getProjectStaffingReadiness,
  getProjectStaffingUnmatched,
  resolveProjectStaffingReview,
  getProjectStaffingMatSummary,
  rebuildProjectStaffingProjection,
  getForecastHolidayCalendars,
  getForecastStaffingTemplates,
  createForecastStaffingTemplate,
  getForecastStaffingTemplate,
  addForecastStaffingTemplateVersion,
  deleteForecastStaffingTemplate,
  getToday,
  getTodayChanges,
  getTodayMeetings,
  getTodayActionItems,
  getTodayPortfolioSignals,
  getTodayDailyBrief,
  getProjects,
  getProjectsPortfolio,
  getProjectOverview,
  getProjectMeetings,
  getProjectFieldOperations,
  getProjectCostTime,
  getProjectScheduleSummary,
  getProjectScheduleControls,
  getProjectScheduleMetricTrend,
  getProjectScheduleMetricTrends,
  getProjectScheduleDrilldown,
  getProjectScheduleDrivers,
  getProjectScheduleBaseline,
  putProjectScheduleBaseline,
  getProjectScheduleBaselines,
  updateProjectScheduleBaselines,
  getProjectScheduleDriverDetail,
  syncProjectScheduleReviewItems,
  getProjectScheduleReviewItems,
  getProjectScheduleReviewItemDetail,
  getProjectScheduleReviewItemEvents,
  patchProjectScheduleReviewItem,
  downloadProjectScheduleExport,
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
  getObsidianMcpConfig,
  patchObsidianMcpConfig,
  getObsidianMcpStatus,
  runObsidianMcpHealthCheck,
  getObsidianMcpTools,
  getObsidianMcpMutations,
  getObsidianMcpReadReceipts,
  runObsidianMcpWriteReadiness,
  enableObsidianMcp,
  disableObsidianMcp,
  restartObsidianMcp,
  testObsidianMcpListDirectory,
  testObsidianMcpSearch,
  testObsidianMcpReadFile,
  testObsidianMcpWriteSmoke,
  getObsidianMcpGrokConfig,
  getObsidianMcpLlmChatStatus,
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
  getForecastDbProjects,
  getForecastGenerationProjects,
  getForecastGenerationRequests,
  getForecastGenerationDateDefaults,
  getForecastDbOutputs,
  getForecastDbOutput,
  getForecastDbMonthlyTable,
  getForecastDbDecisionSupport,
  getForecastDbNarratives,
  getForecastOperatorAssumptions,
  createForecastOperatorAssumption,
  editForecastOperatorAssumption,
  getForecastRequiredAssumptions,
  createForecastRequiredAssumption,
  setForecastRequiredAssumptionSatisfied,
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
  // True DB-native generation (primary operator path; persists v63 outputs).
  startForecastDbNativeRun,
  // DB-config-backed comprehensive generation (legacy package-backed; consumes the live config snapshot).
  startForecastDbConfigRun,
  getForecastDbConfigRuns,
  getForecastGenerationReadiness,
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
  getScheduleHealthData,
  getScheduleActivities,
  getScheduleQuality,
  getScheduleQualityFindings,
  getScheduleQualityMetrics,
  getScheduleCpmSummary,
  getScheduleCpmActivities,
  getScheduleCpmLongestPath,
  getScheduleCpmDiagnostics,
  rerunScheduleQuality,
  getScheduleQualityRun,
  getScheduleProjectQualitySummary,
  getScheduleVersionDiff,
  getScheduleDiffSummary,
  getScheduleDiffDetails,
  getScheduleDiffImpact,
  getScheduleIdentities,
  getScheduleIdentity,
  getScheduleIdentityReview,
  setScheduleSeriesMembership,
  reassignScheduleIdentity,
  splitScheduleIdentity,
  mergeScheduleIdentities,
  uploadScheduleImportPreview,
  commitScheduleImport,
  uploadProjectScheduleImportPreview,
  commitProjectScheduleImport,
  getProjectScheduleImportStatus,
  retryProjectScheduleImportCpm,
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
