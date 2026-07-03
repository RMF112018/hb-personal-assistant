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
  formatNamedComparisonContextLine,
  labelForComparisonBasis,
  normalizeBaselineContext,
  workbenchHref as buildWorkbenchHref,
} from '../lib/scheduleBaselineLabels'

const NAMED_BASIS = new Set<string>([
  'current_contract_baseline',
  'previous_progress_update_baseline',
  'secondary_progress_update_baseline',
])

type DriverBasisResolution =
  | { ok: true; comparisonBasis: ReviewWorkbenchComparisonBasis | 'baseline' }
  | { ok: false; reason: 'conflicting_comparison_params' | 'invalid_comparison_basis' }

function resolveDriverComparisonBasis(
  comparisonBasisParam: string | null,
  basisParam: string | null,
): DriverBasisResolution {
  const comparisonBasis = comparisonBasisParam?.trim() || null
  const basis = basisParam?.trim() || null
  if (comparisonBasis && basis && comparisonBasis !== basis) {
    return { ok: false, reason: 'conflicting_comparison_params' }
  }
  const raw = comparisonBasis || basis || 'prior_update'
  if (raw === 'prior_update' || raw === 'baseline' || NAMED_BASIS.has(raw)) {
    return { ok: true, comparisonBasis: raw as ReviewWorkbenchComparisonBasis | 'baseline' }
  }
  return { ok: false, reason: 'invalid_comparison_basis' }
}

function text(value: unknown, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function dispositionSourceLabel(source: unknown) {
  switch (String(source || '')) {
    case 'named_baseline_review':
      return 'Named baseline review'
    case 'prior_update_review':
      return 'Prior update review'
    case 'preview':
      return 'Open preview (not yet persisted)'
    case 'unavailable_or_preview':
      return 'Disposition unavailable for this comparison mode'
    default:
      return 'Review queue'
  }
}

export function ProjectScheduleDriverDetailPage() {
  const { projectKey = '', activityId: pathActivityId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const queryActivityId = searchParams.get('activity_id')?.trim() || ''
  const activityId = queryActivityId || pathActivityId
  const asOfDate = searchParams.get('as_of') || undefined
  const basisResolution = resolveDriverComparisonBasis(
    searchParams.get('comparison_basis'),
    searchParams.get('basis'),
  )
  const comparisonBasis = basisResolution.ok ? basisResolution.comparisonBasis : 'prior_update'
  const workbenchLink = buildWorkbenchHref(projectKey, { asOf: asOfDate, comparisonBasis })

  const scheduleHref = asOfDate
    ? `/projects/${projectKey}/schedule?as_of=${encodeURIComponent(asOfDate)}`
    : `/projects/${projectKey}/schedule`

  // Friendly index / entry-point state for bare /drivers and /driver-detail (no activityId).
  // This makes the dropdown "Activity Drivers" and "Driver Detail" items safe and useful.
  if (!activityId) {
    return (
      <ProjectWorkspaceShell>
        <section className="space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--hb-muted)]">Schedule</p>
            <h3 className="section-title mb-0 mt-1">Activity Drivers</h3>
          </div>
          <div className="card">
            <p className="text-sm">
              Detailed driver analysis (downstream impacts, logic changes, candidate sequences) is shown for a specific activity.
            </p>
            <p className="mt-2 text-sm text-[var(--hb-muted)]">
              Select a candidate from "Where to Look First" or the Review Workbench on the Schedule Overview, or open a review item that links here.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link className="badge" to={scheduleHref}>
              Back to Schedule Overview
            </Link>
            <Link className="badge" to={workbenchLink}>
              Open Review Workbench
            </Link>
          </div>
        </section>
      </ProjectWorkspaceShell>
    )
  }

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['project', 'schedule', 'driver-detail', projectKey, activityId, asOfDate, comparisonBasis],
    queryFn: () =>
      api.getProjectScheduleDriverDetail(projectKey, activityId, {
        asOf: asOfDate,
        comparisonBasis,
      }),
    enabled: Boolean(projectKey && activityId && basisResolution.ok),
  })

  if (!basisResolution.ok) {
    const message =
      basisResolution.reason === 'conflicting_comparison_params'
        ? 'Driver detail cannot load because two different comparison modes were requested.'
        : 'Driver detail cannot load because the requested comparison mode is not supported.'
    return (
      <ProjectWorkspaceShell>
        <ErrorState userMessage={message} />
      </ProjectWorkspaceShell>
    )
  }

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

  // scheduleHref declared earlier (supports no-ID index state + these links)

  const activity = detail.activity || {}
  const baselineCtx = normalizeBaselineContext(detail.baseline_context)
  const basisLabel = baselineCtx.slotLabel || labelForComparisonBasis(String(detail.comparison_basis || ''))
  const activityTitle = text(activity.activity_name, 'Unnamed activity')
  const comparisonContextLine = formatNamedComparisonContextLine({
    slotLabel: basisLabel,
    displayName: baselineCtx.displayName,
    dataDate: baselineCtx.dataDate,
    asOf: asOfDate || null,
  })
  const downstream = Array.isArray(detail.downstream_impacts) ? detail.downstream_impacts : []
  const upstream = Array.isArray(detail.upstream_path) ? detail.upstream_path : []
  const logic = Array.isArray(detail.logic_changes) ? detail.logic_changes : []
  const reviewStatus = text(detail.review_status, 'open')
  const dispositionSource = dispositionSourceLabel(detail.disposition_source)

  return (
    <ProjectWorkspaceShell>
      <section className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--hb-muted)]">Driver detail</p>
            <h3 className="section-title mb-0 mt-1">{activityTitle}</h3>
            <p className="mt-1 text-sm text-[var(--hb-muted)]">{comparisonContextLine}</p>
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
          <h4 className="text-sm font-semibold">Review Disposition</h4>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <span className="badge capitalize">{reviewStatus}</span>
            <span className="text-[var(--hb-muted)]">{dispositionSource}</span>
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
                  {text(row.change_type, 'Relationship change')}
                  {row.predecessor_activity_name || row.successor_activity_name
                    ? `: ${text(row.predecessor_activity_name, 'Unnamed activity')} → ${text(row.successor_activity_name, 'Unnamed activity')}`
                    : null}
                </li>
              ))}
            </ul>
            <details className="mt-3 text-xs text-[var(--hb-muted)]">
              <summary className="cursor-pointer">Technical relationship IDs</summary>
              <ul className="mt-2 space-y-1">
                {logic.map((row: any, index: number) => (
                  <li key={`tech-${row.change_type}-${index}`}>
                    {text(row.change_type)} {text(row.predecessor_activity_id)} → {text(row.successor_activity_id)}
                  </li>
                ))}
              </ul>
            </details>
          </div>
        )}

        <p className="text-xs text-[var(--hb-muted)]">{text(detail.sequence_cue)}</p>

        <p className="text-xs text-[var(--hb-muted)]">
          Schedule movement and sequence cues are advisory review signals. They do not determine causation,
          entitlement, or responsibility.
        </p>

        <details className="text-xs text-[var(--hb-muted)]">
          <summary className="cursor-pointer">Technical activity reference</summary>
          <p className="mt-2">Activity ID: {text(activity.activity_id || activityId)}</p>
          {baselineCtx.versionKey ? <p>Schedule version key: {baselineCtx.versionKey}</p> : null}
          {detail.review_item_id ? (
            <p>Internal review item reference: {text(detail.review_item_id)}</p>
          ) : null}
        </details>
      </section>
    </ProjectWorkspaceShell>
  )
}
