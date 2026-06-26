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
  useQuery: (options: { queryKey: unknown[]; queryFn: () => unknown; enabled?: boolean }) =>
    useQueryMock(options),
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

const readyTable = {
  surface: 'analytics.forecast.monthly-table',
  output_id: 'fout-1',
  project_key: 'tropical',
  status: 'ready' as const,
  months: [{ month: '2026-06', label: 'Jun 2026', value_type: 'forecast' as const }],
  rows: [
    {
      budget_code_key: '01-100',
      budget_code: '01-100',
      cost_code: '01-100',
      cost_type: 'L',
      cost_category: 'Labor',
      projected_budget: '1000',
      projected_budget_source: null,
      projected_budget_source_warning: null,
      month_values: { '2026-06': '500' },
      completed_to_date: '500',
      forecast_to_complete: '500',
      estimated_at_completion: '1000',
      variance_to_budget: '0',
      confidence: null,
      method_code: null,
      reason_codes: [],
    },
  ],
  total_row: {
    projected_budget: '1000',
    month_values: { '2026-06': '500' },
    completed_to_date: '500',
    forecast_to_complete: '500',
    estimated_at_completion: '1000',
    variance_to_budget: '0',
  },
}

type MonthlyState = {
  outputsLoading: boolean
  outputsError: unknown
  outputs: Array<{ output_id: string; project_key: string; created_display: string | null }>
  monthlyLoading: boolean
  monthlyError: unknown
  monthly: unknown
}

let monthly: MonthlyState

function setMonthly(overrides: Partial<MonthlyState>) {
  monthly = {
    outputsLoading: false,
    outputsError: null,
    outputs: [],
    monthlyLoading: false,
    monthlyError: null,
    monthly: undefined,
    ...overrides,
  }
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
        data: monthly.outputsError ? undefined : { outputs: monthly.outputs },
        isLoading: monthly.outputsLoading,
        error: monthly.outputsError,
        refetch: vi.fn(),
      }
    }
    if (key[0] === 'forecast' && key[1] === 'db-monthly-table') {
      return {
        data: monthly.monthlyError ? undefined : monthly.monthly,
        isLoading: monthly.monthlyLoading,
        error: monthly.monthlyError,
        refetch: vi.fn(),
      }
    }
    return { data: null, isLoading: false, error: null, refetch: vi.fn() }
  })
}

