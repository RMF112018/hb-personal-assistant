import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastExternalEvalPage } from './ForecastExternalEvalPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

function mockData() {
  useQueryMock.mockImplementation(() => ({
    data: {
      evaluations: [
        {
          eval_id: 'ev123',
          display_label: 'External forecast (Manual) — 2026-06 — Jun 20, 2026 1:07 PM',
          status: 'succeeded',
          generated_display: 'Jun 20, 2026 1:07 PM',
        },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }))
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ForecastExternalEvalPage />
    </MemoryRouter>,
  )
}

describe('ForecastExternalEvalPage', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
  })

  it('renders the upload step and prior-evaluations history', () => {
    mockData()
    renderPage()
    expect(screen.getByText('Upload operator forecast')).toBeInTheDocument()
    expect(screen.getByText('Prior evaluations')).toBeInTheDocument()
    expect(
      screen.getByText('External forecast (Manual) — 2026-06 — Jun 20, 2026 1:07 PM'),
    ).toBeInTheDocument()
  })

  it('does not render raw stamps or filesystem paths', () => {
    mockData()
    const { container } = renderPage()
    const text = container.textContent || ''
    expect(text).not.toMatch(/\d{8}_\d{6}/)
    expect(text).not.toMatch(/\/Users\//)
  })
})
