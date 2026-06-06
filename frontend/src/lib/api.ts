/* eslint-disable @typescript-eslint/no-explicit-any */
// Thin client + TanStack Query helpers for the Prompt 07 read-model endpoints.
// Never duplicate backend logic; only fetch and present. All responses are advisory.

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || '/api'
const VALID_UI_ROLES = ['viewer', 'operator', 'admin'] as const
export type LocalUiRole = (typeof VALID_UI_ROLES)[number]

function normalizeRole(value: string | null | undefined): LocalUiRole {
  const role = (value || '').trim().toLowerCase()
  return VALID_UI_ROLES.includes(role as LocalUiRole) ? (role as LocalUiRole) : 'operator'
}

export function getLocalUiRole(): LocalUiRole {
  const envRole = normalizeRole(import.meta.env.VITE_HB_UI_ROLE as string | undefined)
  if (typeof window === 'undefined') return envRole || 'operator'
  return normalizeRole(window.localStorage.getItem('hb-ui-role') || envRole)
}

export function setLocalUiRole(role: LocalUiRole) {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem('hb-ui-role', normalizeRole(role))
  }
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  headers.set('X-HB-UI-Role', getLocalUiRole())
  return fetch(input, { ...init, headers })
}

export type Freshness = { overall: 'fresh' | 'stale' | 'unknown'; minutes_ago_max?: number | null; sources?: string[] }
export type Confidence = { overall: 'source_backed' | 'not_available' | 'in_progress'; badges?: string[] }

export async function getToday(): Promise<any> {
  const res = await apiFetch(`${API_BASE}/today`)
  if (!res.ok) throw new Error(`Failed to load today: ${res.status}`)
  return res.json()
}

export async function getTodayImportant() {
  const res = await apiFetch(`${API_BASE}/today/important`)
  if (!res.ok) throw new Error(`Failed today/important: ${res.status}`)
  return res.json()
}

export async function getTodayChanges() {
  const res = await apiFetch(`${API_BASE}/today/changes`)
  if (!res.ok) throw new Error(`Failed today/changes: ${res.status}`)
  return res.json()
}

export async function getTodayMeetings() {
  const res = await apiFetch(`${API_BASE}/today/meetings`)
  if (!res.ok) throw new Error(`Failed today/meetings: ${res.status}`)
  return res.json()
}

export async function getTodayActionItems() {
  const res = await apiFetch(`${API_BASE}/today/action-items`)
  if (!res.ok) throw new Error(`Failed today/action-items: ${res.status}`)
  return res.json()
}

export async function getTodayPortfolioSignals() {
  const res = await apiFetch(`${API_BASE}/today/portfolio-signals`)
  if (!res.ok) throw new Error(`Failed today/portfolio-signals: ${res.status}`)
  return res.json()
}

export async function getTodayDailyBrief() {
  const res = await apiFetch(`${API_BASE}/today/daily-brief`)
  if (!res.ok) throw new Error(`Failed today/daily-brief: ${res.status}`)
  return res.json()
}

// Prompt 10 / UI-10 Daily Brief external workflow (wizard + detector + presenter-only)
export async function getDailyBriefStatus() {
  const res = await apiFetch(`${API_BASE}/daily-brief/status`)
  if (!res.ok) throw new Error(`Failed daily-brief/status: ${res.status}`)
  return res.json()
}

export async function getDailyBriefLatest() {
  const res = await apiFetch(`${API_BASE}/daily-brief/latest`)
  if (!res.ok) throw new Error(`Failed daily-brief/latest: ${res.status}`)
  return res.json()
}

export async function configureDailyBrief(payload: any) {
  const res = await apiFetch(`${API_BASE}/daily-brief/configure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) throw new Error(`Failed daily-brief/configure: ${res.status}`)
  return res.json()
}

export async function generateDailyBriefSetupInstructions(payload?: any) {
  const res = await apiFetch(`${API_BASE}/daily-brief/generate-setup-instructions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) throw new Error(`Failed daily-brief/generate-setup-instructions: ${res.status}`)
  return res.json()
}

