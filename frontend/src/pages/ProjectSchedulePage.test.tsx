import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectSchedulePage } from './ProjectSchedulePage'

const getProjectsMock = vi.fn()
const getProjectScheduleSummaryMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getProjects: (...args: unknown[]) => getProjectsMock(...args),
      getProjectScheduleSummary: (...args: unknown[]) => getProjectScheduleSummaryMock(...args),
    },
  }
})

const projectsResponse = {
  surface: 'analytics.projects.list',
  projects: [{ project_key: 'tropical', display_name: 'Tropical Resort' }],
}

function action(n: number) {
  return {
    priority: 100 - n,
    code: `action_${n}`,
    title: `Review item ${n}`,
    explanation: `Evidence-backed review item ${n}.`,
    recommended_review: `Review step ${n}.`,
  }
}

function scheduleResponse(overrides = {}) {
  const actions = [1, 2, 3, 4, 5, 6].map(action)
  return {
    surface: 'project_schedule_hub',
    project_key: 'tropical',
    project_display_name: 'Tropical Resort',
    as_of_date: '2026-06-28',
    status: 'partial',
    current_schedule: {
      available: true,
      friendly_label: 'TWNU19',
      data_date: '2026-06-23',
    },
    previous_update: {
      available: true,
      friendly_label: 'TWNU18',
      data_date: '2026-06-16',
    },
    readiness: {
      ready_for_pm_review: true,
      partial_reasons: ['cpm_unavailable'],
      cpm_unavailable: { required: true, reason: 'no persisted computed CPM run' },
    },
    schedule_story: {
      headline: 'Forecast finish moved 9 days later since the previous update.',
      synopsis: 'The current update is TWNU19 with data date 2026-06-23.',
      what_changed: '2 remaining activities moved later since TWNU18.',
      why_it_matters: 'Forecast finish risk remains elevated despite a flat headline delta.',
      primary_change_driver: '2 remaining activities moved later.',
      primary_driver_narrative:
        'The largest movement appears concentrated around WBS-A. Envelope Completion moved or extended by 9 days and appears connected to 3 downstream activities. Review this sequence first.',
      recent_progress_summary: '3 activities completed.',
      remaining_work_summary: '12 activities remain open.',
      critical_path_summary: 'Computed CPM is unavailable, so critical-path confidence is limited.',
      review_next_summary: 'Review remaining negative-float work',
      caveats: ['No claim conclusions.'],
    },
    schedule_trust: { status: 'trusted', review_reasons: [] },
    identity_review: { status: 'trusted', review_reasons: [], identity_review_url: '/schedules/identity-review?project=tropical' },
    source_float_summary: {
      basis: 'source_export_float',
      negative_float_remaining_count: 1,
      zero_float_remaining_count: 2,
      near_critical_source_count: 4,
    },
    computed_cpm_summary: {
      basis: 'application_computed_cpm',
      available: false,
      critical_remaining_count: 3,
      near_critical_remaining_count: 4,
    },
    review_drilldowns: {
      remaining_later: {
        count: 2,
        items: [{ activity_id: 'A1', activity_name: 'Envelope Completion', finish_delta_days: 9 }],
      },
    },
    review_workbench: {
      available: true,
      summary: { open_count: 2, watching_count: 1, reviewed_count: 0, dismissed_count: 0, total_count: 3 },
      preview: [
        { review_item_id: 'ri-1', stable_item_key: 'driver:A1', item_title: 'Review driver: Envelope Completion', review_status: 'open', priority: 88 },
      ],
    },
    change_driver_analysis: {
      available: true,
      advisory_posture: 'sequence_cues_not_causation',
      prior_update: {
        available: true,
        advisory_posture: 'sequence_cues_not_causation',
        summary: {
          candidate_driver_count: 2,
        top_wbs_area: 'WBS-A',
        top_driver_activity_name: 'Envelope Completion',
        top_driver_downstream_count: 3,
        top_driver_milestone_touch_count: 1,
        logic_change_count: 0,
        duration_change_count: 1,
        milestone_impact_count: 1,
      },
      top_drivers: [
        {
          activity_id: 'A1',
          activity_name: 'Envelope Completion',
          wbs_code: 'WBS-A',
          finish_delta_days: 9,
          downstream_moved_later_count: 3,
          review_priority: 72,
        },
      ],
      review_drilldowns: {
        drivers: { count: 2, items: [{ activity_id: 'A1', activity_name: 'Envelope Completion', wbs_code: 'WBS-A', finish_delta_days: 9, downstream_moved_later_count: 3, review_priority: 72 }] },
        logic_changes: { count: 0, items: [] },
        duration_changes: { count: 1, items: [{ activity_id: 'A1', activity_name: 'Envelope Completion', duration_delta_days: 5, finish_delta_days: 9, downstream_moved_later_count: 3 }] },
        milestone_impacts: { count: 1, items: [{ activity_id: 'MS1', activity_name: 'Substantial completion', movement_days: 7, candidate_drivers: [{ activity_name: 'Envelope Completion' }] }] },
        impacted_successors: { count: 3, items: [{ activity_id: 'B1', activity_name: 'Successor B', finish_delta_days: 5 }] },
      },
      },
      baseline: { available: false, reason: 'baseline_unavailable' },
    },
    trend_series: {
      available: true,
      metrics: [
        {
          friendly_label: 'TWNU18',
          data_date: '2026-06-16',
          forecast_finish: '2026-12-06',
          remaining_activity_count: 13,
          negative_float_remaining_count: 1,
          finish_moved_later_count: 0,
        },
        {
          friendly_label: 'TWNU19',
          data_date: '2026-06-23',
          forecast_finish: '2026-12-15',
          remaining_activity_count: 12,
          negative_float_remaining_count: 1,
          finish_moved_later_count: 2,
        },
      ],
    },
    command_summary: {
      forecast_finish: '2026-12-15',
      forecast_finish_delta_days: 9,
      remaining_activity_count: 12,
      remaining_milestone_count: 2,
      critical_remaining_count: 3,
      near_critical_remaining_count: 4,
      negative_float_remaining_count: 1,
      zero_float_remaining_count: 2,
    },
    remaining_health: {
      status: 'watch',
      drivers: ['Remaining activities moved later since the prior update.'],
      float_pressure: {
        negative_float_count: 1,
        zero_float_count: 2,
        near_critical_count: 4,
      },
    },
    change_impact: {
      available: true,
      comparison_basis: 'resolved_finish_date',
      direct_remaining_changes: {
        summary: {
          common_remaining_activities: 10,
          new_remaining_activities: 2,
          finish_moved_later_count: 2,
          finish_moved_earlier_count: 1,
          finish_changed_count: 3,
          worsened_float_count: 1,
          improved_float_count: 1,
          moved_remaining_milestones_count: 1,
          changed_count: 3,
        },
      },
      upstream_remaining_impact: {
        summary: {
          changed_upstream_count: 1,
        },
      },
    },
    computed_cpm: { available: false },
    critical_path: { available: false, activity_count: null },
    trend_summary: {
      available: false,
      reason: 'at_least_two_comparable_updates_required',
      comparable_update_count: 1,
    },
    actions: {
      preview_limit: 5,
      preview: actions.slice(0, 5),
      all_items: actions,
      total_count: 6,
    },
    technical_links: {
      schedule_import_url: '/schedules/imports?project=tropical',
      computed_cpm_url: '/schedules/cpm?project=tropical&version=tropical%7CS1%7C2026-06-23',
    },
    technical_evidence: {
      schedule_version_key: 'tropical|S1|2026-06-23',
      schedule_identity_key: 'identity-main',
      computed_cpm_health: {},
      identity_safe: true,
      source_export_proxy: true,
    },
    ...overrides,
  }
}

