/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { TechnicalDetails } from '../components/common/TechnicalDetails'
import { ProjectScheduleDashboardVisualizations } from '../components/projects/ProjectScheduleDashboardVisualizations'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'
import { api } from '../lib/api'
import type { ProjectScheduleSummaryResponse } from '../lib/api'

function text(value: unknown, fallback = 'Not available') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function formatWbs(item: Record<string, unknown>) {
  const display = item.display_wbs ?? item.wbs_code
  if (display === null || display === undefined || display === '' || display === '—') {
    const reason = item.wbs_context_reason
    return reason ? `WBS not in source (${String(reason)})` : 'WBS not in comparison row'
  }
  return String(display)
}

function num(value: unknown, fallback = '0') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function toneFor(status: unknown) {
  const value = String(status || '').toLowerCase()
  if (value === 'good' || value === 'trusted') return 'border-emerald-800/70'
  if (value === 'watch') return 'border-amber-800/70'
  if (value === 'at_risk' || value === 'blocked' || value === 'review_required' || value === 'excluded') {
    return 'border-red-900/70'
  }
  return 'border-[var(--hb-border)]'
}

function MetricTile({ label, value, helper }: { label: string; value: unknown; helper?: string }) {
  return (
    <div className="rounded border border-[var(--hb-border)] bg-black/10 p-3">
      <div className="text-xs text-[var(--hb-muted)]">{label}</div>
      <div className="mt-1 text-xl font-semibold">{text(value, '—')}</div>
      {helper && <div className="mt-1 text-xs text-[var(--hb-muted)]">{helper}</div>}
    </div>
  )
}

function ReadinessList({ readiness }: { readiness: Record<string, any> }) {
  const partial = Array.isArray(readiness?.partial_reasons) ? readiness.partial_reasons : []
  if (!partial.length) return null
  return (
    <div className="flex flex-wrap gap-2">
      {partial.slice(0, 6).map((key: string) => (
        <span key={key} className="badge">
          {key.replaceAll('_', ' ')}
        </span>
      ))}
    </div>
  )
}

function TrustBanner({
  scheduleTrust,
  identityReview,
}: {
  scheduleTrust: Record<string, any>
  identityReview: Record<string, any>
}) {
  const status = String(scheduleTrust?.status || identityReview?.status || 'unknown')
  if (status === 'trusted') return null
  const reasons = Array.isArray(scheduleTrust?.review_reasons)
    ? scheduleTrust.review_reasons
    : Array.isArray(identityReview?.review_reasons)
      ? identityReview.review_reasons
      : []
  const reviewUrl = text(identityReview?.identity_review_url, '/schedules/identity-review')
  return (
    <div className={`card ${toneFor(status)}`}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--hb-muted)]">Schedule Trust</div>
          <div className="mt-1 font-semibold capitalize">{status.replaceAll('_', ' ')}</div>
          <p className="mt-1 text-sm text-[var(--hb-muted)]">
            {status === 'excluded'
              ? 'The current update is excluded from the trusted schedule series.'
              : 'Schedule comparisons are gated until identity and series membership are resolved.'}
          </p>
          {reasons.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {reasons.slice(0, 4).map((reason: string) => (
                <span key={reason} className="badge">
                  {reason.replaceAll('_', ' ')}
                </span>
              ))}
            </div>
          )}
        </div>
        <Link className="badge shrink-0" to={reviewUrl}>
          Open Identity Review
        </Link>
      </div>
    </div>
  )
}

const DRIVER_TABS = [
  { id: 'drivers', label: 'Candidate Drivers' },
  { id: 'impacted_successors', label: 'Impacted Successors' },
  { id: 'logic_changes', label: 'Logic Changes' },
  { id: 'duration_changes', label: 'Duration Changes' },
  { id: 'milestone_impacts', label: 'Milestone Impacts' },
] as const

const SCHEDULE_CONTROLS_METRICS = [
  'monthly_activity_start_finish_distribution',
  'planned_vs_actual_percent_complete',
  'schedule_performance_ratio',
  'schedule_delay_over_time',
  'schedule_changes_over_time',
  'project_schedule_health_index',
  'schedule_feasibility_score',
  'required_recovery_days',
  'critical_path_length_index',
  'total_float_consumption_index',
  'delay_analysis',
  'window_start_accuracy',
  'window_finish_accuracy',
  'should_have_finished_status',
  'critical_issues_category_model',
  'schedule_compression_ratio',
] as const

