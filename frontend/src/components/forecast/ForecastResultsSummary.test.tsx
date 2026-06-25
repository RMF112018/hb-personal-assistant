import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastResultsSummary } from './ForecastResultsSummary'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

const EMPTY = { data: undefined, isLoading: false, error: null }

type SummaryOverrides = Record<string, unknown>

function mockWithSummary(summary: SummaryOverrides | null) {
  useQueryMock.mockImplementation((opts?: { queryKey: unknown[] }) => {
    if (!opts) return EMPTY
    const kind = opts.queryKey[1]
    if (kind === 'db-outputs') {
      return {
        data: { outputs: [{ output_id: 'fout-x', project_key: 'tropical', created_display: 'Jun 19, 2026' }] },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'db-output') {
      return { data: { output_id: 'fout-x', summary }, isLoading: false, error: null }
    }
    return EMPTY
  })
}

const FULL_SUMMARY: SummaryOverrides = {
  estimated_at_completion: '1234567.89',
  total_cost_to_date: '600000.00',
  cost_to_complete: '500.00',
  current_budget: '1200000.00',
  budget_basis_label: 'Revised budget',
  budget_status: 'available',
  variance_to_budget: '-10.00',
  variance_to_budget_status: 'reconciled',
  variance_to_prior_forecast: '250.00',
  variance_to_prior_forecast_status: 'computed',
  forecast_confidence_label: 'Medium',
  forecast_confidence_basis: 'cost_informed_financial_spine',
  forecast_maturity_label: 'Cost-informed',
  forecast_maturity_basis: 'cost_informed_financial_spine',
  basis_limitations: [],
}

describe('ForecastResultsSummary (consolidated Forecast Summary)', () => {
  beforeEach(() => useQueryMock.mockReset())

  it('renders one Forecast Summary panel with the consolidated KPI cards', () => {
    mockWithSummary(FULL_SUMMARY)
    render(<ForecastResultsSummary project="tropical" />)

    expect(screen.getByText('Forecast Summary')).toBeInTheDocument()

    // EAC shown once, as "Estimated at Completion"; the legacy duplicate labels are gone.
    expect(screen.getByText('Estimated at Completion')).toBeInTheDocument()
    expect(screen.queryByText('Estimated final cost')).not.toBeInTheDocument()
    expect(screen.queryByText('Forecast at completion')).not.toBeInTheDocument()
    expect(screen.queryByText('Maturity status')).not.toBeInTheDocument()

    // New cards present
    expect(screen.getByText('Total Cost to Date')).toBeInTheDocument()
    expect(screen.getByText('Current Budget')).toBeInTheDocument()
    expect(screen.getByText('Variance from Prior Forecast')).toBeInTheDocument()

    // Currency formatted (no raw decimal strings)
    expect(screen.getByText('$1,234,568')).toBeInTheDocument()
    expect(screen.queryByText('1234567.89')).not.toBeInTheDocument()
    expect(screen.getByText('$1,200,000')).toBeInTheDocument()
    expect(screen.getByText('$250.00')).toBeInTheDocument() // prior variance, cents preserved

    // Readiness-based confidence/maturity from v63 — never a v66 "no scorecard"/"Unknown" string.
    expect(screen.getByText('Medium')).toBeInTheDocument()
    expect(screen.getByText('Cost-informed')).toBeInTheDocument()
    expect(screen.queryByText('no scorecard')).not.toBeInTheDocument()
    expect(screen.queryByText('Unknown')).not.toBeInTheDocument()
    expect(screen.queryByText('Unsupported')).not.toBeInTheDocument()

    // The internal output_id never renders.
    expect(screen.queryByText('fout-x')).not.toBeInTheDocument()
  })

  it('renders $0.00 for a real zero prior-forecast variance', () => {
    mockWithSummary({ ...FULL_SUMMARY, variance_to_prior_forecast: '0.00', variance_to_prior_forecast_status: 'computed' })
    render(<ForecastResultsSummary project="tropical" />)
    expect(screen.getByText('$0.00')).toBeInTheDocument()
  })

  it('renders "No prior forecast" when there is no comparable prior output', () => {
    mockWithSummary({ ...FULL_SUMMARY, variance_to_prior_forecast: null, variance_to_prior_forecast_status: 'no_prior_forecast' })
    render(<ForecastResultsSummary project="tropical" />)
    expect(screen.getByText('No prior forecast')).toBeInTheDocument()
  })

  it('renders honest unavailable copy (not $0.00) when budget basis is missing', () => {
    mockWithSummary({ ...FULL_SUMMARY, current_budget: null, budget_basis_label: null, budget_status: 'budget_unavailable' })
    render(<ForecastResultsSummary project="tropical" />)
    expect(screen.getByText('Budget unavailable')).toBeInTheDocument()
  })

  it('renders a clear empty state when no output is persisted', () => {
    useQueryMock.mockImplementation((opts?: { queryKey: unknown[] }) => {
      if (opts?.queryKey[1] === 'db-outputs') {
        return { data: { outputs: [] }, isLoading: false, error: null }
      }
      return EMPTY
    })
    render(<ForecastResultsSummary project="tropical" />)
    expect(screen.getByText('No forecast output yet')).toBeInTheDocument()
  })
})
