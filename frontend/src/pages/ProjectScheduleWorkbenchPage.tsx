/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'
import { api, getLocalUiRole } from '../lib/api'

const STATUSES = ['open', 'watching', 'reviewed', 'dismissed'] as const
const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const
const CONFIDENCES = [
  'production_backed',
  'partial_dimension_support',
  'sparse_support',
  'readiness_only',
  'blocked',
] as const

function text(value: unknown, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function uniqueValues(items: any[], key: string) {
  const values = new Set<string>()
  for (const item of items) {
    const raw = item?.[key] ?? item?.evidence?.[key]
    if (raw) values.add(String(raw))
  }
  return Array.from(values).sort()
}

function ReviewItemEvents({
  projectKey,
  reviewItemId,
  expanded,
}: {
  projectKey: string
  reviewItemId: string
  expanded: boolean
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['project', 'schedule', 'review-item-events', projectKey, reviewItemId],
    queryFn: () => api.getProjectScheduleReviewItemEvents(projectKey, reviewItemId),
    enabled: expanded && Boolean(projectKey && reviewItemId),
  })

  if (!expanded) return null
  if (isLoading) return <p className="mt-2 text-xs text-[var(--hb-muted)]">Loading event history…</p>
  if (error) {
    return <p className="mt-2 text-xs text-[var(--hb-muted)]">Event history could not be loaded.</p>
  }

  const events = Array.isArray((data as any)?.events) ? (data as any).events : []
  if (!events.length) {
    return <p className="mt-2 text-xs text-[var(--hb-muted)]">No events recorded yet.</p>
  }

  return (
    <div className="mt-3 rounded border border-[var(--hb-border)] bg-black/10 p-3">
      <h5 className="text-xs font-semibold uppercase tracking-wide text-[var(--hb-muted)]">Event history</h5>
      <ul className="mt-2 space-y-1 text-xs">
        {events.map((event: any) => (
          <li key={String(event.event_id || `${event.event_type}-${event.created_at}`)}>
            <span className="font-medium">{text(event.event_type)}</span>
            {event.prior_status || event.new_status ? (
              <span className="text-[var(--hb-muted)]">
                {' '}
                ({text(event.prior_status, '')}
                {event.prior_status && event.new_status ? ' → ' : ''}
                {text(event.new_status, '')})
              </span>
            ) : null}
            {event.created_at ? <span className="text-[var(--hb-muted)]"> — {text(event.created_at)}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function ProjectScheduleWorkbenchPage() {
  const { projectKey = '' } = useParams()
  const [searchParams] = useSearchParams()
  const asOfDate = searchParams.get('as_of') || undefined
  const focusReview = searchParams.get('review') || undefined
  const focusRef = useRef<HTMLDivElement | null>(null)
  const queryClient = useQueryClient()
  const role = getLocalUiRole()
  const canSync = role === 'operator' || role === 'admin'
  const [comparisonBasis, setComparisonBasis] = useState<'prior_update' | 'baseline'>('prior_update')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [notesDraft, setNotesDraft] = useState<Record<string, string>>({})
  const [statusFilter, setStatusFilter] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [sourceMetricFilter, setSourceMetricFilter] = useState('')
  const [confidenceFilter, setConfidenceFilter] = useState('')
  const [phaseFilter, setPhaseFilter] = useState('')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [
      'project',
      'schedule',
      'review-items',
      projectKey,
      asOfDate,
      canSync,
      comparisonBasis,
      statusFilter,
      severityFilter,
      sourceMetricFilter,
      confidenceFilter,
      phaseFilter,
    ],
    queryFn: async () => {
      if (canSync && comparisonBasis === 'prior_update') {
        await api.syncProjectScheduleReviewItems(projectKey, { asOf: asOfDate })
      }
      return api.getProjectScheduleReviewItems(projectKey, {
        asOf: asOfDate,
        comparisonBasis,
        reviewStatus: statusFilter || undefined,
        severity: severityFilter || undefined,
        sourceMetric: sourceMetricFilter || undefined,
        confidence: confidenceFilter || undefined,
        phase: phaseFilter || undefined,
      })
    },
    enabled: Boolean(projectKey),
  })

  const updateMutation = useMutation({
    mutationFn: (args: { reviewItemId: string; reviewStatus: string; pmNotes?: string }) =>
      api.patchProjectScheduleReviewItem(projectKey, args.reviewItemId, {
        review_status: args.reviewStatus,
        pm_notes: args.pmNotes,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project', 'schedule', 'review-items', projectKey] })
      void queryClient.invalidateQueries({ queryKey: ['project', 'schedule', projectKey] })
      void queryClient.invalidateQueries({ queryKey: ['project', 'schedule', 'review-item-events', projectKey] })
    },
  })

  const exportMutation = useMutation({
    mutationFn: (format: 'markdown' | 'html') =>
      api.downloadProjectScheduleExport(projectKey, format, { asOf: asOfDate }),
  })

  const scheduleHref = asOfDate
    ? `/projects/${projectKey}/schedule?as_of=${encodeURIComponent(asOfDate)}`
    : `/projects/${projectKey}/schedule`

  const envelope = (data || {}) as Record<string, any>
  const workbench = (envelope.workbench || {}) as Record<string, any>
  const bases = (workbench.bases || {}) as Record<string, any>
  const baselineAvailable = Boolean(bases.baseline?.available)
  const items = Array.isArray(envelope.items) ? envelope.items : []

  const sourceMetrics = useMemo(() => uniqueValues(items, 'source_metric_key'), [items])
  const phases = useMemo(() => uniqueValues(items, 'phase'), [items])
  const productionBackedCount = items.filter((item: any) => item.confidence === 'production_backed').length
  const blockedPreviewCount = items.filter((item: any) => item.confidence === 'blocked').length

  useEffect(() => {
    if (!focusReview || !items.length) return
    const target = items.find(
      (item: any) =>
        String(item.stable_item_key) === focusReview || String(item.review_item_id) === focusReview,
    )
    if (target && focusRef.current) {
      focusRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
      setExpandedId(String(target.review_item_id || target.stable_item_key))
    }
  }, [focusReview, items])

  if (isLoading) {
    return (
      <ProjectWorkspaceShell>
        <LoadingState label="Loading schedule workbench..." />
      </ProjectWorkspaceShell>
    )
  }

  if (error) {
    return (
      <ProjectWorkspaceShell>
        <ErrorState
          userMessage="Schedule workbench could not be loaded."
          error={error}
          onRetry={() => { void refetch() }}
        />
      </ProjectWorkspaceShell>
    )
  }

  return (
    <ProjectWorkspaceShell>
      <section className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h3 className="section-title mb-0">Schedule Workbench</h3>
            <p className="mt-1 text-sm text-[var(--hb-muted)]">
              Persisted PM review queue with disposition carry-forward across updates.
              {asOfDate ? ` As of ${asOfDate}.` : ''}
            </p>
            {!canSync && (
              <p className="mt-1 text-xs text-[var(--hb-muted)]">
                Preview only — operator access is required to sync and update dispositions.
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Link className="badge" to={scheduleHref}>
              Back to Schedule
            </Link>
            <button
              className="badge"
              disabled={exportMutation.isPending}
              onClick={() => {
                void exportMutation.mutateAsync('markdown')
              }}
            >
              Export Memo (Markdown)
            </button>
            <button
              className="badge"
              disabled={exportMutation.isPending}
              onClick={() => {
                void exportMutation.mutateAsync('html')
              }}
            >
              Export Memo (HTML)
            </button>
          </div>
        </div>

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

        <div className="card space-y-3">
          <h4 className="text-sm font-semibold">Filters</h4>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <label className="text-xs">
              <span className="mb-1 block text-[var(--hb-muted)]">Status</span>
              <select
                className="w-full rounded border border-[var(--hb-border)] bg-black/20 px-2 py-1 text-sm"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
              >
                <option value="">All</option>
                {STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              <span className="mb-1 block text-[var(--hb-muted)]">Severity</span>
              <select
                className="w-full rounded border border-[var(--hb-border)] bg-black/20 px-2 py-1 text-sm"
                value={severityFilter}
                onChange={(event) => setSeverityFilter(event.target.value)}
              >
                <option value="">All</option>
                {SEVERITIES.map((severity) => (
                  <option key={severity} value={severity}>
                    {severity}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              <span className="mb-1 block text-[var(--hb-muted)]">Source metric</span>
              <select
                className="w-full rounded border border-[var(--hb-border)] bg-black/20 px-2 py-1 text-sm"
                value={sourceMetricFilter}
                onChange={(event) => setSourceMetricFilter(event.target.value)}
              >
                <option value="">All</option>
                {sourceMetrics.map((metric) => (
                  <option key={metric} value={metric}>
                    {metric}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              <span className="mb-1 block text-[var(--hb-muted)]">Confidence</span>
              <select
                className="w-full rounded border border-[var(--hb-border)] bg-black/20 px-2 py-1 text-sm"
                value={confidenceFilter}
                onChange={(event) => setConfidenceFilter(event.target.value)}
              >
                <option value="">All</option>
                {CONFIDENCES.map((confidence) => (
                  <option key={confidence} value={confidence}>
                    {confidence.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              <span className="mb-1 block text-[var(--hb-muted)]">Phase</span>
              <select
                className="w-full rounded border border-[var(--hb-border)] bg-black/20 px-2 py-1 text-sm"
                value={phaseFilter}
                onChange={(event) => setPhaseFilter(event.target.value)}
              >
                <option value="">All</option>
                {phases.map((phase) => (
                  <option key={phase} value={phase}>
                    {phase}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {!items.length ? (
          <EmptyState
            title="No review cues match the current filters"
            hint={
              blockedPreviewCount > 0
                ? 'Some metrics are readiness-only or blocked; they appear only in preview when unfiltered.'
                : canSync
                  ? 'Open the schedule hub to sync candidates from drivers, milestones, UDF metrics, and float pressure.'
                  : 'No preview items are available for this schedule update.'
            }
          />
        ) : productionBackedCount === 0 && blockedPreviewCount > 0 ? (
          <p className="text-sm text-[var(--hb-muted)]">
            Only readiness-only or blocked metric previews are visible. Production-backed cues require metric readiness.
          </p>
        ) : null}

        {items.length > 0 && (
          <div className="space-y-3">
            {items.map((item: any) => {
              const itemId = String(item.review_item_id || item.stable_item_key)
              const expanded = expandedId === itemId
              const caveats = Array.isArray(item.caveats) ? item.caveats : item.evidence?.caveats || []
              const dataQualityNotes = Array.isArray(item.data_quality_notes)
                ? item.data_quality_notes
                : item.evidence?.data_quality_notes || []
              const notesValue = notesDraft[itemId] ?? text(item.pm_notes, '')

              return (
                <article
                  key={itemId}
                  ref={
                    focusReview &&
                    (String(item.stable_item_key) === focusReview || String(item.review_item_id) === focusReview)
                      ? focusRef
                      : undefined
                  }
                  className={`card ${focusReview && String(item.stable_item_key) === focusReview ? 'ring-1 ring-[var(--hb-border)]' : ''}`}
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="badge capitalize">{text(item.review_status)}</span>
                        <span className="badge">P{text(item.priority)}</span>
                        {item.severity ? <span className="badge capitalize">{text(item.severity)}</span> : null}
                        {item.confidence ? (
                          <span className="badge">{text(item.confidence).replace(/_/g, ' ')}</span>
                        ) : null}
                        <span className="text-xs text-[var(--hb-muted)]">{text(item.item_type)}</span>
                        {item.new_since_last_review ? <span className="badge">New</span> : null}
                        {item.still_open_from_prior ? <span className="badge">Carried forward</span> : null}
                        {item.stale_signal ? <span className="badge">Stale signal</span> : null}
                      </div>
                      <h4 className="mt-2 font-semibold">{text(item.item_title)}</h4>
                      {item.cue_summary ? (
                        <p className="mt-1 text-sm text-[var(--hb-muted)]">{text(item.cue_summary)}</p>
                      ) : null}
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                      <button className="badge" onClick={() => setExpandedId(expanded ? null : itemId)}>
                        {expanded ? 'Hide detail' : 'Show detail'}
                      </button>
                      {item.source_activity_id && (
                        <Link
                          className="badge"
                          to={`/projects/${projectKey}/schedule/drivers/${encodeURIComponent(item.source_activity_id)}?basis=${comparisonBasis}${asOfDate ? `&as_of=${encodeURIComponent(asOfDate)}` : ''}`}
                        >
                          Open Driver Detail
                        </Link>
                      )}
                      {canSync && item.review_item_id ? (
                        <select
                          className="rounded border border-[var(--hb-border)] bg-black/20 px-2 py-1 text-sm"
                          value={text(item.review_status, 'open')}
                          disabled={updateMutation.isPending}
                          onChange={(event) => {
                            void updateMutation.mutateAsync({
                              reviewItemId: String(item.review_item_id),
                              reviewStatus: event.target.value,
                              pmNotes: notesValue || undefined,
                            })
                          }}
                        >
                          {STATUSES.map((status) => (
                            <option key={status} value={status}>
                              {status}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span className="badge capitalize">{text(item.review_status)}</span>
                      )}
                    </div>
                  </div>

                  {expanded && (
                    <div className="mt-4 space-y-3 border-t border-[var(--hb-border)] pt-4 text-sm">
                      <div className="grid gap-2 md:grid-cols-2">
                        <p>
                          <span className="text-[var(--hb-muted)]">Source metric:</span> {text(item.source_metric_key)}
                        </p>
                        <p>
                          <span className="text-[var(--hb-muted)]">Signal type:</span> {text(item.source_signal_type)}
                        </p>
                        <p>
                          <span className="text-[var(--hb-muted)]">Activity:</span>{' '}
                          {text(item.activity_name || item.source_activity_id)}
                        </p>
                        <p>
                          <span className="text-[var(--hb-muted)]">WBS:</span> {text(item.wbs_code)}
                        </p>
                        <p>
                          <span className="text-[var(--hb-muted)]">Phase:</span> {text(item.phase)}
                        </p>
                        <p>
                          <span className="text-[var(--hb-muted)]">Floor:</span> {text(item.floor)}
                        </p>
                        <p>
                          <span className="text-[var(--hb-muted)]">Sector / area:</span> {text(item.sector_area)}
                        </p>
                        <p>
                          <span className="text-[var(--hb-muted)]">Subcontractor:</span> {text(item.subcontractor)}
                        </p>
                      </div>

                      {caveats.length > 0 && (
                        <div>
                          <h5 className="text-xs font-semibold uppercase tracking-wide text-[var(--hb-muted)]">Caveats</h5>
                          <ul className="mt-1 list-disc space-y-1 pl-5 text-xs">
                            {caveats.map((caveat: string) => (
                              <li key={caveat}>{caveat}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {dataQualityNotes.length > 0 && (
                        <div>
                          <h5 className="text-xs font-semibold uppercase tracking-wide text-[var(--hb-muted)]">
                            Data quality notes
                          </h5>
                          <ul className="mt-1 list-disc space-y-1 pl-5 text-xs">
                            {dataQualityNotes.map((note: string) => (
                              <li key={note}>{note}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {canSync && item.review_item_id ? (
                        <div>
                          <label className="text-xs font-semibold uppercase tracking-wide text-[var(--hb-muted)]">
                            PM notes
                          </label>
                          <textarea
                            className="mt-1 w-full rounded border border-[var(--hb-border)] bg-black/20 px-2 py-2 text-sm"
                            rows={3}
                            value={notesValue}
                            onChange={(event) =>
                              setNotesDraft((current) => ({ ...current, [itemId]: event.target.value }))
                            }
                          />
                          <button
                            className="badge mt-2"
                            disabled={updateMutation.isPending}
                            onClick={() => {
                              void updateMutation.mutateAsync({
                                reviewItemId: String(item.review_item_id),
                                reviewStatus: text(item.review_status, 'open'),
                                pmNotes: notesValue,
                              })
                            }}
                          >
                            Save notes
                          </button>
                        </div>
                      ) : item.pm_notes ? (
                        <p className="text-sm text-[var(--hb-muted)]">Notes: {text(item.pm_notes)}</p>
                      ) : null}

                      {item.review_item_id ? (
                        <ReviewItemEvents
                          projectKey={projectKey}
                          reviewItemId={String(item.review_item_id)}
                          expanded={expanded}
                        />
                      ) : null}
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        )}

        <p className="text-xs text-[var(--hb-muted)]">
          Sequence cues only — not causation findings. Dispositions persist by stable item key across schedule updates.
        </p>
      </section>
    </ProjectWorkspaceShell>
  )
}
