import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastResultsSummary } from './ForecastResultsSummary'

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
              estimated_final_cost: '1234567.89',
              cost_to_complete: '500.00',
              variance_to_budget: '-10.00',
              variance_to_prior_forecast: '250.00',
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
        data: { output_id: 'fout-x', forecast_at_completion: '1234600.00' },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'db-decision-support') {
      return {
        data: {
          output_id: 'fout-x',
          maturity: { maturity_tier: 'M4', completed_month_count: 8 },
          confidence_scorecards: [{ scope: 'project', label: 'high', factors: [] }],
          data_availability: [],
          method_eligibility: [],
          model_selection: [],
        },
        isLoading: false,
        error: null,
      }
    }
    return EMPTY
  })
}

describe('ForecastResultsSummary', () => {
  beforeEach(() => useQueryMock.mockReset())

  it('renders headline metrics with formatted currency, confidence, and maturity', () => {
    mockPopulated()
    render(<ForecastResultsSummary project="tropical" />)

    expect(screen.getByText('Results summary')).toBeInTheDocument()
    // Currency is formatted, not the raw decimal string.
    expect(screen.getByText('$1,234,568')).toBeInTheDocument()
    expect(screen.queryByText('1234567.89')).not.toBeInTheDocument()
    expect(screen.getByText('$1,234,600')).toBeInTheDocument()
    expect(screen.getByText('$500')).toBeInTheDocument()
    expect(screen.getByText('-$10')).toBeInTheDocument()
    expect(screen.getByText('$250')).toBeInTheDocument()

    // Confidence + maturity surface as readable labels (text, not color alone).
    expect(screen.getByText('Forecast confidence')).toBeInTheDocument()
    expect(screen.getByText('high')).toBeInTheDocument()
    expect(screen.getByText('Project maturity')).toBeInTheDocument()
    expect(screen.getByText(/M4 · 8 completed months/)).toBeInTheDocument()
    expect(screen.getAllByText('Ready').length).toBeGreaterThanOrEqual(1)

    // The internal output_id is never displayed.
    expect(screen.queryByText('fout-x')).not.toBeInTheDocument()
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