function renderMonthlyRoutes(path: string) {
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

// Only count queries react-query would actually issue: `enabled: false` queries never run, so the
// monthly-table query must not be counted when there is no resolved output id.
function issuedQueryKeys() {
  return useQueryMock.mock.calls
    .map(([options]) => options)
    .filter((options) => options.enabled !== false)
    .map((options) => options.queryKey)
}

describe('Project Monthly Forecasting page', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    setMonthly({})
    mockQueries()
  })

  it('renders inside the project workspace shell with identity, nav, and a back link', () => {
    setMonthly({ outputs: [] })
    renderMonthlyRoutes('/projects/tropical/forecasting/monthly')

    expect(screen.getByText('Project workspace')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Tropical Resort' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Monthly Forecasting' })).toBeInTheDocument()
    expect(
      screen.getByText('Review month-by-month forecast values for this project.'),
    ).toBeInTheDocument()
    // Workspace nav remains visible.
    expect(screen.getByRole('link', { name: 'Forecasting' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to Forecasting' })).toHaveAttribute(
      'href',
      '/projects/tropical/forecasting',
    )
  })

  it('renders the monthly matrix when the latest output has monthly values', () => {
    setMonthly({
      outputs: [{ output_id: 'fout-1', project_key: 'tropical', created_display: 'Jun 19, 2026' }],
      monthly: readyTable,
    })
    renderMonthlyRoutes('/projects/tropical/forecasting/monthly')

    expect(screen.getByText('01-100')).toBeInTheDocument()
    // Month column header from the matrix.
    expect(screen.getByText('Jun 2026')).toBeInTheDocument()
    expect(screen.getByText('Project total')).toBeInTheDocument()
  })

  it('renders a loading state while monthly forecast information loads', () => {
    setMonthly({ outputsLoading: true })
    renderMonthlyRoutes('/projects/tropical/forecasting/monthly')

    expect(screen.getByText('Loading monthly forecast information…')).toBeInTheDocument()
  })

  it('renders a business-facing error state when the monthly read fails', () => {
    setMonthly({ outputsError: new Error('boom') })
    renderMonthlyRoutes('/projects/tropical/forecasting/monthly')

    expect(
      screen.getByText(
        'Monthly forecast information could not be loaded. Check the local data connection and try again.',
      ),
    ).toBeInTheDocument()
  })

  it('renders the no-output state when the project has no forecast output', () => {
    setMonthly({ outputs: [] })
    renderMonthlyRoutes('/projects/tropical/forecasting/monthly')

    expect(
      screen.getByText('No forecast output is available for this project yet.'),
    ).toBeInTheDocument()
  })

  it('renders the no-monthly-values state for a legacy output without month windows', () => {
    setMonthly({
      outputs: [{ output_id: 'fout-1', project_key: 'tropical', created_display: 'Jun 19, 2026' }],
      monthly: { ...readyTable, status: 'legacy_output_no_operator_window' },
    })
    renderMonthlyRoutes('/projects/tropical/forecasting/monthly')

    expect(
      screen.getByText('No monthly forecast values are available for this forecast output yet.'),
    ).toBeInTheDocument()
  })

  it('renders the no-monthly-values state when the output has no rows', () => {
    setMonthly({
      outputs: [{ output_id: 'fout-1', project_key: 'tropical', created_display: 'Jun 19, 2026' }],
      monthly: { ...readyTable, rows: [] },
    })
    renderMonthlyRoutes('/projects/tropical/forecasting/monthly')

    expect(
      screen.getByText('No monthly forecast values are available for this forecast output yet.'),
    ).toBeInTheDocument()
  })

  it('scopes the outputs read to the route project key (non-tropical)', () => {
    setMonthly({ outputs: [] })
    renderMonthlyRoutes('/projects/harbor/forecasting/monthly')

    const keys = issuedQueryKeys()
    expect(keys).toContainEqual(['forecast', 'db-outputs', 'harbor'])
    // Never reads the hard-coded default project when the route project differs.
    expect(keys.some((key) => key[0] === 'forecast' && key[1] === 'db-outputs' && key[2] === 'tropical')).toBe(
      false,
    )
    // Never reads outputs with a missing/undefined project key.
    expect(
      keys.some(
        (key) =>
          key[0] === 'forecast' && key[1] === 'db-outputs' && (key[2] === undefined || key[2] === ''),
      ),
    ).toBe(false)
    // With no resolved output id, the monthly-table query is disabled and must not be counted.
    expect(keys.some((key) => key[0] === 'forecast' && key[1] === 'db-monthly-table')).toBe(false)
  })

  it('issues the monthly-table read only once an output id is resolved', () => {
    setMonthly({
      outputs: [{ output_id: 'fout-1', project_key: 'tropical', created_display: 'Jun 19, 2026' }],
      monthly: readyTable,
    })
    renderMonthlyRoutes('/projects/tropical/forecasting/monthly')

    expect(issuedQueryKeys()).toContainEqual(['forecast', 'db-monthly-table', 'fout-1'])
  })

  it('does not issue forecast reads for an unknown project', () => {
    renderMonthlyRoutes('/projects/unknown/forecasting/monthly')

    expect(issuedQueryKeys()).toEqual([['projects']])
    expect(screen.getByText('Project not found')).toBeInTheDocument()
  })

  it('never invokes forecast generation and adds no export control', () => {
    const dbNative = vi.spyOn(api, 'startForecastDbNativeRun')
    const legacyRun = vi.spyOn(api, 'startForecastRun')
    setMonthly({
      outputs: [{ output_id: 'fout-1', project_key: 'tropical', created_display: 'Jun 19, 2026' }],
      monthly: readyTable,
    })
    renderMonthlyRoutes('/projects/tropical/forecasting/monthly')

    expect(dbNative).not.toHaveBeenCalled()
    expect(legacyRun).not.toHaveBeenCalled()
    expect(
      screen.queryByRole('button', { name: /export|download|csv|excel|full screen/i }),
    ).not.toBeInTheDocument()
    dbNative.mockRestore()
    legacyRun.mockRestore()
  })

  it('keeps /projects/all on the legacy aggregate route, not captured as a project key', () => {
    renderMonthlyRoutes('/projects/all')

    expect(screen.getByText('Legacy aggregate overview.')).toBeInTheDocument()
    expect(screen.queryByText('Project not found')).not.toBeInTheDocument()
  })

  it('omits forbidden implementation copy from the monthly page', () => {
    setMonthly({
      outputs: [{ output_id: 'fout-1', project_key: 'tropical', created_display: 'Jun 19, 2026' }],
      monthly: readyTable,
    })
    renderMonthlyRoutes('/projects/tropical/forecasting/monthly')

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
