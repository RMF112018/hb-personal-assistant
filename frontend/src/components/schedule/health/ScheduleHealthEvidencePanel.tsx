// Source-export evidence sections (Phase 9A.2): Available Schedule Evidence (capability matrix)
// and Critical Path and Float Evidence. Extracted verbatim; behavior unchanged.

import {
  capabilitiesForGroup,
  capabilityStatus,
  capabilityStatusLabel,
  formatSourceCriticalAnalytics,
  labelize,
  statusClass,
  type HealthModel,
} from './healthShared'
import { CapabilityList } from './healthCards'
import { ScheduleHealthProvenanceBadge } from './ScheduleHealthProvenanceBadge'

export function ScheduleHealthEvidencePanel({ model }: { model: HealthModel }) {
  const { capabilities, sourceAnalyticsEvidence } = model
  const analytics = sourceAnalyticsEvidence ? formatSourceCriticalAnalytics(sourceAnalyticsEvidence) : null

  return (
    <>
      <section className="forecast-panel p-4">
        <div className="flex items-center justify-between mb-3 gap-3">
          <h2 className="text-sm font-semibold">Available Schedule Evidence</h2>
          <ScheduleHealthProvenanceBadge basis="source_export" />
        </div>
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
        <div className="flex items-center justify-between mb-1 gap-3">
          <h2 className="text-sm font-semibold">Critical Path and Float Evidence</h2>
          <ScheduleHealthProvenanceBadge basis="source_export" />
        </div>
        <p className="text-xs text-[var(--hb-muted)] mb-3">
          This section reports source critical path evidence. It does not say calculated critical path unless backend
          evidence reports CPM recalculation.
        </p>
        {analytics ? (
          <div className="text-sm space-y-1 mb-3 rounded border border-[var(--hb-border)] p-3">
            {analytics.lines.map((line) => (
              <p key={line}>{line}</p>
            ))}
            {analytics.caveat ? <p className="text-xs text-amber-700 mt-2">{analytics.caveat}</p> : null}
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
    </>
  )
}
