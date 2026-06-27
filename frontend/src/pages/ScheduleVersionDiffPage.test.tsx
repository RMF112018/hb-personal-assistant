import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ScheduleVersionDiffPage } from './ScheduleVersionDiffPage'

const projectsMock = vi.fn()
const versionsMock = vi.fn()
const detailsMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getScheduleProjects: (...args: unknown[]) => projectsMock(...args),
      getScheduleVersions: (...args: unknown[]) => versionsMock(...args),
      getScheduleDiffDetails: (...args: unknown[]) => detailsMock(...args),
    },
  }
})

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [{ path: '/schedules/version-diff', element: <ScheduleVersionDiffPage /> }],
    { initialEntries: ['/schedules/version-diff?project=tropical&diff_id=42'] },
  )
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('ScheduleVersionDiffPage', () => {
  beforeEach(() => {
    projectsMock.mockResolvedValue({
      projects: [{ project_key: 'tropical', display_name: 'Tropical Wind', selectable_for_import: true }],
    })
    versionsMock.mockResolvedValue([])
    detailsMock.mockResolvedValue({
      metadata: {
        diff_id: 42,
        identity_safe: true,
        comparison_type: 'identity_safe_default',
      },
      summary_counts: {
        critical_severity_count: 1,
        major_severity_count: 2,
        moderate_severity_count: 3,
        date_drift_count: 4,
        requires_attention_count: 5,
      },
      detail_rows: [
        {
          detail_id: 'detail-1',
          severity: 'critical',
          change_domain: 'activity',
          change_type: 'date_drift',
          activity_id: 'A1000',
          activity_name: 'Start',
          wbs_code: 'WBS1',
          field_name: 'finish_date',
          from_value: '2026-06-05',
          to_value: '2026-06-17',
          day_delta: 12,
          requires_attention: 1,
        },
      ],
      pagination: { total_count: 1, returned_count: 1, limit: 100, offset: 0 },
    })
  })

  it('renders identity-safe detailed diff metadata and rows', async () => {
    renderPage()
    expect(await screen.findByText('Identity-safe')).toBeInTheDocument()
    expect(screen.getByText('identity_safe_default')).toBeInTheDocument()
    expect(screen.getByText('A1000')).toBeInTheDocument()
    expect(screen.getByText('finish_date')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
  })
})
