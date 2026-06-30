/* eslint-disable @typescript-eslint/no-explicit-any */
import { Link } from 'react-router-dom'

import type { ScheduleControlsComparisonBasis } from '../../lib/api'
import { SectionCard } from '../common/SectionCard'

const COMPARISON_CHOICES: { id: ScheduleControlsComparisonBasis; label: string }[] = [
  { id: 'prior_update', label: 'Prior Update' },
  { id: 'current_contract_baseline', label: 'Current Contract Baseline' },
  { id: 'previous_progress_update_baseline', label: 'Previous Progress Update Baseline' },
  { id: 'secondary_progress_update_baseline', label: 'Secondary Progress Update Baseline' },
]

function text(value: unknown, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function statusTone(status: string) {
  switch (status) {
    case 'healthy':
      return 'text-emerald-400'
    case 'watch':
      return 'text-amber-400'
    case 'review':
      return 'text-orange-400'
    case 'critical':
      return 'text-red-400'
    default:
      return 'text-[var(--hb-muted)]'
  }
}

export type ScheduleControlsPanelProps = {
  controls?: Record<string, any>
  loading?: boolean
  error?: unknown
  comparisonBasis: ScheduleControlsComparisonBasis
  onComparisonBasisChange: (basis: ScheduleControlsComparisonBasis) => void
}

export function ScheduleControlsPanel({
  controls,
  loading = false,
  error,
  comparisonBasis,
  onComparisonBasisChange,
}: ScheduleControlsPanelProps) {
  if (loading) {
    return (
      <SectionCard title="Schedule Controls">
        <p className="text-sm text-[var(--hb-muted)]" role="status">
          Loading schedule controls...
        </p>
      </SectionCard>
    )
  }

  if (error) {
    return (
      <SectionCard title="Schedule Controls">
        <p className="text-sm text-amber-400" role="alert">
          Schedule controls are unavailable right now.
        </p>
      </SectionCard>
    )
  }

  if (!controls?.available) {
    const slotLabel = text(controls?.baseline_context?.slot_label, '')
    const missingNamed =
      controls?.reason === 'baseline_not_selected' && slotLabel
        ? `No ${slotLabel} selected.`
        : null
    return (
      <SectionCard title="Schedule Controls">
        <div className="mb-3 flex flex-wrap gap-2">
          {COMPARISON_CHOICES.map((choice) => (
            <button
              key={choice.id}
              type="button"
              className={`badge ${comparisonBasis === choice.id ? 'ring-1 ring-[var(--hb-border)]' : ''}`}
              onClick={() => onComparisonBasisChange(choice.id)}
            >
              {choice.label}
            </button>
          ))}
        </div>
        <p className="text-sm text-[var(--hb-muted)]">
          {missingNamed || text(controls?.reason?.replace(/_/g, ' '), 'Schedule controls are not available for this project.')}
        </p>
      </SectionCard>
    )
  }

  const summary = controls.summary || {}
  const topControls = Array.isArray(controls.top_controls) ? controls.top_controls : []
  const cpmSection = controls.sections?.cpm_observability || {}
  const workbenchLinks = controls.links || {}

  return (
    <SectionCard title="Schedule Controls">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {COMPARISON_CHOICES.map((choice) => (
            <button
              key={choice.id}
              type="button"
              className={`badge ${comparisonBasis === choice.id ? 'ring-1 ring-[var(--hb-border)]' : ''}`}
              onClick={() => onComparisonBasisChange(choice.id)}
            >
              {choice.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className={`text-xs font-semibold uppercase tracking-wide ${statusTone(String(summary.overall_status || 'unknown'))}`}>
              {text(summary.overall_status, 'unknown').replace(/_/g, ' ')}
            </div>
            <h4 className="mt-1 text-base font-semibold">{text(summary.headline)}</h4>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--hb-muted)]">
              {(summary.supporting_points || []).slice(0, 4).map((point: string) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            {controls.schedule_data_date && (
              <span className="badge">Data date {controls.schedule_data_date}</span>
            )}
            {controls.as_of_date && <span className="badge">As of {controls.as_of_date}</span>}
          </div>
        </div>

        {cpmSection.available && (
          <p className="text-sm text-[var(--hb-muted)]">{text(cpmSection.headline)}</p>
        )}

        {topControls.length > 0 ? (
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--hb-muted)]">Top controls</div>
            {topControls.map((control: any) => (
              <div key={String(control.control_id)} className="rounded border border-[var(--hb-border)] p-3">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="badge">{text(control.category).replace(/_/g, ' ')}</span>
                  <span className="badge">{text(control.severity)}</span>
                  <span className="badge">{text(control.confidence)} confidence</span>
                </div>
                <div className="mt-2 font-medium">{text(control.title)}</div>
                <p className="mt-1 text-sm text-[var(--hb-muted)]">{text(control.summary)}</p>
                <p className="mt-2 text-sm">{text(control.recommended_action)}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  {control.links?.review_item && (
                    <Link className="badge" to={control.links.review_item}>
                      Open review cue
                    </Link>
                  )}
                  {control.links?.driver_detail && (
                    <Link className="badge" to={control.links.driver_detail}>
                      Open driver detail
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--hb-muted)]">No priority controls signals for the selected context.</p>
        )}

        <div className="flex flex-wrap gap-2 text-xs">
          {workbenchLinks.review_workbench && (
            <Link className="badge" to={workbenchLinks.review_workbench}>
              Open review workbench
            </Link>
          )}
        </div>

        <p className="text-xs text-[var(--hb-muted)]">
          Schedule controls identify sequence and data-quality cues for PM review. They do not determine causation,
          entitlement, or responsibility.
        </p>
      </div>
    </SectionCard>
  )
}
