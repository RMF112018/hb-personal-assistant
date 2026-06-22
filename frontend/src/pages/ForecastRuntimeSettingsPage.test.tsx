import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastRuntimeSettingsPage } from './ForecastRuntimeSettingsPage'

const useQueryMock = vi.fn()
const getRoleMock = vi.fn(() => 'admin')

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

vi.mock('../lib/api', () => ({
  getLocalUiRole: () => getRoleMock(),
  api: {
    getForecastRuntimeStatus: vi.fn(),
    getForecastRuntimeConfig: vi.fn(),
    saveForecastRuntimeConfig: vi.fn(),
    repairForecastRuntimeStorage: vi.fn(),
    resetForecastRuntimeDefaults: vi.fn(),
  },
}))

const STATUS = {
  storage_mode: 'app_managed',
  roots: {
    package_roots: { configured: true, valid: true, source: 'managed_default', blocker: null, count: 0 },
    data_root: { configured: true, valid: true, source: 'managed_default', blocker: null },
    runs_root: { configured: true, valid: true, source: 'managed_default', blocker: null },
    eval_root: { configured: true, valid: true, source: 'managed_default', blocker: null },
    db_path: { configured: true, valid: true, source: 'managed_default', blocker: null, schema_version: 61 },
    cfr_src: { configured: false, valid: true, source: 'default', blocker: null },
    config_edit_root: { configured: true, valid: true, source: 'managed_default', blocker: null },
  },
  surfaces_ready: { catalog: true, config: true, run_center: true, external_eval: true, config_edit: true },
}

function mockQueries(config: unknown = undefined) {
  useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
    const kind = opts.queryKey[2]
    if (kind === 'status') {
      return { data: STATUS, isLoading: false, error: null, refetch: vi.fn() }
    }
    if (kind === 'config') {
      return { data: config, isLoading: false, error: null, refetch: vi.fn() }
    }
    return { data: undefined, isLoading: false, error: null, refetch: vi.fn() }
  })
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ForecastRuntimeSettingsPage />
    </MemoryRouter>,
  )
}

describe('ForecastRuntimeSettingsPage', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    getRoleMock.mockReturnValue('admin')
  })

  it('renders storage readiness without asking for paths by default', () => {
    mockQueries()
    renderPage()
    expect(screen.getByText('Storage & database readiness')).toBeInTheDocument()
    expect(screen.getByText(/Managed by HB/)).toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/Absolute path/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Advanced manual path override/i })).toBeInTheDocument()
  })

  it('shows advanced path overrides only when expanded for admin', async () => {
    const user = userEvent.setup()
    mockQueries({ config: { data_root: '/live/data', package_roots: ['/pkg/a'] }, config_file_present: true })
    renderPage()
    expect(screen.queryByDisplayValue('/live/data')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Advanced manual path override/i }))
    expect(await screen.findByDisplayValue('/live/data')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Save overrides/i })).toBeInTheDocument()
  })

  it('shows repair for operator but hides advanced settings', () => {
    getRoleMock.mockReturnValue('operator')
    mockQueries()
    renderPage()
    expect(screen.getByRole('button', { name: /Repair local storage/i })).toBeInTheDocument()
    expect(screen.queryByText(/Advanced manual path override/i)).not.toBeInTheDocument()
  })

  it('hides repair and advanced settings for viewer', () => {
    getRoleMock.mockReturnValue('viewer')
    mockQueries()
    renderPage()
    expect(screen.queryByRole('button', { name: /Repair local storage/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/Advanced manual path override/i)).not.toBeInTheDocument()
  })
})