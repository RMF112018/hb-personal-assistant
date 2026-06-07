/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { ProjectSubNav } from '../components/projects/ProjectSubNav'
import { EmptyState } from '../components/ui/EmptyState'
import { MetricCard } from '../components/dashboard/MetricCard'
import { AttentionItemCard } from '../components/dashboard/AttentionItemCard'
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

  const c = costData || {}
  const metricCards = Array.isArray(c.metric_cards) ? c.metric_cards : []
  const attention = Array.isArray(c.attention_items) ? c.attention_items : []

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
        {metricCards.length === 0 && attention.length === 0 ? (
          <EmptyState title="No cost/time signals" hint="Budget vs actual, change exposure, schedule, and procurement signals appear here." />
        ) : (
          <>
            {metricCards.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                {metricCards.slice(0, 6).map((mc: any, idx: number) => (
                  <MetricCard key={mc.id || mc.metric_id || idx} label={mc.label || mc.name} value={mc.value} unit={mc.unit} status={mc.status} />
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
      <div className="text-xs mt-2"><Link to="/admin" className="underline">Cost code &amp; financial readiness → Admin / Data Confidence</Link></div>
    </div>
  )
}
