import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/common/EmptyState'
import { LoadingState } from '../components/common/LoadingState'
import { MetricCard } from '../components/dashboard/MetricCard'
import { DashboardGrid } from '../components/layout/DashboardGrid'
import { PrimaryPageLayout } from '../components/layout/PrimaryPageLayout'
import { ProjectSubNav } from '../components/projects/ProjectSubNav'
import { SectionCard } from '../components/common/SectionCard'
import { api, type ScheduleReviewDashboardProject } from '../lib/api'
import { safeDisplayText } from '../lib/errorCopy'

const STATUS_FILTERS = [
  { key: '', label: 'All projects' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'operator_action_required', label: 'Operator action' },
  { key: 'needs_review', label: 'Needs review' },
  { key: 'stale', label: 'Stale schedule' },
  { key: 'degraded', label: 'Degraded' },
  { key: 'ready', label: 'Ready' },
  { key: 'missing', label: 'Missing schedule' },
] as const

const FORBIDDEN_DOM_PATTERNS = [
  /schedule_version_key/i,
  /import_id/i,
  /cpm_run_id/i,
  /file_sha256/i,
  /procore_project_id/i,
  /\btropical\|S1\|/i,
]

function trustTone(status: string): 'ok' | 'attention' | 'warn' | undefined {
  if (status === 'ready' || status === 'trusted' || status === 'current') return 'ok'
  if (status === 'degraded' || status === 'stale' || status === 'review_required') return 'attention'
  if (status === 'blocked' || status === 'missing' || status === 'unavailable') return 'warn'
  return undefined
}

function TrustChip({ label, value }: { label: string; value: string }) {
  const tone = trustTone(value)
  const className =
    tone === 'ok'
      ? 'text-emerald-300'
      : tone === 'attention'
        ? 'text-amber-300'
        : tone === 'warn'
          ? 'text-orange-300'
          : 'text-[var(--hb-muted)]'
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <span className="text-[var(--hb-muted)]">{label}</span>
      <span className={className}>{safeDisplayText(value)}</span>
    </span>
  )
}

function ProjectRow({ row }: { row: ScheduleReviewDashboardProject }) {
  const review = row.review_status
  const action = row.recommended_next_action
  return (
    <tr>
      <td>
        <div className="font-medium">{safeDisplayText(row.project_label)}</div>
        <div className="text-xs text-[var(--hb-muted)]">{safeDisplayText(row.portfolio_status)}</div>
      </td>
      <td>
        <div>{safeDisplayText(row.schedule_label || 'No schedule')}</div>
        <div className="text-xs text-[var(--hb-muted)]">
          {row.schedule_data_date ? `Data date ${row.schedule_data_date}` : 'No data date'}
          {row.schedule_age_days != null ? ` · ${row.schedule_age_days}d` : ''}
        </div>
      </td>
      <td>{safeDisplayText(row.schedule_staleness_status)}</td>
      <td>
        <div className="flex flex-col gap-1">
          <TrustChip label="Analytics" value={row.analytics_trust_status} />
          <TrustChip label="Identity" value={row.identity_trust_status} />
          <TrustChip label="CPM" value={row.cpm_trust_status} />
          <TrustChip label="Quality" value={row.quality_trust_status} />
        </div>
      </td>
      <td>
        <div className="text-xs">
          Review {review.needs_review} · Preview {review.preview_cue_count}
        </div>
      </td>
      <td>
        <div className="font-medium text-sm">{safeDisplayText(action?.label)}</div>
        <div className="text-xs text-[var(--hb-muted)]">{safeDisplayText(action?.pm_description)}</div>
        {action?.primary_link ? (
          <Link className="text-xs" to={action.primary_link}>
            Open recommended surface
          </Link>
        ) : null}
      </td>
      <td>
        <div className="flex flex-col gap-1 text-xs">
          <Link to={row.links.hub}>Hub</Link>
          <Link to={row.links.controls}>Controls</Link>
          <Link to={row.links.workbench}>Workbench</Link>
          <Link to={row.links.import}>Import</Link>
          <Link to={row.links.identity_review}>Identity review</Link>
        </div>
      </td>
    </tr>
  )
}

