import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastRunCenterPage } from './ForecastRunCenterPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

const startDbNativeMock = vi.fn().mockResolvedValue({})

vi.mock('../lib/api', () => ({
  api: {
    getForecastGenerationProjects: vi.fn(),
    getForecastGenerationRequests: vi.fn(),
    getForecastGenerationDateDefaults: vi.fn(),
    getForecastDbOutputs: vi.fn(),
    getForecastDbOutput: vi.fn(),
    getForecastDbNarratives: vi.fn(),
    getForecastDbDecisionSupport: vi.fn(),
    getForecastDbMonthlyTable: vi.fn(),
    getForecastOperatorAssumptions: vi.fn(),
    getForecastRequiredAssumptions: vi.fn(),
    startForecastDbNativeRun: (...args: unknown[]) => startDbNativeMock(...args),
    createForecastOperatorAssumption: vi.fn().mockResolvedValue({ ok: true }),
    editForecastOperatorAssumption: vi.fn().mockResolvedValue({ ok: true }),
    createForecastRequiredAssumption: vi.fn().mockResolvedValue({ ok: true }),
    setForecastRequiredAssumptionSatisfied: vi.fn().mockResolvedValue({ ok: true }),
  },
}))

const DATE_DEFAULTS = {
  project_key: 'tropical',
  forecast_start_date: null,
  forecast_start_date_basis: null,
  forecast_cutoff_date: null,
  forecast_cutoff_date_basis: null,
  schedule_version_key: null,
  schedule_data_date: null,
  schedule_data_date_basis: null,
  schedule_source_status: 'missing',
  actuals_start_month: '2026-01',
  actuals_through_month: '2026-05',
  forecast_start_month: '2026-06',
  forecast_end_month: '2026-10',
  forecast_end_month_basis: 'latest_schedule_finish_month',
  warnings: [],
}

const PROJECTS = [
  {
    project_key: 'tropical',
    display_name: 'Tropical Resort',
    has_prior_forecast_output: true,
    latest_forecast_status: 'generated',
    latest_forecast_display: 'Jun 19, 2026',
    readiness_status: 'ready',
    readiness_reasons: [],
  },
  {
    project_key: 'harbor',
    display_name: 'Harbor Tower',
    has_prior_forecast_output: false,
    latest_forecast_display: null,
    readiness_status: 'blocked',
    readiness_reasons: ['no_financial_basis'],
  },
  {
    project_key: 'summit',
    display_name: 'Summit Center',
    has_prior_forecast_output: false,
    latest_forecast_display: null,
    readiness_status: 'degraded',
    readiness_reasons: ['missing_config_snapshot', 'no_prior_forecast_output'],
  },
]

type MockOpts = {
  dateDefaults?: Record<string, unknown>
  requests?: unknown[]
  outputs?: unknown[]
  outputDetail?: Record<string, unknown>
  projects?: unknown[]
}

function installMock(opts: MockOpts = {}) {
  const dateDefaults = opts.dateDefaults ?? DATE_DEFAULTS
  const requests = opts.requests ?? []
  const outputs = opts.outputs ?? []
  const projects = opts.projects ?? PROJECTS
  useQueryMock.mockImplementation((q: { queryKey: unknown[] }) => {
    const k0 = q.queryKey[0]
    const kind = q.queryKey[1]
    const sub = q.queryKey[2]
    const ok = (data: unknown) => ({ data, isLoading: false, error: null, refetch: vi.fn() })
    if (kind === 'generation' && sub === 'projects') return ok({ projects })
    if (kind === 'generation' && sub === 'requests') return ok({ requests })
    if (kind === 'generation' && sub === 'date-defaults') return ok(dateDefaults)
    if (k0 === 'forecast' && kind === 'db-outputs') return ok({ outputs })
    if (k0 === 'forecast' && kind === 'db-output')
      return ok(opts.outputDetail ?? undefined)
    return ok(undefined)
  })
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ForecastRunCenterPage />
    </MemoryRouter>,
  )
}