const DRILLDOWN_LABELS: Record<string, string> = {
  remaining_later: 'Remaining Later',
  remaining_earlier: 'Remaining Earlier',
  finish_changed: 'Finish Changed',
  new_remaining: 'New Remaining',
  worsened_float: 'Worsened Float',
  improved_float: 'Improved Float',
  milestones_later: 'Milestones Later',
  negative_float: 'Negative Float',
  critical_remaining: 'Critical Remaining',
  near_critical_remaining: 'Near-Critical Remaining',
  upstream_cues: 'Upstream Cues',
}

function DrilldownPanel({
  projectKey,
  drilldownType,
  preview,
  asOfDate,
}: {
  projectKey: string
  drilldownType: string
  preview: Record<string, any>
  asOfDate?: string
}) {
  const [expanded, setExpanded] = useState(false)
  const count = Number(preview?.count || 0)
  const previewItems = Array.isArray(preview?.items) ? preview.items : []

  const { data, isFetching } = useQuery({
    queryKey: ['project', 'schedule', projectKey, 'drilldown', drilldownType, asOfDate],
    queryFn: () =>
      api.getProjectScheduleDrilldown(projectKey, drilldownType, {
        limit: 100,
        offset: 0,
        asOf: asOfDate,
      }),
    enabled: expanded && count > 0,
  })

  const items = expanded && Array.isArray((data as any)?.items) ? (data as any).items : previewItems
  if (!count) return null

  return (
    <div className="rounded border border-[var(--hb-border)] p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium">{DRILLDOWN_LABELS[drilldownType] || drilldownType}</div>
        <button className="badge" onClick={() => setExpanded((v) => !v)}>
          {expanded ? (isFetching ? 'Loading…' : 'Collapse') : `View ${count}`}
        </button>
      </div>
      {expanded && (
        <div className="mt-2 space-y-1 text-xs">
          {items.slice(0, 10).map((item: any) => (
            <div key={item.activity_id || item.upstream_activity_id || item.title} className="flex justify-between gap-3">
              <span className="truncate">{text(item.activity_name || item.title)}</span>
              <span className="shrink-0 text-[var(--hb-muted)]">
                {item.finish_delta_days != null ? `${item.finish_delta_days > 0 ? '+' : ''}${item.finish_delta_days}d` : ''}
              </span>
            </div>
          ))}
          {count > items.length && (
            <div className="text-[var(--hb-muted)]">Showing {items.length} of {count} items.</div>
          )}
        </div>
      )}
    </div>
  )
}

