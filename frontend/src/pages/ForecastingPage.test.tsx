import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastingPage } from './ForecastingPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

vi.mock('../hooks/useForecastReadiness', () => ({
  useForecastReadiness: () => ({
    data: {
      storage_mode: 'app_managed',
      surfaces_ready: { catalog: true },
      roots: {
        package_roots: { valid: true, count: 1 },
        data_root: { valid: true },
        db_path: { valid: true },
        runs_root: { valid: true },
        eval_root: { valid: true },
        config_edit_root: { valid: true },
      },
    },
    isLoading: false,
  }),
}))

function mockData() {
  useQueryMock.mockImplementation((opts: { queryKey: unknown[] }) => {
    const kind = opts.queryKey[1]
    const sub = opts.queryKey[2]
    if (kind === 'projects') {
      return {
        data: {
          projects: [
            { project_key: 'tropical', project_name: 'Tropical World Nursery', job_reference: '23-435-01' },
          ],
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'periods') {
      return { data: { periods: [{ period: '2026-June', package_count: 3 }] }, isLoading: false, error: null }
    }
    if (kind === 'packages') {
      return {
        data: {
          packages: [
            {
              package_id: 'abc123def456',
              package_type: 'comprehensive',
              display_label: 'Comprehensive forecast — Jun 15, 2026 3:39 PM',
              status: 'validated',
              generated_display: 'Jun 15, 2026 3:39 PM',
              validation_total: 40,
              validation_passed: 40,
              validation_failed: 0,
            },
          ],
        },
        isLoading: false,
        error: null,
      }
    }
    if (kind === 'runs') return { data: { runs: [] }, isLoading: false, error: null }
    if (kind === 'external') return { data: { evaluations: [] }, isLoading: false, error: null }
    if (kind === 'config' && sub === 'snapshots') {
      return { data: { snapshots: [{ snapshot_name: 'Live', item_count: 12 }] }, isLoading: false, error: null }
    }
    return { data: undefined, isLoading: false, error: null }
  })
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ForecastingPage />
    </MemoryRouter>,
  )
}

describe('ForecastingPage package history', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
  })

  it('lists forecast packages with a friendly label and status', () => {
    mockData()
    renderPage()
    expect(screen.getByText('Forecast packages')).toBeInTheDocument()
    expect(
      screen.getAllByText('Comprehensive forecast — Jun 15, 2026 3:39 PM').length,
    ).toBeGreaterThan(0)
    expect(screen.getAllByText('Ready').length).toBeGreaterThan(0)
    expect(screen.getByText('Review')).toBeInTheDocument()
  })

  it('does not render raw stamps or filesystem paths', () => {
    mockData()
    const { container } = renderPage()
    expect(container.textContent || '').not.toMatch(/\d{8}_\d{6}/)
    expect(container.textContent || '').not.toMatch(/\/Users\//)
  })
})