function selectProject(key: string) {
  fireEvent.change(screen.getByLabelText('Forecast project'), { target: { value: key } })
}

function openCreateModal() {
  fireEvent.click(screen.getByRole('button', { name: 'Create Forecast' }))
}

describe('ForecastRunCenterPage layout + Create Forecast modal', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    startDbNativeMock.mockClear()
  })

  it('orders Construction Forecasting / Project before Forecast Context, with a Create Forecast button', () => {
    installMock()
    const { container } = renderPage()
    const text = container.textContent || ''
    expect(text.indexOf('Construction Forecasting')).toBeGreaterThanOrEqual(0)
    expect(text.indexOf('Construction Forecasting')).toBeLessThan(text.indexOf('Forecast context'))
    expect(screen.getByRole('button', { name: 'Create Forecast' })).toBeInTheDocument()
    // The old standalone Generate panel is gone.
    expect(screen.queryByText('Generate forecast')).not.toBeInTheDocument()
  })

  it('keeps date/month fields out of the page until the modal is opened, and opening runs no forecast', () => {
    installMock()
    renderPage()
    selectProject('tropical')
    // Fields live only in the modal.
    expect(screen.queryByLabelText('Forecast start date')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Actuals start month')).not.toBeInTheDocument()

    openCreateModal()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByLabelText('Forecast start date')).toBeInTheDocument()
    expect(screen.getByLabelText('Forecast cut-off date')).toBeInTheDocument()
    expect(screen.getByLabelText('Actuals start month')).toBeInTheDocument()
    expect(screen.getByLabelText('Actuals through month')).toBeInTheDocument()
    expect(screen.getByLabelText('Forecast start month')).toBeInTheDocument()
    expect(screen.getByLabelText('Forecast end month')).toBeInTheDocument()
    // Forecast Assumptions section is embedded in the modal.
    expect(screen.getByText('Forecast Assumptions')).toBeInTheDocument()
    // Opening the modal never triggers generation.
    expect(startDbNativeMock).not.toHaveBeenCalled()
  })

  it('closes on Cancel without generating', () => {
    installMock()
    renderPage()
    selectProject('tropical')
    openCreateModal()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(startDbNativeMock).not.toHaveBeenCalled()
  })

  it('closes on Escape and on backdrop click without generating', () => {
    installMock()
    const { container } = renderPage()
    selectProject('tropical')

    openCreateModal()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(startDbNativeMock).not.toHaveBeenCalled()

    openCreateModal()
    const backdrop = container.querySelector('.forecast-dialog-backdrop') as HTMLElement
    fireEvent.click(backdrop)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(startDbNativeMock).not.toHaveBeenCalled()
  })

  it('Submit calls the db-native run with dates + month windows, then closes on success', async () => {
    installMock()
    startDbNativeMock.mockResolvedValueOnce({
      request_id: 'req-ok',
      request_status: 'completed',
      db_persisted: true,
      persisted_output_ids: ['fout-1'],
    })
    renderPage()
    selectProject('tropical')
    openCreateModal()
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }))
    await waitFor(() =>
      expect(startDbNativeMock).toHaveBeenCalledWith({
        project_key: 'tropical',
        forecast_start_date: null,
        forecast_cutoff_date: null,
        forecast_cutoff_date_basis: null,
        actuals_start_month: '2026-01',
        actuals_through_month: '2026-05',
        forecast_start_month: '2026-06',
        forecast_end_month: '2026-10',
      }),
    )
    // Modal closes and the honest success banner appears on the page.
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByText(/Forecast generated and saved/i)).toBeInTheDocument()
  })

  it('threads operator-supplied dates (operator_supplied basis) into the request', async () => {
    installMock()
    startDbNativeMock.mockResolvedValueOnce({
      request_id: 'req-ok',
      request_status: 'completed',
      db_persisted: true,
    })
    renderPage()
    selectProject('tropical')
    openCreateModal()
    fireEvent.change(screen.getByLabelText('Forecast start date'), { target: { value: '2026-06-01' } })
    fireEvent.change(screen.getByLabelText('Forecast cut-off date'), { target: { value: '2026-06-24' } })
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }))
    await waitFor(() =>
      expect(startDbNativeMock).toHaveBeenCalledWith(
        expect.objectContaining({
          forecast_start_date: '2026-06-01',
          forecast_cutoff_date: '2026-06-24',
          forecast_cutoff_date_basis: 'operator_supplied',
        }),
      ),
    )
  })

  it('keeps the modal open with curated copy when the db-native run fails (no success banner, no path leak)', async () => {
    installMock()
    startDbNativeMock.mockResolvedValueOnce({
      request_id: 'req-x',
      request_status: 'failed',
      db_persisted: false,
      failure_code: 'run_output_db_write_disabled',
      failure_message: null,
    })
    const { container } = renderPage()
    selectProject('tropical')
    openCreateModal()
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }))
    expect(
      await screen.findByText(/Saving forecast output to the database is turned off/i),
    ).toBeInTheDocument()
    // Modal stays open; no success banner.
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.queryByText(/Forecast generated and saved/i)).not.toBeInTheDocument()
    const text = container.textContent || ''
    expect(text).not.toMatch(/run_output_db_write_disabled/)
    expect(text).not.toMatch(/\/Users\//)
  })

  it('does not claim success for a completed-but-not-persisted response', async () => {
    installMock()
    startDbNativeMock.mockResolvedValueOnce({
      request_id: 'req-np',
      request_status: 'completed',
      db_persisted: false,
      failure_code: 'db_native_output_certification_failed',
      failure_message: null,
    })
    renderPage()
    selectProject('tropical')
    openCreateModal()
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }))
    expect(
      await screen.findByText(/did not pass its safety checks and was not saved/i),
    ).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.queryByText(/Forecast generated and saved/i)).not.toBeInTheDocument()
  })

  it('honestly rejects a request_status="rejected" response', async () => {
    installMock()
    startDbNativeMock.mockResolvedValueOnce({
      request_id: 'req-r',
      request_status: 'rejected',
      db_persisted: false,
      failure_code: 'generation_rejected',
      failure_message: null,
    })
    renderPage()
    selectProject('tropical')
    openCreateModal()
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }))
    expect(await screen.findByText(/The request was rejected\./i)).toBeInTheDocument()
    expect(screen.queryByText(/Forecast generated and saved/i)).not.toBeInTheDocument()
  })

  it('disables the modal Submit when the forecast window overlaps the actuals window', () => {
    installMock()
    renderPage()
    selectProject('tropical')
    openCreateModal()
    fireEvent.change(screen.getByLabelText('Forecast start month'), { target: { value: '2026-05' } })
    expect(screen.getByRole('button', { name: 'Submit' })).toBeDisabled()
    expect(
      screen.getByText('The forecast window must start after the actuals window.'),
    ).toBeInTheDocument()
  })
})

