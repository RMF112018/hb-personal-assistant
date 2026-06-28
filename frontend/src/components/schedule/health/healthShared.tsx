// Shared helpers, derived-model builder, and small card primitives for the Schedule Health
// cockpit (Phase 9A.2). Extracted verbatim from ScheduleQualityPage so the per-section panels stay
// thin and behavior is identical. Pure read-only formatting — no data fetching, no mutation.

import type { ScheduleHealthData, ScheduleSourceCapability } from '../../../lib/api'

export type QualitySummary = {
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

export function parseJsonObject(raw: unknown): Record<string, unknown> {
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

export function parseMetricEvidence(metric: Record<string, unknown>): Record<string, unknown> {
  return parseJsonObject(metric.evidence_json)
}

export function text(value: unknown, fallback = '-'): string {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

export function numberText(value: unknown, fallback = '0'): string {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

export function labelize(value: unknown): string {
  return text(value).replaceAll('_', ' ')
}

export function capabilityStatusLabel(status: unknown): string {
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

export function statusClass(status: string | undefined): string {
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

export function sourceCriticalBasisLabel(basis: string | undefined): string {
  switch (basis) {
    case 'xer_driving_path_flag':
      return 'XER driving path flag'
    case 'xer_total_float_threshold':
      return 'XER total float threshold'
    default:
      return basis?.replaceAll('_', ' ') ?? '-'
  }
}

export function formatSourceCriticalAnalytics(
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

export function formatMetricValue(metric: Record<string, unknown>): { value: string; basis?: string } {
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

export function metricDisplayName(metric: Record<string, unknown>): string {
  const evidence = parseMetricEvidence(metric)
  const override = evidence.display_name_override
  if (typeof override === 'string' && override.trim()) return override
  return text(metric.metric_name ?? metric.metric_code)
}

export function scorecardFromHealth(health?: ScheduleHealthData): Record<string, unknown> {
  return parseJsonObject(health?.quality_summary?.scorecard)
}

export function parsedScorecardObject(scorecard: Record<string, unknown>, key: string): Record<string, unknown> {
  return parseJsonObject(scorecard[key])
}

export function capabilityByKey(capabilities: ScheduleSourceCapability[], key: string): ScheduleSourceCapability | undefined {
  return capabilities.find((cap) => cap.capability_key === key)
}

export function capabilityStatus(capabilities: ScheduleSourceCapability[], key: string): string {
  return String(capabilityByKey(capabilities, key)?.capability_status ?? 'unavailable')
}

export function capabilitiesForGroup(capabilities: ScheduleSourceCapability[], keys: string[]): ScheduleSourceCapability[] {
  return capabilities.filter((cap) => keys.includes(String(cap.capability_key ?? '')))
}

export function factValue(facts: Record<string, unknown>[], key: string): string {
  const fact = facts.find((item) => item.metric_key === key)
  return text(fact?.metric_value)
}

export function diffValue(diffFacts: Record<string, unknown>[], key: string): string {
  const fact = diffFacts.find((item) => item.metric_key === key || item.fact_key === key)
  return text(fact?.metric_value ?? fact?.value)
}

// ---------------------------------------------------------------- derived model

export type HealthModel = {
  currentSchedule: Record<string, unknown>
  importPackage: Record<string, unknown>
  capabilities: ScheduleSourceCapability[]
  baselineProjects: Record<string, unknown>[]
  baselineFacts: Record<string, unknown>[]
  diffFacts: Record<string, unknown>[]
  availableDiffs: Record<string, unknown>[]
  comparisonBasis: Record<string, unknown>
  impactSummary: Record<string, unknown>
  comparisonIdentitySafe: boolean
  comparisonRequiresReview: boolean
  topFindings: Record<string, unknown>[]
  scorecard: Record<string, unknown>
  downstream: Record<string, unknown>
  gaoSummary: Record<string, { posture?: string; reason?: string | null }>
  findingCounts: Record<string, unknown>
  dcmaMetrics: Record<string, unknown>[]
  sourceExportMetrics: Record<string, unknown>[]
  supplementalMetrics: Record<string, unknown>[]
  sourceAnalyticsEvidence: Record<string, unknown> | null
  hasHealthFoundation: boolean
  baselineReferenceOnly: boolean
  baselineAvailable: boolean
  cpmStatus: string
  computedCpmAvailable: boolean
  packageMode: string
  sourceFormat: string
  score: string
  grade: string
  qualityStatus: string
  criticalPathDetail: string
  comparisonDetail: string
  topActionText: string
}

// Computes every derived value the cockpit panels render. Pure; mirrors the original page body
// (ScheduleQualityPage L373-441) one-to-one so behavior is unchanged.
export function buildHealthModel(
  health: ScheduleHealthData | undefined,
  qualityDetail: QualitySummary | undefined,
): HealthModel {
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
  const topFindings = health?.top_health_findings ?? qualityDetail?.top_findings ?? []
  const scorecard = scorecardFromHealth(health)
  const downstream = {
    ...parsedScorecardObject(scorecard, 'downstream_readiness_json'),
    ...(qualityDetail?.downstream_readiness ?? {}),
  }
  const gaoSummary =
    qualityDetail?.gao_category_summary ??
    (parsedScorecardObject(scorecard, 'gao_category_summary_json') as Record<
      string,
      { posture?: string; reason?: string | null }
    >)
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
  // Phase 9A.3: when the 9A.1 computed_cpm_health envelope reports available, Schedule Health
  // surfaces Application-computed CPM and stops presenting CPM as globally "not implemented".
  const computedCpmAvailable = health?.computed_cpm_health?.available === true
  const packageMode = text(importPackage.package_mode ?? currentSchedule.source_type, 'single_file')
  const sourceFormat = text(currentSchedule.source_format ?? qualityDetail?.source_format)
  const score = text(scorecard.quality_score ?? qualityDetail?.quality_score)
  const grade = text(scorecard.quality_grade ?? qualityDetail?.quality_grade)
  const qualityStatus = text(health?.quality_summary?.status ?? qualityDetail?.status, 'not evaluated')
  const criticalPathDetail = computedCpmAvailable
    ? 'Application-computed CPM available. Source critical-path evidence is reported separately below.'
    : cpmStatus === 'deferred'
      ? 'CPM recalculation is deferred; current evidence is source-export or proxy evidence.'
      : `Source critical path status: ${capabilityStatusLabel(capabilityStatus(capabilities, 'source_critical_path'))}`
  const comparisonDetail = comparisonIdentitySafe
    ? `Identity-safe prior: ${text(comparisonBasis.default_prior_schedule_version_key)}`
    : comparisonRequiresReview
      ? 'Default comparison is blocked until schedule identity review is resolved.'
      : `Default comparison unavailable: ${text(comparisonBasis.default_prior_unavailable_reason, 'no prior identity version')}`
  const severe = topFindings.find((finding) => finding.severity === 'critical' || finding.severity === 'warning')
  const topActionText = severe
    ? text(severe.recommended_action ?? severe.finding_summary ?? severe.message)
    : baselineReferenceOnly
      ? 'Upload P6 XML with baselines included to calculate baseline drift and BEI.'
      : !hasHealthFoundation && health
        ? 'Re-import using the package-aware workflow to populate health evidence.'
        : 'Review detailed findings and capability gaps below.'

  return {
    currentSchedule,
    importPackage,
    capabilities,
    baselineProjects,
    baselineFacts,
    diffFacts,
    availableDiffs,
    comparisonBasis,
    impactSummary,
    comparisonIdentitySafe,
    comparisonRequiresReview,
    topFindings,
    scorecard,
    downstream,
    gaoSummary,
    findingCounts,
    dcmaMetrics,
    sourceExportMetrics,
    supplementalMetrics,
    sourceAnalyticsEvidence,
    hasHealthFoundation,
    baselineReferenceOnly,
    baselineAvailable,
    cpmStatus,
    computedCpmAvailable,
    packageMode,
    sourceFormat,
    score,
    grade,
    qualityStatus,
    criticalPathDetail,
    comparisonDetail,
    topActionText,
  }
}
