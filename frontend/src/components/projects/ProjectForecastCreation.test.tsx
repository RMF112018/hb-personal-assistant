import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectDashboardPage } from '../../pages/ProjectDashboardPage'
import { ProjectForecastingPage } from '../../pages/ProjectForecastingPage'
import { ProjectOverviewPage } from '../../pages/ProjectOverviewPage'
import { api } from '../../lib/api'

const useQueryMock = vi.fn()
const invalidateSpy = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[]; queryFn: () => unknown; enabled?: boolean }) =>
    useQueryMock(options),
  useQueryClient: () => ({ invalidateQueries: invalidateSpy }),
}))

// The embedded assumptions section runs its own project-scoped queries/writes; stub it so these
// tests stay focused on the creation flow (the section is exercised in its own suite).
vi.mock('../forecast/ForecastAssumptionsSection', () => ({
  ForecastAssumptionsSection: () => null,
}))

const projectsResponse = {
  surface: 'analytics.projects.list',
  projects: [
    { project_key: 'tropical', display_name: 'Tropical Resort', state_code: 'FL', zip: '33401' },
    { project_key: 'harbor', display_name: 'Harbor Tower', state_code: 'FL', zip: '33101' },
  ],
  guardrails: { read_only: true },
}

const legacyOverview = { summary: 'Legacy aggregate overview.', project_count: 2 }

const validDefaults = {
  project_key: 'harbor',
  forecast_start_date: null,
  forecast_cutoff_date: null,
  forecast_cutoff_date_basis: null,
  actuals_start_month: '2026-01',
  actuals_through_month: '2026-05',
  forecast_start_month: '2026-06',
  forecast_end_month: '2026-10',
  warnings: [],
}

let dateDefaults: unknown

function mockQueries() {
  useQueryMock.mockImplementation((options: { queryKey: unknown[] }) => {
    const key = options.queryKey
    if (key[0] === 'projects') {
      return { data: projectsResponse, isLoading: false, error: null, refetch: vi.fn() }
    }
    if (key[0] === 'project') {
      return { data: legacyOverview, isLoading: false, error: null }
    }
    if (key[0] === 'forecast' && key[1] === 'generation' && key[2] === 'date-defaults') {
      return { data: dateDefaults, isLoading: false, error: null }
    }
    if (key[0] === 'forecast' && key[1] === 'db-outputs') {
      return { data: { outputs: [] }, isLoading: false, error: null, refetch: vi.fn() }
    }
    return { data: undefined, isLoading: false, error: null, refetch: vi.fn() }
  })
}

