/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { ReviewCueCard } from '../components/project-schedule/ReviewCueCard'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'
import { api, getLocalUiRole } from '../lib/api'
import type { ReviewWorkbenchComparisonBasis } from '../lib/api'
import {
  formatNamedComparisonContextLine,
  labelForComparisonBasis,
} from '../lib/scheduleBaselineLabels'

const NAMED_WORKBENCH_BASIS = new Set<ReviewWorkbenchComparisonBasis>([
  'current_contract_baseline',
  'previous_progress_update_baseline',
  'secondary_progress_update_baseline',
])

function parseWorkbenchComparisonBasis(raw: string | null): ReviewWorkbenchComparisonBasis {
  if (raw === 'prior_update' || !raw) return 'prior_update'
  if (NAMED_WORKBENCH_BASIS.has(raw as ReviewWorkbenchComparisonBasis)) {
    return raw as ReviewWorkbenchComparisonBasis
  }
  return 'prior_update'
}

function isNamedWorkbenchBasis(basis: ReviewWorkbenchComparisonBasis): boolean {
  return NAMED_WORKBENCH_BASIS.has(basis)
}

const STATUSES = [
  'needs_review',
  'accepted_for_follow_up',
  'dismissed_not_material',
  'resolved',
  'superseded',
  'duplicate',
] as const
const REASON_REQUIRED = new Set(['dismissed_not_material', 'superseded', 'duplicate', 'resolved'])
const OPERATOR_DISPOSITIONS = [
  { value: 'needs_review', label: 'Needs review' },
  { value: 'accepted_for_follow_up', label: 'Accepted for PM follow-up' },
  { value: 'dismissed_not_material', label: 'Dismissed as not material' },
  { value: 'superseded', label: 'Superseded' },
  { value: 'duplicate', label: 'Duplicate' },
  { value: 'resolved', label: 'Resolved' },
] as const
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

