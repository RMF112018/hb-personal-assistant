import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastRunCenterPage } from './ForecastRunCenterPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

const startDbConfigMock = vi.fn().mockResolvedValue({})

vi.mock('../lib/api', () => ({
  api: {
    getForecastRuns: vi.fn(),
    getForecastDbConfigRuns: vi.fn(),
    getForecastDbConfigRun: vi.fn(),
    getForecastRun: vi.fn(),
    startForecastRun: vi.fn().mockResolvedValue({}),
    startForecastDbConfigRun: (...args: unknown[]) => startDbConfigMock(...args),
  },
}))

function mockData() {
  useQueryMock.mockImplementation((opts: { queryKey: any[] }) => {
    const kind = opts.queryKey[1]
    const sub = opts.queryKey[2]
    if (kind === 'runs' && sub === 'db-config') {
      return {
        data: {
          runs: [
            {
              run_id: 'db999',
              display_label: 'Comprehensive forecast from live config — Jun 21, 2026 9:00 AM',
              status: 'generated',
              generated_display: 'Jun 21, 2026 9:00 AM',
            },
          ],
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      }
    }
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
    startDbConfigMock.mockClear()
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

  it('renders the live-config generation action and merges both run sources', () => {
    mockData()
    renderPage()
    expect(
      screen.getByRole('button', { name: /Generate from live config/i }),
    ).toBeInTheDocument()
    // both a file-config and a live-config run appear, with a Source column distinguishing them
    expect(
      screen.getByText('Comprehensive forecast from live config — Jun 21, 2026 9:00 AM'),
    ).toBeInTheDocument()
    expect(screen.getByText('Live config')).toBeInTheDocument()
    expect(screen.getByText('File config')).toBeInTheDocument()
  })

  it('offers all four generator kinds and passes the selected kind to the API', async () => {
    mockData()
    renderPage()
    const select = screen.getByLabelText('Forecast type') as HTMLSelectElement
    const optionValues = Array.from(select.options).map((o) => o.value)
    expect(optionValues).toEqual(['comprehensive', 'model_controls', 'monthly', 'probability'])

    fireEvent.change(select, { target: { value: 'monthly' } })
    fireEvent.click(screen.getByRole('button', { name: /Generate from live config/i }))
    await waitFor(() => expect(startDbConfigMock).toHaveBeenCalledWith('monthly'))
  })

  it('does not render raw stamps or filesystem paths', () => {
    mockData()
    const { container } = renderPage()
    const text = container.textContent || ''
    expect(text).not.toMatch(/\d{8}_\d{6}/)
    expect(text).not.toMatch(/\/Users\//)
  })
})
