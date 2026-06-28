import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
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
const getEnvironment = vi.fn()
const getSourcesStatus = vi.fn()
const getSchedulerStatus = vi.fn()
const refreshSourcesDryRun = vi.fn()
const refreshSourcesLocal = vi.fn()
const refreshSourcesLive = vi.fn()
const getObsidianMcpConfig = vi.fn()
const patchObsidianMcpConfig = vi.fn()
const getObsidianMcpStatus = vi.fn()
const runObsidianMcpHealthCheck = vi.fn()
const getObsidianMcpTools = vi.fn()
const enableObsidianMcp = vi.fn()
const disableObsidianMcp = vi.fn()
const restartObsidianMcp = vi.fn()
const testObsidianMcpListDirectory = vi.fn()
const testObsidianMcpSearch = vi.fn()
const testObsidianMcpReadFile = vi.fn()
const getObsidianMcpGrokConfig = vi.fn()

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
  getEnvironment: () => getEnvironment(),
  getSourcesStatus: () => getSourcesStatus(),
  getSchedulerStatus: () => getSchedulerStatus(),
  refreshSourcesDryRun: () => refreshSourcesDryRun(),
  refreshSourcesLocal: () => refreshSourcesLocal(),
  refreshSourcesLive: (confirm: boolean) => refreshSourcesLive(confirm),
  getObsidianMcpConfig: () => getObsidianMcpConfig(),
  patchObsidianMcpConfig: (patch: unknown) => patchObsidianMcpConfig(patch),
  getObsidianMcpStatus: () => getObsidianMcpStatus(),
  runObsidianMcpHealthCheck: () => runObsidianMcpHealthCheck(),
  getObsidianMcpTools: () => getObsidianMcpTools(),
  enableObsidianMcp: () => enableObsidianMcp(),
  disableObsidianMcp: () => disableObsidianMcp(),
  restartObsidianMcp: () => restartObsidianMcp(),
  testObsidianMcpListDirectory: (body: unknown) => testObsidianMcpListDirectory(body),
  testObsidianMcpSearch: (body: unknown) => testObsidianMcpSearch(body),
  testObsidianMcpReadFile: (body: unknown) => testObsidianMcpReadFile(body),
  getObsidianMcpGrokConfig: () => getObsidianMcpGrokConfig(),
}))