function renderRoutes(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/projects" element={<div>Projects list</div>} />
        <Route path="/projects/all" element={<ProjectDashboardPage />} />
        <Route path="/projects/:projectKey" element={<ProjectOverviewPage />} />
        <Route path="/projects/:projectKey/forecasting" element={<ProjectForecastingPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

function issuedQueryKeys() {
  return useQueryMock.mock.calls.map(([options]) => options.queryKey)
}

function openModal() {
  fireEvent.click(screen.getByRole('button', { name: 'Create Forecast' }))
}

describe('Project forecast creation', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    invalidateSpy.mockReset()
    dateDefaults = null
    mockQueries()
  })

  it('renders inside the shell with the forecasting tab active', () => {
    renderRoutes('/projects/harbor/forecasting')

    expect(screen.getByText('Project workspace')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Harbor Tower' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Forecasting' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Overview' })).not.toHaveAttribute('aria-current')
  })

  it('renders a Create Forecast entry point and opens a project-scoped modal on click', () => {
    const dbNative = vi.spyOn(api, 'startForecastDbNativeRun').mockResolvedValue({} as never)
    renderRoutes('/projects/harbor/forecasting')

    expect(screen.getByRole('heading', { name: 'Create Forecast' })).toBeInTheDocument()
    expect(
      screen.getByText(
        'Create a new forecast run for this project using the selected forecast window and assumptions.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Create forecast —/)).not.toBeInTheDocument()

    openModal()

    // Modal is scoped to the route project; no other project leaks in (no picker).
    expect(screen.getByText('Create forecast — Harbor Tower')).toBeInTheDocument()
    expect(screen.queryByText('Tropical Resort')).not.toBeInTheDocument()
    // Opening never submits.
    expect(dbNative).not.toHaveBeenCalled()
    dbNative.mockRestore()
  })

  it('closes the modal on Cancel without submitting', () => {
    const dbNative = vi.spyOn(api, 'startForecastDbNativeRun').mockResolvedValue({} as never)
    renderRoutes('/projects/harbor/forecasting')

    openModal()
    expect(screen.getByText('Create forecast — Harbor Tower')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByText('Create forecast — Harbor Tower')).not.toBeInTheDocument()
    expect(dbNative).not.toHaveBeenCalled()
    dbNative.mockRestore()
  })

  it('submits the DB-native run scoped to the route project key (non-tropical)', async () => {
    dateDefaults = validDefaults
    const dbNative = vi.spyOn(api, 'startForecastDbNativeRun').mockResolvedValue({
      request_id: 'req-1',
      request_status: 'completed',
      db_persisted: true,
      persisted_output_ids: ['fout-9'],
      failure_code: null,
      failure_message: null,
    } as never)

    renderRoutes('/projects/harbor/forecasting')
    openModal()
    // Required window fields render.
    expect(screen.getByText('Actuals start month')).toBeInTheDocument()
    expect(screen.getByText('Forecast end month')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Submit' }))

    await waitFor(() =>
      expect(dbNative).toHaveBeenCalledWith({
        project_key: 'harbor',
        forecast_start_date: null,
        forecast_cutoff_date: null,
        forecast_cutoff_date_basis: null,
        actuals_start_month: '2026-01',
        actuals_through_month: '2026-05',
        forecast_start_month: '2026-06',
        forecast_end_month: '2026-10',
      }),
    )
    expect(dbNative).toHaveBeenCalledTimes(1)
    // Never the hard-coded default project.
    expect(dbNative.mock.calls[0][0].project_key).not.toBe('tropical')
    // Project-scoped invalidation + modal closes on success.
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['forecast', 'db-outputs', 'harbor'] }),
    )
    await waitFor(() =>
      expect(screen.queryByText('Create forecast — Harbor Tower')).not.toBeInTheDocument(),
    )
    dbNative.mockRestore()
  })

  it('blocks submit and shows validation copy when the window is incomplete', () => {
    dateDefaults = null // no schedule-derived defaults → blank window
    const dbNative = vi.spyOn(api, 'startForecastDbNativeRun').mockResolvedValue({} as never)
    renderRoutes('/projects/harbor/forecasting')

    openModal()
    expect(
      screen.getByText('Select all four month windows to create a forecast.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Submit' })).toBeDisabled()
    expect(dbNative).not.toHaveBeenCalled()
    dbNative.mockRestore()
  })

  it('surfaces a business-facing error when creation is rejected', async () => {
    dateDefaults = validDefaults
    const dbNative = vi.spyOn(api, 'startForecastDbNativeRun').mockResolvedValue({
      request_id: 'req-2',
      request_status: 'rejected',
      db_persisted: false,
      persisted_output_ids: [],
      failure_code: 'generation_rejected',
      failure_message: 'Forecast generation was rejected for this project.',
    } as never)

    renderRoutes('/projects/harbor/forecasting')
    openModal()
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }))

    await waitFor(() =>
      expect(
        screen.getByText('Forecast generation was rejected for this project.'),
      ).toBeInTheDocument(),
    )
    // Modal stays open; no success refresh.
    expect(screen.getByText('Create forecast — Harbor Tower')).toBeInTheDocument()
    expect(invalidateSpy).not.toHaveBeenCalled()
    dbNative.mockRestore()
  })

  it('adds no export/download control to the creation flow', () => {
    dateDefaults = validDefaults
    const dbNative = vi.spyOn(api, 'startForecastDbNativeRun').mockResolvedValue({} as never)
    renderRoutes('/projects/harbor/forecasting')
    openModal()

    expect(
      screen.queryByRole('button', { name: /export|download|csv|excel/i }),
    ).not.toBeInTheDocument()
    dbNative.mockRestore()
  })

  it('does not mount the creation card or call generation/date APIs for an unknown project', () => {
    const dbNative = vi.spyOn(api, 'startForecastDbNativeRun').mockResolvedValue({} as never)
    renderRoutes('/projects/unknown/forecasting')

    expect(screen.getByText('Project not found')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Create Forecast' })).not.toBeInTheDocument()
    // No date-defaults / generation read fired (card never mounted).
    expect(issuedQueryKeys().some((key) => key[0] === 'forecast' && key[1] === 'generation')).toBe(
      false,
    )
    expect(dbNative).not.toHaveBeenCalled()
    dbNative.mockRestore()
  })

  it('keeps /projects/all on the legacy aggregate route, not captured as a project key', () => {
    renderRoutes('/projects/all')

    expect(screen.getByText('Legacy aggregate overview.')).toBeInTheDocument()
    expect(screen.queryByText('Project not found')).not.toBeInTheDocument()
  })

  it('omits forbidden implementation copy from the creation modal', () => {
    dateDefaults = validDefaults
    const dbNative = vi.spyOn(api, 'startForecastDbNativeRun').mockResolvedValue({} as never)
    renderRoutes('/projects/harbor/forecasting')
    openModal()

    const text = document.body.textContent || ''
    for (const forbidden of [
      'read model',
      'procore_ep_projects',
      'projection',
      'raw payload',
      'JSON',
      'source package',
      '/Users/',
      'stack trace',
    ]) {
      expect(text).not.toContain(forbidden)
    }
    dbNative.mockRestore()
  })
})
