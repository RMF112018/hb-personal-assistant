import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastRunCenterPage } from './ForecastRunCenterPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

function mockData() {
  useQueryMock.mockImplementation((opts: { queryKey: any[] }) => {
    const kind = opts.queryKey[1]
    if (kind === 'runs') {
      return {
        data: {
          runs: [
            {
              run_id: 'abc123',
              display_label: 'Context → analysis forecast — Jun 20, 2026 1:07 PM',
              status: 'succeeded',
              generated_display: 'Jun 20, 2026 1:07 PM',
            },
          ],
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      }
    }
    // detail query (no selection initially)
    return { data: undefined, isLoading: false, error: null, refetch: vi.fn() }
  })
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ForecastRunCenterPage />
    </MemoryRouter>,
  )
}

describe('ForecastRunCenterPage', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
  })

  it('renders the generate action and run history', () => {
    mockData()
    renderPage()
    expect(screen.getByText('Run a forecast')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Generate forecast/i })).toBeInTheDocument()
    expect(screen.getByText('Run history')).toBeInTheDocument()
    expect(
      screen.getByText('Context → analysis forecast — Jun 20, 2026 1:07 PM'),
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
