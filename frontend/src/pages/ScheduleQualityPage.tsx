import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import {
  ScheduleBackLink,
  SchedulePageHeader,
  ScheduleShell,
  ScheduleSubnav,
  ScheduleTable,
  ScheduleTd,
  ScheduleTh,
} from '../components/schedule/SchedulePageChrome'
import {
  ScheduleProjectContext,
  ScheduleProjectPicker,
  useScheduleProjectParam,
  useScheduleProjects,
} from '../components/schedule/ScheduleProjectPicker'
import { ScheduleVersionPicker } from '../components/schedule/ScheduleVersionPicker'
import { EmptyState } from '../components/ui/EmptyState'
import { api, getLocalUiRole } from '../lib/api'
import {
  CPM_RECALCULATION_BANNER,
  formatProjectCapabilityBanner,
  getScheduleFormatLabel,
} from '../lib/scheduleCapabilityCopy'
import { Link } from 'react-router-dom'

type QualitySummary = {
  schedule_version_key?: string
  project_key?: string
  project_display_name?: string | null
  source_format?: string
  status?: string
  completion_posture?: string
  assessment_profile?: string
  quality_score?: string | null
  quality_grade?: string | null
  scorecard?: {
    dcma_measured_count?: number
    dcma_not_measurable_count?: number
    dcma_pass_count?: number
    dcma_warn_count?: number
    dcma_fail_count?: number
  }
  metrics?: Array<Record<string, unknown>>
  gao_category_summary?: Record<string, { posture?: string; reason?: string | null }>
  downstream_readiness?: {
    completion_posture?: string
    cost_mapping?: string
    cost_weighting?: string
    critical_path_analytics?: string
    baseline_analytics?: string
    true_cost_loaded_analytics?: string
    cost_mapping_ready?: boolean
    cost_weighting_ready?: boolean
    blockers?: string[]
  }
  finding_counts?: Record<string, number>
  top_findings?: Array<Record<string, unknown>>
  disclaimer?: string
}

function parseMetricEvidence(metric: Record<string, unknown>): Record<string, unknown> {
  const raw = metric.evidence_json
  if (!raw) return {}
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw) as Record<string, unknown>
    } catch {
      return {}
    }
  }
  return raw as Record<string, unknown>
}

function formatMetricValue(metric: Record<string, unknown>): { value: string; basis?: string } {
  const code = String(metric.metric_code ?? '')
  const evidence = parseMetricEvidence(metric)
  const num = metric.numerator
  const denom = metric.denominator

  if (code === 'dcma_invalid_dates') {
    const total = evidence.total_findings ?? num ?? 0
    const basisLabel = evidence.primary_denominator_basis
      ? String(evidence.primary_denominator_basis).replaceAll('_', ' ')
      : 'date-check subcategories'
    return {
      value: `${total} findings`,
      basis: `basis: ${basisLabel}`,
    }
  }

  if (code === 'source_driving_path_integrity_proxy') {
    const violations = evidence.proxy_violation_count ?? evidence.driving_path_float_consistency_violation_count ?? num ?? 0
    const eligible = evidence.eligible_driving_path_activity_count ?? denom ?? '—'
    const exportCount = evidence.driving_path_activity_count ?? evidence.driving_path_count
    const eligibleBasis = evidence.eligible_denominator_basis
      ? String(evidence.eligible_denominator_basis).replaceAll('_', ' ')
      : 'driving path flag with explicit float'
    const basis =
      exportCount != null
        ? `${exportCount} XER driving-path flags · eligible basis: ${eligibleBasis} · not a DCMA critical path test`
        : `eligible basis: ${eligibleBasis} · not a DCMA critical path test`
    return {
      value: `${violations} violations / ${eligible} eligible`,
      basis,
    }
  }

  if (code === 'dcma_high_duration') {
    const ratio = num != null && denom != null ? `${num}/${denom}` : String(metric.value ?? '—')
    return { value: ratio, basis: 'normalized working days (hours→days for XER)' }
  }

  if (code === 'dcma_relationship_types') {
    const dist = evidence.distribution as Record<string, number> | undefined
    const fs = dist?.FS ?? num
    const total = denom
    if (dist && total != null) {
      const pct = ((Number(fs) / Number(total)) * 100).toFixed(1)
      const other = ['FF', 'SS', 'SF']
        .map((k) => (dist[k] ? `${k} ${dist[k]}` : null))
        .filter(Boolean)
        .join(' · ')
      return {
        value: `FS ${fs} / ${total} (${pct}%)`,
        basis: other || undefined,
      }
    }
  }

  if (num != null && denom != null) {
    return { value: `${num}/${denom}` }
  }
  return { value: String(metric.value ?? '—') }
}

