/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { ProjectSubNav } from '../components/projects/ProjectSubNav'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

export function ProjectFieldOperationsPage() {
  const { projectKey = 'all' } = useParams()
  const key = projectKey || 'all'

  const { data: fieldData, isLoading } = useQuery({
    queryKey: ['project', 'field-operations', key],
    queryFn: () => api.getProjectFieldOperations(key),
  })

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading field operations…</div>
  }

  const items = (fieldData?.items || fieldData || []) as any[]

  return (
    <div>
      <ProjectSubNav projectKey={key} />
      <div className="flex gap-2 mb-3">
        <FreshnessBadge status="stale" minutesAgo={19} />
        <ConfidenceBadge level="source_backed" />
      </div>
      <div className="card">
        <div className="section-title">Field Operations</div>
        <p className="text-sm">Field Operations is the location for startup, closeout, daily log, observations, punch-list, inspections, quality/safety, and superintendent-facing data (advisory). No raw Procore bodies.</p>
        {items.length === 0 ? (
          <EmptyState title="No field signals" hint="Daily logs, observations, punch, inspections, and closeout readiness appear here." />
        ) : (
          <ul className="text-sm list-disc pl-4 mt-2 space-y-1">
            {items.slice(0, 8).map((f: any, i: number) => <li key={i}>{f.title || f.description || JSON.stringify(f).slice(0, 100)}</li>)}
          </ul>
        )}
      </div>
      <div className="text-xs mt-2"><Link to="/admin" className="underline">Field data quality and coverage → Admin</Link></div>
    </div>
  )
}
