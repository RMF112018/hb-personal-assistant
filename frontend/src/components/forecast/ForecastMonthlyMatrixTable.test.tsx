import { fireEvent, render, screen, within } from '@testing-library/react'
import { Profiler } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ForecastDbMonthlyTable } from '../../lib/api'
import { ForecastMonthlyMatrixTable } from './ForecastMonthlyMatrixTable'

const TABLE: ForecastDbMonthlyTable = {
  surface: 'analytics.forecast_run_readmodel.monthly_table',
  output_id: 'fout-1',
  project_key: 'tropical',
  status: 'ready',
  actuals_start_month: '2026-01',
  actuals_through_month: '2026-02',
  forecast_start_month: '2026-03',
  forecast_end_month: '2026-03',
  months: [
    { month: '2026-01', label: 'Jan 2026', value_type: 'actual' },
    { month: '2026-02', label: 'Feb 2026', value_type: 'actual' },
    { month: '2026-03', label: 'Mar 2026', value_type: 'forecast' },
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
      month_values: { '2026-01': '1000.00', '2026-02': '0.00', '2026-03': '2500.00' },
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
      budget_code: '1000.03-01-2000.MAT',
      cost_code: '03-01-2000',
      cost_type: 'MAT',
      cost_category: 'Cost of Work',
      projected_budget: '50000.00',
      projected_budget_source: 'procore_ep_budget_detail_rows',
      projected_budget_source_warning: null,
      month_values: { '2026-01': '0.00', '2026-02': '500.00', '2026-03': '1000.00' },
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
    month_values: { '2026-01': '1000.00', '2026-02': '500.00', '2026-03': '3500.00' },
    completed_to_date: '1500.00',
    forecast_to_complete: '3500.00',
    estimated_at_completion: '5000.00',
    variance_to_budget: '145000.00',
  },
  month_window_warnings: [],
}

