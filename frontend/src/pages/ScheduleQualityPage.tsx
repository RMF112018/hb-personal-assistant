import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

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
import { api, getLocalUiRole, type ScheduleHealthData, type ScheduleSourceCapability } from '../lib/api'
import {
  CPM_RECALCULATION_BANNER,
  formatProjectCapabilityBanner,
  getScheduleFormatLabel,
} from '../lib/scheduleCapabilityCopy'

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

function parseJsonObject(raw: unknown): Record<string, unknown> {
  if (!raw) return {}
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw) as unknown
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : {}
    } catch {
      return {}
    }
  }
  return raw && typeof raw === 'object' && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {}
}

function parseMetricEvidence(metric: Record<string, unknown>): Record<string, unknown> {
  return parseJsonObject(metric.evidence_json)
}

function text(value: unknown, fallback = '-'): string {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function numberText(value: unknown, fallback = '0'): string {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function labelize(value: unknown): string {
  return text(value).replaceAll('_', ' ')
}

function capabilityStatusLabel(status: unknown): string {
  switch (status) {
    case 'available':
      return 'Available'
    case 'partially_available':
      return 'Partially available'
    case 'unavailable':
      return 'Unavailable'
    case 'not_applicable':
      return 'Not applicable'
    case 'requires_companion_file':
      return 'Requires companion file'
    case 'requires_user_mapping':
      return 'Requires mapping/review'
    case 'conflict_detected':
      return 'Conflict detected'
    case 'deferred':
      return 'Deferred'
    default:
      return labelize(status)
  }
}

function statusClass(status: string | undefined): string {
  switch (status) {
    case 'completed':
    case 'passed_threshold':
    case 'available':
    case 'measured_from_accepted_crosswalk':
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
    case 'running':
    case 'pending':
    case 'warning_threshold':
    case 'partially_available':
    case 'requires_companion_file':
    case 'requires_user_mapping':
    case 'requires_crosswalk_review':
      return 'text-amber-600'
    case 'failed':
    case 'failed_threshold':
    case 'conflict_detected':
      return 'text-red-600'
    default:
      return 'text-[var(--hb-muted)]'
  }
}

function sourceCriticalBasisLabel(basis: string | undefined): string {
  switch (basis) {
    case 'xer_driving_path_flag':
      return 'XER driving path flag'
    case 'xer_total_float_threshold':
      return 'XER total float threshold'
    default:
      return basis?.replaceAll('_', ' ') ?? '-'
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
    `Project critical path type: ${text(analytics.source_critical_path_type)}`,
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

  if (code === 'dcma_critical_path_test' && metric.status === 'not_measurable_requires_recalculation') {
    return { value: '-' }
  }

  if (code === 'source_critical_path_available') {
    return { value: `${text(num ?? evidence.source_critical_activity_count)} critical activities` }
  }

  if (code === 'source_msp_critical_slack_available') {
    const consistent = num ?? evidence.consistent_critical_slack_count ?? 0
    const eligible = denom ?? evidence.eligible_evidence_activity_count ?? '-'
    const inconsistent = evidence.inconsistent_critical_slack_count ?? 0
    return {
      value: `${String(consistent)} consistent / ${String(eligible)} eligible`,
      basis: `${String(inconsistent)} inconsistencies | source-export only, not a DCMA critical path test`,
    }
  }

  if (code === 'dcma_invalid_dates') {
    const total = evidence.total_findings ?? num ?? 0
    const basisLabel = evidence.primary_denominator_basis
      ? String(evidence.primary_denominator_basis).replaceAll('_', ' ')
      : 'date-check subcategories'
    return { value: `${total} findings`, basis: `basis: ${basisLabel}` }
  }

  if (code === 'source_driving_path_integrity_proxy') {
    const violations = evidence.proxy_violation_count ?? evidence.driving_path_float_consistency_violation_count ?? num ?? 0
    const eligible = evidence.eligible_driving_path_activity_count ?? denom ?? '-'
    const exportCount = evidence.driving_path_activity_count ?? evidence.driving_path_count
    const eligibleBasis = evidence.eligible_denominator_basis
      ? String(evidence.eligible_denominator_basis).replaceAll('_', ' ')
      : 'driving path flag with explicit float'
    const basis =
      exportCount != null
        ? `${exportCount} XER driving-path flags | eligible basis: ${eligibleBasis} | not a DCMA critical path test`
        : `eligible basis: ${eligibleBasis} | not a DCMA critical path test`
    return { value: `${violations} violations / ${eligible} eligible`, basis }
  }

  if (code === 'dcma_high_duration') {
    const ratio = num != null && denom != null ? `${num}/${denom}` : text(metric.value)
    return { value: ratio, basis: 'normalized working days (hours to days for XER)' }
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
        .join(' | ')
      return { value: `FS ${fs} / ${total} (${pct}%)`, basis: other || undefined }
    }
  }

  if (num != null && denom != null) return { value: `${num}/${denom}` }
  return { value: text(metric.value) }
}

function metricDisplayName(metric: Record<string, unknown>): string {
  const evidence = parseMetricEvidence(metric)
  const override = evidence.display_name_override
  if (typeof override === 'string' && override.trim()) return override
  return text(metric.metric_name ?? metric.metric_code)
}

function scorecardFromHealth(health?: ScheduleHealthData): Record<string, unknown> {
  return parseJsonObject(health?.quality_summary?.scorecard)
}

function parsedScorecardObject(scorecard: Record<string, unknown>, key: string): Record<string, unknown> {
  return parseJsonObject(scorecard[key])
}

function capabilityByKey(capabilities: ScheduleSourceCapability[], key: string): ScheduleSourceCapability | undefined {
  return capabilities.find((cap) => cap.capability_key === key)
}

function capabilityStatus(capabilities: ScheduleSourceCapability[], key: string): string {
  return String(capabilityByKey(capabilities, key)?.capability_status ?? 'unavailable')
}

function capabilitiesForGroup(capabilities: ScheduleSourceCapability[], keys: string[]): ScheduleSourceCapability[] {
  return capabilities.filter((cap) => keys.includes(String(cap.capability_key ?? '')))
}

function factValue(facts: Record<string, unknown>[], key: string): string {
  const fact = facts.find((item) => item.metric_key === key)
  return text(fact?.metric_value)
}

function diffValue(diffFacts: Record<string, unknown>[], key: string): string {
  const fact = diffFacts.find((item) => item.metric_key === key || item.fact_key === key)
  return text(fact?.metric_value ?? fact?.value)
}

function HealthCard({
  title,
  value,
  detail,
  status,
}: {
  title: string
  value: string
  detail?: string
  status?: string
}) {
  return (
    <div className="forecast-panel p-3 min-h-[7rem]">
      <div className="text-xs text-[var(--hb-muted)]">{title}</div>
      <div className={`text-lg font-medium mt-1 ${statusClass(status)}`}>{value}</div>
      {detail ? <div className="text-xs text-[var(--hb-muted)] mt-2 leading-relaxed">{detail}</div> : null}
    </div>
  )
}

function CapabilityList({ title, capabilities }: { title: string; capabilities: ScheduleSourceCapability[] }) {
  return (
    <div className="rounded border border-[var(--hb-border)] p-3">
      <h3 className="text-sm font-semibold mb-2">{title}</h3>
      {capabilities.length === 0 ? (
        <p className="text-sm text-[var(--hb-muted)]">No reported capabilities.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {capabilities.map((cap) => (
            <li key={String(cap.capability_id ?? cap.capability_key)} className="flex items-start justify-between gap-3">
              <span>{labelize(cap.capability_key)}</span>
              <span className={`text-xs font-medium ${statusClass(String(cap.capability_status))}`}>
                {capabilityStatusLabel(cap.capability_status)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function ScheduleQualityPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [projectKey, setProjectKey] = useScheduleProjectParam()
  const [versionKey, setVersionKey] = useState(searchParams.get('version') || '')
  const [compareKey, setCompareKey] = useState(searchParams.get('compare') || 'default_prior')
  const queryClient = useQueryClient()
  const canRerun = getLocalUiRole() === 'operator' || getLocalUiRole() === 'admin'
  const { data: projectsData } = useScheduleProjects()

  const { data: health, isLoading, error, refetch } = useQuery({
    queryKey: ['schedules', 'health-data', versionKey, projectKey || '__unscoped__'],
    queryFn: () => api.getScheduleHealthData(versionKey, projectKey || undefined),
    enabled: Boolean(versionKey),
  })

  const { data: qualityDetail } = useQuery({
    queryKey: ['schedules', 'quality-detail', versionKey],
    queryFn: () => api.getScheduleQuality(versionKey) as Promise<QualitySummary>,
    enabled: Boolean(versionKey && health),
  })

  const rerun = useMutation({
    mutationFn: () => api.rerunScheduleQuality(versionKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules', 'health-data', versionKey] })
      queryClient.invalidateQueries({ queryKey: ['schedules', 'quality-detail', versionKey] })
    },
  })

  const currentSchedule = health?.current_schedule ?? {}
  const importPackage = health?.import_package ?? {}
  const capabilities = health?.capabilities ?? []
  const baselineProjects = health?.baseline_projects ?? []
  const baselineFacts = health?.baseline_health_facts ?? []
  const diffFacts = health?.default_version_diff ?? []
  const availableDiffs = health?.available_version_diffs ?? []
  const comparisonBasis =
    health?.comparison_basis && typeof health.comparison_basis === 'object'
      ? (health.comparison_basis as Record<string, unknown>)
      : {}
  const impactSummary =
    comparisonBasis.impact_summary && typeof comparisonBasis.impact_summary === 'object'
      ? (comparisonBasis.impact_summary as Record<string, unknown>)
      : {}
  const comparisonIdentitySafe = comparisonBasis.identity_safe === true
  const comparisonRequiresReview = comparisonBasis.identity_requires_review === true
  const topFindings = useMemo(
    () => health?.top_health_findings ?? qualityDetail?.top_findings ?? [],
    [health?.top_health_findings, qualityDetail?.top_findings],
  )
  const scorecard = scorecardFromHealth(health)
  const downstream = {
    ...parsedScorecardObject(scorecard, 'downstream_readiness_json'),
    ...(qualityDetail?.downstream_readiness ?? {}),
  }
  const gaoSummary =
    qualityDetail?.gao_category_summary ?? (parsedScorecardObject(scorecard, 'gao_category_summary_json') as Record<string, { posture?: string; reason?: string | null }>)
  const findingCounts = {
    ...parsedScorecardObject(scorecard, 'finding_counts_json'),
    ...(qualityDetail?.finding_counts ?? {}),
  }

  const dcmaMetrics = (qualityDetail?.metrics ?? []).filter((m) => m.metric_family === 'dcma')
  const sourceExportMetrics = (qualityDetail?.metrics ?? []).filter(
    (m) => m.metric_family === 'source_export' || m.metric_code === 'source_critical_path_available',
  )
  const supplementalMetrics = (qualityDetail?.metrics ?? []).filter((m) => m.metric_family === 'supplemental')
  const sourceAnalyticsEvidence =
    qualityDetail?.source_critical_path_analytics ??
    (sourceExportMetrics[0] ? parseMetricEvidence(sourceExportMetrics[0]) : null)

  const hasHealthFoundation = Boolean(
    health && ((health.capabilities?.length ?? 0) > 0 || Object.keys(importPackage).length > 0 || baselineProjects.length > 0 || diffFacts.length > 0),
  )
  const baselineReferenceOnly = capabilityStatus(capabilities, 'baseline_activity_rows') === 'requires_companion_file'
  const baselineAvailable = baselineProjects.length > 0 || baselineFacts.length > 0
  const cpmStatus = capabilityStatus(capabilities, 'cpm_recalculation')
  const packageMode = text(importPackage.package_mode ?? currentSchedule.source_type, 'single_file')
  const sourceFormat = text(currentSchedule.source_format ?? qualityDetail?.source_format)
  const score = text(scorecard.quality_score ?? qualityDetail?.quality_score)
  const grade = text(scorecard.quality_grade ?? qualityDetail?.quality_grade)
  const qualityStatus = text(health?.quality_summary?.status ?? qualityDetail?.status, 'not evaluated')
  const criticalPathDetail =
    cpmStatus === 'deferred'
      ? 'CPM recalculation is deferred; current evidence is source-export or proxy evidence.'
      : `Source critical path status: ${capabilityStatusLabel(capabilityStatus(capabilities, 'source_critical_path'))}`
  const comparisonDetail = comparisonIdentitySafe
    ? `Identity-safe prior: ${text(comparisonBasis.default_prior_schedule_version_key)}`
    : comparisonRequiresReview
      ? 'Default comparison is blocked until schedule identity review is resolved.'
      : `Default comparison unavailable: ${text(comparisonBasis.default_prior_unavailable_reason, 'no prior identity version')}`
  const topActionText = useMemo(() => {
    const severe = topFindings.find((finding) => finding.severity === 'critical' || finding.severity === 'warning')
    if (severe) return text(severe.recommended_action ?? severe.finding_summary ?? severe.message)
    if (baselineReferenceOnly) return 'Upload P6 XML with baselines included to calculate baseline drift and BEI.'
    if (!hasHealthFoundation && health) return 'Re-import using the package-aware workflow to populate health evidence.'
    return 'Review detailed findings and capability gaps below.'
  }, [baselineReferenceOnly, hasHealthFoundation, health, topFindings])

  function onProjectChange(next: string) {
    setProjectKey(next)
    setVersionKey('')
    setCompareKey('default_prior')
    const params = new URLSearchParams(searchParams)
    if (next) params.set('project', next)
    else params.delete('project')
    params.delete('version')
    params.delete('compare')
    setSearchParams(params, { replace: true })
  }

  function onVersionChange(next: string) {
    setVersionKey(next)
    setCompareKey('default_prior')
    const params = new URLSearchParams(searchParams)
    if (next) {
      params.set('version', next)
      const inferred = next.split('|')[0]
      if (inferred) params.set('project', inferred)
    } else {
      params.delete('version')
    }
    params.delete('compare')
    setSearchParams(params, { replace: true })
  }

  function onCompareChange(next: string) {
    setCompareKey(next)
    const params = new URLSearchParams(searchParams)
    if (next && next !== 'default_prior') params.set('compare', next)
    else params.delete('compare')
    setSearchParams(params, { replace: true })
  }

  return (
    <ScheduleShell>
      <ScheduleBackLink />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Schedule Health"
        subtitle="PM-first schedule reliability, baseline drift, version-change, and CPM-quality assessment."
      />

      <div className="forecast-panel p-4 mb-3 max-w-5xl flex flex-wrap gap-3 items-end">
        <ScheduleProjectPicker value={projectKey} onChange={onProjectChange} className="min-w-[16rem]" />
        <ScheduleVersionPicker projectKey={projectKey} value={versionKey} onChange={onVersionChange} />
        <label className="block text-sm min-w-[14rem]">
          <span className="text-[var(--hb-muted)]">Compare against</span>
          <select
            className="mt-1 block w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5 text-sm"
            value={compareKey}
            disabled={!versionKey || availableDiffs.length === 0}
            onChange={(event) => onCompareChange(event.target.value)}
          >
            <option value="default_prior">Default prior version</option>
            {availableDiffs.map((diff, index) => (
              <option key={String(diff.diff_id ?? diff.fact_id ?? index)} value={String(diff.diff_id ?? index)}>
                {text(diff.from_schedule_version_key ?? diff.from_version_key ?? `Available diff ${index + 1}`)}
              </option>
            ))}
          </select>
        </label>
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
            {rerun.isPending ? 'Re-running...' : 'Rerun evaluation'}
          </button>
        ) : null}
      </div>

      {!versionKey ? (
        <EmptyState title="Select a schedule version" hint="Choose a version to review schedule health." />
      ) : null}
      {isLoading ? <p className="text-sm text-[var(--hb-muted)]">Loading schedule health...</p> : null}
      {error ? <EmptyState title="Could not load schedule health" /> : null}

      {versionKey && health ? (
        <div className="space-y-6">
          <div className="text-xs text-[var(--hb-muted)] max-w-5xl border border-[var(--hb-border)] rounded p-3 bg-[var(--hb-surface)] space-y-1">
            <ScheduleProjectContext projectKey={String(health.project_key ?? projectKey)} projects={projectsData?.projects} />
            <div>
              Version: {text(currentSchedule.display_label ?? currentSchedule.schedule_version_key ?? health.schedule_version_key)}
            </div>
            <div>
              Data date: {text(currentSchedule.data_date)} | Imported: {text(currentSchedule.imported_at)} | Source:{' '}
              {getScheduleFormatLabel(sourceFormat)} ({sourceFormat}) | Package: {packageMode}
            </div>
            <div>
              Activities: {numberText(currentSchedule.activity_count)} | Relationships:{' '}
              {numberText(currentSchedule.relationship_count)} | Baselines: {baselineProjects.length} | Quality status:{' '}
              {qualityStatus}
            </div>
            <div>{formatProjectCapabilityBanner(undefined, String(health.project_key ?? projectKey), sourceFormat)}</div>
            <div>{CPM_RECALCULATION_BANNER}</div>
          </div>

          {!hasHealthFoundation ? (
            <div className="forecast-panel p-4 text-sm text-[var(--hb-muted)]">
              Limited health data available for this older schedule import. Re-import using the package-aware workflow to
              populate baseline, capability, and comparison evidence.
            </div>
          ) : null}

          <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            <HealthCard
              title="Schedule health"
              value={`${score} / ${grade}`}
              detail={`Evaluation ${qualityStatus}. DCMA measured ${numberText(scorecard.dcma_measured_count ?? qualityDetail?.scorecard?.dcma_measured_count)} of ${Number(scorecard.dcma_measured_count ?? qualityDetail?.scorecard?.dcma_measured_count ?? 0) + Number(scorecard.dcma_not_measurable_count ?? qualityDetail?.scorecard?.dcma_not_measurable_count ?? 0)} checks.`}
              status={qualityStatus}
            />
            <HealthCard
              title="Update reliability"
              value={labelize(downstream.completion_posture ?? qualityDetail?.completion_posture ?? 'not enough data')}
              detail={`Warnings: ${numberText(findingCounts.warning)} | Critical: ${numberText(findingCounts.critical)}`}
              status={String(downstream.completion_posture ?? qualityStatus)}
            />
            <HealthCard
              title="Finish movement vs prior"
              value={comparisonIdentitySafe ? 'Identity-safe' : 'Not available'}
              detail={
                diffFacts.length > 0
                  ? `Changed activities: ${diffValue(diffFacts, 'activity_changed_count')} | Logic churn: ${diffValue(diffFacts, 'logic_churn_rate')}`
                  : comparisonDetail
              }
              status={comparisonIdentitySafe ? 'available' : 'unavailable'}
            />
            <HealthCard
              title="Impact vs prior"
              value={impactSummary.impact_level ? labelize(String(impactSummary.impact_level)) : 'Not available'}
              detail={
                impactSummary.impact_level
                  ? `Attention: ${numberText(impactSummary.requires_attention_count)} | Top WBS: ${text(impactSummary.top_wbs_code ?? impactSummary.top_wbs_name, 'not classified')}`
                  : comparisonDetail
              }
              status={impactSummary.impact_level ? 'available' : 'unavailable'}
            />
            <HealthCard
              title="Baseline drift"
              value={baselineAvailable ? 'Available' : baselineReferenceOnly ? 'Requires companion file' : 'Not enough data'}
              detail={
                baselineReferenceOnly
                  ? 'Baseline reference detected, but baseline activities were not included in the uploaded files.'
                  : `Baseline projects: ${baselineProjects.length} | Drift: ${factValue(baselineFacts, 'baseline_drift_status')}`
              }
              status={baselineAvailable ? 'available' : baselineReferenceOnly ? 'requires_companion_file' : 'unavailable'}
            />
            <HealthCard
              title="Critical path confidence"
              value={capabilityStatusLabel(capabilityStatus(capabilities, 'source_critical_path'))}
              detail={criticalPathDetail}
              status={capabilityStatus(capabilities, 'source_critical_path')}
            />
            <HealthCard title="Top PM action" value="Review" detail={topActionText} status="partially_available" />
          </section>

          <section className="forecast-panel p-4">
            <h2 className="text-sm font-semibold mb-3">Available Schedule Evidence</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              <CapabilityList
                title="Current Schedule"
                capabilities={capabilitiesForGroup(capabilities, ['current_activity_rows', 'current_relationship_rows', 'activity_codes', 'wbs_rows'])}
              />
              <CapabilityList
                title="Baseline"
                capabilities={capabilitiesForGroup(capabilities, ['baseline_project_rows', 'baseline_activity_rows', 'baseline_relationship_rows', 'baseline_activity_crosswalk', 'baseline_drift', 'bei'])}
              />
              <CapabilityList
                title="Version Comparison"
                capabilities={capabilitiesForGroup(capabilities, ['default_version_diff', 'version_diff_facts'])}
              />
              <CapabilityList
                title="Critical Path / Float"
                capabilities={capabilitiesForGroup(capabilities, ['explicit_total_float', 'explicit_free_float', 'source_critical_path', 'source_driving_path', 'cpm_recalculation'])}
              />
              <CapabilityList
                title="Cost / Resource"
                capabilities={capabilitiesForGroup(capabilities, ['resource_assignments', 'cost_loading', 'cost_schedule_correlation'])}
              />
              <CapabilityList
                title="Deferred"
                capabilities={capabilities.filter((cap) => cap.capability_status === 'deferred')}
              />
            </div>
          </section>

          <section className="forecast-panel p-4">
            <h2 className="text-sm font-semibold mb-2">What Changed Since the Prior Schedule?</h2>
            <div className="mb-3 rounded border border-[var(--hb-border)] p-3 text-sm">
              <div className="font-medium">
                {comparisonIdentitySafe ? 'Identity-safe comparison' : 'Default comparison unavailable'}
              </div>
              <div className="text-xs text-[var(--hb-muted)] mt-1">
                Current identity: {text(comparisonBasis.current_schedule_identity_key)} · Prior identity:{' '}
                {text(comparisonBasis.default_prior_schedule_identity_key)} · Reason:{' '}
                {text(comparisonBasis.default_prior_selection_reason ?? comparisonBasis.default_prior_unavailable_reason)}
              </div>
              {comparisonIdentitySafe && comparisonBasis.detailed_diff_id ? (
                <Link
                  className="inline-flex text-sm underline mt-2"
                  to={`/schedules/version-diff?project=${encodeURIComponent(String(health.project_key ?? projectKey))}&diff_id=${encodeURIComponent(String(comparisonBasis.detailed_diff_id))}`}
                >
                  View detailed diff
                </Link>
              ) : null}
            </div>
            {diffFacts.length === 0 ? (
              <p className="text-sm text-[var(--hb-muted)]">
                No persisted prior-version diff is available. A schedule version only participates in default comparison
                when identity review is resolved and a prior committed version shares the same schedule identity.
              </p>
            ) : (
              <ScheduleTable
                headers={
                  <>
                    <ScheduleTh>Metric</ScheduleTh>
                    <ScheduleTh>Value</ScheduleTh>
                    <ScheduleTh>Status</ScheduleTh>
                    <ScheduleTh>Basis</ScheduleTh>
                  </>
                }
              >
                {diffFacts.slice(0, 12).map((fact, index) => (
                  <tr key={String(fact.fact_id ?? fact.metric_key ?? index)}>
                    <ScheduleTd>{labelize(fact.metric_key ?? fact.fact_key)}</ScheduleTd>
                    <ScheduleTd>{text(fact.metric_value ?? fact.value)}</ScheduleTd>
                    <ScheduleTd className={statusClass(String(fact.status))}>{capabilityStatusLabel(fact.status)}</ScheduleTd>
                    <ScheduleTd>{labelize(fact.basis)}</ScheduleTd>
                  </tr>
                ))}
              </ScheduleTable>
            )}
          </section>

          <section className="forecast-panel p-4">
            <h2 className="text-sm font-semibold mb-2">Baseline Health</h2>
            {!baselineAvailable ? (
              <p className="text-sm text-[var(--hb-muted)]">
                {baselineReferenceOnly
                  ? 'Baseline reference detected, but baseline activities were not included in the uploaded files. Upload P6 XML with baselines included to calculate baseline drift and BEI.'
                  : 'No baseline was available in this import package.'}
              </p>
            ) : (
              <div className="space-y-4">
                {baselineProjects.map((baseline) => {
                  const facts = baselineFacts.filter(
                    (fact) => fact.baseline_project_key === baseline.baseline_project_key,
                  )
                  return (
                    <div key={String(baseline.baseline_project_key)} className="rounded border border-[var(--hb-border)] p-3">
                      <h3 className="text-sm font-semibold">{text(baseline.baseline_project_name)}</h3>
                      <p className="text-xs text-[var(--hb-muted)] mb-2">
                        Type: {text(baseline.baseline_type_name)} | Data date: {text(baseline.baseline_data_date)} |
                        Activities: {numberText(baseline.activity_count)} | Relationships:{' '}
                        {numberText(baseline.relationship_count)}
                      </p>
                      <p className="text-xs text-[var(--hb-muted)] mb-2">
                        Baseline comparison uses activity crosswalk matching. Review required for lower-confidence
                        matches.
                      </p>
                      <ScheduleTable
                        headers={
                          <>
                            <ScheduleTh>Fact</ScheduleTh>
                            <ScheduleTh>Value</ScheduleTh>
                            <ScheduleTh>Status</ScheduleTh>
                          </>
                        }
                      >
                        {facts.slice(0, 10).map((fact) => (
                          <tr key={String(fact.fact_id ?? fact.metric_key)}>
                            <ScheduleTd>{labelize(fact.metric_key)}</ScheduleTd>
                            <ScheduleTd>{text(fact.metric_value)}</ScheduleTd>
                            <ScheduleTd className={statusClass(String(fact.status))}>
                              {capabilityStatusLabel(fact.status)}
                            </ScheduleTd>
                          </tr>
                        ))}
                      </ScheduleTable>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          <section className="forecast-panel p-4">
            <h2 className="text-sm font-semibold mb-1">Critical Path and Float Evidence</h2>
            <p className="text-xs text-[var(--hb-muted)] mb-3">
              This section reports source critical path evidence. It does not say calculated critical path unless backend
              evidence reports CPM recalculation.
            </p>
            {sourceAnalyticsEvidence ? (
              <div className="text-sm space-y-1 mb-3 rounded border border-[var(--hb-border)] p-3">
                {formatSourceCriticalAnalytics(sourceAnalyticsEvidence).lines.map((line) => (
                  <p key={line}>{line}</p>
                ))}
                {formatSourceCriticalAnalytics(sourceAnalyticsEvidence).caveat ? (
                  <p className="text-xs text-amber-700 mt-2">{formatSourceCriticalAnalytics(sourceAnalyticsEvidence).caveat}</p>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-[var(--hb-muted)] mb-3">No detailed source critical path metrics are available.</p>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              {['explicit_total_float', 'explicit_free_float', 'source_critical_path', 'source_driving_path'].map((key) => (
                <div key={key} className="rounded border border-[var(--hb-border)] p-3">
                  <div className="text-xs text-[var(--hb-muted)]">{labelize(key)}</div>
                  <div className={statusClass(capabilityStatus(capabilities, key))}>
                    {capabilityStatusLabel(capabilityStatus(capabilities, key))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold mb-2">DCMA 14-Point Assessment</h2>
            {dcmaMetrics.length === 0 ? (
              <EmptyState title="No DCMA metrics yet" hint="Evaluation may still be pending or this older import has limited detail." />
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
                {dcmaMetrics.map((metric) => {
                  const formatted = formatMetricValue(metric)
                  return (
                    <tr key={String(metric.metric_code)}>
                      <ScheduleTd>{metricDisplayName(metric)}</ScheduleTd>
                      <ScheduleTd>
                        <div>{formatted.value}</div>
                        {formatted.basis ? <div className="text-xs text-[var(--hb-muted)] mt-0.5">{formatted.basis}</div> : null}
                      </ScheduleTd>
                      <ScheduleTd>{text(metric.unit)}</ScheduleTd>
                      <ScheduleTd>
                        warn {text(metric.threshold_warning)} / fail {text(metric.threshold_fail)}
                      </ScheduleTd>
                      <ScheduleTd className={statusClass(String(metric.status))}>{text(metric.status)}</ScheduleTd>
                      <ScheduleTd>{text(metric.not_measurable_reason)}</ScheduleTd>
                    </tr>
                  )
                })}
              </ScheduleTable>
            )}
          </section>

          {sourceExportMetrics.length > 0 || supplementalMetrics.length > 0 ? (
            <section>
              <h2 className="text-sm font-semibold mb-2">Supplemental Source Checks</h2>
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
                {[...sourceExportMetrics, ...supplementalMetrics].map((metric) => {
                  const formatted = formatMetricValue(metric)
                  return (
                    <tr key={String(metric.metric_code)}>
                      <ScheduleTd>{metricDisplayName(metric)}</ScheduleTd>
                      <ScheduleTd>
                        <div>{formatted.value}</div>
                        {formatted.basis ? <div className="text-xs text-[var(--hb-muted)] mt-0.5">{formatted.basis}</div> : null}
                      </ScheduleTd>
                      <ScheduleTd>{text(metric.unit)}</ScheduleTd>
                      <ScheduleTd className={statusClass(String(metric.status))}>{text(metric.status)}</ScheduleTd>
                    </tr>
                  )
                })}
              </ScheduleTable>
            </section>
          ) : null}

          <section>
            <h2 className="text-sm font-semibold mb-2">GAO / AACE Categories</h2>
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
                    <ScheduleTd>{labelize(cat)}</ScheduleTd>
                    <ScheduleTd className={statusClass(info.posture)}>{text(info.posture)}</ScheduleTd>
                    <ScheduleTd>{text(info.reason)}</ScheduleTd>
                  </tr>
                ))}
              </ScheduleTable>
            )}
          </section>

          <section>
            <h2 className="text-sm font-semibold mb-2">Findings</h2>
            {topFindings.length === 0 ? (
              <p className="text-sm text-[var(--hb-muted)]">No findings recorded.</p>
            ) : (
              <ScheduleTable
                headers={
                  <>
                    <ScheduleTh>Severity</ScheduleTh>
                    <ScheduleTh>Code</ScheduleTh>
                    <ScheduleTh>Category</ScheduleTh>
                    <ScheduleTh>Message</ScheduleTh>
                    <ScheduleTh>Activity</ScheduleTh>
                  </>
                }
              >
                {topFindings.map((finding, index) => (
                  <tr key={`${String(finding.finding_code ?? finding.code)}-${index}`}>
                    <ScheduleTd>{text(finding.severity)}</ScheduleTd>
                    <ScheduleTd>{text(finding.finding_code ?? finding.code)}</ScheduleTd>
                    <ScheduleTd>{labelize(finding.category)}</ScheduleTd>
                    <ScheduleTd>{text(finding.recommended_action ?? finding.finding_summary ?? finding.message)}</ScheduleTd>
                    <ScheduleTd>{text(finding.activity_id ?? finding.activity_name)}</ScheduleTd>
                  </tr>
                ))}
              </ScheduleTable>
            )}
          </section>

          <section className="forecast-panel p-4">
            <h2 className="text-sm font-semibold mb-2">Unavailable / Deferred Analysis</h2>
            <ul className="text-sm space-y-1">
              <li>Cost/schedule correlation: {capabilityStatusLabel(health.deferred_domains?.cost_schedule_correlation ?? capabilityStatus(capabilities, 'cost_schedule_correlation'))}</li>
              <li>Resource assignments: {capabilityStatusLabel(capabilityStatus(capabilities, 'resource_assignments'))}</li>
              <li>Cost loading: {capabilityStatusLabel(capabilityStatus(capabilities, 'cost_loading'))}</li>
              <li>CPM recalculation: {capabilityStatusLabel(cpmStatus)}</li>
              <li>Baseline metrics: {baselineAvailable ? 'Available' : baselineReferenceOnly ? 'Requires companion file' : 'Not enough data'}</li>
            </ul>
          </section>

          {qualityStatus === 'pending' || qualityStatus === 'running' ? (
            <button type="button" className="text-sm underline" onClick={() => refetch()}>
              Refresh status
            </button>
          ) : null}
        </div>
      ) : null}
    </ScheduleShell>
  )
}
