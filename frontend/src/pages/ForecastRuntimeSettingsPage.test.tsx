import { render, screen } from '@testing-library/react'
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
  },
}))

const STATUS = {
  roots: {
    package_roots: { configured: true, valid: true, source: 'settings_file', blocker: null, count: 1 },
    data_root: { configured: false, valid: false, source: null, blocker: 'not_configured' },
    runs_root: { configured: false, valid: false, source: null, blocker: 'not_configured' },
    eval_root: { configured: false, valid: false, source: null, blocker: 'not_configured' },
    db_path: { configured: false, valid: false, source: null, blocker: 'not_configured' },
    cfr_src: { configured: false, valid: true, source: 'default', blocker: null },
  },
  surfaces_ready: { catalog: true, config: false, run_center: false, external_eval: false },
}

function mockQueries(config: unknown = undefined) {
  useQueryMock.mockImplementation((opts: { queryKey: any[] }) => {
    const kind = opts.queryKey[2]
    if (kind === 'status') {
      return { data: STATUS, isLoading: false, error: null, refetch: vi.fn() }
    }
    return { data: config, isLoading: false, error: null, refetch: vi.fn() }
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

  it('renders the redaction-safe status with plain-language blockers', () => {
    mockQueries()
    renderPage()
    expect(screen.getByText('Runtime data sources')).toBeInTheDocument()
    expect(screen.getAllByText('Source data folder').length).toBeGreaterThan(0)
    // A not_configured root surfaces as plain copy, never a path.
    expect(screen.getAllByText('Not configured').length).toBeGreaterThan(0)
    expect(screen.getByText('Surfaces ready')).toBeInTheDocument()
  })

  it('pre-fills the edit form from the admin path echo', () => {
    mockQueries({ config: { data_root: '/live/data', package_roots: ['/pkg/a'] } })
    renderPage()
    expect(screen.getByText('Edit data sources')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Save data sources/i })).toBeInTheDocument()
    expect(screen.getByDisplayValue('/live/data')).toBeInTheDocument()
  })

  it('hides the edit form for a viewer role', () => {
    getRoleMock.mockReturnValue('viewer')
    mockQueries()
    renderPage()
    expect(screen.queryByText('Edit data sources')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Save data sources/i })).not.toBeInTheDocument()
  })
})
