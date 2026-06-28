// Unavailable / deferred analysis section (Phase 9A.2). Extracted verbatim; behavior unchanged.

import type { ScheduleHealthData } from '../../../lib/api'
import { capabilityStatus, capabilityStatusLabel, type HealthModel } from './healthShared'
import { ScheduleHealthProvenanceBadge } from './ScheduleHealthProvenanceBadge'

export function ScheduleHealthDeferredPanel({
  model,
  health,
}: {
  model: HealthModel
  health: ScheduleHealthData
}) {
  const { capabilities, cpmStatus, baselineAvailable, baselineReferenceOnly } = model

  return (
    <section className="forecast-panel p-4">
      <div className="flex items-center justify-between mb-2 gap-3">
        <h2 className="text-sm font-semibold">Unavailable / Deferred Analysis</h2>
        <ScheduleHealthProvenanceBadge basis="deferred" />
      </div>
      <ul className="text-sm space-y-1">
        <li>Cost/schedule correlation: {capabilityStatusLabel(health.deferred_domains?.cost_schedule_correlation ?? capabilityStatus(capabilities, 'cost_schedule_correlation'))}</li>
        <li>Resource assignments: {capabilityStatusLabel(capabilityStatus(capabilities, 'resource_assignments'))}</li>
        <li>Cost loading: {capabilityStatusLabel(capabilityStatus(capabilities, 'cost_loading'))}</li>
        <li>CPM recalculation: {capabilityStatusLabel(cpmStatus)}</li>
        <li>Baseline metrics: {baselineAvailable ? 'Available' : baselineReferenceOnly ? 'Requires companion file' : 'Not enough data'}</li>
      </ul>
    </section>
  )
}
