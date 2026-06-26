import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectDashboardPage } from './ProjectDashboardPage'
import { ProjectForecastingPage } from './ProjectForecastingPage'
import { ProjectMonthlyForecastingPage } from './ProjectMonthlyForecastingPage'
import { ProjectOverviewPage } from './ProjectOverviewPage'
import { api } from '../lib/api'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[]; queryFn: () => unknown }) => useQueryMock(options),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
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

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location-search">{location.search}</div>
}

function renderForecastingRoutes(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LocationProbe />
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

  it('renders the Forecast Dashboard for the selected output', () => {
    setForecast({ outputs: availableOutput.outputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting')

    expect(screen.getByRole('heading', { name: 'Forecast Dashboard' })).toBeInTheDocument()
    expect(screen.getByText('Budget vs EAC')).toBeInTheDocument()
    expect(screen.getByText('Cost Position')).toBeInTheDocument()
  })

  it('renders the no-output state when the project has no forecast output', () => {
    setForecast({ outputs: [] })
    renderForecastingRoutes('/projects/tropical/forecasting')

    // Both the summary and the dashboard honestly report the no-output state.
    expect(
      screen.getAllByText('No forecast output is available for this project yet.').length,
    ).toBeGreaterThan(0)
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

  const twoOutputs = [
    {
      output_id: 'out-002',
      project_key: 'tropical',
      created_display: 'Jun 26, 2026',
      estimated_final_cost: '61366869',
      cost_to_complete: null,
      variance_to_budget: null,
      variance_to_prior_forecast: null,
    },
    {
      output_id: 'out-001',
      project_key: 'tropical',
      created_display: 'May 10, 2026',
      estimated_final_cost: '60000000',
      cost_to_complete: null,
      variance_to_budget: null,
      variance_to_prior_forecast: null,
    },
  ]

  it('renders the Forecast History selector when outputs exist', () => {
    setForecast({ outputs: twoOutputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting')

    expect(screen.getByRole('heading', { name: 'Forecast History' })).toBeInTheDocument()
    expect(screen.getByText('Jun 26, 2026')).toBeInTheDocument()
    expect(screen.getByText('May 10, 2026')).toBeInTheDocument()
  })

  it('summary uses the latest output when no outputId is set', () => {
    setForecast({ outputs: twoOutputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting')

    const keys = issuedQueryKeys()
    expect(keys).toContainEqual(['forecast', 'db-output', 'out-002'])
    expect(keys).not.toContainEqual(['forecast', 'db-output', 'out-001'])
  })

  it('summary uses the requested valid output id', () => {
    setForecast({ outputs: twoOutputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting?outputId=out-001')

    expect(issuedQueryKeys()).toContainEqual(['forecast', 'db-output', 'out-001'])
  })

  it('warns and uses the latest output for an invalid outputId, never fetching it', () => {
    setForecast({ outputs: twoOutputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting?outputId=bogus-id')

    expect(
      screen.getByText(
        'The selected forecast output is not available for this project. Showing the latest available output.',
      ),
    ).toBeInTheDocument()
    const keys = issuedQueryKeys()
    expect(keys).toContainEqual(['forecast', 'db-output', 'out-002'])
    expect(keys.some((key) => key[1] === 'db-output' && key[2] === 'bogus-id')).toBe(false)
  })

  it('selecting an output updates the URL query parameter', () => {
    setForecast({ outputs: twoOutputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting')

    fireEvent.click(screen.getByRole('button', { name: /May 10, 2026/ }))
    expect(screen.getByTestId('location-search').textContent).toContain('outputId=out-001')
  })

  it('preserves the selected outputId in the Monthly Forecasting link', () => {
    setForecast({ outputs: twoOutputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting?outputId=out-001')

    expect(screen.getByRole('link', { name: 'Open' })).toHaveAttribute(
      'href',
      '/projects/tropical/forecasting/monthly?outputId=out-001',
    )
  })

  it('does not issue forecast reads for an unknown project', () => {
    renderForecastingRoutes('/projects/unknown/forecasting')

    expect(issuedQueryKeys()).toEqual([['projects']])
    expect(screen.getByText('Project not found')).toBeInTheDocument()
  })

  it('renders a real Create Forecast entry point that opens a modal without submitting', () => {
    const dbNative = vi.spyOn(api, 'startForecastDbNativeRun')
    const legacyRun = vi.spyOn(api, 'startForecastRun')
    setForecast({ outputs: availableOutput.outputs, detail: availableOutput.detail })
    renderForecastingRoutes('/projects/tropical/forecasting')

    expect(screen.getByRole('heading', { name: 'Create Forecast' })).toBeInTheDocument()
    expect(
      screen.getByText(
        'Create a new forecast run for this project using the selected forecast window and assumptions.',
      ),
    ).toBeInTheDocument()
    // Merely rendering the page never triggers generation.
    expect(dbNative).not.toHaveBeenCalled()

    // Clicking opens the modal (scoped to the route project) but does not submit.
    fireEvent.click(screen.getByRole('button', { name: 'Create Forecast' }))
    expect(screen.getByText('Create forecast — Tropical Resort')).toBeInTheDocument()
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
