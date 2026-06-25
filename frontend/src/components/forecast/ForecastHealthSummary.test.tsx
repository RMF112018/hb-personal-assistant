import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastHealthSummary } from './ForecastHealthSummary'
import { deriveForecastHealth } from './forecastHealth'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

const EMPTY = { data: undefined, isLoading: false, error: null }

describe('deriveForecastHealth', () => {
  const base = {
    runFailed: false,
    readinessBlocked: false,
    hasOutput: true,
    confidenceLabel: 'High' as string | null | undefined,
    maturityLabel: 'Full context' as string | null | undefined,
  }

  it('reports a failed selected run first', () => {
    expect(deriveForecastHealth({ ...base, runFailed: true }).level).toBe('failed_run')
  })

  it('reports blocked / no output when blocked or no output exists', () => {
    expect(deriveForecastHealth({ ...base, readinessBlocked: true }).level).toBe('blocked_no_output')
    expect(deriveForecastHealth({ ...base, hasOutput: false }).level).toBe('blocked_no_output')
  })

  it('reports needs-attention for limited readiness confidence or maturity', () => {
    expect(deriveForecastHealth({ ...base, confidenceLabel: 'Low' }).level).toBe('attention')
    expect(deriveForecastHealth({ ...base, maturityLabel: 'Baseline only' }).level).toBe('attention')
    expect(deriveForecastHealth({ ...base, maturityLabel: 'No financial basis' }).level).toBe('attention')
  })

  it('reports usable when output, readiness confidence, and maturity are all strong', () => {
    expect(deriveForecastHealth(base).level).toBe('usable')
    expect(
      deriveForecastHealth({ ...base, confidenceLabel: 'Medium', maturityLabel: 'Cost-informed' }).level,
    ).toBe('usable')
  })
})

function mockHealth(opts: {
  outputs: unknown[]
  confidenceLabel?: string
  maturityLabel?: string
}) {
  useQueryMock.mockImplementation((q?: { queryKey: unknown[] }) => {
    if (q?.queryKey[1] === 'db-outputs') {
      return { data: { outputs: opts.outputs }, isLoading: false, error: null }
    }
    if (q?.queryKey[1] === 'db-output') {
      return {
        data: {
          output_id: 'fout-x',
          summary: {
            forecast_confidence_label: opts.confidenceLabel ?? 'High',
            forecast_maturity_label: opts.maturityLabel ?? 'Full context',
          },
        },
        isLoading: false,
        error: null,
      }
    }
    return EMPTY
  })
}

describe('ForecastHealthSummary', () => {
  beforeEach(() => useQueryMock.mockReset())

  it('shows a usable verdict with a visible text label', () => {
    mockHealth({ outputs: [{ output_id: 'fout-x' }], confidenceLabel: 'High', maturityLabel: 'Full context' })
    render(<ForecastHealthSummary project="tropical" readinessStatus="ready" runFailed={false} />)
    expect(screen.getByText('Forecast health')).toBeInTheDocument()
    expect(screen.getByText('Usable')).toBeInTheDocument()
  })

  it('shows needs-attention for limited maturity', () => {
    mockHealth({ outputs: [{ output_id: 'fout-x' }], confidenceLabel: 'High', maturityLabel: 'Baseline only' })
    render(<ForecastHealthSummary project="tropical" readinessStatus="ready" runFailed={false} />)
    // The verdict label and the status pill both read "Needs attention" (consistent), so >= 1.
    expect(screen.getAllByText('Needs attention').length).toBeGreaterThanOrEqual(1)
  })

  it('shows blocked / no output when no output is persisted', () => {
    mockHealth({ outputs: [] })
    render(<ForecastHealthSummary project="tropical" readinessStatus="ready" runFailed={false} />)
    expect(screen.getByText('Blocked / no output')).toBeInTheDocument()
  })

  it('shows a failed selected run regardless of output', () => {
    mockHealth({ outputs: [{ output_id: 'fout-x' }] })
    render(<ForecastHealthSummary project="tropical" readinessStatus="ready" runFailed={true} />)
    expect(screen.getByText('Failed selected run')).toBeInTheDocument()
  })
})
