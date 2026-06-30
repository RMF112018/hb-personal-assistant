/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react'
import { Link } from 'react-router-dom'

import type { ReviewWorkbenchComparisonBasis } from '../../lib/api'

function text(value: unknown, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

export function ReviewCueTechnicalDetails({ item }: { item: Record<string, any> }) {
  const [open, setOpen] = useState(false)
  const evidence = (item.evidence || {}) as Record<string, any>
  const technical = (evidence.technical_evidence || {}) as Record<string, any>
  if (!evidence.technical_evidence_available) {
    return null
  }

  return (
    <div className="mt-3">
      <button className="badge text-xs" type="button" onClick={() => setOpen((value) => !value)}>
        {open ? 'Hide technical evidence' : 'Show technical evidence'}
      </button>
      {open && (
        <div className="mt-2 rounded border border-[var(--hb-border)] bg-black/10 p-3 text-xs">
          {evidence.source_file_names?.length ? (
            <p>
              <span className="text-[var(--hb-muted)]">Source files:</span>{' '}
              {(evidence.source_file_names as string[]).join(', ')}
            </p>
          ) : null}
          {evidence.source_formats?.length ? (
            <p>
              <span className="text-[var(--hb-muted)]">Source formats:</span>{' '}
              {(evidence.source_formats as string[]).join(', ')}
            </p>
          ) : null}
          {technical.cpm_status ? (
            <p>
              <span className="text-[var(--hb-muted)]">CPM status:</span> {text(technical.cpm_status)}
            </p>
          ) : null}
          {technical.field_lineage?.length ? (
            <div className="mt-2">
              <div className="font-semibold text-[var(--hb-muted)]">Field lineage snippets</div>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {(technical.field_lineage as any[]).map((row, index) => (
                  <li key={`${row.field_name || 'field'}-${index}`}>
                    {text(row.field_name)} ({text(row.source_format)}): {text(row.canonical_value)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <details className="mt-2">
            <summary className="cursor-pointer text-[var(--hb-muted)]">Raw technical payload</summary>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all text-[10px]">
              {JSON.stringify(technical, null, 2)}
            </pre>
          </details>
        </div>
      )}
    </div>
  )
}

type ReviewCueCardProps = {
  item: Record<string, any>
  projectKey: string
  comparisonBasis: ReviewWorkbenchComparisonBasis | 'baseline'
  asOfDate?: string
  canSync: boolean
  expanded: boolean
  notesValue: string
  onToggleExpanded: () => void
  onNotesChange: (value: string) => void
  onSaveNotes: () => void
  onStatusChange: (status: string) => void
  updatePending: boolean
  focusRef?: React.RefObject<HTMLDivElement | null>
  focusReview?: string
  eventsSlot?: React.ReactNode
}

export function ReviewCueCard({
  item,
  projectKey,
  comparisonBasis,
  asOfDate,
  canSync,
  expanded,
  notesValue,
  onToggleExpanded,
  onNotesChange,
  onSaveNotes,
  onStatusChange,
  updatePending,
  focusRef,
  focusReview,
  eventsSlot,
}: ReviewCueCardProps) {
  const evidence = (item.evidence || {}) as Record<string, any>
  const caveats = Array.isArray(item.caveats) ? item.caveats : evidence.caveats || []
  const dataQualityNotes = Array.isArray(item.data_quality_notes)
    ? item.data_quality_notes
    : evidence.data_quality_notes || []
  const driverHref = item.source_activity_id
    ? `/projects/${projectKey}/schedule/drivers/${encodeURIComponent(String(item.source_activity_id))}?basis=${comparisonBasis}${asOfDate ? `&as_of=${encodeURIComponent(asOfDate)}` : ''}`
    : null

  return (
    <article
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
            {evidence.cue_category ? <span className="badge">{text(evidence.cue_category).replace(/_/g, ' ')}</span> : null}
            {item.new_since_last_review ? <span className="badge">New</span> : null}
            {item.still_open_from_prior ? <span className="badge">Carried forward</span> : null}
            {item.stale_signal ? <span className="badge">Stale signal</span> : null}
          </div>
          <h4 className="mt-2 font-semibold">{text(evidence.cue_label || item.item_title)}</h4>
          {item.cue_summary || evidence.cue_summary ? (
            <p className="mt-1 text-sm text-[var(--hb-muted)]">{text(item.cue_summary || evidence.cue_summary)}</p>
          ) : null}
          {evidence.recommended_review_action ? (
            <p className="mt-2 text-sm">{text(evidence.recommended_review_action)}</p>
          ) : null}
          {evidence.evidence_summary ? (
            <p className="mt-2 text-xs text-[var(--hb-muted)]">{text(evidence.evidence_summary)}</p>
          ) : null}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <button className="badge" type="button" onClick={onToggleExpanded}>
            {expanded ? 'Hide detail' : 'Show detail'}
          </button>
          {driverHref ? (
            <Link className="badge" to={driverHref}>
              Open Driver Detail
            </Link>
          ) : null}
          {canSync && item.review_item_id ? (
            <select
              className="rounded border border-[var(--hb-border)] bg-black/20 px-2 py-1 text-sm"
              value={text(item.review_status, 'open')}
              disabled={updatePending}
              onChange={(event) => onStatusChange(event.target.value)}
            >
              {['open', 'watching', 'reviewed', 'dismissed'].map((status) => (
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
              <span className="text-[var(--hb-muted)]">Review as of:</span> {text(evidence.as_of)}
            </p>
            <p>
              <span className="text-[var(--hb-muted)]">Schedule data date:</span> {text(evidence.schedule_data_date)}
            </p>
            <p>
              <span className="text-[var(--hb-muted)]">Source metric:</span> {text(item.source_metric_key)}
            </p>
            <p>
              <span className="text-[var(--hb-muted)]">Signal type:</span> {text(item.source_signal_type)}
            </p>
            <p>
              <span className="text-[var(--hb-muted)]">Activity:</span> {text(item.activity_name || evidence.activity_name)}
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
              <h5 className="text-xs font-semibold uppercase tracking-wide text-[var(--hb-muted)]">Data quality notes</h5>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-xs">
                {dataQualityNotes.map((note: string) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          )}

          <ReviewCueTechnicalDetails item={item} />

          {canSync && item.review_item_id ? (
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-[var(--hb-muted)]">PM notes</label>
              <textarea
                className="mt-1 w-full rounded border border-[var(--hb-border)] bg-black/20 px-2 py-2 text-sm"
                rows={3}
                value={notesValue}
                onChange={(event) => onNotesChange(event.target.value)}
              />
              <button className="badge mt-2" type="button" disabled={updatePending} onClick={onSaveNotes}>
                Save notes
              </button>
            </div>
          ) : item.pm_notes ? (
            <p className="text-sm text-[var(--hb-muted)]">Notes: {text(item.pm_notes)}</p>
          ) : null}

          {eventsSlot}
        </div>
      )}
    </article>
  )
}
