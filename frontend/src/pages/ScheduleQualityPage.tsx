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
  source_critical_path_analytics?: Record<string, unknown> | null
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

function sourceCriticalBasisLabel(basis: string | undefined): string {
  switch (basis) {
    case 'xer_driving_path_flag':
      return 'XER driving path flag'
    case 'xer_total_float_threshold':
      return 'XER total float threshold'
    default:
      return basis?.replaceAll('_', ' ') ?? '—'
  }
}

function formatSourceCriticalAnalytics(
  analytics: Record<string, unknown>,
): { lines: string[]; caveat?: string } {
  const basis = String(analytics.source_critical_basis ?? '')
  const activityCount = Number(analytics.activity_count ?? analytics.source_critical_coverage_denominator ?? 0)
  const criticalCount = Number(analytics.source_critical_activity_count ?? 0)
  const drivingCount = Number(analytics.source_driving_path_count ?? 0)
  const explicitFloat = Number(analytics.explicit_float_activity_count ?? 0)
  const drivingWithFloat = Number(analytics.driving_path_with_explicit_float_count ?? 0)
  const lines = [
    `Basis: ${sourceCriticalBasisLabel(basis)}`,
    `Project critical path type: ${String(analytics.source_critical_path_type ?? '—')}`,
  ]
  if (basis === 'xer_driving_path_flag') {
    lines.push(`Driving path activities: ${drivingCount} / ${activityCount}`)
    lines.push(`Explicit float coverage: ${explicitFloat} / ${activityCount}`)
    lines.push(`Driving path activities with explicit float: ${drivingWithFloat}`)
  } else if (basis === 'xer_total_float_threshold') {
    const threshold = analytics.source_critical_float_threshold_hours ?? 0
    lines.push(
      `Critical activities by float <= ${threshold}h: ${criticalCount} / ${explicitFloat} explicit-float activities`,
    )
    lines.push(`Driving path flags: ${drivingCount} / ${activityCount}`)
    lines.push(`Driving path activities with explicit float: ${drivingWithFloat}`)
  } else {
    lines.push(`Source critical activities: ${criticalCount}`)
  }
  const caveat = analytics.caveat ? String(analytics.caveat) : undefined
  return { lines, caveat }
}

function formatMetricValue(metric: Record<string, unknown>): { value: string; basis?: string } {
  const code = String(metric.metric_code ?? '')
  const evidence = parseMetricEvidence(metric)
  const num = metric.numerator
  const denom = metric.denominator

  if (code === 'dcma_critical_path_test') {
    if (metric.status === 'not_measurable_requires_recalculation') {
      return { value: '—' }
    }
  }

  if (code === 'source_critical_path_available') {
    return {
      value: `${String(num ?? evidence.source_critical_activity_count ?? '—')} critical activities`,
    }
  }

  if (code === 'source_msp_critical_slack_available') {
    const consistent = num ?? evidence.consistent_critical_slack_count ?? 0
    const eligible = denom ?? evidence.eligible_evidence_activity_count ?? '—'
    const inconsistent = evidence.inconsistent_critical_slack_count ?? 0
    return {
      value: `${String(consistent)} consistent / ${String(eligible)} eligible`,
      basis: `${String(inconsistent)} inconsistencies · source-export only, not a DCMA critical path test`,
    }
  }

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
    case 'available_xer_driving_path':
    case 'available_xer_total_float_threshold':
    case 'partial_xer_float_coverage':
      return 'text-emerald-600'
    case 'missing_source_critical_data':
      return 'text-[var(--hb-muted)]'
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
  const sourceExportMetrics = (data?.metrics ?? []).filter(
    (m) => m.metric_family === 'source_export' || m.metric_code === 'source_critical_path_available',
  )
  const supplementalMetrics = (data?.metrics ?? []).filter((m) => m.metric_family === 'supplemental')
  const sourceAnalyticsEvidence =
    data?.source_critical_path_analytics ??
    (sourceExportMetrics[0] ? parseMetricEvidence(sourceExportMetrics[0]) : null)
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

          {sourceExportMetrics.length > 0 || sourceAnalyticsEvidence ? (
            <section>
              <h2 className="text-sm font-semibold mb-1">Source critical path analytics</h2>
              <p className="text-xs text-[var(--hb-muted)] mb-2">
                First-class source-export critical path data from the schedule file. This is not the DCMA
                critical path test and does not substitute for CPM recalculation.
              </p>
              {sourceAnalyticsEvidence ? (
                <div className="text-sm space-y-1 mb-3 rounded border border-[var(--hb-border)] p-3">
                  {formatSourceCriticalAnalytics(sourceAnalyticsEvidence).lines.map((line) => (
                    <p key={line}>{line}</p>
                  ))}
                  {formatSourceCriticalAnalytics(sourceAnalyticsEvidence).caveat ? (
                    <p className="text-xs text-amber-700 mt-2">
                      {formatSourceCriticalAnalytics(sourceAnalyticsEvidence).caveat}
                    </p>
                  ) : null}
                </div>
              ) : null}
              {sourceExportMetrics.length > 0 ? (
                <ScheduleTable
                  headers={
                    <>
                      <ScheduleTh>Metric</ScheduleTh>
                      <ScheduleTh>Value</ScheduleTh>
                      <ScheduleTh>Status</ScheduleTh>
                    </>
                  }
                >
                  {sourceExportMetrics.map((m) => {
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
                        <ScheduleTd className={statusClass(String(m.status))}>{String(m.status)}</ScheduleTd>
                      </tr>
                    )
                  })}
                </ScheduleTable>
              ) : null}
            </section>
          ) : null}

          {supplementalMetrics.length > 0 ? (
            <section>
              <h2 className="text-sm font-semibold mb-1">Source-export supplemental checks</h2>
              <p className="text-xs text-[var(--hb-muted)] mb-2">
                Advisory integrity checks on driving-path flags vs explicit float. These do not replace
                export critical path analytics or CPM recalculation.
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
