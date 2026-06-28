// Small card primitives for the Schedule Health cockpit (Phase 9A.2). Kept in their own file
// (separate from healthShared helpers) so react-refresh fast-refresh stays happy. Extracted
// verbatim from ScheduleQualityPage.

import type { ScheduleSourceCapability } from '../../../lib/api'
import { capabilityStatusLabel, labelize, statusClass } from './healthShared'

export function HealthCard({
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

export function CapabilityList({ title, capabilities }: { title: string; capabilities: ScheduleSourceCapability[] }) {
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