function metricDisplayName(metric: Record<string, unknown>): string {
  const evidence = parseMetricEvidence(metric)
  const override = evidence.display_name_override
  if (typeof override === 'string' && override.trim()) {
    return override
  }
  return String(metric.metric_name ?? metric.metric_code ?? '—')
}

function statusClass(status: string | undefined): string {
  switch (status) {
    case 'completed':
    case 'passed_threshold':
      return 'text-emerald-600'
    case 'running':
    case 'pending':
    case 'warning_threshold':
      return 'text-amber-600'
    case 'failed':
    case 'failed_threshold':
      return 'text-red-600'
    case 'measured_from_derived_finish_float':
    case 'measured_from_explicit_source_float':
    case 'measured_from_xer_driving_path':
    case 'measured_from_source_export_proxy':
    case 'measured_from_msp_critical_flag':
    case 'partially_measurable_critical_float_available':
      return 'text-amber-600'
    case 'not_measurable_missing_data':
    case 'not_measurable_missing_longest_path_data':
    case 'not_measurable_requires_recalculation':
    case 'not_applicable':
      return 'text-[var(--hb-muted)]'
    default:
      return 'text-[var(--hb-muted)]'
  }
}

export function ScheduleQualityPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [projectKey, setProjectKey] = useScheduleProjectParam()
  const [versionKey, setVersionKey] = useState(searchParams.get('version') || '')
  const queryClient = useQueryClient()
  const canRerun = getLocalUiRole() === 'operator' || getLocalUiRole() === 'admin'
  const { data: projectsData } = useScheduleProjects()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['schedules', 'quality', versionKey],
    queryFn: () => api.getScheduleQuality(versionKey) as Promise<QualitySummary>,
    enabled: Boolean(versionKey),
  })

  const rerun = useMutation({
    mutationFn: () => api.rerunScheduleQuality(versionKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules', 'quality', versionKey] })
    },
  })

  const dcmaMetrics = (data?.metrics ?? []).filter((m) => m.metric_family === 'dcma')
  const supplementalMetrics = (data?.metrics ?? []).filter((m) => m.metric_family === 'supplemental')
  const gaoSummary = data?.gao_category_summary ?? {}

  function onProjectChange(next: string) {
    setProjectKey(next)
    setVersionKey('')
  }

  function onVersionChange(next: string) {
    setVersionKey(next)
    const params = new URLSearchParams(searchParams)
    if (next) {
      params.set('version', next)
      const inferred = next.split('|')[0]
      if (inferred) params.set('project', inferred)
    } else {
      params.delete('version')
    }
    setSearchParams(params, { replace: true })
  }

  return (
    <ScheduleShell>
      <ScheduleBackLink />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Schedule quality"
        subtitle="DCMA / GAO / AACE CPM assessment from committed canonical schedule data."
      />

      <p className="text-xs text-[var(--hb-muted)] mb-4 max-w-3xl border border-[var(--hb-border)] rounded p-3 bg-[var(--hb-surface)]">
        {data?.disclaimer ??
          'Schedule quality metrics are deterministic CPM data checks for operator review. This is not forensic delay analysis and does not determine entitlement, responsibility, liability, or compensability.'}
      </p>
      {data?.source_format ? (
        <div className="text-xs text-[var(--hb-muted)] mb-4 max-w-3xl border border-[var(--hb-border)] rounded p-3 bg-[var(--hb-surface)] space-y-1">
          <ScheduleProjectContext
            projectKey={data.project_key ?? projectKey}
            projects={projectsData?.projects}
          />
          <div>
            Source: {getScheduleFormatLabel(data.source_format)} ({data.source_format})
          </div>
          <div>
            {formatProjectCapabilityBanner(
              data.project_display_name ?? undefined,
              data.project_key ?? projectKey,
              data.source_format,
            )}
          </div>
          <div>{CPM_RECALCULATION_BANNER}</div>
        </div>
      ) : null}

      <div className="forecast-panel p-4 mb-3 max-w-3xl flex flex-wrap gap-3 items-end">
        <ScheduleProjectPicker value={projectKey} onChange={onProjectChange} className="min-w-[16rem]" />
        <ScheduleVersionPicker
          projectKey={projectKey}
          value={versionKey}
          onChange={onVersionChange}
        />
        {projectKey ? (
          <Link
            className="text-sm underline self-end pb-1"
            to={`/schedules/versions?project=${encodeURIComponent(projectKey)}`}
          >
            View project versions
          </Link>
        ) : null}
        {versionKey && canRerun ? (
          <button
            type="button"
            className="text-sm px-3 py-1.5 rounded border border-[var(--hb-border)]"
            disabled={rerun.isPending}
            onClick={() => rerun.mutate()}
          >
            {rerun.isPending ? 'Re-running…' : 'Rerun evaluation'}
          </button>
        ) : null}
      </div>

      {!versionKey ? (
        <EmptyState title="Select a schedule version" hint="Choose a version to review quality results." />
      ) : null}
      {isLoading ? <p className="text-sm text-[var(--hb-muted)]">Loading quality assessment…</p> : null}
      {error ? <EmptyState title="Could not load quality assessment" /> : null}

      {versionKey && data ? (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="forecast-panel p-3">
              <div className="text-xs text-[var(--hb-muted)]">Status</div>
              <div className={`text-lg font-medium ${statusClass(data.status)}`}>{data.status ?? '—'}</div>
              {data.completion_posture ? (
                <div className="text-xs text-[var(--hb-muted)] mt-1">{data.completion_posture}</div>
              ) : null}
            </div>
            <div className="forecast-panel p-3">
              <div className="text-xs text-[var(--hb-muted)]">Score / Grade</div>
              <div className="text-lg font-medium">
                {data.quality_score ?? '—'} / {data.quality_grade ?? '—'}
              </div>
            </div>
            <div className="forecast-panel p-3">
              <div className="text-xs text-[var(--hb-muted)]">Profile</div>
              <div className="text-sm font-medium">{data.assessment_profile ?? '—'}</div>
            </div>
            <div className="forecast-panel p-3">
              <div className="text-xs text-[var(--hb-muted)]">DCMA measured / not measurable</div>
              <div className="text-lg font-medium">
                {data.scorecard?.dcma_measured_count ?? 0} / {data.scorecard?.dcma_not_measurable_count ?? 0}
              </div>
            </div>
          </div>

          <section>
            <h2 className="text-sm font-semibold mb-2">DCMA 14-point metrics</h2>
            {dcmaMetrics.length === 0 ? (
              <EmptyState title="No DCMA metrics yet" hint="Evaluation may still be pending." />
            ) : (
              <ScheduleTable
                headers={
                  <>
                    <ScheduleTh>Metric</ScheduleTh>
                    <ScheduleTh>Value</ScheduleTh>
                    <ScheduleTh>Unit</ScheduleTh>
                    <ScheduleTh>Threshold</ScheduleTh>
                    <ScheduleTh>Status</ScheduleTh>
                    <ScheduleTh>Not measurable</ScheduleTh>
                  </>
                }
              >
                {dcmaMetrics.map((m) => {
                  const formatted = formatMetricValue(m)
                  return (
                  <tr key={String(m.metric_code)}>
                    <ScheduleTd>{metricDisplayName(m)}</ScheduleTd>
                    <ScheduleTd>
                      <div>{formatted.value}</div>
                      {formatted.basis ? (
                        <div className="text-xs text-[var(--hb-muted)] mt-0.5">{formatted.basis}</div>
                      ) : null}
                    </ScheduleTd>
                    <ScheduleTd>{String(m.unit ?? '—')}</ScheduleTd>
                    <ScheduleTd>
                      warn {String(m.threshold_warning ?? '—')} / fail {String(m.threshold_fail ?? '—')}
                    </ScheduleTd>
                    <ScheduleTd className={statusClass(String(m.status))}>{String(m.status)}</ScheduleTd>
                    <ScheduleTd>{String(m.not_measurable_reason ?? '—')}</ScheduleTd>
                  </tr>
                  )
                })}
              </ScheduleTable>
            )}
          </section>

          {supplementalMetrics.length > 0 ? (
            <section>
              <h2 className="text-sm font-semibold mb-1">Source-export supplemental checks</h2>
              <p className="text-xs text-[var(--hb-muted)] mb-2">
                Advisory source-export integrity checks. These are not DCMA 14-point metrics and do not
                substitute for CPM recalculation.
              </p>
              <ScheduleTable
                headers={
                  <>
                    <ScheduleTh>Check</ScheduleTh>
                    <ScheduleTh>Value</ScheduleTh>
                    <ScheduleTh>Unit</ScheduleTh>
                    <ScheduleTh>Status</ScheduleTh>
                  </>
                }
              >
                {supplementalMetrics.map((m) => {
                  const formatted = formatMetricValue(m)
                  return (
                    <tr key={String(m.metric_code)}>
                      <ScheduleTd>{metricDisplayName(m)}</ScheduleTd>
                      <ScheduleTd>
                        <div>{formatted.value}</div>
                        {formatted.basis ? (
                          <div className="text-xs text-[var(--hb-muted)] mt-0.5">{formatted.basis}</div>
                        ) : null}
                      </ScheduleTd>
                      <ScheduleTd>{String(m.unit ?? '—')}</ScheduleTd>
                      <ScheduleTd className={statusClass(String(m.status))}>{String(m.status)}</ScheduleTd>
                    </tr>
                  )
                })}
              </ScheduleTable>
            </section>
          ) : null}

          <section>
            <h2 className="text-sm font-semibold mb-2">GAO / AACE categories</h2>
            {Object.keys(gaoSummary).length === 0 ? (
              <p className="text-sm text-[var(--hb-muted)]">No category summary available.</p>
            ) : (
              <ScheduleTable
                headers={
                  <>
                    <ScheduleTh>Category</ScheduleTh>
                    <ScheduleTh>Posture</ScheduleTh>
                    <ScheduleTh>Notes</ScheduleTh>
                  </>
                }
              >
                {Object.entries(gaoSummary).map(([cat, info]) => (
                  <tr key={cat}>
                    <ScheduleTd>{cat.replaceAll('_', ' ')}</ScheduleTd>
                    <ScheduleTd className={statusClass(info.posture)}>{info.posture ?? '—'}</ScheduleTd>
                    <ScheduleTd>{info.reason ?? '—'}</ScheduleTd>
                  </tr>
                ))}
              </ScheduleTable>
            )}
          </section>

          <section className="forecast-panel p-4">
            <h2 className="text-sm font-semibold mb-2">Downstream readiness</h2>
            <ul className="text-sm space-y-1">
              <li>Completion posture: {data.downstream_readiness?.completion_posture ?? data.completion_posture ?? '—'}</li>
              <li>Cost mapping: {data.downstream_readiness?.cost_mapping ?? (data.downstream_readiness?.cost_mapping_ready ? 'ready' : 'not ready')}</li>
              <li>Cost weighting: {data.downstream_readiness?.cost_weighting ?? (data.downstream_readiness?.cost_weighting_ready ? 'ready' : 'blocked')}</li>
              <li>Critical path analytics: {data.downstream_readiness?.critical_path_analytics ?? '—'}</li>
              <li>Baseline analytics: {data.downstream_readiness?.baseline_analytics ?? '—'}</li>
              <li>True cost-loaded analytics: {data.downstream_readiness?.true_cost_loaded_analytics ?? '—'}</li>
              {(data.downstream_readiness?.blockers ?? []).map((b) => (
                <li key={b} className="text-[var(--hb-muted)]">
                  Blocker: {b}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-semibold mb-2">Top findings</h2>
            {(data.top_findings ?? []).length === 0 ? (
              <p className="text-sm text-[var(--hb-muted)]">No findings recorded.</p>
            ) : (
              <ScheduleTable
                headers={
                  <>
                    <ScheduleTh>Severity</ScheduleTh>
                    <ScheduleTh>Code</ScheduleTh>
                    <ScheduleTh>Summary</ScheduleTh>
                    <ScheduleTh>Activity</ScheduleTh>
                  </>
                }
              >
                {(data.top_findings ?? []).map((f, i) => (
                  <tr key={`${f.finding_code}-${i}`}>
                    <ScheduleTd>{String(f.severity)}</ScheduleTd>
                    <ScheduleTd>{String(f.finding_code)}</ScheduleTd>
                    <ScheduleTd>{String(f.finding_summary)}</ScheduleTd>
                    <ScheduleTd>{String(f.activity_id ?? '—')}</ScheduleTd>
                  </tr>
                ))}
              </ScheduleTable>
            )}
          </section>

          {data.status === 'pending' || data.status === 'running' ? (
            <button type="button" className="text-sm underline" onClick={() => refetch()}>
              Refresh status
            </button>
          ) : null}
        </div>
      ) : null}
    </ScheduleShell>
  )
}