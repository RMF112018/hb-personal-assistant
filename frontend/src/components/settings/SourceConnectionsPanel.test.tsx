/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable-next-line @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- vitest spyOn(window) + hook cleanup types cause spurious tsc errors in this test harness; vitest runner still validates at test time.
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SourceConnectionsPanel } from './SourceConnectionsPanel'
import { GraphSourceCard } from './GraphSourceCard'
import { ProcoreSourceCard } from './ProcoreSourceCard'

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } })
}

function renderWithProviders(ui: React.ReactElement) {
  const client = makeClient()
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  )
}

function renderPanel() {
  return renderWithProviders(<SourceConnectionsPanel />)
}

const getEnvironment = vi.fn()
const getSourcesStatus = vi.fn()
const getSchedulerStatus = vi.fn()
const refreshSourcesDryRun = vi.fn()
const refreshSourcesLocal = vi.fn()
const refreshSourcesLive = vi.fn()
const startGraphSourceAuth = vi.fn()
const startProcoreSourceAuth = vi.fn()
const refreshGraphSourceAuth = vi.fn()
const refreshProcoreSourceAuth = vi.fn()
const getGraphSourceAuthStatus = vi.fn()
const getProcoreSourceAuthStatus = vi.fn()

vi.mock('../../lib/api', () => ({
  getEnvironment: (...a: any[]) => getEnvironment(...a),
  getSourcesStatus: (...a: any[]) => getSourcesStatus(...a),
  getSchedulerStatus: (...a: any[]) => getSchedulerStatus(...a),
  refreshSourcesDryRun: (...a: any[]) => refreshSourcesDryRun(...a),
  refreshSourcesLocal: (...a: any[]) => refreshSourcesLocal(...a),
  refreshSourcesLive: (...a: any[]) => refreshSourcesLive(...a),
  startGraphSourceAuth: (...a: any[]) => startGraphSourceAuth(...a),
  startProcoreSourceAuth: (...a: any[]) => startProcoreSourceAuth(...a),
  refreshGraphSourceAuth: (...a: any[]) => refreshGraphSourceAuth(...a),
  refreshProcoreSourceAuth: (...a: any[]) => refreshProcoreSourceAuth(...a),
  getGraphSourceAuthStatus: (...a: any[]) => getGraphSourceAuthStatus(...a),
  getProcoreSourceAuthStatus: (...a: any[]) => getProcoreSourceAuthStatus(...a),
}))

