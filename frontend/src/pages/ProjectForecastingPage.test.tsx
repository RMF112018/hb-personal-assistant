import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectDashboardPage } from './ProjectDashboardPage'
import { ProjectForecastingPage } from './ProjectForecastingPage'
import { ProjectMonthlyForecastingPage } from './ProjectMonthlyForecastingPage'
import { ProjectOverviewPage } from './ProjectOverviewPage'
import { api } from '../lib/api'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[]; queryFn: () => unknown }) => useQueryMock(options),
}))

const projectsResponse = {
  surface: 'analytics.projects.list',
  projects: [
    {
      project_key: 'tropical',
      procore_project_id: '2525840',
      display_name: 'Tropical Resort',
      address: '123 Main St',
      city: 'West Palm Beach',
      state_code: 'FL',
      zip: '33401',
      project_number: 'PR-001',
    },
    {
      project_key: 'harbor',
      procore_project_id: '777',
      display_name: 'Harbor Tower',
      address: '9 Dock Rd',
      city: 'Miami',
      state_code: 'FL',
      zip: '33101',
      project_number: 'PR-002',
    },
  ],
  guardrails: { read_only: true },
}

const legacyOverview = {
  summary: 'Legacy aggregate overview.',
  freshness: { overall: 'fresh', minutes_ago_max: 8 },
  confidence_summary: { overall: 'source_backed' },
  project_count: 2,
}

// Per-test forecast read state, applied by the mocked useQuery on 'forecast' query keys.
type ForecastState = {
  isLoading: boolean
  error: unknown
  outputs: Array<{ output_id: string; project_key: string; created_display: string | null }>
  detail: unknown
}

let forecast: ForecastState

function setForecast(overrides: Partial<ForecastState>) {
  forecast = { isLoading: false, error: null, outputs: [], detail: undefined, ...overrides }
}

function mockQueries() {
  useQueryMock.mockImplementation((options: { queryKey: unknown[] }) => {
    const key = options.queryKey
    if (key[0] === 'projects') {
      return { data: projectsResponse, isLoading: false, error: null, refetch: vi.fn() }
    }
    if (key[0] === 'project') {
      return { data: legacyOverview, isLoading: false, error: null }
    }
    if (key[0] === 'forecast' && key[1] === 'db-outputs') {
      return {
        data: forecast.error ? undefined : { outputs: forecast.outputs },
        isLoading: forecast.isLoading,
        error: forecast.error,
        refetch: vi.fn(),
      }
    }
    if (key[0] === 'forecast' && key[1] === 'db-output') {
      return { data: forecast.detail, isLoading: false, error: null }
    }
    return { data: null, isLoading: false, error: null, refetch: vi.fn() }
  })
}