describe('ForecastRunCenterPage project gating + context', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    startDbNativeMock.mockClear()
  })

  it('disables Create Forecast until a non-blocked project is selected', () => {
    installMock()
    renderPage()
    const button = () => screen.getByRole('button', { name: 'Create Forecast' })
    expect(button()).toBeDisabled()
    selectProject('harbor') // blocked
    expect(button()).toBeDisabled()
    expect(
      screen.getByText('No budget, cost, or baseline data is available to forecast from yet.'),
    ).toBeInTheDocument()
    selectProject('tropical') // ready
    expect(button()).not.toBeDisabled()
  })

  it('allows a degraded (sparse / first-run) project', () => {
    installMock()
    renderPage()
    selectProject('summit')
    expect(screen.getByRole('button', { name: 'Create Forecast' })).not.toBeDisabled()
  })

  it('renders the project selector with readiness in option labels', () => {
    installMock()
    renderPage()
    const select = screen.getByLabelText('Forecast project') as HTMLSelectElement
    const labels = Array.from(select.options).map((o) => o.textContent)
    expect(labels).toContain('Select a project')
    expect(labels).toContain('Tropical Resort')
    expect(labels).toContain('Harbor Tower — blocked')
    expect(labels).toContain('Summit Center — degraded')
  })

  it('renders Forecast Health inside Forecast Context (no standalone health panel)', () => {
    installMock()
    renderPage()
    selectProject('tropical')
    const context = screen.getByText('Forecast context').closest('section')!
    // The health card is inside the Forecast Context panel.
    expect(within(context).getByText('Forecast health')).toBeInTheDocument()
    // No outputs in the default mock → explicit verdict.
    expect(within(context).getByText('Blocked / no output')).toBeInTheDocument()
  })

  it('does not leak raw stamps or filesystem paths', () => {
    installMock()
    const { container } = renderPage()
    selectProject('tropical')
    const text = container.textContent || ''
    expect(text).not.toMatch(/\d{8}_\d{6}/)
    expect(text).not.toMatch(/\/Users\//)
  })
})

