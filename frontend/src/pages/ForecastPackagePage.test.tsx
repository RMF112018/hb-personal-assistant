import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastPackagePage } from './ForecastPackagePage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

function mockData() {
  useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
    const kind = opts.queryKey[1]
    if (kind === 'summary') {
      return {
        data: {
          package_id: 'abc123',
          package_type: 'comprehensive',
          display_label: 'Comprehensive forecast — Jun 15, 2026 3:39 PM',
          project_key: 'tropical',
          period: '2026-June',
          job_reference: '23-435-01',
          generated_display: 'Jun 15, 2026 3:39 PM',
          status: 'validated',
          headline: { canonical_codes_covered: 127, human_review_items: 87 },
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'validation') {
      return { data: { total_checks: 40, passed: 40, failed: 0, failed_checks: [] }, isLoading: false, error: null }
    }
    if (kind === 'rows') {
      return {
        data: {
          rows_available: true,
          row_count: 1,
          rows: [
            {
              cost_code: '03-01-025',
              budget_code_key: '0000.03-01-025.MAT',
              recommended_final_cost: '3561.74',
              cost_to_complete: '2401.29',
              change_amount: '-128.05',
              acceptance_status: 'pending',
            },
          ],
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'review') {
      return {
        data: {
          item_count: 1,
          items: [
            {
              cost_code: '03-01-025',
              review_priority: 'medium',
              review_reason: 'integrated final-cost change',
              acceptance_status: 'pending',
            },
          ],
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'monthly') {
      return {
        data: {
          monthly_available: true,
          project_monthly: [
            { forecast_month: '2026-06', amount: '282.07' },
            { forecast_month: '2026-07', amount: '423.84' },
          ],
          rows: [],
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'probability') {
      return {
        data: {
          probability_available: true,
          rows: [
            {
              cost_code: '03-01-025',
              budget_code_key: '0000.03-01-025.MAT',
              actual_cost_to_date: '1032.40',
              p10: '2103.22',
              p50: '3599.50',
              p80: '5487.45',
              p90: '7006.87',
              p95: '8812.82',
            },
          ],
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'risk') {
      return {
        data: {
          risk_register_available: true,
          rows: [
            {
              cost_code: '03-01-025',
              recommended_final_cost: '3577.00',
              variance_amount: '128.05',
              conflict_count: 2,
              max_conflict_severity: 'high',
              review_priority: 'medium',
            },
          ],
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'top-risks') {
      return {
        data: {
          top_risks_available: true,
          rows: [
            {
              cost_code: '03-01-413',
              recommended_final_cost: '120000.00',
              overrun_amount: '15000.00',
              direction: 'over',
            },
          ],
        },
        isLoading: false,
        error: null,
      }
    }
    return { data: undefined, isLoading: false, error: null }
  })
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/forecasting/abc123']}>
      <Routes>
        <Route path="/forecasting/:packageId" element={<ForecastPackagePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ForecastPackagePage detail', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
  })

  it('renders headline, validation, cost rows, and review queue', () => {
    mockData()
    renderPage()
    expect(screen.getByText('Comprehensive forecast — Jun 15, 2026 3:39 PM')).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
    expect(screen.getByText('Recommended final cost by cost code')).toBeInTheDocument()
    expect(screen.getByText('3561.74')).toBeInTheDocument()
    expect(screen.getByText('Review queue')).toBeInTheDocument()
    expect(screen.getByText('integrated final-cost change')).toBeInTheDocument()
  })

  it('renders the Phase 5 review surfaces', () => {
    mockData()
    renderPage()
    expect(screen.getByText('Monthly cost trend')).toBeInTheDocument()
    expect(screen.getByText('Probability bands by cost code')).toBeInTheDocument()
    expect(screen.getByText('Risk register')).toBeInTheDocument()
    expect(screen.getByText('Top overrun risks')).toBeInTheDocument()
    expect(screen.getByText('8812.82')).toBeInTheDocument() // P95 band
    expect(screen.getByText('high')).toBeInTheDocument() // risk severity
  })

  it('does not render raw stamps or filesystem paths', () => {
    mockData()
    const { container } = renderPage()
    expect(container.textContent || '').not.toMatch(/\d{8}_\d{6}/)
    expect(container.textContent || '').not.toMatch(/\/Users\//)
  })
})
