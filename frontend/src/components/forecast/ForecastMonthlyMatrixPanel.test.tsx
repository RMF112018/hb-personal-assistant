import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ForecastDbMonthlyTable } from '../../lib/api'
import { ForecastMonthlyMatrixPanel } from './ForecastMonthlyMatrixPanel'

const TABLE: ForecastDbMonthlyTable = {
  surface: 'analytics.forecast_run_readmodel.monthly_table',
  output_id: 'fout-1',
  project_key: 'tropical',
  status: 'ready',
  actuals_start_month: '2026-01',
  actuals_through_month: '2026-01',
  forecast_start_month: '2026-02',
  forecast_end_month: '2026-02',
  months: [
    { month: '2026-01', label: 'Jan 2026', value_type: 'actual' },
    { month: '2026-02', label: 'Feb 2026', value_type: 'forecast' },
  ],
  rows: [
    {
      budget_code_key: 'k-lab',
      budget_code: '1000.03-01-1000.LAB',
      cost_code: '03-01-1000',
      cost_type: 'LAB',
      cost_category: 'Preconstruction',
      projected_budget: '100000.00',
      projected_budget_source: 'procore_ep_budget_detail_rows',
      projected_budget_source_warning: null,
      month_values: { '2026-01': '1000.00', '2026-02': '2500.00' },
      completed_to_date: '1000.00',
      forecast_to_complete: '2500.00',
      estimated_at_completion: '3500.00',
      variance_to_budget: '96500.00',
      confidence: 'medium',
      method_code: 'even_spread',
      reason_codes: [],
    },
    {
      budget_code_key: 'k-mat',
      budget_code: '2000.03-01-2000.MAT',
      cost_code: '03-01-2000',
      cost_type: 'MAT',
      cost_category: 'Cost of Work',
      projected_budget: '50000.00',
      projected_budget_source: 'procore_ep_budget_detail_rows',
      projected_budget_source_warning: null,
      month_values: { '2026-01': '500.00', '2026-02': '1000.00' },
      completed_to_date: '500.00',
      forecast_to_complete: '1000.00',
      estimated_at_completion: '1500.00',
      variance_to_budget: '48500.00',
      confidence: 'medium',
      method_code: 'even_spread',
      reason_codes: [],
    },
  ],
  total_row: {
    projected_budget: '150000.00',
    month_values: { '2026-01': '1500.00', '2026-02': '3500.00' },
    completed_to_date: '1500.00',
    forecast_to_complete: '3500.00',
    estimated_at_completion: '5000.00',
    variance_to_budget: '145000.00',
  },
  month_window_warnings: [],
}

vi.mock('../../lib/api', () => ({
  api: {
    getForecastDbOutputs: vi.fn(() => Promise.resolve({ outputs: [] })),
    getForecastDbMonthlyTable: vi.fn(() => Promise.resolve(TABLE)),
  },
}))

// Mock the side-effectful writers so the export-control tests assert wiring without touching exceljs/DOM.
vi.mock('./forecastMonthlyExportWriters', () => ({
  exportCsv: vi.fn(),
  exportXlsx: vi.fn(() => Promise.resolve()),
}))

// The mocked modules (import AFTER vi.mock; vitest hoists the mocks).
import { api } from '../../lib/api'
import { exportCsv, exportXlsx } from './forecastMonthlyExportWriters'

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(
    <QueryClientProvider client={qc}>
      <ForecastMonthlyMatrixPanel project="tropical" activeOutputId="fout-1" />
    </QueryClientProvider>,
  )
}

