/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'
import { api, getLocalUiRole } from '../lib/api'

const STATUSES = ['open', 'watching', 'reviewed', 'dismissed'] as const

function text(value: unknown, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
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

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['project', 'schedule', 'review-items', projectKey, asOfDate, canSync, comparisonBasis],
    queryFn: async () => {
      if (canSync && comparisonBasis === 'prior_update') {
        await api.syncProjectScheduleReviewItems(projectKey, { asOf: asOfDate })
      }
      return api.getProjectScheduleReviewItems(projectKey, {
        asOf: asOfDate,
        comparisonBasis,
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

  useEffect(() => {
    if (!focusReview || !items.length) return
    const target = items.find(
      (item: any) =>
        String(item.stable_item_key) === focusReview || String(item.review_item_id) === focusReview,
    )
    if (target && focusRef.current) {
      focusRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
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

        {!items.length ? (
          <EmptyState
            title="No review items yet"
            hint={
              canSync
                ? 'Open the schedule hub to sync candidates from drivers, milestones, and float pressure.'
                : 'No preview items are available for this schedule update.'
            }
          />
        ) : (
          <div className="space-y-3">
            {items.map((item: any) => (
              <article
                key={item.review_item_id}
                ref={
                  focusReview &&
                  (String(item.stable_item_key) === focusReview || String(item.review_item_id) === focusReview)
                    ? focusRef
                    : undefined
                }
                className={`card ${focusReview && String(item.stable_item_key) === focusReview ? 'ring-1 ring-[var(--hb-border)]' : ''}`}
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="badge capitalize">{text(item.review_status)}</span>
                      <span className="badge">P{text(item.priority)}</span>
                      <span className="text-xs text-[var(--hb-muted)]">{text(item.item_type)}</span>
                    </div>
                    <h4 className="mt-2 font-semibold">{text(item.item_title)}</h4>
                    {item.pm_notes && (
                      <p className="mt-1 text-sm text-[var(--hb-muted)]">Notes: {text(item.pm_notes)}</p>
                    )}
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    {item.source_activity_id && (
                      <Link
                        className="badge"
                        to={`/projects/${projectKey}/schedule/drivers/${encodeURIComponent(item.source_activity_id)}?basis=${comparisonBasis}${asOfDate ? `&as_of=${encodeURIComponent(asOfDate)}` : ''}`}
                      >
                        Open Driver Detail
                      </Link>
                    )}
                    {canSync ? (
                      <select
                        className="rounded border border-[var(--hb-border)] bg-black/20 px-2 py-1 text-sm"
                        value={text(item.review_status, 'open')}
                        disabled={updateMutation.isPending}
                        onChange={(event) => {
                          void updateMutation.mutateAsync({
                            reviewItemId: String(item.review_item_id),
                            reviewStatus: event.target.value,
                            pmNotes: item.pm_notes,
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
              </article>
            ))}
          </div>
        )}

        <p className="text-xs text-[var(--hb-muted)]">
          Sequence cues only — not causation findings. Dispositions persist by stable item key across schedule updates.
        </p>
      </section>
    </ProjectWorkspaceShell>
  )
}