describe('ForecastRunCenterPage history modal', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    startDbNativeMock.mockClear()
  })

  it('opens a reconciled history modal from Forecast Context with saved outputs and request status', () => {
    installMock({
      outputs: [
        {
          output_id: 'fout-1',
          project_key: 'tropical',
          estimated_final_cost: '1700.00',
          cost_to_complete: '850.00',
          variance_to_budget: '200.00',
          variance_to_prior_forecast: null,
          created_display: 'Jun 25, 2026',
        },
        {
          output_id: 'fout-0',
          project_key: 'tropical',
          estimated_final_cost: '1650.00',
          cost_to_complete: null,
          variance_to_budget: null,
          variance_to_prior_forecast: null,
          created_display: 'Jun 18, 2026',
        },
      ],
      requests: [
        {
          request_id: 'req-1',
          run_id: null,
          project_key: 'tropical',
          generation_mode: 'db_config',
          generator_kind: 'comprehensive',
          request_status: 'failed',
          validation_status: 'valid',
          forecast_start_date: null,
          forecast_cutoff_date: null,
          forecast_cutoff_date_basis: null,
          readiness_status_at_request: 'ready',
          readiness_reasons: [],
          failure_code: 'source_package_missing',
          failure_message: null,
          created_utc: '2026-06-25T10:00:00+00:00',
          updated_utc: '2026-06-25T10:00:00+00:00',
        },
      ],
    })
    const { container } = renderPage()
    selectProject('tropical')
    fireEvent.click(screen.getByRole('button', { name: 'Forecast History' }))

    const dialog = within(screen.getByRole('dialog'))
    // Saved forecast outputs render; the non-latest one is selectable (View action), the latest
    // shows as currently viewed.
    expect(dialog.getAllByText('Saved forecast output')).toHaveLength(2)
    expect(dialog.getByRole('button', { name: 'View' })).toBeInTheDocument()
    expect(dialog.getByRole('button', { name: 'Viewing' })).toBeInTheDocument()
    // The failed request shows an honest status + curated, path-free copy; it is not a saved output.
    expect(dialog.getByText('Failed')).toBeInTheDocument()
    expect(dialog.getByText("Forecast source data isn't available yet.")).toBeInTheDocument()
    const text = container.textContent || ''
    expect(text).not.toMatch(/source_package_missing/)
  })

  it('selecting a saved output from history closes the modal', () => {
    installMock({
      outputs: [
        {
          output_id: 'fout-1',
          project_key: 'tropical',
          estimated_final_cost: '1700.00',
          cost_to_complete: null,
          variance_to_budget: null,
          variance_to_prior_forecast: null,
          created_display: 'Jun 25, 2026',
        },
        {
          output_id: 'fout-0',
          project_key: 'tropical',
          estimated_final_cost: '1650.00',
          cost_to_complete: null,
          variance_to_budget: null,
          variance_to_prior_forecast: null,
          created_display: 'Jun 18, 2026',
        },
      ],
    })
    renderPage()
    selectProject('tropical')
    fireEvent.click(screen.getByRole('button', { name: 'Forecast History' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'View' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
