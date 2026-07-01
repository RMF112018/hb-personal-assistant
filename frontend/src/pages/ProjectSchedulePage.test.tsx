import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectSchedulePage } from './ProjectSchedulePage'

const getProjectsMock = vi.fn()
const getProjectScheduleSummaryMock = vi.fn()
const getProjectScheduleMetricTrendsMock = vi.fn()
const getProjectScheduleBaselineMock = vi.fn()
const getProjectScheduleDrilldownMock = vi.fn()
const getProjectScheduleControlsMock = vi.fn()
const getProjectScheduleBaselinesMock = vi.fn()
const downloadProjectScheduleExportMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getProjects: (...args: unknown[]) => getProjectsMock(...args),
      getProjectScheduleSummary: (...args: unknown[]) => getProjectScheduleSummaryMock(...args),
      getProjectScheduleMetricTrends: (...args: unknown[]) => getProjectScheduleMetricTrendsMock(...args),
      getProjectScheduleBaseline: (...args: unknown[]) => getProjectScheduleBaselineMock(...args),
      getProjectScheduleDrilldown: (...args: unknown[]) => getProjectScheduleDrilldownMock(...args),
      downloadProjectScheduleExport: (...args: unknown[]) => downloadProjectScheduleExportMock(...args),
      getProjectScheduleControls: (...args: unknown[]) => getProjectScheduleControlsMock(...args),
      getProjectScheduleBaselines: (...args: unknown[]) => getProjectScheduleBaselinesMock(...args),
      updateProjectScheduleBaselines: vi.fn(),
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

function trendMetric(key: string, overrides: Record<string, unknown> = {}) {
  return {
    available: true,
    metric_key: key,
    display_name: key.replaceAll('_', ' '),
    readiness_status: 'ready_after_trend_aggregation',
    as_of_date: '2026-06-28',
    basis_labels: ['source_export', 'prior_update'],
    comparison_basis: ['prior_update'],
    weighting_basis: key === 'schedule_changes_over_time' ? 'change_count' : 'duration_weighted',
    caveats: ['Review cue only — not causation, entitlement, responsibility, or compensability.'],
    formula_summary: 'Backend-provided formula summary.',
    points: [
      {
        data_date: '2026-06-16',
        period: '2026-06-16',
        month: '2026-06',
        date_family: 'planned_start',
        activity_count: 2,
        planned_percent_complete: 0.25,
        actual_percent_complete: 0.2,
        schedule_performance_ratio: 0.8,
        delay_days: 0,
        gain_days: 0,
        net_movement_days: 0,
        categories: { activity_changes: 1, logic_changes: 0, duration_changes: 0, critical_changes: 0, added_activity_changes: 0, deleted_activity_changes: 0 },
        health_index: 82,
        required_recovery_days: 4,
        critical_path_length_index: 120,
        series: [
          { float_basis: 'source_export', total_float_days: -10 },
          { float_basis: 'computed_cpm', total_float_days: -8 },
        ],
      },
      {
        data_date: '2026-06-23',
        period: '2026-06-23',
        month: '2026-06',
        date_family: 'actual_finish',
        activity_count: 3,
        planned_percent_complete: 0.35,
        actual_percent_complete: 0.3,
        schedule_performance_ratio: 0.86,
        delay_days: 9,
        gain_days: 0,
        net_movement_days: 9,
        categories: { activity_changes: 3, logic_changes: 1, duration_changes: 1, critical_changes: 1, added_activity_changes: 1, deleted_activity_changes: 0 },
        health_index: 84,
        required_recovery_days: 7,
        critical_path_length_index: 130,
        series: [
          { float_basis: 'source_export', total_float_days: -12 },
          { float_basis: 'computed_cpm', total_float_days: -9 },
        ],
      },
    ],
    summary: {},
    unavailable_variants: [{ variant: 'cost_weighted', reason: 'cost_weighted_unavailable' }],
    data_quality_notes: ['Backend note for PM review.'],
    ...overrides,
  }
}

