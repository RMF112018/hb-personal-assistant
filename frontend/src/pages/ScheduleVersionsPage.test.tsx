import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ScheduleVersionsPage } from './ScheduleVersionsPage'

const projectsMock = vi.fn()
const versionsMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getScheduleProjects: (...args: unknown[]) => projectsMock(...args),
      getScheduleVersions: (...args: unknown[]) => versionsMock(...args),
      listScheduleVersions: (...args: unknown[]) => versionsMock(...args),
    },
  }
})

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [{ path: '/schedules/versions', element: <ScheduleVersionsPage /> }],
    { initialEntries: ['/schedules/versions?project=tropical'] },
  )
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('ScheduleVersionsPage', () => {
  beforeEach(() => {
    projectsMock.mockResolvedValue({
      projects: [{ project_key: 'tropical', display_name: 'Tropical Wind' }],
    })
    versionsMock.mockResolvedValue([
      {
        schedule_version_key: 'tropical|1|2026-07-01',
        project_key: 'tropical',
        display_label: 'July update',
        data_date: '2026-07-01',
        source_format: 'primavera_xer',
        imported_at: '2026-07-02',
        activity_count: 10,
        quality_status: 'completed',
        identity_match_status: 'resolved',
        schedule_identity_key: 'identity-1',
        default_prior_available: true,
        default_diff_id: 42,
        default_diff_impact: {
          impact_level: 'high',
          requires_attention_count: 7,
        },
        quality_score: '90',
        quality_grade: 'A',
        cost_loaded_status: 'not_cost_loaded',
      },
    ])
  })

  it('renders compact impact metadata for versions with a default diff', async () => {
    renderPage()
    expect(await screen.findByText('July update')).toBeInTheDocument()
    expect(screen.getByText(/Impact: high \| Attention: 7/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Detail diff' })).toHaveAttribute(
      'href',
      '/schedules/version-diff?project=tropical&diff_id=42',
    )
  })
})