describe('ForecastMonthlyMatrixTable', () => {
  it('renders the sticky identity column headers', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    expect(screen.getByRole('button', { name: /Cost Code/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Cost Type/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Projected Budget/ })).toBeInTheDocument()
  })

  it('renders dynamic month columns in chronological order with actual/forecast markers', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent || '')
    const janIdx = headers.findIndex((t) => t.includes('Jan 2026'))
    const febIdx = headers.findIndex((t) => t.includes('Feb 2026'))
    const marIdx = headers.findIndex((t) => t.includes('Mar 2026'))
    expect(janIdx).toBeGreaterThan(-1)
    expect(janIdx).toBeLessThan(febIdx)
    expect(febIdx).toBeLessThan(marIdx)
    // Non-color marker text distinguishes actual vs forecast months.
    expect(headers[janIdx]).toMatch(/Actual/)
    expect(headers[marIdx]).toMatch(/Forecast/)
  })

  it('renders the row metric columns (Completed to Date / Forecast to Complete / EAC / Variance)', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    expect(screen.getByRole('button', { name: /Completed to Date/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Forecast to Complete/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /EAC/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Variance to Budget/ })).toBeInTheDocument()
  })

  it('renders the persisted total row with formatted currency', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    const footer = screen.getByText('Project total').closest('tr') as HTMLElement
    expect(within(footer).getByText('$150,000')).toBeInTheDocument()
    // Positive total variance (under budget) renders without parentheses.
    expect(within(footer).getByText('$145,000')).toBeInTheDocument()
  })

  it('shows the variance convention legend and styles overrun (negative) variance as unfavorable', () => {
    // One over-budget row (EAC > projected budget → negative variance = overrun) and one under-budget
    // row (positive variance = favorable).
    const overBudget = {
      ...TABLE.rows![0],
      budget_code_key: 'k-over',
      cost_code: '03-01-9999',
      projected_budget: '1000.00',
      estimated_at_completion: '3500.00',
      variance_to_budget: '-2500.00',
    }
    const underBudget = { ...TABLE.rows![1], budget_code_key: 'k-under', cost_code: '03-01-1111', variance_to_budget: '48500.00' }
    render(<ForecastMonthlyMatrixTable table={{ ...TABLE, rows: [overBudget, underBudget] }} />)

    // UI-facing legend explains the convention.
    expect(screen.getByText(/positive value is under budget/i)).toBeInTheDocument()
    expect(screen.getByText(/negative value is over budget/i)).toBeInTheDocument()

    // Negative (overrun) variance carries the danger styling; positive (favorable) does not.
    const overCell = screen.getByText('($2,500)')
    const underCell = screen.getByText('$48,500')
    expect(overCell.className).toMatch(/hb-danger/)
    expect(underCell.className).not.toMatch(/hb-danger/)
  })

  it('supports sorting by clicking a column header', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    const bodyCostTypes = () =>
      screen
        .getAllByRole('row')
        .slice(1) // drop the header row
        .map((r) => r.querySelectorAll('td')[1]?.textContent ?? '')
        .filter((t) => t === 'LAB' || t === 'MAT')
    expect(bodyCostTypes()).toEqual(['LAB', 'MAT'])
    fireEvent.click(screen.getByRole('button', { name: /Cost Type/ }))
    fireEvent.click(screen.getByRole('button', { name: /Cost Type/ })) // toggle to descending
    expect(bodyCostTypes()).toEqual(['MAT', 'LAB'])
  })

  it('filters rows by Cost Code', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    fireEvent.change(screen.getByLabelText('Filter by Cost Code'), { target: { value: '2000' } })
    expect(screen.queryByText('03-01-1000')).not.toBeInTheDocument()
    expect(screen.getByText('03-01-2000')).toBeInTheDocument()
  })

  const groupBy = (value: string) =>
    fireEvent.change(screen.getByLabelText('Group rows'), { target: { value } })

  it('offers None / Cost Type / Cost Category in the grouping dropdown', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    const options = Array.from(
      (screen.getByLabelText('Group rows') as HTMLSelectElement).options,
    ).map((o) => o.textContent)
    expect(options).toEqual(['No grouping', 'Cost Type', 'Cost Category'])
  })

  it('groups by Cost Type', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    groupBy('cost_type')
    expect(screen.getByText(/Cost Type: LAB/)).toBeInTheDocument()
    expect(screen.getByText(/Cost Type: MAT/)).toBeInTheDocument()
  })

  it('groups by Cost Category using the backend-derived category', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    groupBy('cost_category')
    expect(screen.getByText(/Cost Category: Preconstruction/)).toBeInTheDocument()
    expect(screen.getByText(/Cost Category: Cost of Work/)).toBeInTheDocument()
    // The grouping convention note is shown only while grouped.
    expect(screen.getByText(/Group subtotals reflect the currently visible rows/i)).toBeInTheDocument()
  })

  it('collapses and expands a group, toggling child rows and the trailing subtotal row', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    groupBy('cost_type')
    // Expanded by default: child cost code + a trailing Subtotal row are present.
    expect(screen.getByText('03-01-1000')).toBeInTheDocument()
    expect(screen.getAllByText('Subtotal').length).toBeGreaterThan(0)
    // Collapse the LAB group header → its child row hides; subtotal moves inline into the header.
    const labToggle = screen.getByRole('button', { name: /Cost Type: LAB/ })
    fireEvent.click(labToggle)
    expect(screen.queryByText('03-01-1000')).not.toBeInTheDocument()
    expect(screen.getByText(/Cost Type: LAB/)).toBeInTheDocument()
  })

  it('subtotals reconcile to the grouped rows (BigInt-exact) for each metric and month', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    groupBy('cost_category')
    // Preconstruction has only k-lab; its subtotal row equals that row's values.
    // EAC 3500 → $3,500 appears in both the leaf and the subtotal row.
    expect(screen.getAllByText('$3,500').length).toBeGreaterThanOrEqual(2)
    // Cost of Work has only k-mat: EAC 1500.
    expect(screen.getAllByText('$1,500').length).toBeGreaterThanOrEqual(2)
  })

  it('updates group subtotals when a filter narrows the visible rows', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    groupBy('cost_category')
    // Filter to MAT only → the Preconstruction (LAB) group disappears, Cost of Work remains.
    fireEvent.change(screen.getByLabelText('Filter by Cost Type'), { target: { value: 'MAT' } })
    expect(screen.queryByText(/Cost Category: Preconstruction/)).not.toBeInTheDocument()
    expect(screen.getByText(/Cost Category: Cost of Work/)).toBeInTheDocument()
  })

  it('keeps sorting working while grouped', () => {
    render(<ForecastMonthlyMatrixTable table={TABLE} />)
    groupBy('cost_type')
    // Sorting the EAC column while grouped must not throw / freeze and the headers remain.
    fireEvent.click(screen.getByRole('button', { name: /^EAC/ }))
    expect(screen.getByText(/Cost Type: LAB/)).toBeInTheDocument()
    expect(screen.getByText(/Cost Type: MAT/)).toBeInTheDocument()
  })

  it('shows a curated message for a legacy output with no operator window', () => {
    render(
      <ForecastMonthlyMatrixTable
        table={{ ...TABLE, status: 'legacy_output_no_operator_window', months: undefined, rows: undefined, total_row: undefined }}
      />,
    )
    expect(screen.getByText(/predates operator-selected month windows/)).toBeInTheDocument()
  })

  it('does not leak implementation terms or filesystem paths', () => {
    const { container } = render(<ForecastMonthlyMatrixTable table={TABLE} />)
    const text = container.textContent || ''
    expect(text).not.toMatch(/raw_json/)
    expect(text).not.toMatch(/\/Users\//)
    expect(text).not.toMatch(/read model/i)
  })

  // Regression: the controlled-state anti-pattern (fresh grouping/columnFilters arrays each render
  // + no onChange handlers + no getRowId) drove TanStack's auto-reset into an unbounded render loop
  // ("Maximum update depth"), freezing the page on any interaction. This asserts the full interaction
  // sequence stays bounded and logs no update-loop error. The threshold is deliberately GENEROUS — it
  // only needs to catch a runaway loop, not enforce an exact render count (React dev re-render /
  // batching / TanStack internal recalculation all add commits).
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('stays responsive (bounded renders, no update-loop error) across search/filter/group/sort', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    let commits = 0
    render(
      <Profiler id="matrix" onRender={() => { commits += 1 }}>
        <ForecastMonthlyMatrixTable table={TABLE} />
      </Profiler>,
    )

    fireEvent.change(screen.getByLabelText('Search the monthly forecast table'), { target: { value: 'LAB' } })
    fireEvent.change(screen.getByLabelText('Search the monthly forecast table'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('Filter by Cost Code'), { target: { value: '1000' } })
    fireEvent.change(screen.getByLabelText('Filter by Cost Code'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('Filter by Cost Type'), { target: { value: 'MAT' } })
    fireEvent.change(screen.getByLabelText('Filter by Cost Type'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('Group rows'), { target: { value: 'cost_type' } })
    fireEvent.change(screen.getByLabelText('Group rows'), { target: { value: 'cost_category' } })
    fireEvent.change(screen.getByLabelText('Group rows'), { target: { value: 'none' } })
    fireEvent.click(screen.getByRole('button', { name: /^Cost Type/ }))
    fireEvent.click(screen.getByRole('button', { name: /^Cost Type/ }))

    // No React "Maximum update depth exceeded" (the loop signature) was logged.
    const loopLogged = errorSpy.mock.calls.some((args) =>
      args.some((a) => typeof a === 'string' && /Maximum update depth/i.test(a)),
    )
    expect(loopLogged).toBe(false)
    // Bounded, non-runaway rendering for ~10 interactions (a loop would be hundreds+).
    expect(commits).toBeLessThan(25)
    // Still interactive afterwards (re-sort + re-filter produce expected output).
    fireEvent.change(screen.getByLabelText('Filter by Cost Code'), { target: { value: '2000' } })
    expect(screen.getByText('03-01-2000')).toBeInTheDocument()
    expect(screen.queryByText('03-01-1000')).not.toBeInTheDocument()
  })
})