function controlsResponse(overrides: Record<string, unknown> = {}) {
  return {
    available: true,
    advisory_posture: 'sequence_cues_not_causation',
    as_of_date: '2026-06-28',
    schedule_data_date: '2026-06-23',
    comparison_basis: 'prior_update',
    summary: {
      overall_status: 'watch',
      headline: 'Schedule controls recommend PM review of priority sequence and float signals.',
      supporting_points: ['1 open review workbench cues in the selected basis.'],
      primary_review_focus: 'Candidate change driver: Envelope Completion',
      open_review_item_count: 1,
      high_priority_review_item_count: 1,
    },
    top_controls: [
      {
        control_id: 'ctrl-1',
        category: 'critical_path',
        severity: 'review',
        confidence: 'high',
        title: 'Candidate change driver: Envelope Completion',
        summary: 'Candidate driver sequence cue for PM review.',
        recommended_action: 'Review the linked activity sequence and downstream movement before disposition.',
        links: {
          driver_detail: '/projects/tropical/schedule/driver-detail?activity_id=DRV-A&comparison_basis=prior_update',
          review_item: '/projects/tropical/schedule/workbench?review=driver%3ADRV-A&comparison_basis=prior_update',
        },
      },
    ],
    sections: {
      cpm_observability: {
        available: true,
        headline: 'CPM recompute succeeded for the selected schedule version.',
      },
    },
    links: {
      review_workbench: '/projects/tropical/schedule/workbench?comparison_basis=prior_update',
    },
    ...overrides,
  }
}

function trendResponse(overrides: Record<string, unknown> = {}) {
  return {
    available: true,
    project_key: 'tropical',
    as_of_date: '2026-06-28',
    metrics: [
      trendMetric('monthly_activity_start_finish_distribution', { weighting_basis: 'activity_count' }),
      trendMetric('planned_vs_actual_percent_complete'),
      trendMetric('schedule_performance_ratio'),
      trendMetric('schedule_delay_over_time', { weighting_basis: 'calendar_days' }),
      trendMetric('schedule_changes_over_time', { weighting_basis: 'change_count' }),
      trendMetric('project_schedule_health_index', { weighting_basis: 'weighted_penalty_model' }),
      trendMetric('schedule_feasibility_score', {
        available: false,
        reason: 'dependency_inputs_unavailable',
        points: [],
        data_quality_notes: ['Feasibility score is waiting on dependency inputs.'],
      }),
      trendMetric('required_recovery_days', { weighting_basis: 'calendar_days' }),
      trendMetric('critical_path_length_index'),
      trendMetric('total_float_consumption_index', { weighting_basis: 'float_days', basis_labels: ['source_export', 'computed_cpm', 'prior_update'] }),
      trendMetric('delay_analysis', {
        available: false,
        reason: 'prior_update_diff_unavailable',
        points: [],
        caveats: ['This metric is a schedule review cue only; it is not a causation, entitlement, responsibility, or compensability finding.'],
      }),
      trendMetric('window_start_accuracy', {
        available: false,
        reason: 'no_activities_in_window',
        points: [],
        partial_dimension_support: true,
        data_quality_notes: ['UDF dimension coverage is partial.'],
      }),
      trendMetric('window_finish_accuracy', { available: false, reason: 'no_activities_in_window', points: [] }),
      trendMetric('should_have_finished_status', { available: false, reason: 'no_due_unfinished_activities', points: [] }),
      trendMetric('critical_issues_category_model', {
        available: false,
        reason: 'no_candidates',
        points: [],
        caveats: ['This metric is a schedule review cue only; it is not a causation, entitlement, responsibility, or compensability finding.'],
      }),
    ],
    errors: [
      { metric_key: 'schedule_compression_ratio', detail: 'metric_not_trend_ready' },
    ],
    ...overrides,
  }
}

