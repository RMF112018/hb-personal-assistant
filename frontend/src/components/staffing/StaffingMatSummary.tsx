import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { SectionCard } from '../common/SectionCard'

export function StaffingMatSummary({ project }: { project: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['staffing', 'mat-summary', project],
    queryFn: () => api.getProjectStaffingMatSummary(project),
  })

  const materials = (data?.materials ?? []) as Record<string, string>[]

  return (
    <SectionCard title="Materials summary"
      description="MAT actuals summarized by cost code — not person-attributable.">
      {isLoading && <p className="text-sm text-[var(--hb-muted)]">Loading materials…</p>}
      {error && <p className="text-sm text-rose-300">Materials summary is unavailable.</p>}
      {data && (
        materials.length === 0 ? (
          <p className="text-sm text-[var(--hb-muted)]">No material actuals.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {materials.map((m) => (
              <li key={m.cost_code} className="flex items-center justify-between gap-3">
                <span>{m.cost_code} · MAT</span>
                <span className="text-[var(--hb-muted)]">
                  {m.actual_amount} · {m.first_month} → {m.last_month}
                </span>
              </li>
            ))}
          </ul>
        )
      )}
    </SectionCard>
  )
}
