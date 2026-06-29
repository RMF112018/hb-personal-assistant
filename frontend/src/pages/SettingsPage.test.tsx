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
const getObsidianMcpMutations = vi.fn()
const getObsidianMcpReadReceipts = vi.fn()
const runObsidianMcpWriteReadiness = vi.fn()
const enableObsidianMcp = vi.fn()
const disableObsidianMcp = vi.fn()
const restartObsidianMcp = vi.fn()
const testObsidianMcpListDirectory = vi.fn()
const testObsidianMcpSearch = vi.fn()
const testObsidianMcpReadFile = vi.fn()
const testObsidianMcpWriteSmoke = vi.fn()
const getObsidianMcpGrokConfig = vi.fn()
const getObsidianMcpOAuth = vi.fn()
const getObsidianMcpChatGPT = vi.fn()
const runObsidianMcpChatGPTReadiness = vi.fn()

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
  getObsidianMcpMutations: (limit: number) => getObsidianMcpMutations(limit),
  getObsidianMcpReadReceipts: (limit: number) => getObsidianMcpReadReceipts(limit),
  runObsidianMcpWriteReadiness: () => runObsidianMcpWriteReadiness(),
  enableObsidianMcp: () => enableObsidianMcp(),
  disableObsidianMcp: () => disableObsidianMcp(),
  restartObsidianMcp: () => restartObsidianMcp(),
  testObsidianMcpListDirectory: (body: unknown) => testObsidianMcpListDirectory(body),
  testObsidianMcpSearch: (body: unknown) => testObsidianMcpSearch(body),
  testObsidianMcpReadFile: (body: unknown) => testObsidianMcpReadFile(body),
  testObsidianMcpWriteSmoke: () => testObsidianMcpWriteSmoke(),
  getObsidianMcpGrokConfig: () => getObsidianMcpGrokConfig(),
  getObsidianMcpOAuth: () => getObsidianMcpOAuth(),
  getObsidianMcpChatGPT: () => getObsidianMcpChatGPT(),
  runObsidianMcpChatGPTReadiness: () => runObsidianMcpChatGPTReadiness(),
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
        writes_enabled: true,
        vault_markdown_write_enabled: true,
        max_write_chars: 120000,
        write_requires_expected_sha256: true,
        backup_before_replace: true,
        create_parent_dirs_enabled: true,
        allow_full_vault_markdown_writes: true,
        protected_paths: ['.git', '.obsidian', '.trash', '.hb-assistant/backups'],
        blocked_hidden_paths: true,
        allowed_write_file_types: ['md'],
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
        writes_enabled: true,
        vault_markdown_write_enabled: true,
        max_write_chars: 120000,
        write_requires_expected_sha256: true,
        backup_before_replace: true,
        create_parent_dirs_enabled: true,
        allow_full_vault_markdown_writes: true,
        protected_paths: ['.git', '.obsidian', '.trash', '.hb-assistant/backups'],
        blocked_hidden_paths: true,
        allowed_write_file_types: ['md'],
      },
    })
    getObsidianMcpStatus.mockResolvedValue({
      enabled: false,
      service_state: 'stopped',
      mode: 'filesystem',
      token_configured: true,
      tools_registered: 5,
      writes_enabled: true,
      vault_markdown_write_enabled: true,
      blocking_issues: [],
      warnings: [],
    })
    runObsidianMcpHealthCheck.mockResolvedValue({
      ok: true,
      checked_at: '2026-06-28T10:00:00Z',
      blocking_issues: [],
      warnings: [],
      checks: [{ name: 'tool_registry', status: 'pass', detail: 'five tools' }],
    })
    getObsidianMcpMutations.mockResolvedValue({
      mutations: [
        {
          timestamp: '2026-06-28T10:00:00Z',
          action: 'patch_note',
          relative_path: 'Projects/Index.md',
          status: 'applied',
          old_sha256: 'old',
          new_sha256: 'new',
          backup_path: '/safe/backup/Projects/Index.md',
          caller_surface: 'mcp',
        },
      ],
    })
    runObsidianMcpWriteReadiness.mockResolvedValue({
      ok: true,
      vault_writable: true,
      backup_writable: true,
      blocking_issues: [],
    })
    getObsidianMcpTools.mockResolvedValue({
      tools: [
        { name: 'list_directory', category: 'Base', description: 'List files', input_schema_summary: 'path, recursive', enabled: true, last_validation_status: 'pass' },
        { name: 'search_vault', category: 'Base', description: 'Search files', input_schema_summary: 'query, path_scope', enabled: true, last_validation_status: 'pass' },
        { name: 'read_file', category: 'Base', description: 'Read files', input_schema_summary: 'path, max_chars', enabled: true, last_validation_status: 'pass' },
        { name: 'create_note', category: 'Base', description: 'Create notes', input_schema_summary: 'path, content', enabled: true, last_validation_status: 'pass' },
        { name: 'patch_note', category: 'Base', description: 'Replace notes', input_schema_summary: 'path, content, expected_sha256', enabled: true, last_validation_status: 'pass' },
        { name: 'vault_summarize_note', category: 'Vault Intelligence', description: 'Summarize a note', input_schema_summary: 'path', enabled: true, last_validation_status: 'not_run' },
        { name: 'vault_move_note_apply', category: 'File Operations', description: 'Apply a move plan', input_schema_summary: 'plan_id', enabled: true, last_validation_status: 'not_run' },
      ],
    })
    getObsidianMcpReadReceipts.mockResolvedValue({
      read_receipts: [
        { timestamp: '2026-06-28T11:00:00Z', tool_name: 'vault_email_inventory', scope: 'Work/Email/inbox', file_count: 12, principal_kind: 'oauth', truncated: false },
      ],
    })
    enableObsidianMcp.mockResolvedValue({ config: { enabled: true }, status: { service_state: 'running' }, health: { blocking_issues: [], warnings: [] } })
    disableObsidianMcp.mockResolvedValue({ config: { enabled: false }, status: { service_state: 'stopped' }, health: { blocking_issues: [], warnings: [] } })
    restartObsidianMcp.mockResolvedValue({ config: { enabled: true }, status: { service_state: 'running' }, health: { blocking_issues: [], warnings: [] } })
    testObsidianMcpListDirectory.mockResolvedValue({ ok: true, result: { files: [{ path: 'Projects/Scope.md' }] } })
    testObsidianMcpSearch.mockResolvedValue({ ok: true, result: { results: [{ path: 'Projects/Scope.md', snippet: 'conduit' }] } })
    testObsidianMcpReadFile.mockResolvedValue({ ok: true, result: { path: 'Projects/Scope.md', content: 'Scope text', metadata: { truncated: false } } })
    testObsidianMcpWriteSmoke.mockResolvedValue({
      ok: true,
      result: {
        ok: true,
        result: {
          path: 'MCP Write Smoke/hb-mcp-write-smoke.md',
          sha256: 'new',
          bytes: 82,
          event: { action: 'create_note', status: 'applied', relative_path: 'MCP Write Smoke/hb-mcp-write-smoke.md' },
        },
      },
    })
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
    getObsidianMcpOAuth.mockResolvedValue({
      oauth_enabled: true,
      public_base_url: 'https://mcp.bobby-fetting.me',
      client_id: 'hb-obsidian-grok',
      scopes_supported: ['obsidian.read', 'obsidian.write'],
      token_auth_method: 'none (PKCE)',
      endpoints: {
        authorization_endpoint: 'https://mcp.bobby-fetting.me/oauth/authorize',
        token_endpoint: 'https://mcp.bobby-fetting.me/oauth/token',
        metadata_endpoint: 'https://mcp.bobby-fetting.me/.well-known/oauth-authorization-server',
        mcp_url: 'https://mcp.bobby-fetting.me/mcp',
      },
      grok_setup: {
        mcp_url: 'https://mcp.bobby-fetting.me/mcp',
        client_id: 'hb-obsidian-grok',
        client_secret: '',
        authorization_endpoint: 'https://mcp.bobby-fetting.me/oauth/authorize',
        token_endpoint: 'https://mcp.bobby-fetting.me/oauth/token',
        scopes: ['obsidian.read', 'obsidian.write'],
        token_auth_method: 'none (PKCE)',
      },
      recent_events: [{ kind: 'access_token_issued', scope: 'obsidian.read', at: '2026-06-28T10:00:00+00:00' }],
    })
    getObsidianMcpChatGPT.mockResolvedValue({
      enabled: true,
      readonly_mode: true,
      dynamic_client_registration_enabled: true,
      client_id_metadata_document_supported: false,
      initial_scopes: ['obsidian.read'],
      setup: {
        connector_url: 'https://mcp.bobby-fetting.me/mcp',
        protected_resource_metadata_url: 'https://mcp.bobby-fetting.me/.well-known/oauth-protected-resource',
        authorization_server_metadata_url: 'https://mcp.bobby-fetting.me/.well-known/oauth-authorization-server',
        authorization_endpoint: 'https://mcp.bobby-fetting.me/oauth/authorize',
        token_endpoint: 'https://mcp.bobby-fetting.me/oauth/token',
        registration_endpoint: 'https://mcp.bobby-fetting.me/oauth/register',
        registration_mode: 'dynamic_client_registration',
        initial_scope: 'obsidian.read',
        client_id_metadata_document_supported: false,
      },
      recent_events: [],
    })
    runObsidianMcpChatGPTReadiness.mockResolvedValue({
      ok: true,
      checks: [{ name: 'oauth_register_post', status: 'pass', detail: 'POST /oauth/register accepted synthetic public client' }],
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
    expect(screen.getByText('create_note')).toBeInTheDocument()
    expect(screen.getAllByText('patch_note').length).toBeGreaterThan(0)
    expect(screen.getByText('Autonomous Vault Manager')).toBeInTheDocument()
    expect(screen.getByText(/durable authority/i)).toBeInTheDocument()
    expect(screen.getByLabelText('Write mode')).toBeChecked()
    expect(screen.getByLabelText('Markdown management')).toBeChecked()
    expect(screen.getByText('Recent mutation events')).toBeInTheDocument()
    expect(screen.getByText('Projects/Index.md')).toBeInTheDocument()
    // Tool registry is grouped by category, and high-risk writes are flagged.
    expect(screen.getByText(/Vault Intelligence/)).toBeInTheDocument()
    expect(screen.getByText(/File Operations/)).toBeInTheDocument()
    expect(screen.getByText('High-risk write')).toBeInTheDocument()
    // Read/crawl receipts and Grok usage examples are surfaced.
    expect(screen.getByText('Read / crawl receipts')).toBeInTheDocument()
    expect(screen.getAllByText('vault_email_inventory').length).toBeGreaterThan(0)
    expect(screen.getByText('Work/Email/inbox')).toBeInTheDocument()
    expect(screen.getByText('Grok usage examples')).toBeInTheDocument()
    expect(screen.getByText('ChatGPT App Connection')).toBeInTheDocument()
    expect(screen.getByText('https://mcp.bobby-fetting.me/.well-known/oauth-protected-resource')).toBeInTheDocument()
    expect(screen.getByText('https://mcp.bobby-fetting.me/oauth/register')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Copy ChatGPT setup values/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Run readiness check/i })).toBeInTheDocument()
    expect(document.body.textContent).toContain('Bearer <configured-token>')
    expect(document.body.textContent).not.toContain('secret-token')
    expect(document.body.textContent).not.toContain('raw note body')
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

    fireEvent.click(screen.getByRole('button', { name: /Run write readiness/i }))
    await waitFor(() => expect(runObsidianMcpWriteReadiness).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: /Run write smoke test/i }))
    await waitFor(() => expect(testObsidianMcpWriteSmoke).toHaveBeenCalled())
    expect(document.body.textContent).not.toContain('managed note proves')

    fireEvent.click(screen.getByRole('button', { name: /Run readiness check/i }))
    await waitFor(() => expect(runObsidianMcpChatGPTReadiness).toHaveBeenCalled())
  })

  it('renders the Remote Connector / OAuth section with Grok setup values and no token leak', async () => {
    renderSettings()
    await screen.findByText('Remote Connector / OAuth')

    expect(screen.getByText('none (PKCE)')).toBeInTheDocument()
    expect(screen.getByText('hb-obsidian-grok')).toBeInTheDocument()
    expect(screen.getByLabelText('OAuth enabled')).toBeChecked()
    expect(
      screen.getByText('https://mcp.bobby-fetting.me/oauth/authorize'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('https://mcp.bobby-fetting.me/oauth/token'),
    ).toBeInTheDocument()
    expect(screen.getAllByText('https://mcp.bobby-fetting.me/mcp').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /Copy Grok OAuth setup values/i })).toBeInTheDocument()
    expect(screen.getByText('access_token_issued')).toBeInTheDocument()

    // Event labels are safe, but no raw access-token / Bearer value is rendered.
    const text = document.body.textContent || ''
    expect(text).not.toContain('"access_token"')
    expect(text).not.toMatch(/Bearer [A-Za-z0-9_-]{20,}/)
  })

  it('saves the Public MCP Base URL through the config patch', async () => {
    renderSettings()
    await screen.findByText('Remote Connector / OAuth')

    const input = screen.getByLabelText('Public MCP Base URL')
    fireEvent.change(input, { target: { value: 'https://mcp.bobby-fetting.me' } })
    fireEvent.blur(input)
    await waitFor(() =>
      expect(patchObsidianMcpConfig).toHaveBeenCalledWith(
        expect.objectContaining({ public_base_url: 'https://mcp.bobby-fetting.me' }),
      ),
    )
  })
})