function renderPage(
  response = scheduleResponse(),
  trends: Promise<unknown> | unknown = trendResponse(),
  initialEntry = '/projects/tropical/schedule',
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      { path: '/projects', element: <div>Projects list</div> },
      { path: '/projects/:projectKey/schedule', element: <ProjectSchedulePage /> },
    ],
    { initialEntries: [initialEntry] },
  )
  getProjectsMock.mockResolvedValue(projectsResponse)
  getProjectScheduleSummaryMock.mockResolvedValue(response)
  getProjectScheduleMetricTrendsMock.mockReturnValue(trends instanceof Promise ? trends : Promise.resolve(trends))
  getProjectScheduleBaselineMock.mockResolvedValue({
    available: true,
    baseline_summary: (response as Record<string, any>).baseline_summary || {},
  })
  getProjectScheduleDrilldownMock.mockResolvedValue({ count: 1, items: [] })
  getProjectScheduleControlsMock.mockResolvedValue(controlsResponse())
  getProjectScheduleBaselinesMock.mockResolvedValue({
    available: true,
    slots: [
      { slot_key: 'current_contract_baseline', slot_label: 'Current Contract Baseline', status: 'missing', selection: null },
      { slot_key: 'previous_progress_update_baseline', slot_label: 'Previous Progress Update Baseline', status: 'missing', selection: null },
      { slot_key: 'secondary_progress_update_baseline', slot_label: 'Secondary Progress Update Baseline', status: 'missing', selection: null },
    ],
    available_versions: [],
  })
  downloadProjectScheduleExportMock.mockResolvedValue(undefined)
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
    getProjectScheduleMetricTrendsMock.mockReset()
    getProjectScheduleBaselineMock.mockReset()
    getProjectScheduleDrilldownMock.mockReset()
    getProjectScheduleControlsMock.mockReset()
    getProjectScheduleBaselinesMock.mockReset()
    downloadProjectScheduleExportMock.mockReset()
  })

  it('renders baseline anchor helper text and comparison context in controls', async () => {
    renderPage()

    expect(
      await screen.findByText(/Assign a prior schedule update to each of the three named comparison anchors/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/Comparing against Prior Update/)).toBeInTheDocument()
  })

  it('humanizes missing named baseline controls state without raw reason codes', async () => {
    renderPage()
    getProjectScheduleControlsMock.mockImplementation((_projectKey: string, opts?: { comparisonBasis?: string }) => {
      if (opts?.comparisonBasis === 'current_contract_baseline') {
        return Promise.resolve({
          available: false,
          reason: 'baseline_not_selected',
          baseline_context: { slot_label: 'Current Contract Baseline' },
          comparison_basis: 'current_contract_baseline',
        })
      }
      return Promise.resolve(controlsResponse())
    })

    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Current Contract Baseline' }))
    expect(
      await screen.findByText(/Select a prior schedule update for Current Contract Baseline in Baseline Anchors below/i),
    ).toBeInTheDocument()
    expect(screen.queryByText(/baseline_not_selected/)).not.toBeInTheDocument()
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
      '/projects/tropical/schedule/workbench',
    )
    expect(screen.getByText('Where To Look First')).toBeInTheDocument()
    expect(screen.getAllByText('Candidate Drivers').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/appears connected to 3 downstream activities/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Forecast 2026-12-15')).toBeInTheDocument()
    expect(screen.getAllByText('Review Next').length).toBeGreaterThanOrEqual(1)
    expect(await screen.findByText('Schedule Controls')).toBeInTheDocument()
    expect(screen.getByText(/do not determine causation, entitlement, or responsibility/i)).toBeInTheDocument()
    expect(await screen.findByText('Controls Trend Analytics')).toBeInTheDocument()
  })

  it('requests controls trends without as-of when latest context is selected and renders supported panels', async () => {
    renderPage()

    expect(await screen.findByText('Trend Analytics')).toBeInTheDocument()
    expect(getProjectScheduleMetricTrendsMock).toHaveBeenCalledWith('tropical', {
      asOf: undefined,
      metrics: expect.arrayContaining([
        'monthly_activity_start_finish_distribution',
        'planned_vs_actual_percent_complete',
        'schedule_performance_ratio',
        'schedule_changes_over_time',
      ]),
    })
    expect(screen.getByText('Controls Overview')).toBeInTheDocument()
    expect(screen.getByText('Monthly Activity Start/Finish Distribution')).toBeInTheDocument()
    expect(screen.getByText('Planned vs Actual Percent Complete')).toBeInTheDocument()
    expect(screen.getByText('Schedule Performance Ratio')).toBeInTheDocument()
    expect(screen.getByText('Schedule Delay Over Time')).toBeInTheDocument()
    expect(screen.getByText('Schedule Changes Over Time')).toBeInTheDocument()
    expect((await screen.findAllByText('duration weighted')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('prior update').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Backend note for PM review.').length).toBeGreaterThan(0)
    expect(screen.queryByText(/cost weighted/i)).not.toBeInTheDocument()
  })

  it('passes selected as-of to summary, baseline, trends, drilldown, and export calls', async () => {
    const user = userEvent.setup()
    renderPage(
      scheduleResponse({
        technical_links: {
          schedule_import_url: '/schedules/imports?project=tropical',
          computed_cpm_url: '/schedules/cpm?project=tropical&version=tropical%7CS1%7C2026-06-23',
          schedule_export_url: '/api/projects/tropical/schedule/export',
        },
      }),
      trendResponse(),
      '/projects/tropical/schedule?as_of=2026-06-16',
    )

    expect(await screen.findByLabelText('As-of date')).toHaveValue('2026-06-16')
    await waitFor(() => {
      expect(getProjectScheduleSummaryMock).toHaveBeenCalledWith('tropical', { asOf: '2026-06-16' })
      expect(getProjectScheduleBaselineMock).toHaveBeenCalledWith('tropical', { asOf: '2026-06-16' })
      expect(getProjectScheduleMetricTrendsMock).toHaveBeenCalledWith(
        'tropical',
        expect.objectContaining({ asOf: '2026-06-16' }),
      )
      expect(getProjectScheduleControlsMock).toHaveBeenCalledWith('tropical', {
        asOf: '2026-06-16',
        comparisonBasis: 'prior_update',
      })
    })

    expect(screen.getByRole('link', { name: 'Open Workbench' })).toHaveAttribute(
      'href',
      '/projects/tropical/schedule/workbench?as_of=2026-06-16',
    )

    await user.click(screen.getByRole('button', { name: 'View 2' }))
    await waitFor(() => {
      expect(getProjectScheduleDrilldownMock).toHaveBeenCalledWith('tropical', 'remaining_later', {
        limit: 100,
        offset: 0,
        asOf: '2026-06-16',
        comparisonBasis: 'prior_update',
      })
    })

    await user.click(screen.getByRole('button', { name: 'Export Memo' }))
    expect(downloadProjectScheduleExportMock).toHaveBeenCalledWith('tropical', 'markdown', {
      asOf: '2026-06-16',
      comparisonBasis: 'prior_update',
    })
  })

  it('omits as-of from page helper calls when latest context is selected', async () => {
    renderPage(scheduleResponse({ as_of_date: undefined }))

    await screen.findByText('Schedule Controls')
    expect(getProjectScheduleControlsMock).toHaveBeenCalledWith('tropical', {
      asOf: undefined,
      comparisonBasis: 'prior_update',
    })
    expect(getProjectScheduleSummaryMock).toHaveBeenCalledWith('tropical', { asOf: undefined })
    expect(getProjectScheduleBaselineMock).toHaveBeenCalledWith('tropical', { asOf: undefined })
    expect(getProjectScheduleMetricTrendsMock).toHaveBeenCalledWith('tropical', expect.objectContaining({
      asOf: undefined,
    }))
  })

  it('renders blocked and empty metric states without activating unavailable metrics', async () => {
    renderPage()

    expect(await screen.findByText('Blocked / Not Yet Available Metrics')).toBeInTheDocument()
    expect(screen.getByText('Schedule Compression Ratio')).toBeInTheDocument()
    expect(await screen.findByText('Execution Reliability / Review Cues')).toBeInTheDocument()
    expect(screen.getAllByText(/Not yet available/).length).toBeGreaterThanOrEqual(6)
    expect(screen.getByText('Partial UDF dimension coverage reported by backend.')).toBeInTheDocument()
    expect(await screen.findByText('Feasibility score is waiting on dependency inputs.')).toBeInTheDocument()
  })

  it('renders available UDF metric panels when backend marks them available', async () => {
    renderPage(scheduleResponse(), trendResponse({
      metrics: [
        trendMetric('window_start_accuracy', {
          available: true,
          partial_dimension_support: true,
          data_quality_notes: ['Filter Out coverage is sparse on 12% of activities.'],
          points: [{
            data_date: '2026-06-28',
            on_time_count: 4,
            late_count: 1,
            did_not_start_count: 2,
            accuracy_ratio: 0.57,
          }],
        }),
      ],
      errors: [],
    }))

    expect(await screen.findByText('Window Start Accuracy')).toBeInTheDocument()
    expect(await screen.findByText('On time')).toBeInTheDocument()
    expect(screen.getByText('Partial UDF dimension coverage reported by backend.')).toBeInTheDocument()
    expect(screen.queryByText('Requires UDF normalization')).not.toBeInTheDocument()
    expect(document.body.textContent || '').not.toMatch(/responsible party|entitlement finding/i)
  })

  it('renders selected-baseline compression readiness when provided by the backend', async () => {
    renderPage(scheduleResponse(), trendResponse({
      metrics: [
        trendMetric('schedule_compression_ratio', {
          available: false,
          reason: 'selected_baseline_recompute_required',
          points: [],
          selected_baseline: {
            selected_baseline_label: 'TWNU18',
            selected_baseline_data_date: '2026-06-16',
            recompute_required: true,
          },
          data_quality_notes: ['Selected-baseline matching or duration facts are incomplete.'],
        }),
      ],
      errors: [],
    }))

    expect(await screen.findByText('Schedule Compression Ratio')).toBeInTheDocument()
    expect(await screen.findByText('Selected-baseline matching or duration facts are incomplete.')).toBeInTheDocument()
    expect(await screen.findByText(/Selected baseline: TWNU18 \(2026-06-16\).*Recompute\/readiness required/)).toBeInTheDocument()
    expect(screen.queryByText('Not yet available: Requires selected baseline')).not.toBeInTheDocument()
  })

  it('renders accessible loading and clean error states for trend payloads', async () => {
    let resolveTrends: (value: unknown) => void = () => {}
    const loadingView = renderPage(scheduleResponse(), new Promise((resolve) => { resolveTrends = resolve }))

    expect(await screen.findByRole('status')).toHaveTextContent('Loading schedule controls trends')
    resolveTrends(trendResponse({
      metrics: [trendMetric('monthly_activity_start_finish_distribution', { points: [], data_quality_notes: [] })],
      errors: [],
    }))
    expect(await screen.findByText('No trend points are available for the selected update window.')).toBeInTheDocument()
    loadingView.unmount()

    let rejectTrends: (reason?: unknown) => void = () => {}
    renderPage(scheduleResponse(), new Promise((_, reject) => { rejectTrends = reject }))
    expect(await screen.findByRole('status')).toHaveTextContent('Loading schedule controls trends')
    rejectTrends(new Error('500 Internal Server Error: stack trace detail'))
    expect(await screen.findByRole('alert')).toHaveTextContent('Schedule controls trends are unavailable right now.')
    expect(document.body.textContent || '').not.toContain('stack trace detail')
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

  it('shows import button on no-schedule state', async () => {
    renderPage(scheduleResponse({
      status: 'no_schedule',
      current_schedule: { available: false },
      schedule_story: {
        headline: 'No schedule update is imported for this project.',
        synopsis: 'Import a schedule update to review remaining work.',
      },
    }))

    expect(await screen.findByText('No schedule update is imported for this project.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Import schedule package/i })).toBeInTheDocument()
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

  it('suppresses raw activity ids in default driver labels', async () => {
    renderPage()
    await screen.findByText('Envelope Completion')
    expect(screen.queryByText('(A1)')).not.toBeInTheDocument()
    expect(screen.queryByText('A1')).not.toBeInTheDocument()
  })

  it('renders top controls without raw activity id as the primary label', async () => {
    renderPage()
    expect(await screen.findByText('Candidate change driver: Envelope Completion')).toBeInTheDocument()
    const topControlsRegion = screen.getByText('Top controls').closest('div')
    expect(topControlsRegion?.textContent || '').not.toMatch(/\bDRV-A\b/)
  })

  it('renders four controls comparison choices and defaults to Prior Update', async () => {
    renderPage()
    expect(await screen.findByRole('button', { name: 'Prior Update' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Current Contract Baseline' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous Progress Update Baseline' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Secondary Progress Update Baseline' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Since selected baseline' })).not.toBeInTheDocument()
    expect(await screen.findByText('Controls Trend Analytics')).toBeInTheDocument()
  })

  it('requests named baseline comparison for controls when selected', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Current Contract Baseline' }))
    await waitFor(() => {
      expect(getProjectScheduleControlsMock).toHaveBeenLastCalledWith('tropical', {
        asOf: undefined,
        comparisonBasis: 'current_contract_baseline',
      })
    })
  })

  it('propagates driver comparison basis to controls and driver detail links', async () => {
    const user = userEvent.setup()
    renderPage(
      scheduleResponse({
        change_driver_analysis: {
          available: true,
          advisory_posture: 'sequence_cues_not_causation',
          prior_update: scheduleResponse().change_driver_analysis.prior_update,
          baseline: {
            available: true,
            advisory_posture: 'sequence_cues_not_causation',
            summary: { candidate_driver_count: 1 },
            top_drivers: [
              { activity_id: 'A1', activity_name: 'Envelope Completion', review_priority: 80, downstream_count: 2 },
            ],
            review_drilldowns: {
              drivers: { count: 1, items: [{ activity_id: 'A1', activity_name: 'Envelope Completion' }] },
            },
          },
        },
      }),
    )

    await user.click(await screen.findByRole('button', { name: 'Since selected baseline' }))
    await waitFor(() => {
      expect(getProjectScheduleControlsMock).toHaveBeenLastCalledWith('tropical', {
        asOf: undefined,
        comparisonBasis: 'baseline',
      })
    })
    const driverLink = await screen.findByRole('link', { name: 'Envelope Completion' })
    expect(driverLink).toHaveAttribute('href', expect.stringContaining('basis=baseline'))
  })
})