describe('ForecastMonthlyMatrixPanel', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('fetches the monthly table once and does NOT refetch on table interactions', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderPanel()
    await waitFor(() => expect(screen.getByText('03-01-1000')).toBeInTheDocument())

    // Table interactions are client-local — they must never re-hit the endpoint.
    fireEvent.change(screen.getByLabelText('Search the monthly forecast table'), { target: { value: 'LAB' } })
    fireEvent.change(screen.getByLabelText('Search the monthly forecast table'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('Filter by Cost Code'), { target: { value: '2000' } })
    fireEvent.change(screen.getByLabelText('Filter by Cost Code'), { target: { value: '' } })
    // Grouping (dropdown) + expand/collapse are local table state — they must not re-hit the endpoint.
    fireEvent.change(screen.getByLabelText('Group rows'), { target: { value: 'cost_type' } })
    fireEvent.change(screen.getByLabelText('Group rows'), { target: { value: 'cost_category' } })
    fireEvent.click(screen.getByRole('button', { name: /Cost Category: Cost of Work/ }))
    fireEvent.change(screen.getByLabelText('Group rows'), { target: { value: 'none' } })
    await waitFor(() => {})

    expect(vi.mocked(api.getForecastDbMonthlyTable)).toHaveBeenCalledTimes(1)
    // The interaction-resolved-output path never needs the project output list here.
    expect(vi.mocked(api.getForecastDbOutputs)).not.toHaveBeenCalled()
    const loopLogged = errorSpy.mock.calls.some((args) =>
      args.some((a) => typeof a === 'string' && /Maximum update depth/i.test(a)),
    )
    expect(loopLogged).toBe(false)
  })

  it('toggles full screen on this panel only and never refetches', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { container } = renderPanel()
    await waitFor(() => expect(screen.getByText('03-01-1000')).toBeInTheDocument())

    // Not full-screen initially.
    expect(container.querySelector('.forecast-monthly-panel.is-fullscreen')).toBeNull()
    expect(container.querySelector('.forecast-monthly-matrix.is-fullscreen')).toBeNull()

    // Enter full screen.
    fireEvent.click(screen.getByRole('button', { name: 'Full screen' }))
    expect(container.querySelector('.forecast-monthly-panel.is-fullscreen')).not.toBeNull()
    expect(container.querySelector('.forecast-monthly-matrix.is-fullscreen')).not.toBeNull()

    // Exit full screen.
    fireEvent.click(screen.getByRole('button', { name: 'Exit full screen' }))
    expect(container.querySelector('.forecast-monthly-panel.is-fullscreen')).toBeNull()

    // Toggling is pure presentation — the table endpoint is hit exactly once.
    expect(vi.mocked(api.getForecastDbMonthlyTable)).toHaveBeenCalledTimes(1)
    const loopLogged = errorSpy.mock.calls.some((args) =>
      args.some((a) => typeof a === 'string' && /Maximum update depth/i.test(a)),
    )
    expect(loopLogged).toBe(false)
  })

  it('renders the Export control when the monthly table is ready', async () => {
    renderPanel()
    await waitFor(() => expect(screen.getByText('03-01-1000')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Export' })).toBeEnabled()
  })

  it('CSV export invokes the writer without re-fetching the table', async () => {
    renderPanel()
    await waitFor(() => expect(screen.getByText('03-01-1000')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Export' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'CSV' }))

    expect(vi.mocked(exportCsv)).toHaveBeenCalledTimes(1)
    const payload = vi.mocked(exportCsv).mock.calls[0][0]
    expect(payload.outputId).toBe('fout-1')
    expect(payload.rows.some((r) => r.rowType === 'total')).toBe(true)
    // Export reads the already-loaded view; it must not re-hit the endpoint.
    expect(vi.mocked(api.getForecastDbMonthlyTable)).toHaveBeenCalledTimes(1)
  })

  it('Excel export invokes the workbook writer', async () => {
    renderPanel()
    await waitFor(() => expect(screen.getByText('03-01-1000')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Export' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Excel' }))

    await waitFor(() => expect(vi.mocked(exportXlsx)).toHaveBeenCalledTimes(1))
    expect(vi.mocked(api.getForecastDbMonthlyTable)).toHaveBeenCalledTimes(1)
  })

  it('shows PDF as disabled/deferred with explanatory copy', async () => {
    renderPanel()
    await waitFor(() => expect(screen.getByText('03-01-1000')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Export' }))
    // PDF is not an actionable menu item; the deferred guidance is shown instead.
    expect(screen.queryByRole('menuitem', { name: 'PDF' })).toBeNull()
    expect(screen.getByText(/PDF export is not available for wide monthly forecasts yet/i)).toBeInTheDocument()
  })

  it('export still works after toggling full screen and logs no update-loop error', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderPanel()
    await waitFor(() => expect(screen.getByText('03-01-1000')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Full screen' }))
    fireEvent.click(screen.getByRole('button', { name: 'Export' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'CSV' }))

    expect(vi.mocked(exportCsv)).toHaveBeenCalledTimes(1)
    expect(vi.mocked(api.getForecastDbMonthlyTable)).toHaveBeenCalledTimes(1)
    const loopLogged = errorSpy.mock.calls.some((args) =>
      args.some((a) => typeof a === 'string' && /Maximum update depth/i.test(a)),
    )
    expect(loopLogged).toBe(false)
  })
})
