/* eslint-disable @typescript-eslint/no-explicit-any */
// Thin client + TanStack Query helpers for the Prompt 07 read-model endpoints.
// Never duplicate backend logic; only fetch and present. All responses are advisory.

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || '/api'

export type Freshness = { overall: 'fresh' | 'stale' | 'unknown'; minutes_ago_max?: number | null; sources?: string[] }
export type Confidence = { overall: 'source_backed' | 'not_available' | 'in_progress'; badges?: string[] }

export async function getToday(): Promise<any> {
  const res = await fetch(`${API_BASE}/today`)
  if (!res.ok) throw new Error(`Failed to load today: ${res.status}`)
  return res.json()
}

export async function getTodayImportant() {
  const res = await fetch(`${API_BASE}/today/important`)
  if (!res.ok) throw new Error(`Failed today/important: ${res.status}`)
  return res.json()
}

export async function getTodayChanges() {
  const res = await fetch(`${API_BASE}/today/changes`)
  if (!res.ok) throw new Error(`Failed today/changes: ${res.status}`)
  return res.json()
}

export async function getTodayMeetings() {
  const res = await fetch(`${API_BASE}/today/meetings`)
  if (!res.ok) throw new Error(`Failed today/meetings: ${res.status}`)
  return res.json()
}

export async function getTodayActionItems() {
  const res = await fetch(`${API_BASE}/today/action-items`)
  if (!res.ok) throw new Error(`Failed today/action-items: ${res.status}`)
  return res.json()
}

export async function getTodayPortfolioSignals() {
  const res = await fetch(`${API_BASE}/today/portfolio-signals`)
  if (!res.ok) throw new Error(`Failed today/portfolio-signals: ${res.status}`)
  return res.json()
}

export async function getTodayDailyBrief() {
  const res = await fetch(`${API_BASE}/today/daily-brief`)
  if (!res.ok) throw new Error(`Failed today/daily-brief: ${res.status}`)
  return res.json()
}

// Prompt 10 / UI-10 Daily Brief external workflow (wizard + detector + presenter-only)
export async function getDailyBriefStatus() {
  const res = await fetch(`${API_BASE}/daily-brief/status`)
  if (!res.ok) throw new Error(`Failed daily-brief/status: ${res.status}`)
  return res.json()
}

export async function getDailyBriefLatest() {
  const res = await fetch(`${API_BASE}/daily-brief/latest`)
  if (!res.ok) throw new Error(`Failed daily-brief/latest: ${res.status}`)
  return res.json()
}

export async function configureDailyBrief(payload: any) {
  const res = await fetch(`${API_BASE}/daily-brief/configure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) throw new Error(`Failed daily-brief/configure: ${res.status}`)
  return res.json()
}

export async function generateDailyBriefSetupInstructions(payload?: any) {
  const res = await fetch(`${API_BASE}/daily-brief/generate-setup-instructions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) throw new Error(`Failed daily-brief/generate-setup-instructions: ${res.status}`)
  return res.json()
}

export async function validateDailyBriefOutputFolder(payload: any) {
  const res = await fetch(`${API_BASE}/daily-brief/validate-output-folder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  })
  if (!res.ok) throw new Error(`Failed daily-brief/validate-output-folder: ${res.status}`)
  return res.json()
}

export async function detectDailyBriefLatest() {
  const res = await fetch(`${API_BASE}/daily-brief/detect-latest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) throw new Error(`Failed daily-brief/detect-latest: ${res.status}`)
  return res.json()
}

export async function getProjectsPortfolio() {
  const res = await fetch(`${API_BASE}/projects/portfolio`)
  if (!res.ok) throw new Error(`Failed portfolio: ${res.status}`)
  return res.json()
}

export async function getProjectOverview(projectKey: string) {
  const path = projectKey === 'all' ? '/projects/all/overview' : `/projects/${encodeURIComponent(projectKey)}/overview`
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`Failed overview: ${res.status}`)
  return res.json()
}

export async function getProjectMeetings(projectKey: string) {
  const path = projectKey === 'all' ? '/projects/all/meetings' : `/projects/${encodeURIComponent(projectKey)}/meetings`
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`Failed meetings: ${res.status}`)
  return res.json()
}

export async function getProjectFieldOperations(projectKey: string) {
  const path = projectKey === 'all' ? '/projects/all/field-operations' : `/projects/${encodeURIComponent(projectKey)}/field-operations`
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`Failed field-operations: ${res.status}`)
  return res.json()
}

export async function getProjectCostTime(projectKey: string) {
  const path = projectKey === 'all' ? '/projects/all/cost-time' : `/projects/${encodeURIComponent(projectKey)}/cost-time`
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`Failed cost-time: ${res.status}`)
  return res.json()
}

export async function getMyItems() {
  const res = await fetch(`${API_BASE}/my-items`)
  if (!res.ok) throw new Error(`Failed my-items: ${res.status}`)
  return res.json()
}

export async function getMyItemsActionItems() {
  const res = await fetch(`${API_BASE}/my-items/action-items`)
  if (!res.ok) throw new Error(`Failed my-items/action-items: ${res.status}`)
  return res.json()
}

export async function getMyItemsMeetings() {
  const res = await fetch(`${API_BASE}/my-items/meetings`)
  if (!res.ok) throw new Error(`Failed my-items/meetings: ${res.status}`)
  return res.json()
}

export async function getMyItemsCorrespondence() {
  const res = await fetch(`${API_BASE}/my-items/correspondence`)
  if (!res.ok) throw new Error(`Failed my-items/correspondence: ${res.status}`)
  return res.json()
}

export async function getMyItemsFiles() {
  const res = await fetch(`${API_BASE}/my-items/files`)
  if (!res.ok) throw new Error(`Failed my-items/files: ${res.status}`)
  return res.json()
}

export async function getMyItemsFollowedProjects() {
  const res = await fetch(`${API_BASE}/my-items/followed-projects`)
  if (!res.ok) throw new Error(`Failed my-items/followed-projects: ${res.status}`)
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
}
