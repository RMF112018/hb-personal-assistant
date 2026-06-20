import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastPackagePage } from './ForecastPackagePage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

function mockData() {
  useQueryMock.mockImplementation((opts: { queryKey: any[] }) => {
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
    expect(screen.getByText('Validated')).toBeInTheDocument()
    expect(screen.getByText('Recommended final cost by cost code')).toBeInTheDocument()
    expect(screen.getByText('3561.74')).toBeInTheDocument()
    expect(screen.getByText('Human-review queue')).toBeInTheDocument()
    expect(screen.getByText('integrated final-cost change')).toBeInTheDocument()
  })

  it('does not render raw stamps or filesystem paths', () => {
    mockData()
    const { container } = renderPage()
    expect(container.textContent || '').not.toMatch(/\d{8}_\d{6}/)
    expect(container.textContent || '').not.toMatch(/\/Users\//)
  })
})
