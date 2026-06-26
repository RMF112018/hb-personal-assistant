import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectForecastDashboardVisualizations } from './ProjectForecastDashboardVisualizations'
import {
  buildBudgetVsEac,
  buildCostPosition,
  buildMonthlySeries,
  parseMoney,
} from './projectForecastDashboardData'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[]; queryFn: () => unknown; enabled?: boolean }) =>
    useQueryMock(options),
}))

const SUMMARY = {
  estimated_at_completion: '12500000',
  total_cost_to_date: '7000000',
  cost_to_complete: '5500000',
  current_budget: '12000000',
  budget_basis_label: 'Revised budget',
  budget_status: 'reconciled',
  variance_to_budget: '500000',
  variance_to_budget_status: 'computed',
  variance_to_prior_forecast: '0.00',
  variance_to_prior_forecast_status: 'computed',
  forecast_confidence_label: 'High',
  forecast_confidence_basis: null,
  forecast_maturity_label: 'Full context',
  forecast_maturity_basis: null,
  basis_limitations: [],
}

const MONTHLY_TABLE = {
  surface: 's',
  output_id: 'out-002',
  project_key: 'harbor',
  status: 'ready' as const,
  months: [
    { month: '2026-06', label: 'Jun 2026', value_type: 'actual' as const },
    { month: '2026-07', label: 'Jul 2026', value_type: 'forecast' as const },
  ],
  total_row: {
    projected_budget: '1000',
    month_values: { '2026-06': '500', '2026-07': '750' },
    completed_to_date: '500',
    forecast_to_complete: '750',
    estimated_at_completion: '1250',
    variance_to_budget: '0',
  },
}

type State = {
  outputsLoading: boolean
  outputsError: unknown
  outputs: Array<{ output_id: string; project_key: string; created_display: string | null }>
  detail: unknown
  detailError: unknown
  monthly: unknown
  monthlyError: unknown
}

let state: State

function setState(overrides: Partial<State>) {
  state = {
    outputsLoading: false,
    outputsError: null,
    outputs: [{ output_id: 'out-002', project_key: 'harbor', created_display: 'Jun 26, 2026' }],
    detail: { output_id: 'out-002', summary: SUMMARY },
    detailError: null,
    monthly: MONTHLY_TABLE,
    monthlyError: null,
    ...overrides,
  }
}

function mockQueries() {
  useQueryMock.mockImplementation((options: { queryKey: unknown[] }) => {
    const key = options.queryKey
    if (key[0] === 'forecast' && key[1] === 'db-outputs') {
      return {
        data: state.outputsError ? undefined : { outputs: state.outputs },
        isLoading: state.outputsLoading,
        error: state.outputsError,
        refetch: vi.fn(),
      }
    }
    if (key[0] === 'forecast' && key[1] === 'db-output') {
      return { data: state.detailError ? undefined : state.detail, isLoading: false, error: state.detailError }
    }
    if (key[0] === 'forecast' && key[1] === 'db-monthly-table') {
      return {
        data: state.monthlyError ? undefined : state.monthly,
        isLoading: false,
        error: state.monthlyError,
      }
    }
    return { data: undefined, isLoading: false, error: null, refetch: vi.fn() }
  })
}

function issuedQueryKeys() {
  return useQueryMock.mock.calls
    .map(([options]) => options)
    .filter((options) => options.enabled !== false)
    .map((options) => options.queryKey)
}

describe('projectForecastDashboardData', () => {
  it('parseMoney parses finite decimals and rejects invalid input', () => {
    expect(parseMoney('12500000')).toBe(12500000)
    expect(parseMoney('0.00')).toBe(0)
    expect(parseMoney(null)).toBeNull()
    expect(parseMoney('')).toBeNull()
    expect(parseMoney('NaN')).toBeNull()
    expect(parseMoney('not-a-number')).toBeNull()
  })

  it('buildBudgetVsEac needs both budget and EAC', () => {
    expect(buildBudgetVsEac(SUMMARY).hasData).toBe(true)
    expect(buildBudgetVsEac({ ...SUMMARY, current_budget: null }).hasData).toBe(false)
    expect(buildBudgetVsEac({ ...SUMMARY, estimated_at_completion: 'NaN' }).hasData).toBe(false)
  })

  it('buildCostPosition needs both cost-to-date and cost-to-complete', () => {
    expect(buildCostPosition(SUMMARY).hasData).toBe(true)
    expect(buildCostPosition({ ...SUMMARY, cost_to_complete: null }).hasData).toBe(false)
  })

  it('buildMonthlySeries omits non-finite months and keeps certified zeros', () => {
    const table = {
      ...MONTHLY_TABLE,
      months: [
        ...MONTHLY_TABLE.months,
        { month: '2026-08', label: 'Aug 2026', value_type: 'forecast' as const },
        { month: '2026-09', label: 'Sep 2026', value_type: 'forecast' as const },
      ],
      total_row: {
        ...MONTHLY_TABLE.total_row,
        month_values: { '2026-06': '500', '2026-07': '750', '2026-08': '0.00', '2026-09': 'NaN' },
      },
    }
    const result = buildMonthlySeries(table)
    expect(result.hasData).toBe(true)
    expect(result.series.map((p) => p.month)).toEqual(['2026-06', '2026-07', '2026-08'])
    expect(result.series.find((p) => p.month === '2026-08')?.amount).toBe(0)
  })

  it('buildMonthlySeries returns no data when total_row is missing or status not ready', () => {
    expect(buildMonthlySeries({ ...MONTHLY_TABLE, total_row: null }).hasData).toBe(false)
    expect(
      buildMonthlySeries({ ...MONTHLY_TABLE, status: 'legacy_output_no_operator_window' }).hasData,
    ).toBe(false)
  })
})