function renderPage(response = scheduleResponse()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      { path: '/projects', element: <div>Projects list</div> },
      { path: '/projects/:projectKey/schedule', element: <ProjectSchedulePage /> },
    ],
    { initialEntries: ['/projects/tropical/schedule'] },
  )
  getProjectsMock.mockResolvedValue(projectsResponse)
  getProjectScheduleSummaryMock.mockResolvedValue(response)
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('ProjectSchedulePage', () => {
  beforeEach(() => {
    getProjectsMock.mockReset()
    getProjectScheduleSummaryMock.mockReset()
  })

  it('renders a PM-facing above-fold schedule story and scoped project tab', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Schedule' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Schedule' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText(/As of 2026-06-28/)).toBeInTheDocument()
    expect(screen.getByText(/Data date 2026-06-23/)).toBeInTheDocument()
    expect(screen.getByText('Forecast finish moved 9 days later since the previous update.')).toBeInTheDocument()
    expect(screen.getByText('Remaining-Work Health')).toBeInTheDocument()
    expect(screen.getByText('Remaining Earlier')).toBeInTheDocument()
    expect(screen.getByText('Milestones Later')).toBeInTheDocument()
    expect(screen.getAllByText('What Changed').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Why It Matters')).toBeInTheDocument()
    expect(screen.getByText('Source Float (Export)')).toBeInTheDocument()
    expect(screen.getByText('Computed CPM')).toBeInTheDocument()
    expect(screen.getByText('Review Workbench')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Workbench' })).toHaveAttribute(
      'href',
      '/projects/tropical/schedule/workbench?as_of=2026-06-28',
    )
    expect(screen.getByText('Where To Look First')).toBeInTheDocument()
    expect(screen.getAllByText('Candidate Drivers').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/appears connected to 3 downstream activities/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Forecast 2026-12-15')).toBeInTheDocument()
    expect(screen.getAllByText('Review Next').length).toBeGreaterThanOrEqual(1)
  })

  it('shows trust banner when schedule trust requires review', async () => {
    renderPage(scheduleResponse({
      schedule_trust: { status: 'review_required', review_reasons: ['low_activity_overlap'] },
      identity_review: {
        status: 'review_required',
        review_reasons: ['low_activity_overlap'],
        identity_review_url: '/schedules/identity-review?project=tropical',
      },
    }))

    expect(await screen.findByText('Schedule Trust')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Identity Review' })).toHaveAttribute(
      'href',
      '/schedules/identity-review?project=tropical',
    )
  })

  it('shows only the top 5 action items by default and can view all', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('Review item 1')).toBeInTheDocument()
    expect(screen.getByText('Review item 5')).toBeInTheDocument()
    expect(screen.queryByText('Review item 6')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'View All' }))

    expect(screen.getByText('Review item 6')).toBeInTheDocument()
  })

  it('links no-schedule state to schedule import with project query', async () => {
    renderPage(scheduleResponse({
      status: 'no_schedule',
      current_schedule: { available: false },
      schedule_story: {
        headline: 'No schedule update is imported for this project.',
        synopsis: 'Import a schedule update to review remaining work.',
      },
    }))

    expect(await screen.findByText('No schedule update is imported for this project.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Import Schedule' })).toHaveAttribute(
      'href',
      '/schedules/imports?project=tropical',
    )
  })

  it('does not render raw technical identifiers in the default view', async () => {
    renderPage()

    await screen.findByText('Forecast finish moved 9 days later since the previous update.')
    const rendered = document.body.textContent || ''
    for (const forbidden of [
      'schedule_version_key',
      'schedule_identity_key',
      'computed_cpm_health',
      'identity_safe',
      'source_export_proxy',
      'tropical|S1|2026-06-23',
    ]) {
      expect(rendered).not.toContain(forbidden)
    }
  })
})
