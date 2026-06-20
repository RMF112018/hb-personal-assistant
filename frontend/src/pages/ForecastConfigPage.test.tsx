import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastConfigPage } from './ForecastConfigPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

function mockData() {
  useQueryMock.mockImplementation((opts: { queryKey: any[] }) => {
    const kind = opts.queryKey[2]
    if (kind === 'snapshots') {
      return {
        data: {
          snapshots: [
            {
              snapshot_id: 'c3b4a67d',
              snapshot_name: 'tropical-live-config',
              created_display: 'Jun 19, 2026',
              item_count: 194,
            },
          ],
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'snapshot') {
      return {
        data: {
          snapshot_id: 'c3b4a67d',
          snapshot_name: 'tropical-live-config',
          created_display: 'Jun 19, 2026',
          item_count: 194,
          domains: [
            { domain: 'forecast_controls', display_label: 'Forecast controls', item_count: 64, source_count: 1 },
            { domain: 'project', display_label: 'Project settings', item_count: 1, source_count: 1 },
          ],
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'domain') {
      return {
        data: {
          domain: 'forecast_controls',
          display_label: 'Forecast controls',
          item_count: 1,
          truncated: false,
          items: [
            {
              item_id: 'it-ctrl-1',
              fields: { cost_code: '10-01-340', accepted_final_cost: '123456.78', acceptance_status: 'accepted' },
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
    <MemoryRouter>
      <ForecastConfigPage />
    </MemoryRouter>,
  )
}

describe('ForecastConfigPage', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
  })

  it('renders the snapshot, domain tiles, and item rows', () => {
    mockData()
    renderPage()
    expect(screen.getByText('Forecast configuration')).toBeInTheDocument()
    // appears as both the domain tile and (auto-selected) section title
    expect(screen.getAllByText('Forecast controls').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Project settings')).toBeInTheDocument()
    expect(screen.getByText('10-01-340')).toBeInTheDocument()
    expect(screen.getByText('123456.78')).toBeInTheDocument()
  })

  it('does not render raw stamps, paths, or endpoints', () => {
    mockData()
    const { container } = renderPage()
    const text = container.textContent || ''
    expect(text).not.toMatch(/\d{8}_\d{6}/)
    expect(text).not.toMatch(/\/Users\//)
    expect(text).not.toMatch(/localhost/)
  })
})
