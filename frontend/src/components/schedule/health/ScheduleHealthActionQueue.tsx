// Risk & action queue (Phase 9A.2): the findings table, kept as the prioritized review list.
// Extracted verbatim; behavior unchanged.

import { ScheduleTable, ScheduleTd, ScheduleTh } from '../SchedulePageChrome'
import { labelize, text, type HealthModel } from './healthShared'
import { ScheduleHealthProvenanceBadge } from './ScheduleHealthProvenanceBadge'

export function ScheduleHealthActionQueue({ model }: { model: HealthModel }) {
  const { topFindings } = model

  return (
    <section>
      <div className="flex items-center justify-between mb-2 gap-3">
        <h2 className="text-sm font-semibold">Findings</h2>
        <ScheduleHealthProvenanceBadge basis="derived_read_model" />
      </div>
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
  )
}
