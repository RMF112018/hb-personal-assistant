import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ScheduleIdentityReviewPage } from './ScheduleIdentityReviewPage'

const reviewMock = vi.fn()
const reassignMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    getScheduleProjects: vi.fn().mockResolvedValue({
      projects: [{ project_key: 'tropical', display_name: 'Tropical Wind', selectable_for_import: true }],
    }),
    getScheduleIdentityReview: (...args: unknown[]) => reviewMock(...args),
    reassignScheduleIdentity: (...args: unknown[]) => reassignMock(...args),
    splitScheduleIdentity: vi.fn(),
    mergeScheduleIdentities: vi.fn(),
  }
})

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [{ path: '/schedules/identity-review', element: <ScheduleIdentityReviewPage /> }],
    { initialEntries: ['/schedules/identity-review?project=tropical'] },
  )
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('ScheduleIdentityReviewPage', () => {
  beforeEach(() => {
    reviewMock.mockReset()
    reassignMock.mockReset()
    reviewMock.mockResolvedValue({
      project_key: 'tropical',
      review_items: [
        {
          schedule_version_key: 'tropical|B|2026-07-01',
          schedule_identity_key: 'identity-review',
          source_filename_redacted: 'renamed.xer',
          source_format: 'primavera_xer',
          activity_count: 2,
          candidate_count: 1,
          match_status: 'requires_review',
          no_match_reason: 'no_content_compatible_match',
        },
      ],
      active_identities: [
        {
          schedule_identity_key: 'identity-target',
          canonical_schedule_name: 'Target schedule',
        },
      ],
    })
    reassignMock.mockResolvedValue({})
  })

  it('renders review items and assigns an existing identity', async () => {
    renderPage()
    expect(await screen.findByText('renamed.xer')).toBeInTheDocument()
    fireEvent.change(screen.getAllByRole('combobox')[1], {
      target: { value: 'identity-target' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Assign/i }))
    await waitFor(() =>
      expect(reassignMock).toHaveBeenCalledWith(
        'tropical',
        'tropical|B|2026-07-01',
        'identity-target',
        'operator identity review',
      ),
    )
  })
})
