// Schedule Health Overview section (Phase 9A.2). Version-identity strip, limited-health banner,
// and the executive top-cards row. Extracted verbatim from ScheduleQualityPage; behavior unchanged.

import type { ComponentProps } from 'react'

import { ScheduleProjectContext } from '../ScheduleProjectPicker'
import {
  CPM_RECALCULATION_BANNER,
  formatProjectCapabilityBanner,
  getScheduleFormatLabel,
} from '../../../lib/scheduleCapabilityCopy'
import type { ScheduleHealthData } from '../../../lib/api'
import {
  capabilityStatus,
  capabilityStatusLabel,
  diffValue,
  factValue,
  labelize,
  numberText,
  text,
  type HealthModel,
  type QualitySummary,
} from './healthShared'
import { HealthCard } from './healthCards'

export function ScheduleHealthOverview({
  model,
  health,
  qualityDetail,
  projectKey,
  projects,
}: {
  model: HealthModel
  health: ScheduleHealthData
  qualityDetail?: QualitySummary
  projectKey: string
  projects?: ComponentProps<typeof ScheduleProjectContext>['projects']
}) {
  const {
    currentSchedule,
    capabilities,
    baselineProjects,
    baselineFacts,
    diffFacts,
    impactSummary,
    comparisonIdentitySafe,
    scorecard,
    downstream,
    findingCounts,
    baselineReferenceOnly,
    baselineAvailable,
    packageMode,
    sourceFormat,
    score,
    grade,
    qualityStatus,
    criticalPathDetail,
    comparisonDetail,
    topActionText,
    hasHealthFoundation,
    computedCpmAvailable,
  } = model

  return (
    <>
      <div className="text-xs text-[var(--hb-muted)] max-w-5xl border border-[var(--hb-border)] rounded p-3 bg-[var(--hb-surface)] space-y-1">
        <ScheduleProjectContext projectKey={String(health.project_key ?? projectKey)} projects={projects} />
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
        <div>{computedCpmAvailable ? 'CPM: Application-computed CPM available' : CPM_RECALCULATION_BANNER}</div>
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
    </>
  )
}
