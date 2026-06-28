// Quality metrics section (Phase 9A.2): DCMA 14-Point, Supplemental Source Checks, GAO/AACE.
// Extracted verbatim; behavior unchanged. DCMA/GAO are quality-metric basis; supplemental checks
// are source-export.

import { EmptyState } from '../../ui/EmptyState'
import { ScheduleTable, ScheduleTd, ScheduleTh } from '../SchedulePageChrome'
import {
  formatMetricValue,
  labelize,
  metricDisplayName,
  statusClass,
  text,
  type HealthModel,
} from './healthShared'
import { ScheduleHealthProvenanceBadge } from './ScheduleHealthProvenanceBadge'

export function ScheduleHealthQualityPanel({ model }: { model: HealthModel }) {
  const { dcmaMetrics, sourceExportMetrics, supplementalMetrics, gaoSummary } = model

  return (
    <>
      <section>
        <div className="flex items-center justify-between mb-2 gap-3">
          <h2 className="text-sm font-semibold">DCMA 14-Point Assessment</h2>
          <ScheduleHealthProvenanceBadge basis="quality_metric" />
        </div>
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
          <div className="flex items-center justify-between mb-2 gap-3">
            <h2 className="text-sm font-semibold">Supplemental Source Checks</h2>
            <ScheduleHealthProvenanceBadge basis="source_export" />
          </div>
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
        <div className="flex items-center justify-between mb-2 gap-3">
          <h2 className="text-sm font-semibold">GAO / AACE Categories</h2>
          <ScheduleHealthProvenanceBadge basis="quality_metric" />
        </div>
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
    </>
  )
}
