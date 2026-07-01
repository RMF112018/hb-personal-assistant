/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'
import { api } from '../lib/api'
import type { ReviewWorkbenchComparisonBasis } from '../lib/api'
import {
  labelForComparisonBasis,
  normalizeBaselineContext,
  workbenchHref as buildWorkbenchHref,
} from '../lib/scheduleBaselineLabels'

const NAMED_BASIS = new Set<string>([
  'current_contract_baseline',
  'previous_progress_update_baseline',
  'secondary_progress_update_baseline',
])

function resolveDriverComparisonBasis(
  comparisonBasisParam: string | null,
  basisParam: string | null,
): ReviewWorkbenchComparisonBasis | 'baseline' {
  const comparisonBasis = comparisonBasisParam?.trim() || null
  const basis = basisParam?.trim() || null
  if (comparisonBasis && basis && comparisonBasis !== basis) {
    return 'prior_update'
  }
  const raw = comparisonBasis || basis || 'prior_update'
  if (raw === 'prior_update' || raw === 'baseline' || NAMED_BASIS.has(raw)) {
    return raw as ReviewWorkbenchComparisonBasis | 'baseline'
  }
  return 'prior_update'
}

function text(value: unknown, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

export function ProjectScheduleDriverDetailPage() {
  const { projectKey = '', activityId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const asOfDate = searchParams.get('as_of') || undefined
  const comparisonBasis = resolveDriverComparisonBasis(
    searchParams.get('comparison_basis'),
    searchParams.get('basis'),
  )
  const workbenchLink = buildWorkbenchHref(projectKey, { asOf: asOfDate, comparisonBasis })

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['project', 'schedule', 'driver-detail', projectKey, activityId, asOfDate, comparisonBasis],
    queryFn: () =>
      api.getProjectScheduleDriverDetail(projectKey, activityId, {
        asOf: asOfDate,
        comparisonBasis,
      }),
    enabled: Boolean(projectKey && activityId),
  })

  if (isLoading) {
    return (
      <ProjectWorkspaceShell>
        <LoadingState label="Loading driver detail..." />
      </ProjectWorkspaceShell>
    )
  }

  if (error) {
    return (
      <ProjectWorkspaceShell>
        <ErrorState
          userMessage="Driver detail could not be loaded."
          error={error}
          onRetry={() => { void refetch() }}
        />
      </ProjectWorkspaceShell>
    )
  }

  const detail = (data || {}) as Record<string, any>
  if (!detail.available) {
    return (
      <ProjectWorkspaceShell>
        <EmptyState
          title="Driver detail unavailable"
          hint={text(detail.reason, 'Comparison or activity facts are not available.')}
          actions={
            <Link
              className="badge"
              to={
                asOfDate
                  ? `/projects/${projectKey}/schedule?as_of=${encodeURIComponent(asOfDate)}`
                  : `/projects/${projectKey}/schedule`
              }
            >
              Back to Schedule
            </Link>
          }
        />
      </ProjectWorkspaceShell>
    )
  }

  const scheduleHref = asOfDate
    ? `/projects/${projectKey}/schedule?as_of=${encodeURIComponent(asOfDate)}`
    : `/projects/${projectKey}/schedule`

  const activity = detail.activity || {}
  const baselineCtx = normalizeBaselineContext(detail.baseline_context)
  const basisLabel = baselineCtx.slotLabel || labelForComparisonBasis(String(detail.comparison_basis || ''))
  const downstream = Array.isArray(detail.downstream_impacts) ? detail.downstream_impacts : []
  const upstream = Array.isArray(detail.upstream_path) ? detail.upstream_path : []
  const logic = Array.isArray(detail.logic_changes) ? detail.logic_changes : []

  return (
    <ProjectWorkspaceShell>
      <section className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="section-title mb-0">Driver Detail</h3>
            <p className="mt-1 text-sm text-[var(--hb-muted)]">
              {text(activity.activity_name) || 'Unnamed activity'} · {basisLabel}
              {baselineCtx.displayName ? ` · ${baselineCtx.displayName}` : ''}
              {asOfDate ? ` · As of ${asOfDate}` : ''}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link className="badge" to={workbenchLink}>
              Workbench
            </Link>
            <Link className="badge" to={scheduleHref}>
              Schedule Hub
            </Link>
          </div>
        </div>

        <div className="card">
          <h4 className="text-sm font-semibold">Side-by-Side Movement</h4>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div className="rounded border border-[var(--hb-border)] p-3 text-sm">
              <div className="text-xs text-[var(--hb-muted)]">Prior</div>
              <div>Start {text(activity.prior_start)}</div>
              <div>Finish {text(activity.prior_finish)}</div>
              <div>Float {text(activity.prior_float)}</div>
            </div>
            <div className="rounded border border-[var(--hb-border)] p-3 text-sm">
              <div className="text-xs text-[var(--hb-muted)]">Current</div>
              <div>Start {text(activity.current_start)}</div>
              <div>Finish {text(activity.current_finish)}</div>
              <div>Float {text(activity.current_float)}</div>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
            <div>Start Δ {activity.start_delta_days != null ? `${activity.start_delta_days}d` : '—'}</div>
            <div>Finish Δ {activity.finish_delta_days != null ? `${activity.finish_delta_days}d` : '—'}</div>
            <div>Float Δ {activity.float_delta_days != null ? `${activity.float_delta_days}d` : '—'}</div>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="card">
            <h4 className="text-sm font-semibold">Upstream Path</h4>
            <ul className="mt-2 space-y-1 text-sm">
              {upstream.map((node: any) => (
                <li key={node.activity_id}>
                  {text(node.activity_name) || 'Unnamed activity'}
                </li>
              ))}
              {!upstream.length && <li className="text-[var(--hb-muted)]">No upstream chain in preview.</li>}
            </ul>
          </div>
          <div className="card">
            <h4 className="text-sm font-semibold">Downstream Impacts</h4>
            <ul className="mt-2 space-y-1 text-sm">
              {downstream.map((node: any) => (
                <li key={node.activity_id}>
                  {text(node.activity_name)} · finish Δ {text(node.finish_delta_days)}d
                </li>
              ))}
              {!downstream.length && <li className="text-[var(--hb-muted)]">No downstream movement in preview.</li>}
            </ul>
          </div>
        </div>

        {logic.length > 0 && (
          <div className="card">
            <h4 className="text-sm font-semibold">Logic Changes</h4>
            <ul className="mt-2 space-y-1 text-sm">
              {logic.map((row: any, index: number) => (
                <li key={`${row.change_type}-${index}`}>
                  {text(row.change_type)} {text(row.predecessor_activity_id)} → {text(row.successor_activity_id)}
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="text-xs text-[var(--hb-muted)]">{text(detail.sequence_cue)}</p>
      </section>
    </ProjectWorkspaceShell>
  )
}