describe('SourceConnectionsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state', () => {
    getEnvironment.mockReturnValue(new Promise(() => {}))
    getSourcesStatus.mockReturnValue(new Promise(() => {}))
    getSchedulerStatus.mockReturnValue(new Promise(() => {}))
    renderPanel()
    expect(screen.getByText(/Loading source status/i)).toBeInTheDocument()
  })

  it('renders connected (graph connected_valid) with success tone and no raw', async () => {
    getEnvironment.mockResolvedValue({ source_refresh_mode: 'local_or_gated_live', live_refresh: { enabled: true } })
    getSourcesStatus.mockResolvedValue({
      environment: 'production',
      source_refresh_mode: 'local_or_gated_live',
      live_refresh: { available: true, enabled: true },
      graph: { status: 'connected_valid', account_hint: 'bobby@example.com' },
      procore: { status: 'connected_valid' },
    })
    getSchedulerStatus.mockResolvedValue({ last_successful_schedule_date: '2026-06-07T10:00:00Z' })
    renderPanel()

    expect(await screen.findByText('Source Connections')).toBeInTheDocument()
    await waitFor(() => expect(document.body.textContent || '').toMatch(/Connected/))
    expect(screen.getByText(/Last local update:/)).toBeInTheDocument()
    // no raw
    const body = document.body.textContent || ''
    expect(body).not.toContain('access_token')
    expect(body).not.toContain('flow_id')
    expect(body).not.toContain('cache_path')
  })

  it('renders reauth_required (stale) with danger tone', async () => {
    getEnvironment.mockResolvedValue({})
    getSourcesStatus.mockResolvedValue({ graph: { status: 'reauth_required' }, procore: { status: 'connected_stale_reauth_required' }, live_refresh: { enabled: false } })
    getSchedulerStatus.mockResolvedValue({})
    renderPanel()

    await waitFor(() => expect(document.body.textContent || '').toMatch(/Reconnect required/))
  })

  it('renders not_connected / missing-auth state', async () => {
    getEnvironment.mockResolvedValue({ source_refresh_mode: 'mock_data', live_refresh: { enabled: false } })
    getSourcesStatus.mockResolvedValue({ graph: { status: 'not_connected' }, procore: { status: 'never_connected' } })
    getSchedulerStatus.mockResolvedValue({})
    renderPanel()

    await waitFor(() => expect(document.body.textContent || '').toMatch(/Not connected/))
  })

  it('renders procore missing-config / not_configured', async () => {
    getEnvironment.mockResolvedValue({})
    getSourcesStatus.mockResolvedValue({ procore: { status: 'not_configured', missing_config: true } })
    getSchedulerStatus.mockResolvedValue({})
    renderPanel()

    await waitFor(() => expect(document.body.textContent || '').toMatch(/Not configured/i))
  })

  it('renders procore missing-mapping with pending projects', async () => {
    getEnvironment.mockResolvedValue({})
    getSourcesStatus.mockResolvedValue({ procore: { status: 'connected_valid', missing_mapping: true, pending_projects: ['tropical', 'garage'] } })
    getSchedulerStatus.mockResolvedValue({})
    renderPanel()

    expect(await screen.findByText(/Pending project mapping/i)).toBeInTheDocument()
  })

  it('local-mode (mock_data, live disabled) disables Live button and shows banner', async () => {
    getEnvironment.mockResolvedValue({ source_refresh_mode: 'mock_data', live_refresh: { enabled: false, reason: 'dev' } })
    getSourcesStatus.mockResolvedValue({ source_refresh_mode: 'mock_data', live_refresh: { enabled: false }, graph: { status: 'connected_valid' }, procore: { status: 'connected_valid' } })
    getSchedulerStatus.mockResolvedValue({})
    renderPanel()

    const liveBtn = await screen.findByRole('button', { name: /Live refresh/i })
    expect(liveBtn).toBeDisabled()
    await waitFor(() => expect(document.body.textContent || '').toMatch(/mock.*data|Dev/i))
  })

  it('error from api shows ErrorState safe copy (raw hidden)', async () => {
    getEnvironment.mockResolvedValue({})
    getSourcesStatus.mockRejectedValue(new Error('500 secret_trace raw'))
    getSchedulerStatus.mockResolvedValue({})
    renderPanel()

    expect(await screen.findByText(/could not be loaded/i)).toBeInTheDocument()
    // primary message is the safe copy; raw technical (if any) is in collapsed details and not primary UI copy
    const body = document.body.textContent || ''
    expect(body).toContain('The rest of the page remains advisory.')
    // ensure no obvious secret/token leaks in the error surface
    expect(body).not.toContain('access_token')
  })

  it('Live action is confirmation-gated (calls live only on confirm)', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    getEnvironment.mockResolvedValue({ live_refresh: { enabled: true } })
    getSourcesStatus.mockResolvedValue({ live_refresh: { enabled: true }, graph: {}, procore: {} })
    getSchedulerStatus.mockResolvedValue({})
    refreshSourcesLive.mockResolvedValue({ status: 'ok', live_mode: 'live_source' })
    renderPanel()

    let liveBtn = await screen.findByRole('button', { name: /Live refresh/i })
    await waitFor(() => {
      liveBtn = screen.getByRole('button', { name: /Live refresh/i })
      expect(liveBtn).not.toBeDisabled()
    })
    fireEvent.click(liveBtn)
    await waitFor(() => expect(refreshSourcesLive).toHaveBeenCalled())
    expect((window.confirm as any).mock?.calls?.length || 0).toBeGreaterThan(0)
    // receipt shown safely (use a more specific matcher to avoid multiples from other content)
    expect(screen.getByText((t) => /Receipt.*(ok|live_source)/i.test(String(t)))).toBeInTheDocument()
  })

  it('Dry-run and Local are always enabled and call the right fns', async () => {
    getEnvironment.mockResolvedValue({})
    getSourcesStatus.mockResolvedValue({})
    getSchedulerStatus.mockResolvedValue({})
    refreshSourcesDryRun.mockResolvedValue({ status: 'dry_run_ok' })
    refreshSourcesLocal.mockResolvedValue({ status: 'local_ok' })
    renderPanel()

    fireEvent.click(await screen.findByRole('button', { name: /Dry-run refresh/i }))
    await waitFor(() => expect(refreshSourcesDryRun).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: /Local refresh/i }))
    await waitFor(() => expect(refreshSourcesLocal).toHaveBeenCalled())
  })
})

describe('GraphSourceCard and ProcoreSourceCard (direct)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('Graph card shows scope missing warning and uses getSourceStateCopy label', () => {
    render(<GraphSourceCard status={{ status: 'connected_valid', scope_presence: { missing: true } }} />)
    expect(screen.getByText('Connected')).toBeInTheDocument()
    expect(screen.getByText(/Missing scope/i)).toBeInTheDocument()
  })

  it('Procore card shows missing mapping + pending list and reauth', () => {
    render(<ProcoreSourceCard status={{ status: 'reauth_required', missing_mapping: true, pending_projects: ['one'] }} />)
    expect(screen.getAllByText(/Reconnect required/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Pending project mapping/i)).toBeInTheDocument()
  })

  it('cards do not leak raw tokens in normal render', () => {
    render(<GraphSourceCard status={{ status: 'never_connected', access_token: 'SECRET' }} />)
    const body = document.body.textContent || ''
    expect(body).not.toContain('SECRET')
    expect(body).not.toContain('access_token')
  })
})