export async function validateDailyBriefOutputFolder(payload: any) {
  const res = await apiFetch(`${API_BASE}/daily-brief/validate-output-folder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) throw new Error(`Failed daily-brief/validate-output-folder: ${res.status}`)
  return res.json()
}

export async function detectDailyBriefLatest() {
  const res = await apiFetch(`${API_BASE}/daily-brief/detect-latest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) throw new Error(`Failed daily-brief/detect-latest: ${res.status}`)
  return res.json()
}

export async function getProjectsPortfolio() {
  const res = await apiFetch(`${API_BASE}/projects/portfolio`)
  if (!res.ok) throw new Error(`Failed portfolio: ${res.status}`)
  return res.json()
}

export async function getProjectOverview(projectKey: string) {
  const path = projectKey === 'all' ? '/projects/all/overview' : `/projects/${encodeURIComponent(projectKey)}/overview`
  const res = await apiFetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`Failed overview: ${res.status}`)
  return res.json()
}

export async function getProjectMeetings(projectKey: string) {
  const path = projectKey === 'all' ? '/projects/all/meetings' : `/projects/${encodeURIComponent(projectKey)}/meetings`
  const res = await apiFetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`Failed meetings: ${res.status}`)
  return res.json()
}

export async function getProjectFieldOperations(projectKey: string) {
  const path = projectKey === 'all' ? '/projects/all/field-operations' : `/projects/${encodeURIComponent(projectKey)}/field-operations`
  const res = await apiFetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`Failed field-operations: ${res.status}`)
  return res.json()
}

export async function getProjectCostTime(projectKey: string) {
  const path = projectKey === 'all' ? '/projects/all/cost-time' : `/projects/${encodeURIComponent(projectKey)}/cost-time`
  const res = await apiFetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`Failed cost-time: ${res.status}`)
  return res.json()
}

export async function getMyItems() {
  const res = await apiFetch(`${API_BASE}/my-items`)
  if (!res.ok) throw new Error(`Failed my-items: ${res.status}`)
  return res.json()
}

export async function getMyItemsActionItems() {
  const res = await apiFetch(`${API_BASE}/my-items/action-items`)
  if (!res.ok) throw new Error(`Failed my-items/action-items: ${res.status}`)
  return res.json()
}

export async function getMyItemsMeetings() {
  const res = await apiFetch(`${API_BASE}/my-items/meetings`)
  if (!res.ok) throw new Error(`Failed my-items/meetings: ${res.status}`)
  return res.json()
}

export async function getMyItemsCorrespondence() {
  const res = await apiFetch(`${API_BASE}/my-items/correspondence`)
  if (!res.ok) throw new Error(`Failed my-items/correspondence: ${res.status}`)
  return res.json()
}

export async function getMyItemsFiles() {
  const res = await apiFetch(`${API_BASE}/my-items/files`)
  if (!res.ok) throw new Error(`Failed my-items/files: ${res.status}`)
  return res.json()
}

export async function getMyItemsFollowedProjects() {
  const res = await apiFetch(`${API_BASE}/my-items/followed-projects`)
  if (!res.ok) throw new Error(`Failed my-items/followed-projects: ${res.status}`)
  return res.json()
}

// Prompt 11 / UI-11 Admin / Data Confidence (detailed support surfaces)
export async function getAdmin() {
  const res = await apiFetch(`${API_BASE}/admin`)
  if (!res.ok) throw new Error(`Failed admin: ${res.status}`)
  return res.json()
}

export async function getAdminSourceSyncHealth() {
  const res = await apiFetch(`${API_BASE}/admin/source-sync-health`)
  if (!res.ok) throw new Error(`Failed admin/source-sync-health: ${res.status}`)
  return res.json()
}

export async function getAdminWorkflowJobHealth() {
  const res = await apiFetch(`${API_BASE}/admin/workflow-job-health`)
  if (!res.ok) throw new Error(`Failed admin/workflow-job-health: ${res.status}`)
  return res.json()
}

export async function getAdminEvidenceGuardrails() {
  const res = await apiFetch(`${API_BASE}/admin/evidence-guardrails`)
  if (!res.ok) throw new Error(`Failed admin/evidence-guardrails: ${res.status}`)
  return res.json()
}

export async function getAdminRetrievalAiQuality() {
  const res = await apiFetch(`${API_BASE}/admin/retrieval-ai-quality`)
  if (!res.ok) throw new Error(`Failed admin/retrieval-ai-quality: ${res.status}`)
  return res.json()
}

