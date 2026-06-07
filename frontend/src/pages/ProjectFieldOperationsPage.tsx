/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { ProjectSubNav } from '../components/projects/ProjectSubNav'
import { EmptyState } from '../components/ui/EmptyState'
import { MetricCard } from '../components/dashboard/MetricCard'
import { AttentionItemCard } from '../components/dashboard/AttentionItemCard'
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

  const f = fieldData || {}
  const metricCards = Array.isArray(f.metric_cards) ? f.metric_cards : []
  const attention = Array.isArray(f.attention_items) ? f.attention_items : []
  const ff = f.freshness || {}
  const cc = f.confidence_summary || {}

  return (
    <div>
      <ProjectSubNav projectKey={key} />
      <div className="flex gap-2 mb-3">
        <FreshnessBadge status={ff.overall || 'unknown'} minutesAgo={ff.minutes_ago_max} />
        <ConfidenceBadge level={cc.overall || 'not_available'} />
      </div>
      <div className="card">
        <div className="section-title">Field Operations</div>
        <p className="text-sm">Field Operations is the location for startup, closeout, daily log, observations, punch-list, inspections, quality/safety, and superintendent-facing data (advisory). No raw Procore bodies.</p>
        {metricCards.length === 0 && attention.length === 0 ? (
          <EmptyState title="No field signals" hint="Daily logs, observations, punch, inspections, and closeout readiness appear here." />
        ) : (
          <>
            {metricCards.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                {metricCards.slice(0, 6).map((c: any, idx: number) => (
                  <MetricCard key={c.id || c.metric_id || idx} label={c.label || c.name} value={c.value} unit={c.unit} status={c.status} />
                ))}
              </div>
            )}
            {attention.length > 0 && (
              <div className="space-y-2">
                {attention.slice(0, 6).map((a: any, idx: number) => (
                  <AttentionItemCard key={a.id || idx} title={a.title} when={a.when || a.age} project={a.project} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
      <div className="text-xs mt-2"><Link to="/admin" className="underline">Field data quality and coverage → Admin</Link></div>
    </div>
  )
}
