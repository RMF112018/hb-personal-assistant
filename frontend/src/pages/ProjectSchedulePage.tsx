/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { TechnicalDetails } from '../components/common/TechnicalDetails'
import { ProjectWorkspaceShell } from '../components/projects/ProjectWorkspaceShell'
import { api } from '../lib/api'
import type { ProjectScheduleSummaryResponse } from '../lib/api'

function text(value: unknown, fallback = 'Not available') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function num(value: unknown, fallback = '0') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function toneFor(status: unknown) {
  const value = String(status || '').toLowerCase()
  if (value === 'good') return 'border-emerald-800/70'
  if (value === 'watch') return 'border-amber-800/70'
  if (value === 'at_risk' || value === 'blocked') return 'border-red-900/70'
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

export function ProjectSchedulePage() {
  const { projectKey = '' } = useParams()
  const [showAllActions, setShowAllActions] = useState(false)
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['project', 'schedule', projectKey],
    queryFn: () => api.getProjectScheduleSummary(projectKey),
    enabled: Boolean(projectKey),
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
  const links = schedule.technical_links || {}
  const actionEnvelope = schedule.actions || {}
  const previewActions = Array.isArray(actionEnvelope.preview) ? actionEnvelope.preview : []
  const allActions = Array.isArray(actionEnvelope.all_items) ? actionEnvelope.all_items : previewActions
  const visibleActions = showAllActions ? allActions : previewActions

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
          <ReadinessList readiness={readiness} />
        </div>

        <div className={`card ${toneFor(health.status)}`}>
          <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
            <div>
              <div className="text-xs uppercase tracking-wide text-[var(--hb-muted)]">Schedule Story</div>
              <h4 className="mt-1 text-xl font-semibold">{text(story.headline)}</h4>
              <p className="mt-2 text-sm text-[var(--hb-muted)]">{text(story.synopsis)}</p>
              <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
                <div>
                  <div className="text-xs text-[var(--hb-muted)]">Primary Driver</div>
                  <div>{text(story.primary_change_driver)}</div>
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
              <MetricTile label="Float Pressure" value={num(command.negative_float_remaining_count)} helper="negative-float remaining" />
            </div>
          </div>
        </div>

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
              <MetricTile label="Worsened Float" value={direct.summary?.worsened_float_count} />
              <MetricTile label="Changed Remaining" value={direct.summary?.changed_count} />
              <MetricTile label="Upstream Cues" value={upstream.summary?.changed_upstream_count} />
            </div>
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
            {trends.available ? (
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
