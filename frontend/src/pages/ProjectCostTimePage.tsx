/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { ProjectSubNav } from '../components/projects/ProjectSubNav'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

export function ProjectCostTimePage() {
  const { projectKey = 'all' } = useParams()
  const key = projectKey || 'all'

  const { data: costData, isLoading } = useQuery({
    queryKey: ['project', 'cost-time', key],
    queryFn: () => api.getProjectCostTime(key),
  })

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading cost &amp; time…</div>
  }

  const items = (costData?.items || costData || []) as any[]

  return (
    <div>
      <ProjectSubNav projectKey={key} />
      <div className="flex gap-2 mb-3">
        <FreshnessBadge status="fresh" />
        <ConfidenceBadge level="source_backed" />
      </div>
      <div className="card">
        <div className="section-title">Cost &amp; Time</div>
        <p className="text-sm">Cost &amp; Time is the location for cost/change, billing/cash/retention, schedule, procurement, and cost/time-impacting RFI/submittal/design-decision signals (advisory, source-backed). Drill to Admin for WBS/cost code completeness, financial readiness, and coverage.</p>
        {items.length === 0 ? (
          <EmptyState title="No cost/time signals" hint="Budget vs actual, change exposure, schedule, and procurement signals appear here." />
        ) : (
          <ul className="text-sm list-disc pl-4 mt-2 space-y-1">
            {items.slice(0, 8).map((c: any, i: number) => <li key={i}>{c.title || c.description || JSON.stringify(c).slice(0, 100)}</li>)}
          </ul>
        )}
      </div>
      <div className="text-xs mt-2"><Link to="/admin" className="underline">Cost code &amp; financial readiness → Admin / Data Confidence</Link></div>
    </div>
  )
}