export async function getAdminPermissionsGovernance() {
  const res = await apiFetch(`${API_BASE}/admin/permissions-governance`)
  if (!res.ok) throw new Error(`Failed admin/permissions-governance: ${res.status}`)
  return res.json()
}

export async function getAdminDataCompleteness() {
  const res = await apiFetch(`${API_BASE}/admin/data-completeness`)
  if (!res.ok) throw new Error(`Failed admin/data-completeness: ${res.status}`)
  return res.json()
}

// Prompt 14B / UI-14B Settings / Connection Management UX (accounts, projects, sources, keywords, daily-brief, preferences, admin-sync)
export async function getSettings() {
  const res = await apiFetch(`${API_BASE}/settings`)
  if (!res.ok) throw new Error(`Failed settings: ${res.status}`)
  return res.json()
}

export async function getSettingsAccounts() {
  const res = await apiFetch(`${API_BASE}/settings/accounts`)
  if (!res.ok) throw new Error(`Failed settings/accounts: ${res.status}`)
  return res.json()
}

export async function getSettingsProjects() {
  const res = await apiFetch(`${API_BASE}/settings/projects`)
  if (!res.ok) throw new Error(`Failed settings/projects: ${res.status}`)
  return res.json()
}

export async function getSettingsSources() {
  const res = await apiFetch(`${API_BASE}/settings/sources`)
  if (!res.ok) throw new Error(`Failed settings/sources: ${res.status}`)
  return res.json()
}

export async function getSettingsKeywords() {
  const res = await apiFetch(`${API_BASE}/settings/keywords`)
  if (!res.ok) throw new Error(`Failed settings/keywords: ${res.status}`)
  return res.json()
}

export async function getSettingsDailyBrief() {
  const res = await apiFetch(`${API_BASE}/settings/daily-brief`)
  if (!res.ok) throw new Error(`Failed settings/daily-brief: ${res.status}`)
  return res.json()
}

export async function getSettingsPreferences() {
  const res = await apiFetch(`${API_BASE}/settings/preferences`)
  if (!res.ok) throw new Error(`Failed settings/preferences: ${res.status}`)
  return res.json()
}

export async function getSettingsAdminSync() {
  const res = await apiFetch(`${API_BASE}/settings/admin-sync`)
  if (!res.ok) throw new Error(`Failed settings/admin-sync: ${res.status}`)
  return res.json()
}

export async function patchSettingsPreferences(payload: any) {
  const res = await apiFetch(`${API_BASE}/settings/preferences`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) throw new Error(`Failed settings/preferences patch: ${res.status}`)
  return res.json()
}

export async function patchSettingsAdmin(payload: any) {
  const res = await apiFetch(`${API_BASE}/settings/admin`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) throw new Error(`Failed settings/admin patch: ${res.status}`)
  return res.json()
}

// For UI-08/09 the pages progressively move from local illustrative data to useQuery + these fns.
// All responses are advisory; never duplicate backend logic.
export const api = {
  getToday,
  getTodayImportant,
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
  getMyItemsActionItems,
  getMyItemsMeetings,
  getMyItemsCorrespondence,
  getMyItemsFiles,
  getMyItemsFollowedProjects,
  // Prompt 10 Daily Brief wizard + detector surfaces
  getDailyBriefStatus,
  getDailyBriefLatest,
  configureDailyBrief,
  generateDailyBriefSetupInstructions,
  validateDailyBriefOutputFolder,
  detectDailyBriefLatest,
  // Prompt 11 / UI-11 Admin / Data Confidence detailed surfaces
  getAdmin,
  getAdminSourceSyncHealth,
  getAdminWorkflowJobHealth,
  getAdminEvidenceGuardrails,
  getAdminRetrievalAiQuality,
  getAdminPermissionsGovernance,
  getAdminDataCompleteness,
  // Prompt 14B Settings / Connection Management UX
  getSettings,
  getSettingsAccounts,
  getSettingsProjects,
  getSettingsSources,
  getSettingsKeywords,
  getSettingsDailyBrief,
  getSettingsPreferences,
  getSettingsAdminSync,
  patchSettingsPreferences,
  patchSettingsAdmin,
}