function renderForecastingRoutes(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/projects" element={<div>Projects list</div>} />
        <Route path="/projects/all" element={<ProjectDashboardPage />} />
        <Route path="/projects/:projectKey" element={<ProjectOverviewPage />} />
        <Route path="/projects/:projectKey/forecasting" element={<ProjectForecastingPage />} />
        <Route
          path="/projects/:projectKey/forecasting/monthly"
          element={<ProjectMonthlyForecastingPage />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

function issuedQueryKeys() {
  return useQueryMock.mock.calls.map(([options]) => options.queryKey)
}

const availableOutput = {
  outputs: [{ output_id: 'fout-1', project_key: 'tropical', created_display: 'Jun 19, 2026' }],
  detail: {
    output_id: 'fout-1',
    summary: {
      estimated_at_completion: '12500000',
      total_cost_to_date: '7000000',
      cost_to_complete: '5500000',
      current_budget: '12000000',
      budget_basis_label: 'Revised budget',
      variance_to_budget: '500000',
      variance_to_prior_forecast: '0.00',
      variance_to_prior_forecast_status: 'computed',
      forecast_confidence_label: 'High',
      forecast_maturity_label: 'Full context',
    },
  },
}

describe('Project Forecasting page', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    setForecast({})
    mockQueries()
  })

  it('renders inside the project workspace shell with the forecasting tab active', () => {
    setForecast({ outputs: availableOutput.outputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting')

    // Project identity via the shared shell header.
    expect(screen.getByText('Project workspace')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Tropical Resort' })).toBeInTheDocument()
    expect(screen.getByText('123 Main St · West Palm Beach, FL 33401')).toBeInTheDocument()

    // Forecasting tab active; Overview not.
    expect(screen.getByRole('link', { name: 'Forecasting' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Overview' })).not.toHaveAttribute('aria-current')

    expect(screen.getByRole('heading', { name: 'Forecasting' })).toBeInTheDocument()
  })

  it('renders the headline KPI values when a forecast output is available', () => {
    setForecast({ outputs: availableOutput.outputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting')

    expect(screen.getByText('Last forecast update: Jun 19, 2026')).toBeInTheDocument()
    expect(screen.getByText('Estimated at Completion')).toBeInTheDocument()
    expect(screen.getByText('$12,500,000')).toBeInTheDocument()
    expect(screen.getByText('Cost to Complete')).toBeInTheDocument()
    expect(screen.getByText('Forecast Confidence')).toBeInTheDocument()
    expect(screen.getByText('High')).toBeInTheDocument()
  })

  it('renders the no-output state when the project has no forecast output', () => {
    setForecast({ outputs: [] })
    renderForecastingRoutes('/projects/tropical/forecasting')

    expect(
      screen.getByText('No forecast output is available for this project yet.'),
    ).toBeInTheDocument()
  })

  it('renders a loading state while forecast information is loading', () => {
    setForecast({ isLoading: true })
    renderForecastingRoutes('/projects/tropical/forecasting')

    expect(screen.getByText('Loading forecast information…')).toBeInTheDocument()
  })

  it('renders a business-facing error state when forecast information fails to load', () => {
    setForecast({ error: new Error('boom') })
    renderForecastingRoutes('/projects/tropical/forecasting')

    expect(
      screen.getByText(
        'Forecast information could not be loaded. Check the local data connection and try again.',
      ),
    ).toBeInTheDocument()
  })

  it('scopes forecast reads to the route project key (non-tropical)', () => {
    setForecast({ outputs: [] })
    renderForecastingRoutes('/projects/harbor/forecasting')

    const keys = issuedQueryKeys()
    expect(keys).toContainEqual(['forecast', 'db-outputs', 'harbor'])
    // Never reads the hard-coded default project when the route project differs.
    expect(keys.some((key) => key[0] === 'forecast' && key[2] === 'tropical')).toBe(false)
    // Never reads with a missing/undefined project key.
    expect(
      keys.some((key) => key[0] === 'forecast' && (key[2] === undefined || key[2] === '')),
    ).toBe(false)
  })

  it('does not issue forecast reads for an unknown project', () => {
    renderForecastingRoutes('/projects/unknown/forecasting')

    expect(issuedQueryKeys()).toEqual([['projects']])
    expect(screen.getByText('Project not found')).toBeInTheDocument()
  })

  it('never invokes forecast generation from the forecasting tab', () => {
    const dbNative = vi.spyOn(api, 'startForecastDbNativeRun')
    const legacyRun = vi.spyOn(api, 'startForecastRun')
    setForecast({ outputs: availableOutput.outputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting')

    expect(screen.getByRole('heading', { name: 'Create Forecast' })).toBeInTheDocument()
    expect(
      screen.getByText('Project-specific forecast creation will be wired in a future pass.'),
    ).toBeInTheDocument()
    expect(dbNative).not.toHaveBeenCalled()
    expect(legacyRun).not.toHaveBeenCalled()
    dbNative.mockRestore()
    legacyRun.mockRestore()
  })

  it('links to the monthly forecasting route', () => {
    setForecast({ outputs: [] })
    renderForecastingRoutes('/projects/tropical/forecasting')

    expect(screen.getByRole('heading', { name: 'Monthly Forecasting' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open' })).toHaveAttribute(
      'href',
      '/projects/tropical/forecasting/monthly',
    )
  })

  it('renders the monthly forecasting route without the dashboard content', () => {
    setForecast({ outputs: [] })
    renderForecastingRoutes('/projects/tropical/forecasting/monthly')

    expect(screen.getByRole('heading', { name: 'Monthly Forecasting' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to Forecasting' })).toHaveAttribute(
      'href',
      '/projects/tropical/forecasting',
    )

    // The monthly route must not render the main Forecasting dashboard content.
    expect(screen.queryByRole('heading', { name: 'Create Forecast' })).not.toBeInTheDocument()
    expect(
      screen.queryByText(
        'Review forecast status, latest forecast output, and project-specific forecasting tools.',
      ),
    ).not.toBeInTheDocument()
  })

  it('keeps /projects/all on the legacy aggregate route, not captured as a project key', () => {
    renderForecastingRoutes('/projects/all')

    expect(screen.getByText('Legacy aggregate overview.')).toBeInTheDocument()
    expect(screen.queryByText('Project not found')).not.toBeInTheDocument()
  })

  it('omits forbidden implementation copy from the forecasting page', () => {
    setForecast({ outputs: availableOutput.outputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting')

    const text = document.body.textContent || ''
    for (const forbidden of [
      'read model',
      'procore_ep_projects',
      'projection',
      'raw payload',
      'JSON',
      'source package',
      '/Users/',
    ]) {
      expect(text).not.toContain(forbidden)
    }
  })
})
