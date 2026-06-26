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

// The mocked module (import AFTER vi.mock; vitest hoists the mock).
import { api } from '../../lib/api'

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
})
