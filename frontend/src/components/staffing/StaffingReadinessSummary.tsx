import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { SectionCard } from '../common/SectionCard'
import { humanizeCode } from './staffingShared'

const STATUS_COPY: Record<string, { label: string; cls: string }> = {
  ready: { label: 'Ready', cls: 'text-emerald-300' },
  degraded: { label: 'Needs review', cls: 'text-amber-300' },
  blocked: { label: 'Not ready', cls: 'text-rose-300' },
}

export function StaffingReadinessSummary({ project }: { project: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['staffing', 'readiness', project],
    queryFn: () => api.getProjectStaffingReadiness(project),
  })

  const status = data?.readiness_status ?? 'degraded'
  const copy = STATUS_COPY[status] ?? STATUS_COPY.degraded
  const reasons = data?.readiness_reasons ?? []

  return (
    <SectionCard
      title="Staffing readiness"
      description="Whether this project's staffing is ready to feed a forecast."
    >
      {isLoading && <p className="text-sm text-[var(--hb-muted)]">Loading readiness…</p>}
      {error && <p className="text-sm text-rose-300">Readiness is unavailable.</p>}
      {data && (
        <div className="space-y-2">
          <div className="flex items-center gap-3 text-sm">
            <span className={`font-medium ${copy.cls}`}>{copy.label}</span>
            <span className="text-[var(--hb-muted)]">
              {data.active_row_count} active row{data.active_row_count === 1 ? '' : 's'}
              {data.unmatched_review_count > 0
                ? ` · ${data.unmatched_review_count} to review`
                : ''}
            </span>
          </div>
          {reasons.length > 0 && (
            <ul className="list-disc pl-5 text-sm text-[var(--hb-muted)]">
              {reasons.map((r) => (
                <li key={r}>{humanizeCode(r)}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </SectionCard>
  )
}
