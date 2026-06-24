import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastOperatorAssumptionsPanel } from './ForecastOperatorAssumptionsPanel'

const useQueryMock = vi.fn()
const refetchOps = vi.fn()
const refetchReq = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

const createOperator = vi.fn().mockResolvedValue({ ok: true })
const editOperator = vi.fn().mockResolvedValue({ ok: true })
const createRequired = vi.fn().mockResolvedValue({ ok: true })
const setSatisfied = vi.fn().mockResolvedValue({ ok: true })

vi.mock('../../lib/api', () => ({
  api: {
    getForecastOperatorAssumptions: vi.fn(),
    getForecastRequiredAssumptions: vi.fn(),
    createForecastOperatorAssumption: (...args: unknown[]) => createOperator(...args),
    editForecastOperatorAssumption: (...args: unknown[]) => editOperator(...args),
    createForecastRequiredAssumption: (...args: unknown[]) => createRequired(...args),
    setForecastRequiredAssumptionSatisfied: (...args: unknown[]) => setSatisfied(...args),
  },
}))

function mockPopulated() {
  useQueryMock.mockImplementation((opts?: { queryKey: unknown[] }) => {
    const kind = opts?.queryKey[1]
    if (kind === 'operator-assumptions') {
      return {
        data: {
          assumptions: [
            {
              assumption_id: 'a1',
              project_key: 'tropical',
              assumption_type: 'labor_rate',
              budget_code_key: null,
              value: '125.00',
              unit: 'usd_per_hour',
              source: null,
              operator: null,
              confidence_impact: 'raises',
              is_required: false,
              reused_from_prior: false,
              overridden: false,
              created_display: 'Jun 23, 2026',
              updated_display: 'Jun 23, 2026',
            },
          ],
        },
        error: null,
        refetch: refetchOps,
      }
    }
    if (kind === 'required-assumptions') {
      return {
        data: {
          required: [
            {
              id: 'r1',
              project_key: 'tropical',
              assumption_type: 'escalation_rate',
              reason: 'trade coverage',
              satisfied: false,
              created_display: 'Jun 23, 2026',
              updated_display: 'Jun 23, 2026',
            },
          ],
        },
        error: null,
        refetch: refetchReq,
      }
    }
    return { data: undefined, error: null, refetch: vi.fn() }
  })
}

describe('ForecastOperatorAssumptionsPanel', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    createOperator.mockClear()
    editOperator.mockClear()
    createRequired.mockClear()
    setSatisfied.mockClear()
    refetchOps.mockClear()
    refetchReq.mockClear()
  })

  it('renders captured assumptions and required rows with a satisfied pill', () => {
    mockPopulated()
    render(<ForecastOperatorAssumptionsPanel project="tropical" />)
    expect(screen.getByText('labor_rate')).toBeInTheDocument()
    expect(screen.getByText('125.00')).toBeInTheDocument()
    expect(screen.getByText('escalation_rate')).toBeInTheDocument()
    // not-satisfied required → "Needs attention" pill
    expect(screen.getByText('Needs attention')).toBeInTheDocument()
  })

  it('submits a new operator assumption and refetches', async () => {
    mockPopulated()
    render(<ForecastOperatorAssumptionsPanel project="tropical" />)
    fireEvent.change(screen.getByLabelText('Assumption type'), {
      target: { value: 'escalation_rate' },
    })
    fireEvent.change(screen.getByLabelText('Value'), { target: { value: '0.03' } })
    fireEvent.click(screen.getByText('Add assumption'))
    await waitFor(() => expect(createOperator).toHaveBeenCalledTimes(1))
    expect(createOperator).toHaveBeenCalledWith(
      'tropical',
      expect.objectContaining({ assumption_type: 'escalation_rate', value: '0.03' }),
    )
    await waitFor(() => expect(refetchOps).toHaveBeenCalled())
  })

  it('blocks submit with an empty assumption type', () => {
    mockPopulated()
    render(<ForecastOperatorAssumptionsPanel project="tropical" />)
    fireEvent.click(screen.getByText('Add assumption'))
    expect(createOperator).not.toHaveBeenCalled()
    expect(screen.getByText('Assumption type is required.')).toBeInTheDocument()
  })

  it('toggles a required assumption satisfied', async () => {
    mockPopulated()
    render(<ForecastOperatorAssumptionsPanel project="tropical" />)
    fireEvent.click(screen.getByText('Mark satisfied'))
    await waitFor(() => expect(setSatisfied).toHaveBeenCalledWith('r1', true))
    await waitFor(() => expect(refetchReq).toHaveBeenCalled())
  })
})
