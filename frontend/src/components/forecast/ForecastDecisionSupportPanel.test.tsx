import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastDecisionSupportPanel } from './ForecastDecisionSupportPanel'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

const EMPTY = { data: undefined, isLoading: false, error: null }

function mockPopulated() {
  useQueryMock.mockImplementation((opts?: { queryKey: unknown[] }) => {
    if (!opts) return EMPTY
    const kind = opts.queryKey[1]
    if (kind === 'db-outputs') {
      return {
        data: {
          outputs: [
            {
              output_id: 'fout-x',
              project_key: 'tropical',
              estimated_final_cost: '500.00',
              cost_to_complete: '100.00',
              variance_to_budget: '-10.00',
              created_display: 'Jun 19, 2026',
            },
          ],
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'db-output') {
      return {
        data: {
          output_id: 'fout-x',
          estimated_final_cost: '500.00',
          cost_to_complete: '100.00',
          variance_to_budget: '-10.00',
          budget_codes: [
            {
              budget_code_key: 'k1',
              cost_code: '03-01-025',
              forecast_action: 'hold',
              confidence: 'high',
              recommended_projected_cost: '500.00',
            },
          ],
          risks: [{}],
          monthly: [],
          probability: [],
          changes: [],
          staffing: [],
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'db-decision-support') {
      return {
        data: {
          output_id: 'fout-x',
          maturity: { maturity_tier: 'M2', completed_month_count: 2 },
          data_availability: [
            { domain: 'monthly_actuals', availability: 'available', reason: 'rows present' },
            { domain: 'owner', availability: 'unavailable', reason: 'no v59 source table yet' },
          ],
          confidence_scorecards: [{ scope: 'project', label: 'high', factors: [] }],
          method_eligibility: [{ method: 'burn_rate', status: 'eligible_weighted', weight: '0.70' }],
          model_selection: [],
        },
        isLoading: false,
        error: null,
      }
    }
    return { data: undefined, isLoading: false, error: null }
  })
}

describe('ForecastDecisionSupportPanel', () => {
  beforeEach(() => useQueryMock.mockReset())

  it('renders metrics, maturity, confidence, availability, method eligibility, and recommendations', () => {
    mockPopulated()
    render(<ForecastDecisionSupportPanel />)
    expect(screen.getByText('Estimated final cost')).toBeInTheDocument()
    expect(screen.getByText('Project maturity')).toBeInTheDocument()
    expect(screen.getByText('M2')).toBeInTheDocument()
    // confidence high -> "Ready" pill; availability available -> "Ready"; at least one present
    expect(screen.getAllByText('Ready').length).toBeGreaterThanOrEqual(1)
    // unavailable owner domain surfaces as a missing-data "Unsupported" signal
    expect(screen.getByText('owner')).toBeInTheDocument()
    expect(screen.getAllByText('Unsupported').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('monthly_actuals')).toBeInTheDocument()
    expect(screen.getByText('burn_rate')).toBeInTheDocument()
    expect(screen.getByText('03-01-025')).toBeInTheDocument()
  })

  it('renders a graceful empty state when no outputs are persisted', () => {
    useQueryMock.mockImplementation((opts?: { queryKey: unknown[] }) => {
      if (opts?.queryKey[1] === 'db-outputs') {
        return { data: { outputs: [] }, isLoading: false, error: null }
      }
      return EMPTY
    })
    render(<ForecastDecisionSupportPanel />)
    expect(screen.getByText('No persisted forecast outputs yet')).toBeInTheDocument()
  })

  it('shows an advisory when the forecast database is unavailable', () => {
    useQueryMock.mockImplementation((opts?: { queryKey: unknown[] }) => {
      if (opts?.queryKey[1] === 'db-outputs') {
        return { data: undefined, isLoading: false, error: new Error('503') }
      }
      return EMPTY
    })
    render(<ForecastDecisionSupportPanel />)
    expect(screen.getByText(/Forecast database not available/)).toBeInTheDocument()
  })
})
