import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SettingsPage } from './SettingsPage'

const refetchAccounts = vi.fn()
const refetchDataQuality = vi.fn()
const getProjectConnections = vi.fn()
const getDailyBriefStatus = vi.fn()
const generateDailyBriefSetupInstructions = vi.fn()
const configureDailyBrief = vi.fn()
const detectDailyBriefLatest = vi.fn()
const patchSettingsPreferences = vi.fn()
const getProjectKeywords = vi.fn()
const addProjectKeyword = vi.fn()
const explainProjectKeywordMatch = vi.fn()
const getAdminPendingApprovals = vi.fn()
const getDataQualityDetail = vi.fn()

vi.mock('../app/providers', () => ({
  useTheme: () => ({ theme: 'dark', setTheme: vi.fn() }),
}))

vi.mock('../hooks/useOnboardingReadiness', () => ({
  useConnectionsAccounts: () => ({
    data: {
      graph: { status: 'connected_valid', account: 'operator@example.com' },
      procore: { status: 'connected_valid' },
    },
    refetch: refetchAccounts,
    isFetching: false,
  }),
}))

vi.mock('../hooks/useDataQualitySummary', () => ({
  useDataQualitySummary: () => ({
    data: { status: 'good', message: 'Approved sources are current.', admin_detail_available: true },
    error: null,
    refetch: refetchDataQuality,
    isFetching: false,
  }),
}))

vi.mock('../lib/api', () => ({
  getProjectConnections: () => getProjectConnections(),
  getDailyBriefStatus: () => getDailyBriefStatus(),
  generateDailyBriefSetupInstructions: (body: unknown) => generateDailyBriefSetupInstructions(body),
  configureDailyBrief: (patch: unknown) => configureDailyBrief(patch),
  detectDailyBriefLatest: () => detectDailyBriefLatest(),
  patchSettingsPreferences: (patch: unknown) => patchSettingsPreferences(patch),
  getProjectKeywords: (project: string) => getProjectKeywords(project),
  addProjectKeyword: (project: string, term: string, strength: number) => addProjectKeyword(project, term, strength),
  explainProjectKeywordMatch: (project: string, term: string) => explainProjectKeywordMatch(project, term),
  getAdminPendingApprovals: () => getAdminPendingApprovals(),
  getDataQualityDetail: () => getDataQualityDetail(),
  startGraphDeviceAuth: vi.fn(),
  getGraphAuthStatus: vi.fn(),
  disconnectGraphLocal: vi.fn(),
  startProcoreAuth: vi.fn(),
  getProcoreAuthStatus: vi.fn(),
  exchangeProcoreCode: vi.fn(),
  disconnectProcoreLocal: vi.fn(),
  previewProjectConnection: vi.fn(),
  saveProjectConnection: vi.fn(),
  approveFirstSyncAdmin: vi.fn(),
  rejectFirstSyncAdmin: vi.fn(),
}))

function renderSettings() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>,
  )
}

describe('SettingsPage guided setup', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getProjectConnections.mockResolvedValue({ items: [] })
    getDailyBriefStatus.mockResolvedValue({
      state: 'configured_waiting',
      config: { enabled: true, show_on_today: true, output_folder: '', file_pattern: 'HB-Daily-Brief-*.md' },
    })
    generateDailyBriefSetupInstructions.mockResolvedValue({
      scheduled_prompt: 'hidden scheduled task text',
      mcp_setup_note: 'hidden advanced setup note',
    })
    configureDailyBrief.mockResolvedValue({
      state: 'configured_waiting',
      config: { enabled: true, show_on_today: true, output_folder: '', file_pattern: 'HB-Daily-Brief-*.md' },
    })
    detectDailyBriefLatest.mockResolvedValue({ state: 'brief_available' })
    patchSettingsPreferences.mockResolvedValue({ ok: true })
    getProjectKeywords.mockResolvedValue({ keywords: [{ title: 'foundation review' }] })
    addProjectKeyword.mockResolvedValue({ ok: true })
    explainProjectKeywordMatch.mockResolvedValue({ title: 'Matches project naming.' })
    getAdminPendingApprovals.mockResolvedValue({ items: [] })
    getDataQualityDetail.mockResolvedValue({ summary: { status: 'good' }, sources: [] })
  })

  it('renders guided settings sections in order', async () => {
    renderSettings()

    // Page label is now non-heading visual text (see PrimaryPageLayout); inner panel headings are still h3/role=heading.
    await screen.findByText('Settings')
    const headings = screen.getAllByRole('heading').map((heading) => heading.textContent)
    expect(headings).toEqual(expect.arrayContaining([
      'Account Connections',
      'Project Connections',
      'Daily Brief',
      'Preferences',
      'Project Keywords',
      'Data Health',
      'Update Approval',
    ]))
    expect(headings.indexOf('Account Connections')).toBeLessThan(headings.indexOf('Project Connections'))
    expect(headings.indexOf('Project Connections')).toBeLessThan(headings.indexOf('Daily Brief'))
    expect(headings.indexOf('Daily Brief')).toBeLessThan(headings.indexOf('Preferences'))
    expect(headings.indexOf('Preferences')).toBeLessThan(headings.indexOf('Project Keywords'))
    expect(headings.indexOf('Project Keywords')).toBeLessThan(headings.indexOf('Data Health'))
  })

  it('omits forbidden setup/debug copy from normal Settings UI', async () => {
    renderSettings()
    await screen.findByText('Account Connections')

    const text = document.body.textContent || ''
    for (const forbidden of [
      'Prompt 14B',
      'Prompt 20',
      'FPR-004',
      'Load Accounts Status',
      'Load Projects',
      'Load Source Scope',
      'preview→save',
      'raw panels',
      'raw JSON',
      'project_matching_only',
      'local dev role',
    ]) {
      expect(text).not.toContain(forbidden)
    }
  })

  it('renders normalized action labels for account, project, and data health panels', async () => {
    renderSettings()
    await screen.findByRole('button', { name: 'Check connection status' })

    expect(screen.getByRole('button', { name: 'Review project connections' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Data Health' })).toHaveAttribute('href', '/admin')
  })

  it('keeps Daily Brief advanced setup details collapsed', async () => {
    renderSettings()
    const advancedButton = await screen.findByRole('button', { name: 'Advanced setup' })
    fireEvent.click(advancedButton)

    await waitFor(() => expect(generateDailyBriefSetupInstructions).toHaveBeenCalled())
    expect(screen.getByText('Advanced Daily Brief details').closest('details')).not.toHaveAttribute('open')
  })

  it('renders keyword list and explanation without raw object output', async () => {
    renderSettings()
    await screen.findByText('Project Keywords')

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'tropical' } })
    fireEvent.click(screen.getByRole('button', { name: 'Refresh keywords' }))
    expect(await screen.findByText('foundation review')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Keyword'), { target: { value: 'foundation' } })
    fireEvent.click(screen.getByRole('button', { name: 'Explain match' }))
    expect(await screen.findByText('Matches project naming.')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('[object Object]')
  })
})
