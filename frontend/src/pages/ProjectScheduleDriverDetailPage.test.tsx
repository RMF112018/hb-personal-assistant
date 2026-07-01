import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectScheduleDriverDetailPage } from './ProjectScheduleDriverDetailPage'

const getProjectScheduleDriverDetailMock = vi.fn()
const getProjectsMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getProjects: (...args: unknown[]) => getProjectsMock(...args),
      getProjectScheduleDriverDetail: (...args: unknown[]) => getProjectScheduleDriverDetailMock(...args),
    },
  }
})

const driverDetail = {
  available: true,
  comparison_basis: 'current_contract_baseline',
  baseline_context: {
    slot_label: 'Current Contract Baseline',
    schedule_version_key: 'tropical|S1|2026-06-01',
    display_name: 'Contract baseline issued 2026-06-01',
  },
  activity: {
    activity_id: 'DRV-A',
    activity_name: 'Concrete pour',
    prior_start: '2026-06-01',
    current_start: '2026-06-02',
    prior_finish: '2026-06-10',
    current_finish: '2026-06-12',
    prior_float: '5',
    current_float: '3',
    start_delta_days: 1,
    finish_delta_days: 2,
    float_delta_days: -2,
  },
  downstream_impacts: [],
  upstream_path: [],
  logic_changes: [],
  sequence_cue: 'Sequence cue only — review logic and dates; not a causation finding.',
}

const routes = [
  { path: '/projects/:projectKey/schedule/driver-detail', element: <ProjectScheduleDriverDetailPage /> },
  { path: '/projects/:projectKey/schedule/drivers/:activityId', element: <ProjectScheduleDriverDetailPage /> },
]

function renderPage(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('ProjectScheduleDriverDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getProjectsMock.mockResolvedValue({
      surface: 'analytics.projects.list',
      projects: [{ project_key: 'tropical', display_name: 'Tropical Resort' }],
    })
    getProjectScheduleDriverDetailMock.mockResolvedValue(driverDetail)
  })

  it('loads named basis from comparison_basis query param and shows humanized labels', async () => {
    renderPage(
      '/projects/tropical/schedule/driver-detail?activity_id=DRV-A&comparison_basis=current_contract_baseline&as_of=2026-07-03',
    )
    await waitFor(() => {
      expect(getProjectScheduleDriverDetailMock).toHaveBeenCalledWith('tropical', 'DRV-A', {
        asOf: '2026-07-03',
        comparisonBasis: 'current_contract_baseline',
      })
    })
    expect(await screen.findByRole('heading', { name: 'Concrete pour' })).toBeInTheDocument()
    expect(screen.getByText(/Comparing against Current Contract Baseline/)).toBeInTheDocument()
    expect(screen.queryByText(/current_contract_baseline/)).not.toBeInTheDocument()
  })

  it('reads slash-bearing activity_id from query param', async () => {
    getProjectScheduleDriverDetailMock.mockResolvedValue({
      ...driverDetail,
      activity: { ...driverDetail.activity, activity_id: 'FAB/DEL-10', activity_name: 'Fabrication delivery' },
    })
    renderPage(
      '/projects/tropical/schedule/driver-detail?activity_id=FAB%2FDEL-10&comparison_basis=current_contract_baseline&as_of=2026-07-03',
    )
    await waitFor(() => {
      expect(getProjectScheduleDriverDetailMock).toHaveBeenCalledWith('tropical', 'FAB/DEL-10', {
        asOf: '2026-07-03',
        comparisonBasis: 'current_contract_baseline',
      })
    })
    expect(await screen.findByText(/Fabrication delivery/)).toBeInTheDocument()
  })

  it('rejects conflicting basis and comparison_basis without calling API', async () => {
    renderPage(
      '/projects/tropical/schedule/driver-detail?activity_id=DRV-A&basis=prior_update&comparison_basis=current_contract_baseline',
    )
    await screen.findByText(/two different comparison modes were requested/)
    expect(getProjectScheduleDriverDetailMock).not.toHaveBeenCalled()
  })

  it('preserves as_of on unavailable back link', async () => {
    getProjectScheduleDriverDetailMock.mockResolvedValue({ available: false, reason: 'baseline_not_selected' })
    renderPage(
      '/projects/tropical/schedule/driver-detail?activity_id=DRV-A&comparison_basis=current_contract_baseline&as_of=2026-07-03',
    )
    await screen.findByText('Driver detail unavailable')
    const back = screen.getByRole('link', { name: 'Back to Schedule' })
    expect(back.getAttribute('href')).toBe('/projects/tropical/schedule?as_of=2026-07-03')
  })

  it('workbench link preserves named basis and as_of', async () => {
    renderPage(
      '/projects/tropical/schedule/driver-detail?activity_id=DRV-A&comparison_basis=current_contract_baseline&as_of=2026-07-03',
    )
    const workbench = await screen.findByRole('link', { name: 'Workbench' })
    expect(workbench.getAttribute('href')).toContain('comparison_basis=current_contract_baseline')
    expect(workbench.getAttribute('href')).toContain('as_of=2026-07-03')
  })

  it('supports legacy path param route for simple activity IDs', async () => {
    renderPage('/projects/tropical/schedule/drivers/DRV-A?comparison_basis=current_contract_baseline&as_of=2026-07-03')
    await waitFor(() => {
      expect(getProjectScheduleDriverDetailMock).toHaveBeenCalledWith('tropical', 'DRV-A', {
        asOf: '2026-07-03',
        comparisonBasis: 'current_contract_baseline',
      })
    })
  })
})