describe('ProjectForecastDashboardVisualizations', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    setState({})
    mockQueries()
  })

  it('renders the dashboard blocks with accessible captions', () => {
    render(<ProjectForecastDashboardVisualizations projectKey="harbor" requestedOutputId={null} />)

    expect(screen.getByRole('heading', { name: 'Forecast Dashboard' })).toBeInTheDocument()
    expect(screen.getByText('Budget vs EAC')).toBeInTheDocument()
    expect(screen.getByText('Cost Position')).toBeInTheDocument()
    expect(screen.getByText('Monthly Forecast Distribution')).toBeInTheDocument()
    expect(screen.getByText(/Current Budget \$12,000,000 · EAC \$12,500,000/)).toBeInTheDocument()
    expect(screen.getByText(/2 months · Jun 2026–Jul 2026/)).toBeInTheDocument()
    // Accessible chart roles.
    expect(screen.getAllByRole('img').length).toBeGreaterThanOrEqual(3)
  })

  it('never renders NaN even with invalid numeric strings', () => {
    setState({
      detail: {
        output_id: 'out-002',
        summary: { ...SUMMARY, current_budget: 'NaN', estimated_at_completion: 'garbage' },
      },
    })
    render(<ProjectForecastDashboardVisualizations projectKey="harbor" requestedOutputId={null} />)

    expect(document.body.textContent || '').not.toContain('NaN')
    // Budget vs EAC drops out (needs both finite); Cost Position still renders.
    expect(screen.queryByText('Budget vs EAC')).not.toBeInTheDocument()
    expect(screen.getByText('Cost Position')).toBeInTheDocument()
  })

  it('scopes the outputs read to the route project key and uses the validated id for detail/monthly', () => {
    render(<ProjectForecastDashboardVisualizations projectKey="harbor" requestedOutputId={null} />)

    const keys = issuedQueryKeys()
    expect(keys).toContainEqual(['forecast', 'db-outputs', 'harbor'])
    expect(keys).toContainEqual(['forecast', 'db-output', 'out-002'])
    expect(keys).toContainEqual(['forecast', 'db-monthly-table', 'out-002'])
    expect(keys.some((key) => key[0] === 'forecast' && key[2] === 'tropical')).toBe(false)
  })

  it('never fetches detail/monthly for an invalid requested output id', () => {
    render(
      <ProjectForecastDashboardVisualizations projectKey="harbor" requestedOutputId="bogus-id" />,
    )

    const keys = issuedQueryKeys()
    // Falls back to the latest valid output; the bogus id is never used for detail/monthly.
    expect(keys).toContainEqual(['forecast', 'db-output', 'out-002'])
    expect(keys.some((key) => key[1] === 'db-output' && key[2] === 'bogus-id')).toBe(false)
    expect(keys.some((key) => key[1] === 'db-monthly-table' && key[2] === 'bogus-id')).toBe(false)
  })

  it('renders loading, error, no-output, and no-chart-data states', () => {
    setState({ outputsLoading: true })
    const { rerender } = render(
      <ProjectForecastDashboardVisualizations projectKey="harbor" requestedOutputId={null} />,
    )
    expect(screen.getByText('Loading forecast dashboard…')).toBeInTheDocument()

    setState({ detailError: new Error('boom') })
    rerender(<ProjectForecastDashboardVisualizations projectKey="harbor" requestedOutputId={null} />)
    expect(
      screen.getByText(
        'Forecast dashboard could not be loaded. Check the local data connection and try again.',
      ),
    ).toBeInTheDocument()

    setState({ outputs: [] })
    rerender(<ProjectForecastDashboardVisualizations projectKey="harbor" requestedOutputId={null} />)
    expect(
      screen.getByText('No forecast output is available for this project yet.'),
    ).toBeInTheDocument()

    setState({ detail: { output_id: 'out-002', summary: null }, monthly: { ...MONTHLY_TABLE, total_row: null } })
    rerender(<ProjectForecastDashboardVisualizations projectKey="harbor" requestedOutputId={null} />)
    expect(
      screen.getByText(
        'No dashboard visualization data is available for the selected forecast output yet.',
      ),
    ).toBeInTheDocument()
  })

  it('adds no export/download control and omits forbidden copy', () => {
    render(<ProjectForecastDashboardVisualizations projectKey="harbor" requestedOutputId={null} />)

    expect(
      screen.queryByRole('button', { name: /export|download|csv|excel|fullscreen|full screen/i }),
    ).not.toBeInTheDocument()
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
  })
})
