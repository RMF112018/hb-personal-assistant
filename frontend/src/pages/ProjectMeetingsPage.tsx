/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { ProjectSubNav } from '../components/projects/ProjectSubNav'
import { EmptyState } from '../components/ui/EmptyState'
import { MetricCard } from '../components/dashboard/MetricCard'
import { AttentionItemCard } from '../components/dashboard/AttentionItemCard'
import { api } from '../lib/api'

export function ProjectMeetingsPage() {
  const { projectKey = 'all' } = useParams()
  const key = projectKey || 'all'

  const { data: meetingsData, isLoading } = useQuery({
    queryKey: ['project', 'meetings', key],
    queryFn: () => api.getProjectMeetings(key),
  })

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading meetings…</div>
  }

  const m = meetingsData || {}
  const metricCards = Array.isArray(m.metric_cards) ? m.metric_cards : []
  const attention = Array.isArray(m.attention_items) ? m.attention_items : []

  return (
    <div>
      <ProjectSubNav projectKey={key} />
      <div className="flex gap-2 mb-3">
        <FreshnessBadge status="fresh" />
        <ConfidenceBadge level="source_backed" />
      </div>
      <div className="card">
        <div className="section-title">Meetings Needing Prep / Recent</div>
        <p className="text-sm">Construction-native meeting list (prep status, attendees, linked items, Daily Brief context). No raw calendar payloads.</p>
        {metricCards.length === 0 && attention.length === 0 ? (
          <EmptyState title="No meeting data" hint="Calendar + Procore context will appear after sync." />
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
        <div className="text-xs mt-2 text-[var(--hb-muted)]">Uses calendar, Outlook, meeting action items, related files, related Procore context, and Daily Brief/meeting-prep context. Contextual under Projects (or All Projects). Not a top-level nav.</div>
      </div>
      <div className="mt-2 text-xs"><Link to="/my-items" className="underline">See My Items for personal meeting queue →</Link></div>
    </div>
  )
}
