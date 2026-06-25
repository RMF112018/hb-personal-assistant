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
          commitment_exposure: [
            { budget_code_key: 'k1', committed_amount: '1000.00', exposure_amount: '750.00' },
          ],
          schedule_phasing: [
            { budget_code_key: 'k1', phase: 'direct', start_month: '2026-07', end_month: '2026-08', amount: '3000.00' },
          ],
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

  it('renders detail-only: availability, method eligibility, recommendations, exposure, phasing', () => {
    mockPopulated()
    render(<ForecastDecisionSupportPanel project="tropical" />)
    // Detail panel — the headline cost KPI / maturity-status cards moved to the Forecast Summary.
    expect(screen.queryByText('Estimated final cost')).not.toBeInTheDocument()
    expect(screen.queryByText('Project maturity')).not.toBeInTheDocument()
    expect(screen.queryByText('Maturity status')).not.toBeInTheDocument()
    expect(screen.queryByText('no scorecard')).not.toBeInTheDocument()
    // availability available -> "Ready" pill present; unavailable owner -> "Unsupported"
    expect(screen.getAllByText('Ready').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('owner')).toBeInTheDocument()
    expect(screen.getAllByText('Unsupported').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('monthly_actuals')).toBeInTheDocument()
    expect(screen.getByText('burn_rate')).toBeInTheDocument()
    expect(screen.getByText('03-01-025')).toBeInTheDocument()
    // commitment exposure + schedule phasing surfaces
    expect(screen.getByText('Commitment exposure')).toBeInTheDocument()
    expect(screen.getByText('750.00')).toBeInTheDocument()
    expect(screen.getByText('Schedule phasing')).toBeInTheDocument()
    expect(screen.getByText('2026-07–2026-08')).toBeInTheDocument()
  })

  it('shows a neutral not-populated note (not an error) when v66 decision support is empty', () => {
    useQueryMock.mockImplementation((opts?: { queryKey: unknown[] }) => {
      const kind = opts?.queryKey[1]
      if (kind === 'db-outputs') {
        return { data: { outputs: [{ output_id: 'fout-x', created_display: 'Jun 19, 2026' }] }, isLoading: false, error: null }
      }
      if (kind === 'db-output') {
        return {
          data: {
            output_id: 'fout-x',
            budget_codes: [{ budget_code_key: 'k1', cost_code: '03-01-025', forecast_action: 'hold', confidence: 'high', recommended_projected_cost: '500.00' }],
            risks: [],
            commitment_exposure: [],
            schedule_phasing: [],
          },
          isLoading: false,
          error: null,
        }
      }
      if (kind === 'db-decision-support') {
        return { data: { output_id: 'fout-x', maturity: null, data_availability: [], confidence_scorecards: [], method_eligibility: [], model_selection: [] }, isLoading: false, error: null }
      }
      return EMPTY
    })
    render(<ForecastDecisionSupportPanel project="tropical" />)
    expect(screen.getByText(/not populated for this output/)).toBeInTheDocument()
    // recommendations from v63 still render — v66 emptiness does not poison the v63 output
    expect(screen.getByText('03-01-025')).toBeInTheDocument()
  })

  it('renders a graceful empty state when no outputs are persisted', () => {
    useQueryMock.mockImplementation((opts?: { queryKey: unknown[] }) => {
      if (opts?.queryKey[1] === 'db-outputs') {
        return { data: { outputs: [] }, isLoading: false, error: null }
      }
      return EMPTY
    })
    render(<ForecastDecisionSupportPanel project="tropical" />)
    expect(screen.getByText('No persisted forecast outputs yet')).toBeInTheDocument()
  })

  it('shows an advisory when the forecast database is unavailable', () => {
    useQueryMock.mockImplementation((opts?: { queryKey: unknown[] }) => {
      if (opts?.queryKey[1] === 'db-outputs') {
        return { data: undefined, isLoading: false, error: new Error('503') }
      }
      return EMPTY
    })
    render(<ForecastDecisionSupportPanel project="tropical" />)
    expect(screen.getByText(/Forecast database not available/)).toBeInTheDocument()
  })
})