function renderSettings() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
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
    getEnvironment.mockResolvedValue({
      surface: 'environment',
      status: 'ok',
      environment: 'dev',
      source_refresh_mode: 'mock_data',
      live_refresh: { available: false, enabled: false, reason: 'disabled in test' },
      guardrails: { read_only: true },
    })
    getSourcesStatus.mockResolvedValue({
      surface: 'sources.status',
      status: 'ok',
      source_refresh_mode: 'mock_data',
      live_refresh: { available: false, enabled: false, reason: 'disabled in test' },
      graph: { state: 'connected_valid' },
      procore: { state: 'connected' },
      scheduler: { last_successful_schedule_date: null },
      guardrails: { read_only: true },
    })
    getSchedulerStatus.mockResolvedValue({
      surface: 'scheduler.status',
      status: 'ok',
      last_successful_schedule_date: null,
      guardrails: { read_only: true },
    })
    refreshSourcesDryRun.mockResolvedValue({ status: 'ok', live_read_performed: false })
    refreshSourcesLocal.mockResolvedValue({ status: 'ok', live_read_performed: false })
    refreshSourcesLive.mockResolvedValue({ status: 'blocked', live_read_performed: false })
    getObsidianMcpConfig.mockResolvedValue({
      config: {
        enabled: false,
        mode: 'filesystem',
        vault_root: '/Users/bobbyfetting/Documents/Obsidian Vault',
        host: '127.0.0.1',
        port: 3010,
        token_configured: true,
        max_file_mb: 100,
        max_result_chars: 12000,
        allowed_file_types: ['md', 'txt', 'pdf', 'docx'],
        default_scope: 'Projects',
        endpoint_url: 'http://127.0.0.1:3010/mcp',
      },
    })
    patchObsidianMcpConfig.mockResolvedValue({
      config: {
        enabled: true,
        mode: 'filesystem',
        vault_root: '/Users/bobbyfetting/Documents/Obsidian Vault',
        host: '127.0.0.1',
        port: 3010,
        token_configured: true,
        max_file_mb: 100,
        max_result_chars: 12000,
        allowed_file_types: ['md', 'txt', 'pdf', 'docx'],
        default_scope: 'Projects',
        endpoint_url: 'http://127.0.0.1:3010/mcp',
      },
    })
    getObsidianMcpStatus.mockResolvedValue({
      enabled: false,
      service_state: 'stopped',
      mode: 'filesystem',
      token_configured: true,
      tools_registered: 3,
      blocking_issues: [],
      warnings: [],
    })
    runObsidianMcpHealthCheck.mockResolvedValue({
      ok: true,
      checked_at: '2026-06-28T10:00:00Z',
      blocking_issues: [],
      warnings: [],
      checks: [{ name: 'tool_registry', status: 'pass', detail: 'three tools' }],
    })
    getObsidianMcpTools.mockResolvedValue({
      tools: [
        { name: 'list_directory', description: 'List files', input_schema_summary: 'path, recursive', enabled: true, last_validation_status: 'pass' },
        { name: 'search_vault', description: 'Search files', input_schema_summary: 'query, path_scope', enabled: true, last_validation_status: 'pass' },
        { name: 'read_file', description: 'Read files', input_schema_summary: 'path, max_chars', enabled: true, last_validation_status: 'pass' },
      ],
    })
    enableObsidianMcp.mockResolvedValue({ config: { enabled: true }, status: { service_state: 'running' }, health: { blocking_issues: [], warnings: [] } })
    disableObsidianMcp.mockResolvedValue({ config: { enabled: false }, status: { service_state: 'stopped' }, health: { blocking_issues: [], warnings: [] } })
    restartObsidianMcp.mockResolvedValue({ config: { enabled: true }, status: { service_state: 'running' }, health: { blocking_issues: [], warnings: [] } })
    testObsidianMcpListDirectory.mockResolvedValue({ ok: true, result: { files: [{ path: 'Projects/Scope.md' }] } })
    testObsidianMcpSearch.mockResolvedValue({ ok: true, result: { results: [{ path: 'Projects/Scope.md', snippet: 'conduit' }] } })
    testObsidianMcpReadFile.mockResolvedValue({ ok: true, result: { path: 'Projects/Scope.md', content: 'Scope text', metadata: { truncated: false } } })
    getObsidianMcpGrokConfig.mockResolvedValue({
      token_value_returned: false,
      mcp_config: {
        mcpServers: {
          'hb-obsidian-hybrid': {
            type: 'streamable-http',
            url: 'http://127.0.0.1:3010/mcp',
            headers: { Authorization: 'Bearer <configured-token>' },
          },
        },
      },
    })
  })

  it('renders guided settings sections in order', async () => {
    renderSettings()

    // Chrome header owns the page title (no duplicate body label from PrimaryPageLayout).
    // Wait for first panel content instead of removed page label, then assert inner h3 headings.
    await screen.findByText('Account Connections')
    const headings = screen.getAllByRole('heading').map((heading) => heading.textContent)
    expect(headings).toEqual(expect.arrayContaining([
      'Account Connections',
      'Project Connections',
      'Daily Brief',
      'Obsidian MCP',
      'Preferences',
      'Project Keywords',
      'Data Health',
      'Update Approval',
    ]))
    expect(headings.indexOf('Account Connections')).toBeLessThan(headings.indexOf('Project Connections'))
    expect(headings.indexOf('Project Connections')).toBeLessThan(headings.indexOf('Daily Brief'))
    expect(headings.indexOf('Daily Brief')).toBeLessThan(headings.indexOf('Obsidian MCP'))
    expect(headings.indexOf('Obsidian MCP')).toBeLessThan(headings.indexOf('Preferences'))
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
      'hb-assistant obsidian-mcp',
      'Terminal',
      'secret-token',
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

  it('renders Obsidian MCP controls and tool registry without token values', async () => {
    renderSettings()
    await screen.findByText('Obsidian MCP')

    expect(screen.getByRole('button', { name: /Run Health Check/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Enable MCP/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Restart MCP service/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Copy Grok MCP config/i })).toBeInTheDocument()
    expect(await screen.findByText('list_directory')).toBeInTheDocument()
    expect(screen.getByText('search_vault')).toBeInTheDocument()
    expect(screen.getByText('read_file')).toBeInTheDocument()
    expect(document.body.textContent).toContain('Bearer <configured-token>')
    expect(document.body.textContent).not.toContain('secret-token')
  })

  it('runs Obsidian MCP health check and test actions from Settings', async () => {
    renderSettings()
    await screen.findByText('Obsidian MCP')

    fireEvent.click(screen.getByRole('button', { name: /Run Health Check/i }))
    await waitFor(() => expect(runObsidianMcpHealthCheck).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('Search query'), { target: { value: 'conduit' } })
    fireEvent.click(screen.getByRole('button', { name: /Run test search/i }))
    await waitFor(() => expect(testObsidianMcpSearch).toHaveBeenCalledWith(expect.objectContaining({ query: 'conduit' })))

    fireEvent.change(screen.getByLabelText('Directory path'), { target: { value: 'Projects' } })
    fireEvent.click(screen.getByRole('button', { name: /Run test directory listing/i }))
    await waitFor(() => expect(testObsidianMcpListDirectory).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('File path'), { target: { value: 'Projects/Scope.md' } })
    fireEvent.click(screen.getByRole('button', { name: /Run test file read/i }))
    await waitFor(() => expect(testObsidianMcpReadFile).toHaveBeenCalled())
  })
})
