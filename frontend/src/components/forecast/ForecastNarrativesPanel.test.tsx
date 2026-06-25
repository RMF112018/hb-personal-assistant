import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastNarrativesPanel } from './ForecastNarrativesPanel'

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
        data: { outputs: [{ output_id: 'fout-x', project_key: 'tropical', created_display: 'Jun 19, 2026' }] },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'db-narratives') {
      // Already curated by the API: no raw_json, no stamps (the read-model strips/scrubs them).
      return {
        data: {
          output_id: 'fout-x',
          narratives: {
            project: [
              {
                narrative_key: 'header',
                estimated_final_cost: '500.00',
                cost_to_complete: '100.00',
                variance_to_budget: '10.00',
                override_count: 1,
                narrative: 'Forecast EAC 500.00 across 1 budget code(s).',
              },
            ],
            human_override: [
              {
                narrative_key: 'k1',
                budget_code_key: 'k1',
                column: 'recommended_projected_cost',
                original: '450.00',
                override: '500.00',
                delta_amount: '50.00',
                applied_display: 'Jun 19, 2026',
                narrative: 'Operator override on k1.',
              },
            ],
            source_qa: [
              {
                narrative_key: 'analysis_package',
                null_projected_cost_count: 0,
                zero_projected_cost_count: 0,
                duplicate_budget_code_keys: [],
                narrative: 'Source QA over 1 budget code(s); forecast period [redacted].',
              },
            ],
            lineage: [
              {
                narrative_key: 'package_sha256_chain',
                context_sha256: 'a'.repeat(64),
                analysis_sha256: 'b'.repeat(64),
                output_sha256: 'c'.repeat(64),
                methodology_sha256: 'd'.repeat(64),
                narrative: 'Package sha256 chain.',
              },
            ],
          },
        },
        isLoading: false,
        error: null,
      }
    }
    return EMPTY
  })
}

describe('ForecastNarrativesPanel', () => {
  beforeEach(() => useQueryMock.mockReset())

  it('renders project totals, override audit, source QA, and lineage chips', () => {
    mockPopulated()
    render(<ForecastNarrativesPanel project="tropical" />)
    // project narrative text renders (the headline cost KPI cards moved to the Forecast Summary)
    expect(screen.getByText('Forecast EAC 500.00 across 1 budget code(s).')).toBeInTheDocument()
    expect(screen.queryByText('Estimated final cost')).not.toBeInTheDocument()
    expect(screen.queryByText('Operator overrides')).not.toBeInTheDocument()
    // human-override audit row (original → override)
    expect(screen.getByText('Human overrides · 1')).toBeInTheDocument()
    expect(screen.getByText('450.00 → 500.00')).toBeInTheDocument()
    // source QA advisory shows the already-redacted narrative
    expect(screen.getByText(/forecast period \[redacted\]/)).toBeInTheDocument()
    // lineage sha chips
    expect(screen.getByText('Package lineage (sha256 chain)')).toBeInTheDocument()
    expect(screen.getByText('a'.repeat(64))).toBeInTheDocument()
  })

  it('renders a graceful empty state when no outputs are persisted', () => {
    useQueryMock.mockImplementation((opts?: { queryKey: unknown[] }) => {
      if (opts?.queryKey[1] === 'db-outputs') {
        return { data: { outputs: [] }, isLoading: false, error: null }
      }
      return EMPTY
    })
    render(<ForecastNarrativesPanel project="tropical" />)
    expect(screen.getByText('No persisted forecast outputs yet')).toBeInTheDocument()
  })

  it('shows an advisory when the forecast database is unavailable', () => {
    useQueryMock.mockImplementation((opts?: { queryKey: unknown[] }) => {
      if (opts?.queryKey[1] === 'db-outputs') {
        return { data: undefined, isLoading: false, error: new Error('503') }
      }
      return EMPTY
    })
    render(<ForecastNarrativesPanel project="tropical" />)
    expect(screen.getByText(/Forecast database not available/)).toBeInTheDocument()
  })
})