function DriverEvidenceSection({
  projectKey,
  driverHub,
  asOfDate,
}: {
  projectKey: string
  driverHub: Record<string, any>
  asOfDate?: string
}) {
  const [comparisonBasis, setComparisonBasis] = useState<'prior_update' | 'baseline'>('prior_update')
  const driverAnalysis =
    comparisonBasis === 'baseline'
      ? driverHub.baseline || { available: false }
      : driverHub.prior_update || driverHub
  const [activeTab, setActiveTab] = useState<(typeof DRIVER_TABS)[number]['id']>('drivers')
  const topDrivers = Array.isArray(driverAnalysis.top_drivers) ? driverAnalysis.top_drivers : []
  const [selectedDriverId, setSelectedDriverId] = useState<string>(String(topDrivers[0]?.activity_id || ''))
  const drilldowns = driverAnalysis.review_drilldowns || {}
  const preview = drilldowns[activeTab] || {}
  const count = Number(preview.count || 0)
  const needsDriver = activeTab === 'impacted_successors'

  const { data, isFetching } = useQuery({
    queryKey: ['project', 'schedule', projectKey, 'drivers', activeTab, selectedDriverId, asOfDate],
    queryFn: () =>
      api.getProjectScheduleDrivers(projectKey, activeTab, {
        limit: 50,
        offset: 0,
        asOf: asOfDate,
        driverActivityId: needsDriver ? selectedDriverId : undefined,
      }),
    enabled: Boolean(projectKey) && count > 0 && (!needsDriver || Boolean(selectedDriverId)),
  })

  const items = Array.isArray((data as any)?.items) ? (data as any).items : (Array.isArray(preview.items) ? preview.items : [])

  if (!driverAnalysis.available) {
    return (
      <p className="text-sm text-[var(--hb-muted)]">
        Driver analysis unavailable: {text(driverAnalysis.reason, 'comparison or trust gates not satisfied')}.
      </p>
    )
  }

  const baselineAvailable = Boolean(driverHub.baseline?.available)

  return (
    <div className="space-y-3">
      {baselineAvailable && (
        <div className="flex flex-wrap gap-2">
          <button
            className={`badge ${comparisonBasis === 'prior_update' ? 'ring-1 ring-[var(--hb-border)]' : ''}`}
            onClick={() => setComparisonBasis('prior_update')}
          >
            Since previous update
          </button>
          <button
            className={`badge ${comparisonBasis === 'baseline' ? 'ring-1 ring-[var(--hb-border)]' : ''}`}
            onClick={() => setComparisonBasis('baseline')}
          >
            Since selected baseline
          </button>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {DRIVER_TABS.map((tab) => (
          <button
            key={tab.id}
            className={`badge ${activeTab === tab.id ? 'ring-1 ring-[var(--hb-border)]' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {needsDriver && topDrivers.length > 0 && (
        <select
          className="w-full max-w-md rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5 text-sm"
          value={selectedDriverId}
          onChange={(e) => setSelectedDriverId(e.target.value)}
        >
          {topDrivers.map((driver: any) => (
            <option key={String(driver.activity_id)} value={String(driver.activity_id)}>
              {text(driver.activity_name)} ({text(driver.activity_id)})
            </option>
          ))}
        </select>
      )}
      {isFetching && <p className="text-xs text-[var(--hb-muted)]">Loading evidence…</p>}
      <div className="overflow-x-auto rounded border border-[var(--hb-border)]">
        <table className="min-w-full text-left text-xs">
          <thead className="bg-black/20 text-[var(--hb-muted)]">
            <tr>
              {activeTab === 'drivers' && (
                <>
                  <th className="px-3 py-2">Activity</th>
                  <th className="px-3 py-2">WBS</th>
                  <th className="px-3 py-2">Finish Δ</th>
                  <th className="px-3 py-2">Downstream</th>
                  <th className="px-3 py-2">Priority</th>
                </>
              )}
              {activeTab === 'impacted_successors' && (
                <>
                  <th className="px-3 py-2">Successor</th>
                  <th className="px-3 py-2">Finish Δ</th>
                  <th className="px-3 py-2">Float Δ</th>
                  <th className="px-3 py-2">Critical</th>
                </>
              )}
              {activeTab === 'logic_changes' && (
                <>
                  <th className="px-3 py-2">Change</th>
                  <th className="px-3 py-2">Predecessor</th>
                  <th className="px-3 py-2">Successor</th>
                  <th className="px-3 py-2">Linked Movement</th>
                </>
              )}
              {activeTab === 'duration_changes' && (
                <>
                  <th className="px-3 py-2">Activity</th>
                  <th className="px-3 py-2">Duration Δ</th>
                  <th className="px-3 py-2">Finish Δ</th>
                  <th className="px-3 py-2">Downstream</th>
                </>
              )}
              {activeTab === 'milestone_impacts' && (
                <>
                  <th className="px-3 py-2">Milestone</th>
                  <th className="px-3 py-2">Movement</th>
                  <th className="px-3 py-2">Candidate Drivers</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 12).map((item: any, index: number) => (
              <tr key={item.activity_id || item.predecessor_activity_id || index} className="border-t border-[var(--hb-border)]">
                {activeTab === 'drivers' && (
                  <>
                    <td className="px-3 py-2">
                      <Link
                        className="underline"
                        to={`/projects/${projectKey}/schedule/drivers/${encodeURIComponent(String(item.activity_id || ''))}`}
                      >
                        {text(item.activity_name)}
                      </Link>
                    </td>
                    <td className="px-3 py-2">{formatWbs(item)}</td>
                    <td className="px-3 py-2">{item.finish_delta_days != null ? `${item.finish_delta_days}d` : '—'}</td>
                    <td className="px-3 py-2">{num(item.downstream_moved_later_count)}</td>
                    <td className="px-3 py-2">P{num(item.review_priority)}</td>
                  </>
                )}
                {activeTab === 'impacted_successors' && (
                  <>
                    <td className="px-3 py-2">{text(item.activity_name)}</td>
                    <td className="px-3 py-2">{item.finish_delta_days != null ? `${item.finish_delta_days}d` : '—'}</td>
                    <td className="px-3 py-2">{item.float_delta_days != null ? `${item.float_delta_days}d` : '—'}</td>
                    <td className="px-3 py-2">{item.computed_cpm_critical ? 'Yes' : '—'}</td>
                  </>
                )}
                {activeTab === 'logic_changes' && (
                  <>
                    <td className="px-3 py-2">{text(item.change_type)}</td>
                    <td className="px-3 py-2">{text(item.predecessor_activity_id)}</td>
                    <td className="px-3 py-2">{text(item.successor_activity_id)}</td>
                    <td className="px-3 py-2">{item.finish_movement_linked ? 'Yes' : '—'}</td>
                  </>
                )}
                {activeTab === 'duration_changes' && (
                  <>
                    <td className="px-3 py-2">{text(item.activity_name)}</td>
                    <td className="px-3 py-2">{item.duration_delta_days != null ? `${item.duration_delta_days}d` : '—'}</td>
                    <td className="px-3 py-2">{item.finish_delta_days != null ? `${item.finish_delta_days}d` : '—'}</td>
                    <td className="px-3 py-2">{num(item.downstream_moved_later_count)}</td>
                  </>
                )}
                {activeTab === 'milestone_impacts' && (
                  <>
                    <td className="px-3 py-2">{text(item.activity_name)}</td>
                    <td className="px-3 py-2">{item.movement_days != null ? `${item.movement_days}d` : '—'}</td>
                    <td className="px-3 py-2">
                      {(Array.isArray(item.candidate_drivers) ? item.candidate_drivers : [])
                        .map((d: any) => text(d.activity_name))
                        .join(', ') || '—'}
                    </td>
                  </>
                )}
              </tr>
            ))}
            {!items.length && (
              <tr>
                <td className="px-3 py-3 text-[var(--hb-muted)]" colSpan={5}>
                  No {DRIVER_TABS.find((t) => t.id === activeTab)?.label.toLowerCase()} in preview.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-[var(--hb-muted)]">
        Sequence cues only — not causation findings. Showing up to 12 of {count || items.length} items.
      </p>
    </div>
  )
}

export function ProjectSchedulePage() {
  const { projectKey = '' } = useParams()
  const [searchParams] = useSearchParams()
  const focusDriver = searchParams.get('driver')
  const focusReview = searchParams.get('review')
  const focusBasis = searchParams.get('basis') === 'baseline' ? 'baseline' : 'prior_update'
  const [showAllActions, setShowAllActions] = useState(false)
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['project', 'schedule', projectKey],
    queryFn: () => api.getProjectScheduleSummary(projectKey),
    enabled: Boolean(projectKey),
  })
  const trendSchedule = (data || {}) as ProjectScheduleSummaryResponse
  const trendCurrent = trendSchedule.current_schedule || {}
  const trendAsOf = String(trendSchedule.as_of_date || trendCurrent.data_date || '')
  const {
    data: controlsTrendPayload,
    isLoading: controlsTrendLoading,
    error: controlsTrendError,
  } = useQuery({
    queryKey: ['project', 'schedule', projectKey, 'controls-trends', trendAsOf],
    queryFn: () =>
      api.getProjectScheduleMetricTrends(projectKey, {
        asOf: trendAsOf || undefined,
        metrics: [...SCHEDULE_CONTROLS_METRICS],
      }),
    enabled: Boolean(projectKey) && Boolean(trendCurrent?.available) && !isLoading && !error,
  })

  if (isLoading) {
    return (
      <ProjectWorkspaceShell>
        <LoadingState label="Loading schedule intelligence..." />
      </ProjectWorkspaceShell>
    )
  }

  if (error) {
    return (
      <ProjectWorkspaceShell>
        <ErrorState
          userMessage="Project schedule intelligence could not be loaded."
          error={error}
          onRetry={() => { void refetch() }}
        />
      </ProjectWorkspaceShell>
    )
  }

  const schedule = (data || {}) as ProjectScheduleSummaryResponse
  const story = schedule.schedule_story || {}
  const current = schedule.current_schedule || {}
  const previous = schedule.previous_update || {}
  const readiness = schedule.readiness || {}
  const command = schedule.command_summary || {}
  const health = schedule.remaining_health || {}
  const floatPressure = health.float_pressure || {}
  const cpm = schedule.computed_cpm || {}
  const criticalPath = schedule.critical_path || {}
  const change = schedule.change_impact || {}
  const direct = change.direct_remaining_changes || {}
  const upstream = change.upstream_remaining_impact || {}
  const trends = schedule.trend_summary || {}
  const trendSeries = schedule.trend_series || {}
  const scheduleTrust = schedule.schedule_trust || {}
  const identityReview = schedule.identity_review || {}
  const baseline = schedule.baseline_summary || {}
  const reviewDrilldowns = schedule.review_drilldowns || {}
  const driverHub = schedule.change_driver_analysis || {}
  const driverAnalysis = driverHub.prior_update || driverHub
  const driverSummary = driverAnalysis.summary || {}
  const reviewWorkbench = schedule.review_workbench || {}
  const sourceFloat = schedule.source_float_summary || {}
  const computedCpmSummary = schedule.computed_cpm_summary || {}
  const links = schedule.technical_links || {}
  const actionEnvelope = schedule.actions || {}
  const previewActions = Array.isArray(actionEnvelope.preview) ? actionEnvelope.preview : []
  const allActions = Array.isArray(actionEnvelope.all_items) ? actionEnvelope.all_items : previewActions
  const visibleActions = showAllActions ? allActions : previewActions
  const trendMetrics = Array.isArray(trendSeries.metrics) ? trendSeries.metrics : []
  const primaryDrilldowns = [
    'remaining_later',
    'remaining_earlier',
    'finish_changed',
    'new_remaining',
    'worsened_float',
    'milestones_later',
    'upstream_cues',
  ]

  if (schedule.status === 'no_schedule') {
    return (
      <ProjectWorkspaceShell>
        <section className="space-y-4">
          <div>
            <h3 className="section-title mb-0">Schedule</h3>
            <p className="mt-1 text-sm text-[var(--hb-muted)]">
              As of {text(schedule.as_of_date)}. No schedule update is available for this project.
            </p>
          </div>
          <EmptyState
            title={text(story.headline)}
            hint={text(story.synopsis)}
            actions={
              <Link className="badge" to={text(links.schedule_import_url, `/schedules/imports?project=${projectKey}`)}>
                Import Schedule
              </Link>
            }
          />
        </section>
      </ProjectWorkspaceShell>
    )
  }

  return (
    <ProjectWorkspaceShell>
      <section className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h3 className="section-title mb-0">Schedule</h3>
            <p className="mt-1 text-sm text-[var(--hb-muted)]">
              As of {text(schedule.as_of_date)} · Current update {text(current.friendly_label)} · Data date {text(current.data_date)}
              {previous?.available ? ` · Previous data date ${text(previous.data_date)}` : ''}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link className="badge" to={`/projects/${projectKey}/schedule/import`}>
              Import Schedule
            </Link>
            <Link
              className="badge"
              to={
                schedule.as_of_date
                  ? `/projects/${projectKey}/schedule/workbench?as_of=${encodeURIComponent(String(schedule.as_of_date))}`
                  : `/projects/${projectKey}/schedule/workbench`
              }
            >
              Open Workbench
            </Link>
            {links.schedule_export_url && (
              <button
                className="badge"
                type="button"
                onClick={() => {
                  void api.downloadProjectScheduleExport(projectKey, 'markdown', {
                    asOf: schedule.as_of_date ? String(schedule.as_of_date) : undefined,
                  })
                }}
              >
                Export Memo
              </button>
            )}
          </div>
          <ReadinessList readiness={readiness} />
        </div>

        {(focusDriver || focusReview) && (
          <div className="card text-sm">
            <div className="font-medium">Focused review link</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {focusDriver && (
                <Link
                  className="badge"
                  to={`/projects/${projectKey}/schedule/drivers/${encodeURIComponent(focusDriver)}?basis=${focusBasis}${schedule.as_of_date ? `&as_of=${encodeURIComponent(String(schedule.as_of_date))}` : ''}`}
                >
                  Open driver {focusDriver}
                </Link>
              )}
              {focusReview && (
                <Link
                  className="badge"
                  to={`/projects/${projectKey}/schedule/workbench?review=${encodeURIComponent(focusReview)}${schedule.as_of_date ? `&as_of=${encodeURIComponent(String(schedule.as_of_date))}` : ''}`}
                >
                  Open review item
                </Link>
              )}
            </div>
          </div>
        )}

        <TrustBanner scheduleTrust={scheduleTrust} identityReview={identityReview} />

        <div className={`card ${toneFor(health.status)}`}>
          <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
            <div>
              <div className="text-xs uppercase tracking-wide text-[var(--hb-muted)]">Schedule Story</div>
              <h4 className="mt-1 text-xl font-semibold">{text(story.headline)}</h4>
              <p className="mt-2 text-sm text-[var(--hb-muted)]">{text(story.synopsis)}</p>
              {(story.what_changed || story.why_it_matters) && (
                <div className="mt-3 space-y-2 text-sm">
                  {story.what_changed && (
                    <div>
                      <div className="text-xs text-[var(--hb-muted)]">What Changed</div>
                      <div>{text(story.what_changed)}</div>
                    </div>
                  )}
                  {story.why_it_matters && (
                    <div>
                      <div className="text-xs text-[var(--hb-muted)]">Why It Matters</div>
                      <div>{text(story.why_it_matters)}</div>
                    </div>
                  )}
                </div>
              )}
              <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
                <div>
                  <div className="text-xs text-[var(--hb-muted)]">Primary Driver</div>
                  <div>{text(story.primary_driver_narrative || story.primary_change_driver)}</div>
                </div>
                <div>
                  <div className="text-xs text-[var(--hb-muted)]">Review Next</div>
                  <div>{text(story.review_next_summary)}</div>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <MetricTile label="Forecast Finish" value={command.forecast_finish} helper={`${num(command.forecast_finish_delta_days, '—')} days vs prior`} />
              <MetricTile label="Remaining Work" value={command.remaining_activity_count} helper={`${num(command.remaining_milestone_count)} milestones`} />
              <MetricTile label="Critical / Near" value={`${num(command.critical_remaining_count)} / ${num(command.near_critical_remaining_count)}`} />
              <MetricTile label="Float Pressure" value={num(command.negative_float_remaining_count)} helper="source-export negative float" />
            </div>
          </div>
        </div>

        <div className="card">
          <ProjectScheduleDashboardVisualizations
            schedule={schedule}
            trendPayload={controlsTrendPayload as any}
            trendLoading={controlsTrendLoading}
            trendError={controlsTrendError}
          />
        </div>

        {reviewWorkbench.available && (
          <div className="card">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold">Review Workbench</h4>
                <p className="mt-1 text-xs text-[var(--hb-muted)]">
                  {num(reviewWorkbench.summary?.open_count)} open · {num(reviewWorkbench.summary?.watching_count)} watching
                </p>
              </div>
              <Link
                className="badge"
                to={
                  schedule.as_of_date
                    ? `/projects/${projectKey}/schedule/workbench?as_of=${encodeURIComponent(String(schedule.as_of_date))}`
                    : `/projects/${projectKey}/schedule/workbench`
                }
              >
                Open Queue
              </Link>
            </div>
            <div className="mt-3 space-y-2">
              {(Array.isArray(reviewWorkbench.preview) ? reviewWorkbench.preview : []).slice(0, 4).map((item: any) => (
                <div key={item.review_item_id || item.stable_item_key} className="rounded border border-[var(--hb-border)] p-2 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span>{text(item.item_title)}</span>
                    <span className="badge capitalize">{text(item.review_status)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {driverAnalysis.available && (
          <div className="card">
            <h4 className="text-sm font-semibold">Where To Look First</h4>
            <p className="mt-1 text-sm text-[var(--hb-muted)]">
              {text(story.primary_driver_narrative || story.primary_change_driver)}
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
              <MetricTile label="Top WBS" value={driverSummary.top_wbs_area} />
              <MetricTile label="Candidate Drivers" value={driverSummary.candidate_driver_count} />
              <MetricTile label="Downstream (Top)" value={driverSummary.top_driver_downstream_count} />
              <MetricTile label="Milestone Touches" value={driverSummary.top_driver_milestone_touch_count} />
            </div>
            <div className="mt-4">
              <DriverEvidenceSection
                projectKey={projectKey}
                driverHub={driverHub}
                asOfDate={schedule.as_of_date}
              />
            </div>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <div className="card">
            <h4 className="text-sm font-semibold">Source Float (Export)</h4>
            <p className="mt-1 text-xs text-[var(--hb-muted)]">Float values from the imported schedule file.</p>
            <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
              <MetricTile label="Negative" value={sourceFloat.negative_float_remaining_count ?? floatPressure.negative_float_count} />
              <MetricTile label="Zero" value={sourceFloat.zero_float_remaining_count ?? floatPressure.zero_float_count} />
              <MetricTile label="Near Critical" value={sourceFloat.near_critical_source_count ?? floatPressure.near_critical_count} />
            </div>
          </div>
          <div className="card">
            <h4 className="text-sm font-semibold">Computed CPM</h4>
            <p className="mt-1 text-xs text-[var(--hb-muted)]">Application-computed critical path analysis.</p>
            <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
              <MetricTile label="Available" value={computedCpmSummary.available ?? cpm.available ? 'Yes' : 'No'} />
              <MetricTile label="Critical" value={computedCpmSummary.critical_remaining_count ?? command.critical_remaining_count} />
              <MetricTile label="Near Critical" value={computedCpmSummary.near_critical_remaining_count ?? command.near_critical_remaining_count} />
            </div>
            {(computedCpmSummary.drilldown_url || links.computed_cpm_url) && (
              <Link
                className="mt-3 inline-block text-xs underline"
                to={text(computedCpmSummary.drilldown_url || links.computed_cpm_url)}
              >
                Open technical CPM
              </Link>
            )}
          </div>
        </div>

        {baseline?.status && baseline.status !== 'no_selection' && (
          <div className="card">
            <h4 className="text-sm font-semibold">Baseline Comparison</h4>
            <p className="mt-1 text-xs text-[var(--hb-muted)]">
              {baseline.selected_baseline_available
                ? `Selected baseline ${text(baseline.selected_baseline_label)} (${text(baseline.selected_baseline_data_date)})`
                : baseline.original_baseline_detected
                  ? `Original baseline detected: ${text(baseline.original_baseline_label)}`
                  : 'No user-selected baseline yet.'}
            </p>
            {baseline.comparison && Object.keys(baseline.comparison).length > 0 && (
              <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                <MetricTile label="Finish Later" value={baseline.comparison.finish_moved_later_count} />
                <MetricTile label="Finish Earlier" value={baseline.comparison.finish_moved_earlier_count} />
                <MetricTile label="Finish Changed" value={baseline.comparison.finish_changed_count} />
                <MetricTile
                  label="Forecast Δ"
                  value={baseline.comparison.forecast_finish_delta_days != null ? `${baseline.comparison.forecast_finish_delta_days}d` : '—'}
                />
              </div>
            )}
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[1fr_1fr_1fr]">
          <div className={`card ${toneFor(health.status)}`}>
            <h4 className="text-sm font-semibold">Remaining-Work Health</h4>
            <div className="mt-2 text-2xl font-semibold capitalize">{text(health.status).replaceAll('_', ' ')}</div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
              <MetricTile label="Negative" value={floatPressure.negative_float_count} />
              <MetricTile label="Zero" value={floatPressure.zero_float_count} />
              <MetricTile label="Near" value={floatPressure.near_critical_count} />
            </div>
            <ul className="mt-3 space-y-1 text-xs text-[var(--hb-muted)]">
              {(Array.isArray(health.drivers) ? health.drivers : []).slice(0, 3).map((driver: string) => (
                <li key={driver}>{driver}</li>
              ))}
            </ul>
          </div>

          <div className="card">
            <h4 className="text-sm font-semibold">What Changed</h4>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <MetricTile label="Remaining Later" value={direct.summary?.finish_moved_later_count} />
              <MetricTile label="Remaining Earlier" value={direct.summary?.finish_moved_earlier_count} />
              <MetricTile label="Finish Changed" value={direct.summary?.finish_changed_count ?? direct.summary?.changed_count} />
              <MetricTile label="New Remaining" value={direct.summary?.new_remaining_activities} />
              <MetricTile label="Worsened Float" value={direct.summary?.worsened_float_count} />
              <MetricTile label="Improved Float" value={direct.summary?.improved_float_count} />
              <MetricTile label="Milestones Later" value={direct.summary?.moved_remaining_milestones_count} />
              <MetricTile label="Upstream Cues" value={upstream.summary?.changed_upstream_count} />
            </div>
            {Object.keys(reviewDrilldowns).length > 0 && (
              <div className="mt-3 space-y-2">
                {primaryDrilldowns.map((key) => (
                  <DrilldownPanel
                    key={key}
                    projectKey={projectKey}
                    drilldownType={key}
                    preview={reviewDrilldowns[key] || {}}
                    asOfDate={schedule.as_of_date}
                  />
                ))}
              </div>
            )}
            <p className="mt-3 text-xs text-[var(--hb-muted)]">
              Upstream cues are sequence review prompts, not causation findings.
            </p>
          </div>

          <div className="card">
            <h4 className="text-sm font-semibold">Critical Path</h4>
            <div className="mt-2 text-sm text-[var(--hb-muted)]">{text(story.critical_path_summary)}</div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <MetricTile label="CPM" value={cpm.available ? 'Available' : 'Unavailable'} />
              <MetricTile label="Path Items" value={criticalPath.activity_count} />
            </div>
            {links.computed_cpm_url && (
              <Link className="mt-3 inline-block text-xs underline" to={links.computed_cpm_url}>
                Open technical CPM
              </Link>
            )}
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
          <div className="card">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold">Review Next</h4>
                <p className="mt-1 text-xs text-[var(--hb-muted)]">Top review items are ranked for PM attention.</p>
              </div>
              {allActions.length > previewActions.length && (
                <button className="badge" onClick={() => setShowAllActions((v) => !v)}>
                  {showAllActions ? 'Show Top 5' : 'View All'}
                </button>
              )}
            </div>
            <div className="mt-3 space-y-2">
              {visibleActions.map((action: any) => (
                <article key={action.code || action.title} className="rounded border border-[var(--hb-border)] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="font-medium">{text(action.title)}</div>
                    <span className="badge">P{num(action.priority)}</span>
                  </div>
                  <p className="mt-1 text-sm text-[var(--hb-muted)]">{text(action.explanation)}</p>
                  <p className="mt-2 text-xs text-[var(--hb-muted)]">{text(action.recommended_review)}</p>
                </article>
              ))}
              {!visibleActions.length && (
                <div className="text-sm text-[var(--hb-muted)]">No schedule review actions are available yet.</div>
              )}
            </div>
          </div>

          <div className="card">
            <h4 className="text-sm font-semibold">Trends</h4>
            {trendMetrics.length > 0 ? (
              <div className="mt-3 space-y-2">
                {trendMetrics.slice(-6).map((item: any) => (
                  <div key={`${item.friendly_label}-${item.data_date}`} className="rounded border border-[var(--hb-border)] p-2 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium">{text(item.friendly_label)}</span>
                      <span className="text-[var(--hb-muted)]">{text(item.data_date)}</span>
                    </div>
                    <div className="mt-1 grid grid-cols-2 gap-1 text-xs text-[var(--hb-muted)]">
                      <span>Forecast {text(item.forecast_finish, '—')}</span>
                      <span>Remaining {num(item.remaining_activity_count)}</span>
                      <span>Neg float {num(item.negative_float_remaining_count)}</span>
                      <span>Later {num(item.finish_moved_later_count)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : trends.available ? (
              <div className="mt-3 space-y-2">
                {(Array.isArray(trends.series) ? trends.series : []).slice(-6).map((item: any) => (
                  <div key={`${item.friendly_label}-${item.data_date}`} className="flex items-center justify-between gap-3 text-sm">
                    <span>{text(item.friendly_label)}</span>
                    <span className="text-[var(--hb-muted)]">{text(item.data_date)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-[var(--hb-muted)]">
                Trend unavailable: {text(trends.reason, 'at least two comparable updates required')}.
              </p>
            )}
          </div>
        </div>

        <TechnicalDetails
          summary="Technical evidence"
          details={
            <div className="space-y-2">
              <div className="flex flex-wrap gap-2">
                {Object.entries(links).map(([key, href]) => (
                  <Link key={key} className="badge" to={String(href)}>
                    {key.replaceAll('_', ' ')}
                  </Link>
                ))}
              </div>
              <div>Raw schedule identifiers are available only in API technical evidence and standalone schedule drilldowns.</div>
            </div>
          }
        />
      </section>
    </ProjectWorkspaceShell>
  )
}
