import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectScheduleWorkbenchPage } from './ProjectScheduleWorkbenchPage'

const syncProjectScheduleReviewItemsMock = vi.fn()
const getProjectScheduleReviewItemsMock = vi.fn()
const getProjectScheduleReviewItemEventsMock = vi.fn()
const patchProjectScheduleReviewItemMock = vi.fn()
const getProjectsMock = vi.fn()
const getLocalUiRoleMock = vi.fn(() => 'operator' as 'operator' | 'viewer' | 'admin')

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getProjects: (...args: unknown[]) => getProjectsMock(...args),
      syncProjectScheduleReviewItems: (...args: unknown[]) => syncProjectScheduleReviewItemsMock(...args),
      getProjectScheduleReviewItems: (...args: unknown[]) => getProjectScheduleReviewItemsMock(...args),
      getProjectScheduleReviewItemEvents: (...args: unknown[]) => getProjectScheduleReviewItemEventsMock(...args),
      patchProjectScheduleReviewItem: (...args: unknown[]) => patchProjectScheduleReviewItemMock(...args),
    },
    getLocalUiRole: () => getLocalUiRoleMock(),
  }
})

const reviewItems = {
  available: true,
  count: 2,
  items: [
    {
      review_item_id: 'psri-1',
      stable_item_key: 'driver:DRV-A',
      item_type: 'driver',
      item_title: 'Review driver: Concrete pour',
      priority: 85,
      review_status: 'open',
      source_activity_id: 'DRV-A',
      source_metric_key: 'change_driver_analysis',
      source_signal_type: 'driver',
      confidence: 'production_backed',
      severity: 'high',
      cue_summary: 'Candidate driver sequence cue for PM review.',
      recommended_review_action: 'Review the linked activity sequence and downstream movement before disposition.',
      evidence_summary: 'Canonical activity merged from primary.xer.',
      caveats: [
        'This is a schedule-control review cue for PM follow-up. It is not a causation, responsibility, entitlement, compensability, or delay-damages determination.',
      ],
      evidence: {
        as_of: '2026-07-03',
        schedule_data_date: '2026-07-01',
        cue_category: 'change_driver',
        cue_label: 'Candidate change driver',
        recommended_review_action: 'Review the linked activity sequence and downstream movement before disposition.',
        evidence_summary: 'Canonical activity merged from primary.xer.',
        technical_evidence_available: true,
        technical_evidence: {
          import_id: 'imp-current',
          cpm_status: 'success',
        },
      },
      phase: 'Phase 1',
    },
    {
      review_item_id: 'psri-2',
      stable_item_key: 'milestone:MS-1',
      item_type: 'milestone',
      item_title: 'Milestone moved later: Substantial completion',
      priority: 72,
      review_status: 'watching',
      source_activity_id: 'MS-1',
      source_metric_key: 'milestones',
      confidence: 'production_backed',
      severity: 'high',
    },
  ],
}

function renderPage(path = '/projects/tropical/schedule/workbench?as_of=2026-07-03') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [{ path: '/projects/:projectKey/schedule/workbench', element: <ProjectScheduleWorkbenchPage /> }],
    { initialEntries: [path] },
  )
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('ProjectScheduleWorkbenchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getLocalUiRoleMock.mockReturnValue('operator')
    getProjectsMock.mockResolvedValue({
      surface: 'analytics.projects.list',
      projects: [{ project_key: 'tropical', display_name: 'Tropical Resort' }],
    })
    syncProjectScheduleReviewItemsMock.mockResolvedValue({ available: true, workbench: { available: true } })
    getProjectScheduleReviewItemsMock.mockResolvedValue(reviewItems)
    getProjectScheduleReviewItemEventsMock.mockResolvedValue({
      available: true,
      events: [{ event_type: 'created', created_at: '2026-07-03T10:00:00Z' }],
    })
    patchProjectScheduleReviewItemMock.mockResolvedValue({ item: reviewItems.items[0] })
  })

  it('syncs review items for operators and passes as_of', async () => {
    renderPage()

    await waitFor(() => {
      expect(syncProjectScheduleReviewItemsMock).toHaveBeenCalledWith('tropical', {
        asOf: '2026-07-03',
        comparisonBasis: 'prior_update',
      })
    })
    expect(getProjectScheduleReviewItemsMock).toHaveBeenCalledWith('tropical', {
      asOf: '2026-07-03',
      comparisonBasis: 'prior_update',
      reviewStatus: undefined,
      severity: undefined,
      sourceMetric: undefined,
      confidence: undefined,
      phase: undefined,
    })
    expect(await screen.findByText('Candidate change driver')).toBeInTheDocument()
    expect(screen.queryByText('imp-current')).not.toBeInTheDocument()
  })

  it('loads preview only for viewers without syncing', async () => {
    getLocalUiRoleMock.mockReturnValue('viewer')
    renderPage()

    await waitFor(() => {
      expect(getProjectScheduleReviewItemsMock).toHaveBeenCalledWith('tropical', {
      asOf: '2026-07-03',
      comparisonBasis: 'prior_update',
      reviewStatus: undefined,
      severity: undefined,
      sourceMetric: undefined,
      confidence: undefined,
      phase: undefined,
    })
    })
    expect(syncProjectScheduleReviewItemsMock).not.toHaveBeenCalled()
    expect(await screen.findByText(/Preview only/)).toBeInTheDocument()
    const card = screen.getByText('Candidate change driver').closest('article')
    expect(card).toBeTruthy()
    expect(within(card as HTMLElement).queryByText('Save notes')).not.toBeInTheDocument()
  })

  it('patches disposition and saves notes for operators', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Candidate change driver')
    const detailButtons = screen.getAllByRole('button', { name: 'Show detail' })
    await user.click(detailButtons[0])

    await waitFor(() => {
      expect(getProjectScheduleReviewItemEventsMock).toHaveBeenCalledWith('tropical', 'psri-1')
    })
    expect(screen.getByText(/not a causation/i)).toBeInTheDocument()

    const card = screen.getByText('Candidate change driver').closest('article')
    const select = within(card as HTMLElement).getByRole('combobox')
    await user.selectOptions(select, 'reviewed')

    await waitFor(() => {
      expect(patchProjectScheduleReviewItemMock).toHaveBeenCalledWith('tropical', 'psri-1', {
        review_status: 'reviewed',
        pm_notes: undefined,
      })
    })

    const notes = screen.getByRole('textbox')
    await user.type(notes, 'checked driver')
    await user.click(screen.getByRole('button', { name: 'Save notes' }))

    await waitFor(() => {
      expect(patchProjectScheduleReviewItemMock).toHaveBeenCalledWith('tropical', 'psri-1', {
        review_status: 'open',
        pm_notes: 'checked driver',
      })
    })
  })

  it('keeps technical evidence collapsed by default and shows advisory copy', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Candidate change driver')
    expect(screen.getByText(/Sequence cues only/)).toBeInTheDocument()
    expect(screen.queryByText('imp-current')).not.toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Show detail' })[0])
    expect(screen.getByText(/Show technical evidence/)).toBeInTheDocument()
    expect(screen.queryByText(/Raw technical payload/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Show technical evidence' }))
    expect(screen.getByText(/Raw technical payload/)).toBeInTheDocument()
  })
})