export function ProjectScheduleReviewDashboardPage() {
  const [statusFilter, setStatusFilter] = useState('')
  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ['schedule-review-dashboard', statusFilter || 'all'],
    queryFn: () => api.getScheduleReviewDashboard({ status: statusFilter || null }),
    placeholderData: keepPreviousData,
  })

  const summary = data?.portfolio_summary
  const projects = data?.projects || []

  const showInitialLoading = isLoading && !data

  const emptyState = useMemo(() => {
    if (!data) return null
    if (statusFilter === 'ready' && projects.length === 0) {
      return {
        title: 'All visible projects are clear',
        body: 'No projects match the ready filter. Other projects may still need operator action or review.',
      }
    }
    if (statusFilter && projects.length === 0) {
      return {
        title: 'No projects match this filter',
        body: 'Try another portfolio filter or return to all projects.',
      }
    }
    if ((summary?.project_count || 0) === 0) {
      return {
        title: 'No projects in portfolio',
        body: 'Project records will appear here after they are available in the project catalog.',
      }
    }
    if ((summary?.projects_without_schedule || 0) === summary?.project_count && projects.length > 0) {
      return {
        title: 'No schedules imported yet',
        body: 'Import committed schedules to enable portfolio schedule review rollups.',
      }
    }
    return null
  }, [data, projects.length, statusFilter, summary])

  if (showInitialLoading) {
    return <LoadingState label="Loading schedule review dashboard" />
  }

  if (isError || !data) {
    return (
      <PrimaryPageLayout title="Schedule Review Dashboard">
        <EmptyState title="Dashboard unavailable" body="Schedule review dashboard data could not be loaded." />
      </PrimaryPageLayout>
    )
  }

  return (
    <PrimaryPageLayout
      title="Schedule Review Dashboard"
      subtitle="Portfolio rollup of schedule trust, quality, review workload, and recommended next actions."
      actions={
        <button
          type="button"
          className="btn-secondary"
          onClick={async () => {
            const response = await api.downloadScheduleReviewDashboardExport({
              format: 'markdown',
              status: statusFilter || null,
            })
            const blob = await response.blob()
            const url = URL.createObjectURL(blob)
            const anchor = document.createElement('a')
            anchor.href = url
            anchor.download = 'portfolio-schedule-review.md'
            anchor.click()
            URL.revokeObjectURL(url)
          }}
        >
          Export summary
        </button>
      }
    >
      <ProjectSubNav projectKey="all" />
      <div className="subnav filter-row mt-4 flex flex-wrap gap-2" aria-label="Portfolio filters">
        {STATUS_FILTERS.map((filter) => (
          <button
            key={filter.key || 'all'}
            type="button"
            className={statusFilter === filter.key ? 'active' : ''}
            onClick={() => setStatusFilter(filter.key)}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <DashboardGrid className="mt-4">
        <MetricCard label="Total projects" value={summary?.project_count ?? 0} />
        <MetricCard label="Ready" value={summary?.ready_count ?? 0} status="ok" />
        <MetricCard label="Degraded" value={summary?.degraded_count ?? 0} status="attention" />
        <MetricCard label="Blocked" value={summary?.blocked_count ?? 0} status="warn" />
        <MetricCard label="Missing schedule" value={summary?.projects_without_schedule ?? 0} status="warn" />
        <MetricCard label="Stale schedule" value={summary?.stale_schedule_count ?? 0} status="attention" />
        <MetricCard label="Needs review" value={summary?.needs_review_count ?? 0} status="attention" />
        <MetricCard
          label="Operator action required"
          value={summary?.operator_action_required_count ?? 0}
          status="warn"
        />
      </DashboardGrid>

      <SectionCard title="Priority projects" className="mt-6">
        {isFetching ? <div className="text-xs text-[var(--hb-muted)] mb-2">Refreshing portfolio…</div> : null}
        {emptyState ? (
          <EmptyState title={emptyState.title} body={emptyState.body} />
        ) : (
          <div className="overflow-x-auto" data-testid="portfolio-project-table">
            <table className="data-table w-full">
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Schedule</th>
                  <th>Staleness</th>
                  <th>Trust</th>
                  <th>Review</th>
                  <th>Recommended action</th>
                  <th>Links</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((row) => (
                  <ProjectRow key={row.project_key} row={row} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </PrimaryPageLayout>
  )
}

export function portfolioDashboardForbiddenDomText(text: string): boolean {
  return FORBIDDEN_DOM_PATTERNS.some((pattern) => pattern.test(text))
}
