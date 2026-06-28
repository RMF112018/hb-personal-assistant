// Baseline / package health section (Phase 9A.2). Baseline crosswalk evidence per baseline
// project. Extracted verbatim; behavior unchanged.

import { ScheduleTable, ScheduleTd, ScheduleTh } from '../SchedulePageChrome'
import { capabilityStatusLabel, labelize, numberText, statusClass, text, type HealthModel } from './healthShared'
import { ScheduleHealthProvenanceBadge } from './ScheduleHealthProvenanceBadge'

export function ScheduleHealthBaselinePanel({ model }: { model: HealthModel }) {
  const { baselineProjects, baselineFacts, baselineAvailable, baselineReferenceOnly } = model

  return (
    <section className="forecast-panel p-4">
      <div className="flex items-center justify-between mb-2 gap-3">
        <h2 className="text-sm font-semibold">Baseline Health</h2>
        <ScheduleHealthProvenanceBadge basis="baseline_crosswalk" />
      </div>
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
  )
}