function num(value: unknown) {
  if (value === null || value === undefined || value === '') return '0'
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
  const [searchParams, setSearchParams] = useSearchParams()
  const rawAsOf = searchParams.get('as_of') || ''
  const asOfDate = /^\d{4}-\d{2}-\d{2}$/.test(rawAsOf) ? rawAsOf : undefined
  const focusReview = searchParams.get('review') || undefined
  const urlComparisonBasis = searchParams.get('comparison_basis')
  const focusRef = useRef<HTMLDivElement | null>(null)
  const queryClient = useQueryClient()
  const role = getLocalUiRole()
  const canSync = role === 'operator' || role === 'admin'
  const [comparisonBasis, setComparisonBasis] = useState<ReviewWorkbenchComparisonBasis>(() =>
    parseWorkbenchComparisonBasis(urlComparisonBasis),
  )
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [notesDraft, setNotesDraft] = useState<Record<string, string>>({})
  const [statusFilter, setStatusFilter] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [sourceMetricFilter, setSourceMetricFilter] = useState('')
  const [confidenceFilter, setConfidenceFilter] = useState('')
  const [phaseFilter, setPhaseFilter] = useState('')
  const [selectedPreview, setSelectedPreview] = useState<Record<string, boolean>>({})
  const [reasonDraft, setReasonDraft] = useState<Record<string, string>>({})

  const namedPreview = isNamedWorkbenchBasis(comparisonBasis)

  const baselinesQuery = useQuery({
    queryKey: ['project', 'schedule', projectKey, 'baselines', asOfDate || 'latest'],
    queryFn: () => api.getProjectScheduleBaselines(projectKey, { asOf: asOfDate }),
    enabled: Boolean(projectKey),
  })

  useEffect(() => {
    setComparisonBasis(parseWorkbenchComparisonBasis(urlComparisonBasis))
  }, [urlComparisonBasis])

  const selectedNamedSlots = useMemo(() => {
    const slots = Array.isArray((baselinesQuery.data as any)?.slots) ? (baselinesQuery.data as any).slots : []
    return slots.filter((slot: any) => slot.status === 'selected')
  }, [baselinesQuery.data])

  const activeNamedSlot = useMemo(() => {
    if (!namedPreview) return null
    return (
      selectedNamedSlots.find((slot: any) => String(slot.slot_key) === comparisonBasis) || {
        slot_label: labelForComparisonBasis(comparisonBasis),
        selection: null,
        status: 'missing',
      }
    )
  }, [comparisonBasis, namedPreview, selectedNamedSlots])
  const namedSlotReady = !namedPreview || activeNamedSlot?.status === 'selected'
  const canSyncWorkbench = canSync && (!namedPreview || namedSlotReady)

  const selectComparisonBasis = (basis: ReviewWorkbenchComparisonBasis) => {
    setComparisonBasis(basis)
    const next = new URLSearchParams(searchParams)
    if (basis === 'prior_update') {
      next.delete('comparison_basis')
    } else {
      next.set('comparison_basis', basis)
    }
    setSearchParams(next, { replace: true })
  }

  const reviewItemsQueryKey = [
    'project',
    'schedule',
    'review-items',
    projectKey,
    asOfDate,
    canSyncWorkbench,
    comparisonBasis,
    statusFilter,
    severityFilter,
    sourceMetricFilter,
    confidenceFilter,
    phaseFilter,
  ] as const

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: reviewItemsQueryKey,
    queryFn: () =>
      api.getProjectScheduleReviewItems(projectKey, {
        asOf: asOfDate,
        comparisonBasis,
        reviewStatus: statusFilter || undefined,
        severity: severityFilter || undefined,
        sourceMetric: sourceMetricFilter || undefined,
        confidence: confidenceFilter || undefined,
        phase: phaseFilter || undefined,
      }),
    enabled: Boolean(projectKey),
  })

  const syncMutation = useMutation({
    mutationFn: () => api.syncProjectScheduleReviewItems(projectKey, { asOf: asOfDate, comparisonBasis }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...reviewItemsQueryKey] })
    },
  })

  const promoteMutation = useMutation({
    mutationFn: (stableItemKeys: string[]) =>
      api.promoteProjectScheduleReviewItems(projectKey, { stable_item_keys: stableItemKeys }, {
        asOf: asOfDate,
        comparisonBasis,
      }),
    onSuccess: () => {
      setSelectedPreview({})
      void queryClient.invalidateQueries({ queryKey: [...reviewItemsQueryKey] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: (args: {
      reviewItemId: string
      reviewStatus: string
      pmNotes?: string
      dispositionReason?: string
    }) =>
      api.patchProjectScheduleReviewItem(projectKey, args.reviewItemId, {
        disposition: args.reviewStatus,
        pm_notes: args.pmNotes,
        disposition_reason: args.dispositionReason,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...reviewItemsQueryKey] })
      void queryClient.invalidateQueries({ queryKey: ['project', 'schedule', projectKey, asOfDate] })
      void queryClient.invalidateQueries({ queryKey: ['project', 'schedule', 'review-item-events', projectKey] })
    },
  })

  const exportMutation = useMutation({
    mutationFn: (format: 'markdown' | 'html') =>
      api.downloadProjectScheduleExport(projectKey, format, {
        asOf: asOfDate,
        comparisonBasis,
      }),
  })

  const scheduleHref = asOfDate
    ? `/projects/${projectKey}/schedule?as_of=${encodeURIComponent(asOfDate)}`
    : `/projects/${projectKey}/schedule`

  const envelope = (data || {}) as Record<string, any>
  const workbench = (envelope.workbench || {}) as Record<string, any>
  const items = Array.isArray(envelope.items) ? envelope.items : []
  const reviewStatus = (workbench.review_status || workbench.summary || {}) as Record<string, any>
  const previewItems = items.filter((item: any) => !item.review_item_id)
  const persistedItems = items.filter((item: any) => item.review_item_id)
  const selectedPreviewKeys = Object.entries(selectedPreview)
    .filter(([, selected]) => selected)
    .map(([key]) => key)
  const readOnlyNamedPreview =
    Boolean(workbench.read_only_baseline_preview) || (namedPreview && !namedSlotReady)
  const namedComparisonLine = namedPreview
    ? formatNamedComparisonContextLine({
        slotLabel: activeNamedSlot?.slot_label || labelForComparisonBasis(comparisonBasis),
        displayName: activeNamedSlot?.selection?.display_name,
        dataDate: activeNamedSlot?.selection?.schedule_data_date,
        asOf: asOfDate || null,
      })
    : null

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

  function renderReviewCard(item: any, isPreview: boolean) {
    const itemId = String(item.review_item_id || item.stable_item_key)
    const expanded = expandedId === itemId
    const notesValue = notesDraft[itemId] ?? text(item.pm_notes, '')
    const reasonValue = reasonDraft[itemId] ?? text(item.disposition_reason, '')
    const stableKey = String(item.stable_item_key || itemId)

    return (
      <ReviewCueCard
        key={itemId}
        item={item}
        projectKey={projectKey}
        comparisonBasis={comparisonBasis}
        asOfDate={asOfDate}
        canSync={canSyncWorkbench}
        isPreview={isPreview}
        selectable={isPreview && canSyncWorkbench}
        selected={Boolean(selectedPreview[stableKey])}
        onSelectChange={(selected) =>
          setSelectedPreview((current) => ({ ...current, [stableKey]: selected }))
        }
        expanded={expanded}
        notesValue={notesValue}
        reasonValue={reasonValue}
        operatorDispositions={OPERATOR_DISPOSITIONS}
        reasonRequiredDispositions={REASON_REQUIRED}
        focusRef={focusRef}
        focusReview={focusReview}
        updatePending={updateMutation.isPending}
        onToggleExpanded={() => setExpandedId(expanded ? null : itemId)}
        onNotesChange={(value) => setNotesDraft((current) => ({ ...current, [itemId]: value }))}
        onReasonChange={(value) => setReasonDraft((current) => ({ ...current, [itemId]: value }))}
        onSaveNotes={() => {
          void updateMutation.mutateAsync({
            reviewItemId: String(item.review_item_id),
            reviewStatus: text(item.review_status, 'needs_review'),
            pmNotes: notesValue,
            dispositionReason: reasonValue || undefined,
          })
        }}
        onStatusChange={(reviewStatus) => {
          void updateMutation.mutateAsync({
            reviewItemId: String(item.review_item_id),
            reviewStatus,
            pmNotes: notesValue || undefined,
            dispositionReason: reasonValue || undefined,
          })
        }}
        eventsSlot={
          item.review_item_id ? (
            <ReviewItemEvents
              projectKey={projectKey}
              reviewItemId={String(item.review_item_id)}
              expanded={expanded}
            />
          ) : null
        }
      />
    )
  }

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
              {namedPreview && namedSlotReady
                ? `Named baseline review — sync and disposition for ${labelForComparisonBasis(comparisonBasis)}.`
                : readOnlyNamedPreview
                  ? 'Live preview for named baseline comparison — select a valid baseline anchor to persist dispositions.'
                  : 'Persisted PM review queue with disposition carry-forward across updates.'}
              {asOfDate ? ` As of ${asOfDate}.` : ''}
            </p>
            {!canSyncWorkbench && (
              <p className="mt-1 text-xs text-[var(--hb-muted)]">
                {namedPreview && !namedSlotReady
                  ? 'Select a valid named baseline anchor on the Schedule hub before syncing review cues.'
                  : 'Preview only — operator access is required to sync and update dispositions.'}
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
            {canSyncWorkbench ? (
              <>
                <button
                  className="badge"
                  type="button"
                  disabled={syncMutation.isPending}
                  onClick={() => {
                    void syncMutation.mutateAsync()
                  }}
                >
                  Sync all materializable cues
                </button>
                <button
                  className="badge"
                  type="button"
                  disabled={promoteMutation.isPending || selectedPreviewKeys.length === 0}
                  onClick={() => {
                    void promoteMutation.mutateAsync(selectedPreviewKeys)
                  }}
                >
                  Promote selected preview cues
                </button>
              </>
            ) : null}
          </div>
        </div>

        {reviewStatus.pm_summary ? (
          <div className="rounded border border-[var(--hb-border)] bg-black/20 px-4 py-3 text-sm" role="status">
            <div className="font-medium">Review status</div>
            <p className="mt-1 text-[var(--hb-muted)]">{text(reviewStatus.pm_summary)}</p>
            <p className="mt-2 text-xs text-[var(--hb-muted)]">
              {num(reviewStatus.preview_cue_count)} preview · {num(reviewStatus.persisted_item_count)} persisted ·{' '}
              {num(reviewStatus.needs_review)} needs review · {num(reviewStatus.accepted_for_follow_up)} accepted ·{' '}
              {num(reviewStatus.blocked)} blocked
            </p>
            {reviewStatus.recommended_next_action ? (
              <p className="mt-1 text-xs">{text(reviewStatus.recommended_next_action)}</p>
            ) : null}
          </div>
        ) : null}

        {readOnlyNamedPreview && (
          <div
            className="rounded border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm"
            role="status"
          >
            <div className="font-medium text-amber-200">
              {namedPreview && !namedSlotReady
                ? 'Named baseline not ready'
                : 'Selected baseline preview — read only'}
            </div>
            <p className="mt-1 text-[var(--hb-muted)]">
              {namedPreview && !namedSlotReady
                ? 'This named baseline anchor is missing or invalid. Choose a baseline on the Schedule hub, then return here to sync review cues.'
                : 'This Workbench view compares against the legacy selected baseline. Review signals are preview only — switch to Prior Update or a named baseline anchor to persist dispositions.'}
            </p>
            {namedComparisonLine ? (
              <p className="mt-2 text-xs text-[var(--hb-muted)]">{namedComparisonLine}</p>
            ) : null}
          </div>
        )}

        {namedPreview && namedSlotReady && !readOnlyNamedPreview ? (
          <div className="rounded border border-[var(--hb-border)] bg-black/20 px-4 py-3 text-sm" role="status">
            <div className="font-medium">Named baseline review</div>
            {namedComparisonLine ? (
              <p className="mt-1 text-xs text-[var(--hb-muted)]">{namedComparisonLine}</p>
            ) : null}
            <p className="mt-1 text-xs text-[var(--hb-muted)]">
              Dispositions are saved separately from Prior Update and other named baseline anchors.
            </p>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <button
            className={`badge ${comparisonBasis === 'prior_update' ? 'ring-1 ring-[var(--hb-border)]' : ''}`}
            onClick={() => selectComparisonBasis('prior_update')}
          >
            Since previous update
          </button>
          {selectedNamedSlots.map((slot: any) => (
            <button
              key={String(slot.slot_key)}
              className={`badge ${comparisonBasis === slot.slot_key ? 'ring-1 ring-[var(--hb-border)]' : ''}`}
              onClick={() => selectComparisonBasis(slot.slot_key as ReviewWorkbenchComparisonBasis)}
            >
              {text(slot.slot_label, labelForComparisonBasis(String(slot.slot_key)))}
            </button>
          ))}
        </div>

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
                : canSyncWorkbench
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
          <div className="space-y-6">
            {previewItems.length > 0 ? (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold">Preview cues</h4>
                {previewItems.map((item: any) => renderReviewCard(item, true))}
              </div>
            ) : null}
            {persistedItems.length > 0 ? (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold">Persisted review items</h4>
                {persistedItems.map((item: any) => renderReviewCard(item, false))}
              </div>
            ) : null}
            {!previewItems.length && !persistedItems.length
              ? items.map((item: any) => renderReviewCard(item, !item.review_item_id))
              : null}
          </div>
        )}

        <p className="text-xs text-[var(--hb-muted)]">
          Sequence cues only — not causation findings.
          {readOnlyNamedPreview
            ? ' Named baseline preview does not persist PM dispositions.'
            : ' Dispositions persist by stable item key across schedule updates.'}
        </p>
      </section>
    </ProjectWorkspaceShell>
  )
}
